# Financial Audit AI

Agentic AI Financial Auditor built with Python, LangChain, and Streamlit.

## Features
- **Ledger Screener** — AI-powered audit, anomaly detection, Trial Balance, P&L Statement
- **Form 16 Generator** — TDS computation, Old/New regime comparison, PDF output
- **GST Filing** — GSTR-1 & GSTR-3B preparation, GSTIN validation, rate-wise analysis
- **AI Assistant** — Chat with specialized financial agents

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Run
uv run streamlit run app.py
```

Or use the run script:
- Windows: `run.bat`
- Linux/Mac: `bash run.sh`

## Sample Data
Test files are in `sample_data/`:
- `sample_ledger.csv` — 98-entry accounting ledger
- `sample_gst_invoices.csv` — 29 GST invoices (B2B + B2C)
- `sample_employee.csv` — 15 employees with salary & TDS data
