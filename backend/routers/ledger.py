import json
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user, CurrentUser
from backend.config import get_settings
from backend.session_store import get_session
from src.tools.ledger_tools import create_ledger_tools
from src.utils.pdf_generator import generate_ledger_report_pdf
from fastapi.responses import Response

router = APIRouter(prefix="/ledger", tags=["Ledger Analysis"])


def _get_tools(user: CurrentUser):
    store = get_session(user.session_id)
    if store["ledger_df"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No ledger uploaded. Please upload a ledger file first.")
    return create_ledger_tools(store), store


@router.get("/summary")
async def ledger_summary(user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[0].run("full"))
    store["ledger_summary"] = result
    return result


@router.get("/anomalies")
async def ledger_anomalies(user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[1].run("all"))
    store["anomalies"] = result.get("anomalies", [])
    return result


@router.get("/trial-balance")
async def trial_balance(user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[2].run("all"))
    store["trial_balance"] = result
    return result


@router.get("/pl-statement")
async def pl_statement(user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[3].run("full"))
    store["pl_statement"] = result
    return result


@router.get("/top-transactions")
async def top_transactions(n: int = 10, user: CurrentUser = Depends(get_current_user)):
    tools, _ = _get_tools(user)
    return json.loads(tools[4].run(str(n)))


@router.get("/preview")
async def ledger_preview(page: int = 1, page_size: int = 50, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    df = store.get("ledger_df")
    if df is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No ledger uploaded.")
    total = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    slice_df = df.iloc[start:end].fillna("")
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": slice_df.to_dict("records"),
        "columns": list(df.columns),
    }


@router.get("/report/pdf")
async def download_audit_report(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    summary = store.get("ledger_summary") or {}
    anomalies = store.get("anomalies") or []
    if not summary:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Run ledger analysis first.")
    pdf = generate_ledger_report_pdf(summary, anomalies, store.get("company_name") or get_settings().default_company_name)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=audit_report.pdf"})
