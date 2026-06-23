# 🧠 Nexus Cortex — Enterprise Multi-Agent Data Analytics Platform

> **Kaggle AI Agents Capstone — Agents for Business Track**
> Built with OpenRouter (GPT-4.1-nano + Gemini 2.5 Flash Lite), FastAPI, and a hierarchical multi-agent architecture.

---

## 🎯 Problem Statement

Business analysts spend hours manually processing CSV datasheets, cross-referencing market trends, financial metrics, and operational bottlenecks — often in silos. Insights are slow, inconsistent, and expensive.

**Nexus Cortex solves this** by deploying a team of AI agents that simultaneously analyze uploaded business data from three expert perspectives — market strategy, financial analysis, and operations optimization — in seconds.

---

## 💡 Why Agents?

A single LLM call gives one perspective. Agents give you a **boardroom**.

| Traditional LLM | Nexus Cortex Agents |
|---|---|
| One response | 3 parallel expert responses |
| No specialization | Market, Financial, Ops agents |
| Static prompt | RAG context from your data |
| No memory | Session-based chat history |
| No tool use | MCP server with CSV tools |

---

## 🏗️ Architecture

```
User Query + CSV Upload
        │
        ▼
┌─────────────────────┐
│   FastAPI Backend   │  ← main.py
│  (Rate limit + Auth)│
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Scope Validator   │  ← strict_prompts.py
│ (Business scope     │
│  enforcement)       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   RAG MCP Layer     │  ← rag_mcp.py + mcp_server.py
│ (CSV parsed into    │
│  structured context)│
└────────┬────────────┘
         │
    ┌────┴─────────────────────────┐
    │     Parallel Agent Dispatch  │  ← ai_engine.py
    │                              │
    ▼            ▼                 ▼
┌─────────┐ ┌─────────┐ ┌──────────────┐
│ Market  │ │Financial│ │  Operations  │
│Strategist│ │Analyst  │ │  Optimizer   │
└────┬────┘ └────┬────┘ └──────┬───────┘
     │           │              │
  4 Sub-      4 Sub-         4 Sub-
  Agents      Agents         Agents
  (async)     (async)        (async)
     │           │              │
     └───────────┴──────────────┘
                 │
                 ▼
     Synthesized Streaming Response
          (SSE to Frontend)
                 │
                 ▼
    ┌────────────────────────┐
    │   Google ADK Agent     │  ← adk_agent.py
    │ (Gemini 2.5 Flash Lite)│
    │  Additional Analysis   │
    └────────────────────────┘
```

---

## ✅ Kaggle Evaluation Concepts Demonstrated

| Concept | Where | How |
|---|---|---|
| **Multi-agent system (ADK)** | `ai_engine.py`, `adk_agent.py` | 3 Main Agents + 12 Sub-Agents + Google ADK Agent |
| **MCP Server** | `mcp_server.py` | CSV tools: summarize, filter, stats, top values |
| **Security features** | `main.py` | API key auth, rate limiting, UUID validation, CORS |
| **Deployability** | `Dockerfile`, `docker-compose.yml` | Docker ready, health check endpoint |
| **Agent Skills (CLI)** | `cli.py` | Full CLI for agents + MCP tools |
| **RAG** | `rag_mcp.py` | CSV parsed into structured context injected into prompts |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- OpenRouter API key → https://openrouter.ai/keys
- Docker (optional)

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/nexus-cortex.git
cd nexus-cortex
```

### 2. Set up environment
```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 3. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Run the backend
```bash
uvicorn main:app --reload --port 8000
```

### 5. Open the frontend
Open `index.html` in your browser directly, or serve it:
```bash
# From project root
python -m http.server 3000
```
Then visit: http://localhost:3000

---

## 🐳 Docker Deployment

```bash
# Build and run
docker build -t nexus-cortex ./backend
docker run -p 8000:8000 --env-file backend/.env nexus-cortex

# Or with docker-compose
docker-compose up --build
```

---

## 💻 CLI Usage (Agent Skills)

```bash
cd backend

# List available MCP tools
python cli.py --mcp-list

# Run MCP tool directly
python cli.py --mcp-tool csv_summarize --mcp-params '{"csv_content":"product,price\nA,10\nB,20"}'

# Run ADK agent (Gemini 2.5 Flash Lite)
python cli.py "analyze sales trends" --adk

# Run with CSV file context
python cli.py "what are the top products?" --file data.csv --agent market

# Output as JSON
python cli.py "revenue analysis" --json
```

---

## 🔧 MCP Server Tools

| Tool | Description |
|---|---|
| `csv_summarize` | Row count, columns, null counts, sample data |
| `csv_column_stats` | Min, max, mean, median for any column |
| `csv_filter` | Filter rows by column value |
| `csv_top_values` | Top N most frequent values in a column |

---

## 🤖 Agent Roster

### Main Agents (GPT-4.1-nano via OpenRouter)
| Agent | Specialty |
|---|---|
| **Market Strategist** | Trends, competitor analysis, market gaps |
| **Financial Analyst** | Revenue forecasting, cost optimization, ROI |
| **Operations Optimizer** | Workflow efficiency, supply chain, quality |

### Sub-Agents (4 per Main Agent, RAM-controlled)
Each main agent leads 4 specialized sub-agents that run in parallel:
- **Market:** Trend Predictor, Competitor Intel, Sector Scanner, Risk Assessor
- **Financial:** Budget Optimizer, Forecast Engine, Audit Trail, Cost Analyzer
- **Operations:** Workflow Manager, Resource Allocator, Supply Chain Analyst, Quality Monitor

### ADK Agent (Gemini 2.5 Flash Lite via OpenRouter)
Google ADK-style agent providing additional cross-domain analysis.

---

## 🔐 Security Features

- **API Key Authentication** — Bearer token via `NEXUS_API_KEY` env var
- **Rate Limiting** — 10 requests per 60 seconds per session
- **UUID Session Validation** — Invalid session IDs rejected with 400
- **Query Length Limit** — Max 4000 characters
- **File Size Limit** — Max 50MB uploads
- **CORS Protection** — Environment-driven allowed origins
- **No Secrets in Code** — All keys via `.env` (never committed)

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## 📁 Project Structure

```
nexus-cortex/
├── backend/
│   ├── main.py              # FastAPI server + security
│   ├── ai_engine.py         # Multi-agent orchestrator
│   ├── adk_agent.py         # Google ADK agent (Gemini)
│   ├── mcp_server.py        # MCP server + CSV tools
│   ├── rag_mcp.py           # RAG pipeline + CSV parser
│   ├── ram_optimizer.py     # RAM-aware concurrency
│   ├── strict_prompts.py    # Agent prompts + scope enforcement
│   ├── cli.py               # Agent CLI tool
│   ├── __init__.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── tests/
│       └── test_api.py
├── index.html               # Frontend dashboard
├── app.js                   # Frontend logic + SSE streaming
├── style.css                # UI styles
├── ui_effects.js            # Animations + effects
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## 🌐 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | ✅ Yes | OpenRouter API key |
| `SITE_URL` | No | Your deployment URL (default: localhost:3000) |
| `NEXUS_API_KEY` | No | Protect endpoints with Bearer auth |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.11 |
| AI Models | GPT-4.1-nano, Gemini 2.5 Flash Lite |
| AI Provider | OpenRouter |
| Frontend | Vanilla JS, HTML5, CSS3, Canvas API |
| Streaming | Server-Sent Events (SSE) |
| Deployment | Docker, Uvicorn |
| Testing | Pytest, FastAPI TestClient |

---

## 📜 License

MIT License — free to use and modify.

---

*Built for Kaggle AI Agents Intensive Vibe Coding Capstone 2026 — Agents for Business Track*