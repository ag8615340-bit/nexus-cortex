"""
ai_engine.py
Hierarchical Agent Routing Engine powered by OpenRouter.
3 Main Agents each lead 4 sub-agents in an async message-passing pipeline.
The RAM optimizer dynamically controls how many sub-agent coroutines are spawned.

Architecture:
    User Query
        └──> Scope Validator
                └──> For each active Main Agent (parallel):
                        ├──> Sub-Agent A (async) ─┐
                        ├──> Sub-Agent B (async) ─┤──> Collation → Main Agent synthesis
                        ├──> Sub-Agent C (async) ─┘
                        └──> Sub-Agent D (async) ─┘
                                └──> Final Response (streamed to frontend)
"""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from strict_prompts import AGENT_PROMPTS, FORMATTING_RULES, SUB_AGENTS, validate_query_scope
from ram_optimizer import get_active_sub_agent_count, get_active_indices_for_ram
from rag_mcp import RagContext, extract_structured_context

load_dotenv()

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# OpenRouter Configuration
# API key is loaded from .env — never hardcoded
# ──────────────────────────────────────────────
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE}/chat/completions"
OPENROUTER_MODEL = "openai/gpt-4.1-nano"          # Main agents model
ADK_MODEL = "google/gemini-2.5-flash-lite-preview-06-17"  # ADK agent model
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")  # Loaded from .env
REQUEST_TIMEOUT = 60.0  # seconds


# ──────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────

@dataclass
class SubAgent:
    """A single sub-agent within the matrix."""
    agent_type: str          # e.g. "market_strategist"
    index: int               # 0-3 within its main agent
    name: str                # e.g. "Trend Predictor"
    description: str         # e.g. "Identifies emerging market patterns..."
    active: bool = True


@dataclass
class MainAgent:
    """A main agent that leads a team of sub-agents."""
    agent_type: str          # e.g. "market_strategist"
    display_name: str        # e.g. "Market Strategist"
    sub_agents: List[SubAgent] = field(default_factory=list)
    system_prompt: str = ""


@dataclass
class AgentResponse:
    """The final compiled response from a main agent."""
    agent_type: str
    content: str
    sub_agent_reports: List[str] = field(default_factory=list)
    ram_used: str = ""
    latency_ms: float = 0.0


@dataclass
class SessionState:
    """Per-session state for the agent ecosystem."""
    session_id: str
    ram_gb: int = 8
    uploaded_file: Optional[str] = None
    rag_context: Optional[RagContext] = None
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


# ──────────────────────────────────────────────
# Agent Orchestrator
# ──────────────────────────────────────────────

class AgentOrchestrator:
    """
    The central orchestrator that manages the hierarchical agent system.
    Handles session management, RAG context injection, sub-agent dispatch,
    and streaming responses back to the frontend.
    """

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self._sessions: Dict[str, SessionState] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(REQUEST_TIMEOUT),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    # SITE_URL loaded from .env for OpenRouter tracking
                    "HTTP-Referer": os.getenv("SITE_URL", "http://localhost:3000"),
                    "X-Title": "Nexus Cortex",
                },
            )
        return self._http_client

    async def _call_openrouter(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> str:
        """
        Make a non-streaming call to the OpenRouter API.
        Supports both GPT-4.1-nano (main agents) and Gemini 2.5 Flash Lite (ADK agent).
        Returns the response text, or an error string if the call fails.
        """
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY is not set. Check your .env file.")
            return "[Agent error: API key not configured — set OPENROUTER_API_KEY in .env]"

        client = await self._get_client()
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }

        try:
            response = await client.post(OPENROUTER_CHAT_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            # OpenRouter returns OpenAI-compatible response format
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        except httpx.TimeoutException:
            logger.warning("OpenRouter request timed out after %ss", REQUEST_TIMEOUT)
            return "[Agent timeout — skipped]"

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:500]
            logger.error("OpenRouter HTTP error: %s - %s", status, body)
            if status == 401:
                return "[Agent error: Invalid API key — check OPENROUTER_API_KEY in .env]"
            elif status == 429:
                return "[Agent error: Rate limited by OpenRouter — try again shortly]"
            return f"[Agent error: HTTP {status}]"

        except httpx.RequestError as exc:
            logger.error("OpenRouter connection error: %s", exc)
            return f"[Agent error: Cannot connect to OpenRouter — {exc}]"

        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error("OpenRouter response parse error: %s", exc)
            return "[Agent error: Invalid response from model]"

    # ── Session Management ────────────────────

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get an existing session or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
            logger.info("Created new session: %s", session_id)
        return self._sessions[session_id]

    def update_ram(self, session_id: str, ram_gb: int) -> Dict[str, Any]:
        """Update the RAM configuration for a session and return new profile."""
        session = self.get_or_create_session(session_id)
        session.ram_gb = ram_gb
        profile = get_active_sub_agent_count(ram_gb)

        # Build active sub-agent status map for frontend sync
        indices = get_active_indices_for_ram(ram_gb)
        agent_status = {}
        for agent_type, active_idxs in indices.items():
            agent_status[agent_type] = {
                "active_indices": active_idxs,
                "active_count": len(active_idxs),
            }

        return {
            "ram_gb": profile.total_gb,
            "used_gb": profile.used_gb,
            "available_gb": profile.available_gb,
            "usage_pct": profile.usage_pct,
            "max_concurrent_sub_agents": profile.max_concurrent_sub_agents,
            "sub_agents_per_main_agent": profile.sub_agents_per_main_agent,
            "recommendation": profile.recommendation,
            "agent_status": agent_status,
        }

    def store_rag_context(self, session_id: str, rag_ctx: RagContext) -> None:
        """Store parsed RAG context for a session after file upload."""
        session = self.get_or_create_session(session_id)
        session.rag_context = rag_ctx
        session.uploaded_file = rag_ctx.filename
        logger.info("Stored RAG context for session %s: %s", session_id, rag_ctx.filename)

    def get_rag_context(self, session_id: str) -> Optional[RagContext]:
        """Get the stored RAG context for a session."""
        session = self.get_or_create_session(session_id)
        return session.rag_context

    # ── Sub-agent Execution ───────────────────

    async def _run_sub_agent(
        self,
        agent_type: str,
        sub_agent: SubAgent,
        user_query: str,
        rag_context_str: str,
    ) -> str:
        """
        Run a single sub-agent against OpenRouter (GPT-4.1-nano).
        Each sub-agent gets a focused prompt about its specialty area.
        Sub-agents run in parallel via asyncio.gather() for speed.
        """
        prompt = (
            f"You are '{sub_agent.name}', a specialized sub-agent under the "
            f"'{agent_type.replace('_', ' ').title()}' main agent.\n\n"
            f"Your role: {sub_agent.description}\n\n"
            f"{FORMATTING_RULES}\n\n"
            "Based on the datasheet context and the user query below, "
            "provide your specific analysis from your area of expertise. "
            "Be concise (2-4 sentences) and data-driven. "
            "If the data doesn't cover your area, say 'No relevant data in this scope.'\n\n"
            f"{'Datasheet Context:\n\n' + rag_context_str if rag_context_str else 'No datasheet uploaded yet.'}"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_query},
        ]

        response = await self._call_openrouter(messages, temperature=0.3)
        return f"[{sub_agent.name}]: {response}"

    async def _run_main_agent(
        self,
        agent_type: str,
        user_query: str,
        rag_context_str: str,
        active_indices: List[int],
        ram_gb: int = 8,
    ) -> AgentResponse:
        """
        Run a main agent: spawn its active sub-agents in parallel,
        collect their reports, then synthesise the final response.
        RAM configuration controls how many sub-agents are active.
        """
        start_time = time.time()
        sub_agent_reports: List[str] = []

        # 🔽🔽🔽 SIRF YAHI BLOCK CHANGE HUA HAI 🔽🔽🔽
        # Build list of active sub-agents based on RAM config
        all_subs = SUB_AGENTS[agent_type]
        active_subs = []
        for idx in active_indices:
            if idx < len(all_subs):
                sub_data = all_subs[idx]                     # ← ✅ DICT hai: {"name": "...", "description": "..."}
                name = sub_data["name"]                      # ← ✅ Direct key access, no .split()
                active_subs.append(SubAgent(
                    agent_type=agent_type,
                    index=idx,
                    name=name,
                    description=sub_data["description"],     # ← ✅ Full description from dict key
                    active=True,
                ))
        # 🔼🔼🔼 SIRF YAHI BLOCK CHANGE HUA HAI 🔼🔼🔼

        # Run all active sub-agents in parallel (asyncio.gather)
        if active_subs:
            tasks = [
                self._run_sub_agent(agent_type, sub, user_query, rag_context_str)
                for sub in active_subs
            ]
            # return_exceptions=True: one sub-agent failure won't cancel others
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    sub_agent_reports.append(f"[{active_subs[i].name}]: Error — {str(result)}")
                else:
                    sub_agent_reports.append(result)

        # Synthesis: main agent reviews sub-agent reports and crafts final response
        system_prompt = AGENT_PROMPTS[agent_type]["content"]
        if rag_context_str:
            system_prompt += f"\n\nDatasheet Context:\n\n{rag_context_str}"

        collation_text = "\n\n".join(sub_agent_reports) if sub_agent_reports else "No sub-agents were active."

        synthesis_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "assistant",
                "content": (
                    f"Here are the reports from my sub-agents:\n\n{collation_text}\n\n"
                    "Now I will synthesise these into a final response for the user."
                ),
            },
            {"role": "user", "content": user_query},
        ]

        final_response = await self._call_openrouter(synthesis_messages, temperature=0.4)

        latency = (time.time() - start_time) * 1000  # ms
        ram_profile = get_active_sub_agent_count(ram_gb)

        return AgentResponse(
            agent_type=agent_type,
            content=final_response,
            sub_agent_reports=sub_agent_reports,
            ram_used=f"{ram_profile.total_gb}GB config",
            latency_ms=round(latency, 0),
        )

    # ── Public: Process a chat message ────────

    async def process_chat(
        self,
        session_id: str,
        user_query: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user chat query through the full agent pipeline.

        Yields SSE-compatible dicts:
            {"type": "status", "message": "...", "ram": {...}}
            {"type": "scope_error", "message": "Error: Query out of business scope."}
            {"type": "agent_response", "agent": "...", "content": "...", ...}
            {"type": "done", "agent_count": N}
        """
        # 0. Handle greetings — return a warm welcome without agent dispatch
        greeting_words = {"hi", "hello", "hey", "hie", "okie", "ok", "okay", "yo", "sup", "howdy", "greetings"}
        q_stripped = user_query.strip().lower()
        if len(q_stripped.split()) <= 2 or q_stripped in greeting_words:
            greeting_responses = [
                "Hello! I'm Nexus Cortex, your enterprise agent ecosystem. I have 3 main agents (Market Strategist, Financial Analyst, Operations Optimizer) ready to analyze your data. Upload a CSV or datasheet to get started!",
                "Hi there! I'm online and ready. Upload a datasheet file and I'll analyze it for strengths, weaknesses, market gaps, and production recommendations.",
                "Hey! Nexus Cortex here. Upload a CSV file or ask me a business analysis question to get started.",
            ]
            greeting_text = random.choice(greeting_responses)
            # Use actual session RAM profile — not hardcoded values
            session = self.get_or_create_session(session_id)
            profile = get_active_sub_agent_count(session.ram_gb)
            yield {
                "type": "status",
                "message": "Greeting detected — returning welcome message.",
                "ram": {
                    "total_gb": profile.total_gb,
                    "used_gb": profile.used_gb,
                    "usage_pct": profile.usage_pct,
                },
            }
            yield {
                "type": "agent_response",
                "agent": "nexus_cortex",
                "content": greeting_text,
                "sub_agent_reports": ["[System]: Greeting handled — no sub-agent dispatch needed."],
                "latency_ms": 0.0,
            }
            yield {"type": "done", "agent_count": 1}
            return

        # 1. Scope validation — reject non-business queries before API calls
        scope_error = validate_query_scope(user_query)
        if scope_error:
            yield {"type": "scope_error", "message": scope_error}
            return

        session = self.get_or_create_session(session_id)
        profile = get_active_sub_agent_count(session.ram_gb)
        active_indices_map = get_active_indices_for_ram(session.ram_gb)

        # 2. Build RAG context string from uploaded file (if any)
        rag_context_str = ""
        if session.rag_context:
            rag_context_str = extract_structured_context(session.rag_context)

        # 3. All 3 main agents always active at orchestrator level
        main_agents = ["market_strategist", "financial_analyst", "operations_optimizer"]

        yield {
            "type": "status",
            "message": (
                f"Routing query to {len(main_agents)} main agents "
                f"({profile.sub_agents_per_main_agent} sub-agents each)..."
            ),
            "ram": {
                "total_gb": profile.total_gb,
                "used_gb": profile.used_gb,
                "usage_pct": profile.usage_pct,
            },
        }

        # 4. Run all 3 main agents in parallel (asyncio.as_completed for streaming)
        tasks = [
            self._run_main_agent(
                agent_type=agent_type,
                user_query=user_query,
                rag_context_str=rag_context_str,
                active_indices=active_indices_map.get(agent_type, []),
                ram_gb=session.ram_gb,
            )
            for agent_type in main_agents
        ]

        responses: List[AgentResponse] = []
        # as_completed: yield each agent response as soon as it finishes
        for coro in asyncio.as_completed(tasks):
            try:
                response = await coro
                responses.append(response)
                yield {
                    "type": "agent_response",
                    "agent": response.agent_type,
                    "content": response.content,
                    "sub_agent_reports": response.sub_agent_reports,
                    "latency_ms": response.latency_ms,
                }
            except Exception as exc:
                logger.error("Main agent task failed: %s", exc, exc_info=True)

        # 5. Store exchange in chat history (keep last 50 messages)
        session.chat_history.append({"role": "user", "content": user_query})
        for resp in responses:
            session.chat_history.append({
                "role": "assistant",
                "agent": resp.agent_type,
                "content": resp.content,
            })
        if len(session.chat_history) > 50:
            session.chat_history = session.chat_history[-50:]

        yield {"type": "done", "agent_count": len(responses)}

    async def cleanup(self):
        """Close the HTTP client on server shutdown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            logger.info("HTTP client closed.")

    async def get_chat_history(self, session_id: str) -> List[Dict[str, str]]:
        """Retrieve chat history for a session."""
        session = self.get_or_create_session(session_id)
        return session.chat_history


# ── Singleton ─────────────────────────────────
# Module-level initialization — thread safe for FastAPI
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the singleton AgentOrchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
        logger.info("AgentOrchestrator initialized with model: %s", OPENROUTER_MODEL)
    return _orchestrator