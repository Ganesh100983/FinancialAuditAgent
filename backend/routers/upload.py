import io
import textwrap

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.auth import get_current_user, CurrentUser
from backend.session_store import get_session
from src.utils.data_processor import parse_ledger, parse_gst_data, parse_employee_data

router = APIRouter(prefix="/upload", tags=["File Upload"])

_SAMPLES: dict[str, str] = {
    "ledger": textwrap.dedent("""\
        date,voucher_no,narration,account,debit,credit
        01-04-2024,JV0001,Opening Balance,Cash Account,0,500000
        05-04-2024,JV0002,Sales - ABC Pvt Ltd,Sales Account,0,150000
        10-04-2024,JV0003,Office Rent - April,Rent Expense,45000,0
        12-04-2024,JV0004,Staff Salaries,Salary Expense,200000,0
        15-04-2024,JV0005,Purchase - XYZ Suppliers,Purchase Account,80000,0
        20-04-2024,JV0006,Sales - DEF Corp,Sales Account,0,220000
        25-04-2024,JV0007,Electricity Bill,Utilities Expense,8500,0
        28-04-2024,JV0008,Bank Interest Received,Interest Income,0,3200
        30-04-2024,JV0009,Depreciation - Equipment,Depreciation,12000,0
        30-04-2024,JV0010,TDS Payable,TDS Liability,15000,0
    """),
    "gst": textwrap.dedent("""\
        invoice_no,invoice_date,party_name,party_gstin,hsn_code,taxable_value,cgst_rate,sgst_rate,igst_rate,invoice_type
        INV-001,01-04-2024,ABC Pvt Ltd,27AABCE1234A1Z5,8471,100000,9,9,0,B2B
        INV-002,03-04-2024,Retail Customer,,9983,25000,9,9,0,B2C
        INV-003,07-04-2024,DEF Exports Ltd,29AABCD5678B2Z3,8523,200000,0,0,18,B2B
        INV-004,10-04-2024,GHI Trading,24AABCG9012C3Z1,4901,50000,6,6,0,B2B
        INV-005,15-04-2024,Walk-in Customer,,9984,12000,9,9,0,B2C
        INV-006,20-04-2024,JKL Industries,07AABCJ3456D4Z9,8443,175000,9,9,0,B2B
        INV-007,25-04-2024,MNO Services,33AABCM7890E5Z7,9985,80000,9,9,0,B2B
        INV-008,28-04-2024,Retail Customer,,8517,18000,9,9,0,B2C
    """),
    "employee": textwrap.dedent("""\
        employee_id,name,pan,designation,basic_salary,hra,special_allowance,lta,medical_allowance,professional_tax,tds_deducted,section_80c,section_80d
        E001,Rahul Sharma,ABCRS1234F,Senior Engineer,60000,24000,18000,5000,1250,200,8000,150000,25000
        E002,Priya Nair,ABCPN5678G,Product Manager,80000,32000,25000,6000,1250,200,15000,150000,50000
        E003,Arjun Mehta,ABCAM9012H,Junior Developer,35000,14000,10000,3000,1250,200,2000,80000,0
        E004,Sunita Rao,ABCSR3456I,HR Executive,42000,16800,12000,4000,1250,200,3500,100000,25000
        E005,Vikram Patel,ABCVP7890J,Finance Manager,75000,30000,22000,6000,1250,200,12000,150000,50000
    """),
}


@router.get("/sample/{file_type}", tags=["File Upload"])
async def download_sample(file_type: str):
    if file_type not in _SAMPLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No sample for '{file_type}'. Use: ledger, gst, employee.")
    csv_bytes = _SAMPLES[file_type].encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sample_{file_type}.csv"},
    )

MAX_SIZE_MB = 20
ALLOWED_TYPES = {
    "text/csv", "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _validate(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_TYPES and not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only CSV and Excel files are accepted.")


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {MAX_SIZE_MB} MB limit.")
    return data


@router.post("/ledger")
async def upload_ledger(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    _validate(file)
    data = await _read(file)
    df, msg = parse_ledger(data, file.filename)
    if df is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)

    store = get_session(user.session_id)
    store["ledger_df"] = df
    store["ledger_summary"] = None
    store["anomalies"] = None
    store["trial_balance"] = None
    store["pl_statement"] = None

    return {"message": msg, "rows": len(df), "columns": list(df.columns)}


@router.post("/gst")
async def upload_gst(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    _validate(file)
    data = await _read(file)
    df, msg = parse_gst_data(data, file.filename)
    if df is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)

    store = get_session(user.session_id)
    store["gst_df"] = df
    store["gst_summary_data"] = None
    store["gstr1_data"] = None
    store["gstr3b_data"] = None

    return {"message": msg, "rows": len(df), "columns": list(df.columns)}


@router.post("/employee")
async def upload_employee(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    _validate(file)
    data = await _read(file)
    df, msg = parse_employee_data(data, file.filename)
    if df is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)

    store = get_session(user.session_id)
    store["employee_df"] = df
    store["form16_data"] = {}

    return {"message": msg, "rows": len(df), "columns": list(df.columns)}


@router.get("/status")
async def upload_status(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    return {
        "ledger":    store["ledger_df"] is not None and {"rows": len(store["ledger_df"])},
        "gst":       store["gst_df"] is not None and {"rows": len(store["gst_df"])},
        "employee":  store["employee_df"] is not None and {"rows": len(store["employee_df"])},
    }
