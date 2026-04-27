"""
In-memory session store keyed by session_id (from JWT).
Each session holds the user's uploaded DataFrames and analysis results.
In production, replace with Redis for multi-process / multi-instance deployments.
"""
import threading
from datetime import datetime, timezone, timedelta

from backend.config import get_settings

_lock = threading.Lock()
_sessions: dict[str, dict] = {}


def _default_store() -> dict:
    s = get_settings()
    default_company = {
        "id": "default",
        "name": s.default_company_name,
        "gstin": s.default_gstin,
        "tan": s.default_tan,
        "pan": s.default_pan,
        "address": "Mumbai, Maharashtra - 400001",
        "financial_year": s.default_financial_year,
    }
    return {
        # uploaded data
        "ledger_df": None,
        "gst_df": None,
        "employee_df": None,
        # companies list & active selection
        "companies": [default_company],
        "active_company_id": "default",
        # active company fields (kept in sync with selected company)
        "company_name": s.default_company_name,
        "company_gstin": s.default_gstin,
        "company_tan": s.default_tan,
        "company_pan": s.default_pan,
        "company_address": "Mumbai, Maharashtra - 400001",
        "financial_year": s.default_financial_year,
        "openai_api_key": s.openai_api_key,
        # analysis results (cached)
        "ledger_summary": None,
        "anomalies": None,
        "trial_balance": None,
        "pl_statement": None,
        "gst_summary_data": None,
        "gstr1_data": None,
        "gstr3b_data": None,
        "form16_data": {},
        # metadata
        "_created_at": datetime.now(timezone.utc).isoformat(),
        "_last_accessed": datetime.now(timezone.utc).isoformat(),
    }


def get_session(session_id: str) -> dict:
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = _default_store()
        else:
            _sessions[session_id]["_last_accessed"] = datetime.now(timezone.utc).isoformat()
        return _sessions[session_id]


def delete_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def evict_expired_sessions() -> int:
    """Remove sessions older than TTL. Call periodically from a background task."""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.session_ttl_hours)
    evicted = 0
    with _lock:
        expired = [
            sid for sid, data in _sessions.items()
            if datetime.fromisoformat(data["_last_accessed"]) < cutoff
        ]
        for sid in expired:
            del _sessions[sid]
            evicted += 1
    return evicted


def session_stats() -> dict:
    with _lock:
        return {
            "total_sessions": len(_sessions),
            "sessions": [
                {
                    "id": sid[:8] + "...",
                    "created": data["_created_at"],
                    "last_accessed": data["_last_accessed"],
                    "has_ledger": data["ledger_df"] is not None,
                    "has_gst": data["gst_df"] is not None,
                    "has_employees": data["employee_df"] is not None,
                }
                for sid, data in _sessions.items()
            ],
        }
