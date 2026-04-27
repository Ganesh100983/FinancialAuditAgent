import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from backend.auth import get_current_user, CurrentUser
from backend.session_store import get_session
from src.tools.gst_tools import create_gst_tools
from src.utils.pdf_generator import generate_gst_report_pdf
from src.models.financial_models import GSTR1Summary

router = APIRouter(prefix="/gst", tags=["GST Filing"])


class GSTFilingRequest(BaseModel):
    gstin: str = ""
    period: str = ""


def _get_tools(user: CurrentUser):
    store = get_session(user.session_id)
    if store["gst_df"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No GST invoice data uploaded.")
    return create_gst_tools(store), store


@router.get("/summary")
async def gst_summary(user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[0].run("all"))
    store["gst_summary_data"] = result
    return result


@router.post("/gstr1")
async def generate_gstr1(req: GSTFilingRequest, user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[1].run({"gstin": req.gstin, "period": req.period}))
    if "error" in result:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result["error"])
    store["gstr1_data"] = result
    return result


@router.post("/gstr3b")
async def generate_gstr3b(req: GSTFilingRequest, user: CurrentUser = Depends(get_current_user)):
    tools, store = _get_tools(user)
    result = json.loads(tools[2].run({"gstin": req.gstin, "period": req.period}))
    if "error" in result:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result["error"])
    store["gstr3b_data"] = result
    return result


@router.get("/validate-gstin")
async def validate_gstin(gstin: str, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    tools = create_gst_tools(store)
    return json.loads(tools[3].run(gstin))


@router.get("/liability-by-rate")
async def liability_by_rate(user: CurrentUser = Depends(get_current_user)):
    tools, _ = _get_tools(user)
    return json.loads(tools[4].run("all"))


@router.get("/preview")
async def gst_preview(page: int = 1, page_size: int = 50, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    df = store.get("gst_df")
    if df is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No GST data uploaded.")
    total = len(df)
    start = (page - 1) * page_size
    slice_df = df.iloc[start: start + page_size].fillna("")
    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": slice_df.to_dict("records"),
        "columns": list(df.columns),
    }


@router.get("/download/gstr1")
async def download_gstr1(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    data = store.get("gstr1_data")
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generate GSTR-1 first.")
    content = json.dumps(data, indent=2, default=str).encode()
    gstin = data.get("gstin", "GSTIN")
    period = data.get("period", "period")
    return Response(content=content, media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=GSTR1_{gstin}_{period}.json"})


@router.get("/download/gstr3b")
async def download_gstr3b(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    data = store.get("gstr3b_data")
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generate GSTR-3B first.")
    content = json.dumps(data, indent=2, default=str).encode()
    gstin = data.get("gstin", "GSTIN")
    period = data.get("period", "period")
    return Response(content=content, media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=GSTR3B_{gstin}_{period}.json"})


@router.get("/download/gstr1/pdf")
async def download_gstr1_pdf(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    data = store.get("gstr1_data")
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generate GSTR-1 first.")
    gstr1 = GSTR1Summary(**{k: data.get(k, v) for k, v in GSTR1Summary.model_fields.items()
                             if k in data})
    pdf = generate_gst_report_pdf(gstr1)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=GSTR1_report.pdf"})
