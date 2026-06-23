"""
main.py
Nexus Cortex — FastAPI Application Server
Enterprise Multi-Agent Data Analytics Platform powered by OpenRouter (openai/gpt-4.1-nano).

Endpoints:
    POST /upload-file   — Upload a CSV/datasheet for RAG ingestion
    POST /chat          — Send a query to the agent ecosystem (streaming)
    POST /toggle-ram    — Adjust simulated RAM allocation
    GET  /chat-history  — Retrieve chat history for a session
    GET  /session-state — Get current session state (RAM, files, etc.)
    GET  /health        — Health check
"""

import asyncio
import csv
import io
import json
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ai_engine import get_orchestrator
from rag_mcp import parse_csv_datasheet
from ram_optimizer import get_active_sub_agent_count

# ── Logging ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nexus.main")

# ── Constants ─────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024        # 50 MB
MAX_QUERY_LENGTH = 4000                  # characters
SUPPORTED_EXTENSIONS = {".csv", ".json"}

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# CORS — environment-driven
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

# ── Auth & Rate Limiting ─────────────────────
security = HTTPBearer(auto_error=False)
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT = 10       # max requests
_RATE_WINDOW = 60      # per 60 seconds


def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Simple API key auth via Bearer token."""
    token = credentials.credentials if credentials else ""
    expected_key = os.getenv("NEXUS_API_KEY", "")
    if expected_key and token != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Set NEXUS_API_KEY in .env or pass as Bearer token.",
        )
    return token


def rate_limit(session_id: str):
    """Simple sliding window rate limiter per session."""
    now = time.time()
    window = _rate_limit_store[session_id]
    _rate_limit_store[session_id] = [t for t in window if now - t < _RATE_WINDOW]
    if len(_rate_limit_store[session_id]) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {_RATE_LIMIT} requests per {_RATE_WINDOW}s.",
        )
    _rate_limit_store[session_id].append(now)


# ── App Lifetime ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Nexus Cortex backend starting...")
    logger.info("Using OpenRouter model: openai/gpt-4.1-nano")
    logger.info("CORS origins: %s", _ALLOWED_ORIGINS)
    yield
    orchestrator = get_orchestrator()
    await orchestrator.cleanup()
    logger.info("Nexus Cortex backend shut down.")


# ── FastAPI App ──────────────────────────────
app = FastAPI(
    title="Nexus Cortex API",
    version="3.3.0",
    description="Enterprise Multi-Agent Data Analytics Platform — OpenRouter-powered",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-Id", "Authorization"],
)


# ── Helpers ──────────────────────────────────

def _get_session_id_from_request(
    session_id: Optional[str],
    x_session_id: Optional[str],
) -> str:
    """Extract, validate, or generate a session ID."""
    sid = (session_id or x_session_id or "").strip()
    if not sid:
        sid = str(uuid.uuid4())
        logger.info("No session_id provided — created new session: %s", sid)
        return sid
    if not _UUID_PATTERN.match(sid):
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id format. Must be a valid UUID.",
        )
    return sid


def _validate_query(query: str) -> str:
    """Validate and sanitize a user chat query."""
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long ({len(query)} chars). Maximum is {MAX_QUERY_LENGTH}.",
        )
    return query


def _format_column(c) -> Dict[str, Any]:
    """Serialize a ColumnProfile to a response-safe dict."""
    base: Dict[str, Any] = {
        "name": c.name,
        "dtype": c.dtype,
        "unique": c.unique_count,
        "nulls": c.null_count,
    }
    if c.dtype == "numeric":
        base.update({
            "min": c.min_val,
            "max": c.max_val,
            "mean": round(c.mean, 2) if c.mean is not None else None,
        })
    return base


async def _read_upload_safely(file: UploadFile) -> bytes:
    """Stream-read an upload with a running size guard to prevent OOM."""
    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )
    chunks: List[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 64):
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _json_to_rag_context(raw_content: str, filename: str):
    """Convert a JSON array of objects to a RagContext via CSV conversion."""
    MAX_JSON_ROWS = 100_000
    try:
        json_data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")
    if not isinstance(json_data, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of objects.")
    if len(json_data) == 0:
        raise HTTPException(status_code=400, detail="JSON array is empty.")
    if len(json_data) > MAX_JSON_ROWS:
        raise HTTPException(status_code=400, detail=f"JSON has {len(json_data)} rows — maximum is {MAX_JSON_ROWS}.")
    if not isinstance(json_data[0], dict):
        raise HTTPException(status_code=400, detail="JSON array items must be objects.")
    fieldnames = list(json_data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(json_data)
    return parse_csv_datasheet(output.getvalue(), filename=filename)


# ── Endpoints ────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check — confirms server is running and version info."""
    return {
        "status": "healthy",
        "model": "openai/gpt-4.1-nano",
        "provider": "OpenRouter",
        "version": app.version,
        "timestamp": time.time(),
    }


@app.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(""),
    x_session_id: str = Form(""),
    auth: str = Depends(verify_api_key),
):
    """Upload a CSV or JSON file for RAG ingestion."""
    sid = _get_session_id_from_request(session_id, x_session_id)
    rate_limit(sid)
    logger.info("Upload request: session=%s file=%s", sid, file.filename)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.",
        )
    raw_bytes = await _read_upload_safely(file)
    try:
        raw_content = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode file: {exc}")
    if ext == ".csv":
        rag_ctx = parse_csv_datasheet(raw_content, filename=file.filename)
    else:
        rag_ctx = await _json_to_rag_context(raw_content, filename=file.filename)
    if rag_ctx is None:
        raise HTTPException(status_code=400, detail="Could not parse the uploaded file.")
    orchestrator = get_orchestrator()
    orchestrator.store_rag_context(sid, rag_ctx)
    return {
        "error": False,
        "session_id": sid,
        "filename": file.filename,
        "rows_sampled": rag_ctx.summary_stats.get("rows_sampled", rag_ctx.row_count),
        "total_rows": rag_ctx.row_count,
        "columns": len(rag_ctx.columns),
        "column_details": [_format_column(c) for c in rag_ctx.columns],
        "summary_stats": rag_ctx.summary_stats,
        "issues": rag_ctx.detected_issues,
    }


@app.post("/chat")
async def chat(
    request: Request,
    query: str = Form(..., max_length=MAX_QUERY_LENGTH),
    session_id: str = Form(""),
    x_session_id: str = Form(""),
    auth: str = Depends(verify_api_key),
):
    """Send a query to the agent ecosystem. Returns SSE streaming response."""
    sid = _get_session_id_from_request(session_id, x_session_id)
    rate_limit(sid)
    query = _validate_query(query)
    logger.info("Chat request: session=%s query=%s", sid, query[:80])
    orchestrator = get_orchestrator()

    async def event_stream():
        try:
            async for event in orchestrator.process_chat(sid, query):
                if await request.is_disconnected():
                    logger.info("Client disconnected mid-stream: session=%s", sid)
                    return
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            logger.info("Stream cancelled (client disconnected): session=%s", sid)
            return
        except Exception as exc:
            logger.error("Chat processing error: %s", exc, exc_info=True)
            error_event = {"type": "error", "detail": f"Internal error: {exc}"}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": sid,
        },
    )


@app.post("/toggle-ram")
async def toggle_ram(
    ram_gb: int = Form(...),
    session_id: str = Form(""),
    x_session_id: str = Form(""),
    auth: str = Depends(verify_api_key),
):
    """Adjust the simulated RAM allocation for the agent system."""
    if ram_gb not in (4, 8, 16):
        raise HTTPException(status_code=400, detail=f"Invalid RAM value '{ram_gb}'. Must be 4, 8, or 16 GB.")
    sid = _get_session_id_from_request(session_id, x_session_id)
    rate_limit(sid)
    logger.info("Toggle RAM: session=%s gb=%s", sid, ram_gb)
    orchestrator = get_orchestrator()
    result = orchestrator.update_ram(sid, ram_gb)
    return {"error": False, "session_id": sid, "ram": result}


@app.get("/chat-history")
async def chat_history(
    session_id: str = Query(default=""),
    x_session_id: str = Query(default="", alias="x_session_id"),
    auth: str = Depends(verify_api_key),
):
    """Retrieve the chat history for a given session."""
    sid = _get_session_id_from_request(session_id, x_session_id)
    rate_limit(sid)
    orchestrator = get_orchestrator()
    history = await orchestrator.get_chat_history(sid)
    return {"error": False, "session_id": sid, "history": history, "message_count": len(history)}


@app.get("/session-state")
async def session_state(
    session_id: str = Query(default=""),
    x_session_id: str = Query(default="", alias="x_session_id"),
    auth: str = Depends(verify_api_key),
):
    """Get the current state of a session (RAM, uploaded file, etc.)."""
    sid = _get_session_id_from_request(session_id, x_session_id)
    rate_limit(sid)
    orchestrator = get_orchestrator()
    session = orchestrator.get_or_create_session(sid)
    ram_profile = get_active_sub_agent_count(session.ram_gb)
    return {
        "error": False,
        "session_id": sid,
        "ram_gb": session.ram_gb,
        "ram_profile": {
            "total_gb": ram_profile.total_gb,
            "used_gb": ram_profile.used_gb,
            "available_gb": ram_profile.available_gb,
            "usage_pct": ram_profile.usage_pct,
            "max_concurrent_sub_agents": ram_profile.max_concurrent_sub_agents,
            "sub_agents_per_main_agent": ram_profile.sub_agents_per_main_agent,
            "recommendation": ram_profile.recommendation,
        },
        "uploaded_file": session.uploaded_file,
        "chat_message_count": len(session.chat_history),
        "created_at": session.created_at,
    }