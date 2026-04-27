# Financial Audit AI

An agentic AI-powered financial audit platform built with **FastAPI** (backend) and **React** (frontend). Covers ledger analysis, Form 16 generation, GST filing, and a natural-language AI assistant — all in one web application.

---

## Features

| Module | Capabilities |
|---|---|
| **Ledger Screener** | Upload CSV/XLSX ledger, anomaly detection, trial balance, P&L statement, monthly charts, raw data viewer, PDF audit report |
| **Form 16 Generator** | Employee tax computation (Old & New regime), HRA/LTA/Chapter VI-A deductions, regime comparison, PDF Form 16 download |
| **GST Filing** | GSTR-1 & GSTR-3B generation, GSTIN validation, liability by rate, invoice breakdown, JSON + PDF download |
| **AI Assistant** | Chat with a LangChain agent backed by OpenAI GPT-4o-mini; uses financial tools based on uploaded data |

---

## Tech Stack

**Backend**
- Python 3.11+ · FastAPI · Uvicorn
- LangChain 0.3 · OpenAI GPT-4o-mini
- Pandas · ReportLab (PDF) · OpenPyXL
- python-jose (JWT) · passlib/bcrypt · SlowAPI (rate limiting)
- pydantic-settings · python-dotenv

**Frontend**
- React 18 · Vite · TailwindCSS
- Zustand (state) · Axios · Recharts
- react-dropzone · react-hot-toast · lucide-react

---

## Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager (`pip install uv`)
- Node.js 18+ and npm
- An OpenAI API key

---

## Setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd FinancialAuditAgent
```

Copy the environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...your-key...

APP_TITLE="Financial Audit AI"

# Company defaults (used in generated PDFs)
COMPANY_NAME="Your Company Name"
COMPANY_GSTIN="27AABCU9603R1ZX"
COMPANY_TAN="MUMA12345A"
COMPANY_PAN="AABCU9603R"
FINANCIAL_YEAR="2024-25"
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running (Development)

Open two terminals:

**Terminal 1 — Backend**
```bash
uv run uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

The app will be available at **http://localhost:5173**. The frontend dev server proxies `/api` requests to the backend at port 8000.

---

## Running (Production)

Build the React app and serve everything from FastAPI:

```bash
cd frontend
npm run build
cd ..
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The built frontend is served from `frontend/dist/` by FastAPI's static file handler. Access the app at **http://localhost:8000**.

---

## Demo Credentials

| Username | Password | Role |
|---|---|---|
| `auditor` | `FinAudit@2025` | Auditor |
| `viewer` | `FinView@2025` | Viewer |

> To add or change users, edit `demo_users` in `backend/config.py` and restart the server.

---

## API Documentation

Once the backend is running, interactive API docs are available at:

- **Swagger UI** — http://localhost:8000/docs
- **ReDoc** — http://localhost:8000/redoc
- **Health check** — http://localhost:8000/api/health

All protected endpoints require a Bearer token obtained from `POST /api/v1/auth/login`.

---

## Sample Data

The app provides built-in sample files for testing. Use the **Download sample** link in each upload widget, or call the endpoint directly:

| File type | Endpoint |
|---|---|
| Ledger | `GET /api/v1/upload/sample/ledger` |
| GST invoices | `GET /api/v1/upload/sample/gst` |
| Employee data | `GET /api/v1/upload/sample/employee` |

Pre-built sample files are also in `sample_data/`:

| File | Contents |
|---|---|
| `sample_ledger.csv` | 98-entry accounting ledger |
| `sample_gst_invoices.csv` | 29 GST invoices (B2B + B2C) |
| `sample_employee.csv` | 15 employees with salary & TDS data |

---

## Project Structure

```
FinancialAuditAgent/
├── backend/
│   ├── main.py              # FastAPI app, middleware, router registration
│   ├── config.py            # pydantic-settings config (reads .env)
│   ├── auth.py              # JWT auth, OAuth2 password bearer
│   ├── session_store.py     # In-memory per-user session (TTL: 8 h)
│   └── routers/
│       ├── auth.py          # /auth/login, /auth/logout, /auth/me
│       ├── upload.py        # /upload/ledger|gst|employee, /upload/sample/{type}
│       ├── ledger.py        # /ledger/summary|anomalies|trial-balance|pl-statement|…
│       ├── form16.py        # /form16/employees|compute|compare-regimes|download/{id}
│       ├── gst.py           # /gst/summary|gstr1|gstr3b|validate-gstin|…
│       └── chat.py          # /chat/stream (SSE), /chat/settings
├── src/
│   ├── tools/
│   │   ├── ledger_tools.py  # LangChain tools: summary, anomalies, trial balance, P&L
│   │   ├── form16_tools.py  # LangChain tools: list employees, compute tax, compare regimes
│   │   └── gst_tools.py     # LangChain tools: summary, GSTR-1, GSTR-3B, GSTIN validator
│   ├── models/
│   │   └── financial_models.py  # Pydantic models for Form 16, GSTR-1, GSTR-3B
│   └── utils/
│       └── pdf_generator.py     # ReportLab PDF builders (ledger report, GSTR-1, Form 16)
├── frontend/
│   ├── src/
│   │   ├── pages/           # Login, Dashboard, LedgerScreener, Form16Generator, GSTFiling, AIAssistant, Settings
│   │   ├── components/ui/   # FileUpload, DataTable, MetricCard, Badge, …
│   │   ├── api/client.js    # Axios instance + all API helpers + downloadBlob()
│   │   └── store/           # Zustand store (auth, uploads)
│   ├── vite.config.js       # Vite config with /api proxy to :8000
│   └── package.json
├── sample_data/             # Test CSV files
├── pyproject.toml           # Python project + uv dependencies
└── .env                     # Environment variables (not committed)
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `SECRET_KEY` | `test12345` | JWT signing secret — **change in production** |
| `ACCESS_TOKEN_EXPIRE_HOURS` | `24` | JWT token lifetime |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CORS allowed origins (comma-separated) |
| `SESSION_TTL_HOURS` | `8` | Uploaded data session lifetime |
| `COMPANY_NAME` | `ABC Pvt Ltd` | Default company name in PDFs |
| `COMPANY_GSTIN` | `27AABCE1234A1Z5` | Default GSTIN in PDFs |
| `COMPANY_TAN` | `MUMA12345A` | Default TAN in PDFs |
| `DEFAULT_FINANCIAL_YEAR` | `2024-25` | Financial year shown on Form 16 |

> **Important:** Set a strong, random `SECRET_KEY` before deploying to production.
