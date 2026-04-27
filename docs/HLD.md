# High-Level Design (HLD)
## FinAudit AI — Agentic Financial Audit Platform
**Version:** 2.0 | **Date:** April 2026 | **Stack:** Python 3.14 · FastAPI · LangGraph · React 18 · Tailwind CSS

---

## 1. System Overview

FinAudit AI is a multi-user, agentic web application that automates three core financial audit workflows for Indian businesses:

1. **Ledger Screening** — Anomaly detection, Trial Balance, P&L Statement from raw accounting data
2. **Form 16 Generation** — TDS certificate computation under Old and New tax regimes (FY 2024-25)
3. **GST Filing** — GSTR-1 and GSTR-3B return generation with GSTIN validation

An embedded **AI Assistant** layer allows auditors to query their data in natural language, with GPT-4o mini reasoning over the same tools via a LangGraph ReAct agent.

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT BROWSER                               │
│                                                                         │
│   ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐  │
│   │  Login   │  │  Dashboard   │  │ Ledger / │  │   AI Assistant   │  │
│   │  (JWT)   │  │  (Overview)  │  │ F16 / GST│  │  (SSE Streaming) │  │
│   └────┬─────┘  └──────┬───────┘  └────┬─────┘  └────────┬─────────┘  │
│        │               │               │                  │             │
│        └───────────────┴───────────────┴──────────────────┘             │
│                                 │                                        │
│              Axios (REST) + fetch (SSE/EventStream)                      │
│              Authorization: Bearer <JWT>                                 │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP / JSON  │  text/event-stream
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND  (:8000)                        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Middleware Stack                                                  │  │
│  │  CORSMiddleware → Request Logger → RateLimiter (slowapi)          │  │
│  │  Global Exception Handler → JWT Authentication (OAuth2Bearer)     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ /auth     │ │ /upload    │ │ /ledger  │ │ /form16  │ │ /gst     │ │
│  │ Router    │ │ Router     │ │ Router   │ │ Router   │ │ Router   │ │
│  └─────┬─────┘ └─────┬──────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│        │              │              │             │             │       │
│        ▼              ▼              └─────────────┴─────────────┘       │
│  ┌──────────┐  ┌──────────────┐            │                             │
│  │ Auth     │  │ Session      │            ▼                             │
│  │ (JWT +   │  │ Store        │    ┌───────────────┐                    │
│  │  bcrypt) │  │ (in-memory   │    │  Tools Layer  │                    │
│  └──────────┘  │  dict +      │    │  (Python fns) │                    │
│                │  threading   │    └───────────────┘                    │
│                │  .Lock)      │                                          │
│                └─────────────-┘                                          │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /chat/stream Router                                                │ │
│  │                                                                     │ │
│  │   ChatRequest → _build_agent() → LangGraph ReAct Agent             │ │
│  │   agent.astream_events(v2) → SSE generator → StreamingResponse     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         AI / LLM LAYER                                    │
│                                                                           │
│   LangGraph create_react_agent                                            │
│   ┌──────────────────────────────────────────────────────────────────┐   │
│   │  System Prompt (CA / Tax Expert persona)                          │   │
│   │         ↕                                                         │   │
│   │  GPT-4o mini  ←→  Tool Calling Loop (ReAct)                      │   │
│   │         ↕                                                         │   │
│   │  [ledger_tools | form16_tools | gst_tools]  ←  session data_store│   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│   OpenAI API  (api.openai.com)                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **UI Framework** | React 18 + Vite + Tailwind CSS | Component reuse, fast HMR, utility-first styling |
| **API Framework** | FastAPI | Async-native, automatic OpenAPI docs, Pydantic validation |
| **LLM Orchestration** | LangGraph `create_react_agent` | Modern LangChain 1.x API, built-in tool-calling loop, streaming support |
| **LLM Model** | GPT-4o mini | Cost-effective, fast, sufficient for structured financial reasoning |
| **Streaming** | SSE via `fetch + ReadableStream` | `EventSource` API doesn't support `Authorization` headers |
| **Session Store** | In-memory dict + `threading.Lock` | Simple single-process deployment; Redis migration path documented |
| **Authentication** | JWT (HS256) + bcrypt | Stateless, per-request user isolation via `session_id` in token |
| **Package Manager** | UV | Fast dependency resolution; replaces pip/poetry |
| **PDF Generation** | ReportLab | No external service dependency; full control over Form 16 layout |

---

## 4. Module Breakdown

### 4.1 Frontend (React)

```
frontend/src/
├── App.jsx                  — Router, protected-route guard
├── main.jsx                 — React root, Toaster config
├── api/client.js            — Axios instance, JWT interceptor, API functions
├── store/useAppStore.js     — Zustand global state (auth, uploads, settings)
├── hooks/useSSE.js          — SSE streaming hook (fetch + ReadableStream)
├── components/
│   ├── layout/              — Layout, Sidebar, Header
│   └── ui/                  — MetricCard, DataTable, FileUpload,
│                               Badge, StreamingOutput, SkeletonLoader
└── pages/
    ├── Login.jsx
    ├── Dashboard.jsx
    ├── LedgerScreener.jsx
    ├── Form16Generator.jsx
    ├── GSTFiling.jsx
    ├── AIAssistant.jsx
    └── Settings.jsx
```

### 4.2 Backend (FastAPI)

```
backend/
├── main.py             — App factory, middleware, lifespan, router mounts
├── config.py           — Pydantic BaseSettings (.env loader)
├── auth.py             — JWT encode/decode, bcrypt, get_current_user dependency
├── session_store.py    — Thread-safe in-memory session dict + TTL eviction
└── routers/
    ├── auth.py         — POST /login, POST /logout, GET /me
    ├── upload.py       — POST /ledger, /gst, /employee; GET /status
    ├── ledger.py       — GET summary, anomalies, trial-balance, pl-statement, ...
    ├── form16.py       — GET employees, POST compute, POST compare-regimes, ...
    ├── gst.py          — GET summary, POST gstr1, POST gstr3b, GET validate-gstin
    └── chat.py         — POST /stream (SSE), GET/PUT /settings
```

### 4.3 Core Business Logic (src/)

```
src/
├── models/financial_models.py   — Pydantic v2 domain models
├── utils/
│   ├── data_processor.py        — CSV/XLSX parsing, column alias mapping
│   └── pdf_generator.py         — ReportLab PDF builders
├── tools/
│   ├── ledger_tools.py          — 5 StructuredTools (summary, anomalies, ...)
│   ├── form16_tools.py          — 3 StructuredTools (list, compute, compare)
│   └── gst_tools.py             — 5 StructuredTools (summary, gstr1, gstr3b, ...)
└── agents/
    ├── ledger_agent.py          — CA persona + ledger tools
    ├── form16_agent.py          — Tax expert persona + form16 tools
    └── gst_agent.py             — GST expert persona + gst tools
```

---

## 5. Data Flow — Two Paths

### Path 1: Structured API (No LLM)
```
User action (e.g. "Load Ledger Summary")
  → Axios GET /api/v1/ledger/summary
  → FastAPI validates JWT → extracts session_id
  → Calls ledger_tools[0].run("full") directly
  → Returns JSON to React → renders MetricCard / Chart
```

### Path 2: AI Assistant (LLM + ReAct)
```
User types query → selects agent type (ledger/form16/gst)
  → fetch POST /api/v1/chat/stream  body: { message, agent_type }
  → FastAPI: _build_agent(agent_type, api_key, session_store)
  → LangGraph ReAct loop:
      GPT-4o mini decides which tool(s) to call
      → tool executes on in-memory DataFrame
      → result returned to LLM as tool output
      → LLM generates final narrative
  → astream_events(v2) yields token chunks
  → SSE: data: {"type":"token","content":"..."}\n\n
  → React useSSE hook appends to output state
  → StreamingOutput renders with blinking cursor
```

---

## 6. Security Model

| Layer | Control |
|---|---|
| Authentication | JWT (HS256), 24-hour expiry, `session_id` embedded in token |
| Authorization | `get_current_user` FastAPI dependency on every protected endpoint |
| Data Isolation | Each user's DataFrames stored in their own `session_id` bucket |
| Rate Limiting | 10 req/min on `/chat/stream`, 60 req/min default (slowapi) |
| CORS | Explicit origin whitelist (configurable via `.env`) |
| API Key | OpenAI key stored server-side in session store, never returned to browser |
| File Validation | MIME type check + 20 MB size limit on all uploads |

---

## 7. Deployment Modes

### Development (dual-server)
```
run.bat / run.sh
  ├── uvicorn backend.main:app --port 8000 --reload   (FastAPI)
  └── npm run dev (Vite)  --port 5173                 (React + proxy /api → :8000)
```

### Production (single-server)
```
npm run build  →  frontend/dist/
uvicorn backend.main:app --port 8000
  └── FastAPI serves frontend/dist as static files
      catch-all route → index.html (SPA routing)
```

---

## 8. Technology Stack Summary

| Layer | Technology | Version |
|---|---|---|
| Frontend | React | 18.3 |
| Build Tool | Vite | 5.3 |
| Styling | Tailwind CSS | 3.4 |
| Charts | Recharts | 2.12 |
| State Management | Zustand | 4.5 |
| HTTP Client | Axios | 1.7 |
| Backend | FastAPI | 0.115+ |
| ASGI Server | Uvicorn | 0.30+ |
| LLM Orchestration | LangGraph / LangChain | 1.x |
| LLM Model | OpenAI GPT-4o mini | — |
| Data Processing | Pandas | 2.x |
| PDF Generation | ReportLab | 4.x |
| Auth | python-jose + passlib/bcrypt | — |
| Rate Limiting | slowapi | 0.1.9 |
| Package Manager | UV | Latest |

---

## 9. Scalability & Production Gaps

| Gap | Current State | Production Fix |
|---|---|---|
| Session Store | In-memory dict | Redis (with TTL) |
| User Store | Hardcoded dict in config.py | PostgreSQL + Alembic |
| File Storage | In-memory DataFrame | S3 / Azure Blob (parse on upload, store parquet) |
| Multi-process | Not supported (shared memory) | Replace session store with Redis first |
| HTTPS | Not configured | Nginx reverse proxy + Let's Encrypt |
| Secrets | `.env` file | AWS Secrets Manager / Vault |
| Logging | stdout | Structured JSON → ELK / CloudWatch |
