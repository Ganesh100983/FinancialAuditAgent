import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from backend.auth import get_current_user, CurrentUser
from backend.session_store import get_session
from src.tools.form16_tools import create_form16_tools
from src.utils.pdf_generator import generate_form16_pdf
from src.models.financial_models import Form16Data, Form16PartA, Form16PartB

router = APIRouter(prefix="/form16", tags=["Form 16"])


class TaxComputeRequest(BaseModel):
    employee_id: str
    regime: str = "Old"
    rent_paid: float = 0.0
    is_metro: bool = True


def _get_tools(user: CurrentUser):
    store = get_session(user.session_id)
    if store["employee_df"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No employee data uploaded.")
    return create_form16_tools(store), store


@router.get("/employees")
async def list_employees(user: CurrentUser = Depends(get_current_user)):
    tools, _ = _get_tools(user)
    return json.loads(tools[0].run("all"))


def _regime_shape(raw: dict) -> dict:
    return {
        "gross_salary":      raw.get("gross_salary", 0),
        "hra_exemption":     raw.get("hra_exemption", 0),
        "standard_deduction":raw.get("standard_deduction", 0),
        "section_80c":       raw.get("section_80c", 0),
        "section_80d":       raw.get("section_80d", 0),
        "taxable_income":    raw.get("net_taxable_income", 0),
        "income_tax":        raw.get("income_tax", 0),
        "surcharge":         raw.get("surcharge", 0),
        "cess":              raw.get("cess", 0),
        "rebate_87a":        raw.get("rebate_87a", 0),
        "total_tax_payable": raw.get("total_tax_liability", 0),
    }


@router.post("/compute")
async def compute_tax(req: TaxComputeRequest, user: CurrentUser = Depends(get_current_user)):
    tools, _ = _get_tools(user)
    args = {"employee_id": req.employee_id, "rent_paid": req.rent_paid, "is_metro": req.is_metro}
    old_raw = json.loads(tools[1].run({**args, "regime": "Old"}))
    if "error" in old_raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, old_raw["error"])
    new_raw = json.loads(tools[1].run({**args, "regime": "New"}))
    return {
        "employee_id":   req.employee_id,
        "employee_name": old_raw.get("employee_name", ""),
        "old_regime":    _regime_shape(old_raw),
        "new_regime":    _regime_shape(new_raw),
    }


@router.post("/compare-regimes")
async def compare_regimes(req: TaxComputeRequest, user: CurrentUser = Depends(get_current_user)):
    tools, _ = _get_tools(user)
    result = json.loads(tools[2].run({
        "employee_id": req.employee_id,
        "regime": "both",
        "rent_paid": req.rent_paid,
        "is_metro": req.is_metro,
    }))
    if "error" in result:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result["error"])
    raw_recommended = result.get("recommended_regime", "New Regime")
    recommended = "new" if "New" in raw_recommended else "old"
    saving = result.get("tax_saving_old_vs_new", 0)
    return {
        "recommended":   recommended,
        "recommendation": result.get("recommendation_reason", ""),
        "tax_savings":   abs(saving),
    }


@router.get("/download/{employee_id}")
async def download_form16(
    employee_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    store = get_session(user.session_id)
    form16_data = store.get("form16_data", {})
    data = form16_data.get(employee_id)
    if not data:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Form 16 not generated for employee '{employee_id}'. Run compute first."
        )
    try:
        form16 = Form16Data(
            part_a=Form16PartA(**data["part_a"]),
            part_b=Form16PartB(**data["part_b"]),
            employee_id=data.get("employee_id", employee_id),
            generated_on=data.get("generated_on", datetime.now().strftime("%d-%m-%Y")),
        )
        pdf = generate_form16_pdf(form16)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"PDF generation failed: {e}")

    emp_name = data.get("part_a", {}).get("employee_name", employee_id).replace(" ", "_")
    filename = f"Form16_{emp_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/summary")
async def form16_summary(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    form16_data = store.get("form16_data", {})
    rows = []
    for emp_id, data in form16_data.items():
        pa = data.get("part_a", {})
        pb = data.get("part_b", {})
        rows.append({
            "employee_id": emp_id,
            "name": pa.get("employee_name", ""),
            "pan": pa.get("employee_pan", ""),
            "gross_salary": pb.get("gross_salary", 0),
            "net_taxable_income": pb.get("net_taxable_income", 0),
            "total_tax_liability": pb.get("total_tax_liability", 0),
            "tds_deducted": pb.get("tds_deducted", 0),
            "tax_payable": pb.get("tax_payable_or_refund", 0),
            "regime": pb.get("regime", "Old"),
        })
    return {"total": len(rows), "employees": rows}
