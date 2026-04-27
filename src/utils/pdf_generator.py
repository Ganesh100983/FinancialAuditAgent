import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import KeepTogether
from reportlab.graphics.shapes import Drawing, Circle, String as GrString

from src.models.financial_models import Form16Data, GSTR1Summary, GSTR3BSummary


# ── Font registration ─────────────────────────────────────────────────────────
# Helvetica (built-in) only covers Latin-1 and cannot render ₹ (U+20B9).
# Calibri ships with every Windows 7+ install and has full ₹ support.
_WIN_FONTS = r"C:\Windows\Fonts"
_FONT  = "Helvetica"
_FONTB = "Helvetica-Bold"
_RUPEE = "Rs."          # fallback symbol if font lacks ₹

def _try_register(name: str, name_bold: str, regular: str, bold: str) -> bool:
    try:
        pdfmetrics.registerFont(TTFont(name,      regular))
        pdfmetrics.registerFont(TTFont(name_bold, bold))
        pdfmetrics.registerFontFamily(name, normal=name, bold=name_bold)
        return True
    except Exception:
        return False

# Try Calibri first, then Arial, then stay with Helvetica
if _try_register("Calibri", "Calibri-Bold",
                 os.path.join(_WIN_FONTS, "calibri.ttf"),
                 os.path.join(_WIN_FONTS, "calibrib.ttf")):
    _FONT, _FONTB, _RUPEE = "Calibri", "Calibri-Bold", "Rs."
elif _try_register("Arial", "Arial-Bold",
                   os.path.join(_WIN_FONTS, "arial.ttf"),
                   os.path.join(_WIN_FONTS, "arialbd.ttf")):
    _FONT, _FONTB, _RUPEE = "Arial", "Arial-Bold", "Rs."


NAVY = colors.HexColor("#1E3A5F")
LIGHT_BLUE = colors.HexColor("#D6E4F0")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
GREEN = colors.HexColor("#27AE60")
RED = colors.HexColor("#E74C3C")
ORANGE = colors.HexColor("#F39C12")


# ── Watermark ─────────────────────────────────────────────────────────────────
def _watermark_callback(company_name: str):
    """Returns an onPage callback that stamps a diagonal watermark on every page."""
    def _draw(canvas, _):
        canvas.saveState()
        canvas.setFont(_FONTB, 52)
        canvas.setFillColor(colors.Color(0.78, 0.78, 0.78, alpha=0.13))
        w, h = A4
        canvas.translate(w / 2, h / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, company_name)
        canvas.restoreState()
    return _draw


# ── Company seal ──────────────────────────────────────────────────────────────
def _seal_drawing(company_name: str, size: float = 72) -> Drawing:
    """Circular company seal with initials and SEAL label."""
    d = Drawing(size, size)
    cx, cy, r = size / 2, size / 2, size / 2 - 2
    d.add(Circle(cx, cy, r,       fillColor=None, strokeColor=NAVY, strokeWidth=1.8))
    d.add(Circle(cx, cy, r - 7,   fillColor=None, strokeColor=NAVY, strokeWidth=0.6))
    initials = "".join(w[0] for w in company_name.split() if w)[:4].upper()
    d.add(GrString(cx, cy,        initials, textAnchor="middle", fontSize=15,
                   fontName=_FONTB, fillColor=NAVY))
    d.add(GrString(cx, cy - 16,   "SEAL",   textAnchor="middle", fontSize=6.5,
                   fontName=_FONTB, fillColor=NAVY))
    d.add(GrString(cx, cy + 18,   company_name[:18], textAnchor="middle", fontSize=5.5,
                   fontName=_FONT, fillColor=NAVY))
    return d


# ── Signature block ───────────────────────────────────────────────────────────
def _signature_block(company_name: str, gstin: str = "", date_str: str = "") -> list:
    """Returns a list of flowables forming the authorized-signatory footer."""
    date_str = date_str or datetime.now().strftime("%d-%m-%Y")

    lbl  = ParagraphStyle("sl", fontName=_FONT,  fontSize=8,  textColor=colors.HexColor("#555555"))
    bold = ParagraphStyle("sb", fontName=_FONTB, fontSize=9,  textColor=NAVY)
    tiny = ParagraphStyle("st", fontName=_FONT,  fontSize=7.5, textColor=colors.grey)

    sig_data = [
        [
            Paragraph("For", lbl),
            "",
            Paragraph(f"Date: <b>{date_str}</b>", lbl),
        ],
        [
            Paragraph(f"<b>{company_name}</b>", bold),
            _seal_drawing(company_name, 70),
            Paragraph(f"GSTIN: {gstin}" if gstin else "", tiny),
        ],
        [
            Paragraph("_" * 32, lbl),
            "",
            "",
        ],
        [
            Paragraph("Authorized Signatory", bold),
            "",
            Paragraph("(Digitally Verified)", tiny),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[8 * cm, 3.5 * cm, 6 * cm])
    sig_table.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("LINEABOVE",     (0, 0), (-1,  0), 1.2, NAVY),
        ("BACKGROUND",    (0, 0), (-1,  0), LIGHT_BLUE),
        ("VALIGN",        (1, 0), (1, -1), "MIDDLE"),
        ("ALIGN",         (1, 0), (1, -1), "CENTER"),
        ("SPAN",          (1, 0), (1, -1)),
    ]))
    return [Spacer(1, 0.6 * cm), sig_table]


def _header_style(size=10, bold=True, color=colors.white, align=TA_CENTER):
    return ParagraphStyle(
        "header",
        fontName=_FONTB if bold else _FONT,
        fontSize=size,
        textColor=color,
        alignment=align,
        spaceAfter=2,
    )


def _cell_style(size=9, bold=False, align=TA_LEFT):
    return ParagraphStyle(
        "cell",
        fontName=_FONTB if bold else _FONT,
        fontSize=size,
        textColor=colors.black,
        alignment=align,
        spaceAfter=1,
    )


def generate_form16_pdf(form16: Form16Data) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "title", fontName=_FONTB, fontSize=14,
        textColor=colors.white, alignment=TA_CENTER, spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "subtitle", fontName=_FONTB, fontSize=10,
        textColor=colors.white, alignment=TA_CENTER, spaceAfter=2
    )
    body_style = ParagraphStyle(
        "body", fontName=_FONT, fontSize=9,
        textColor=colors.black, spaceAfter=3
    )
    label_style = ParagraphStyle(
        "label", fontName=_FONTB, fontSize=9,
        textColor=NAVY, spaceAfter=2
    )

    header_data = [
        [Paragraph("FORM 16", title_style)],
        [Paragraph(
            f"Certificate under Section 203 of the Income-tax Act, 1961 for Tax Deducted at Source from Salary",
            subtitle_style
        )],
        [Paragraph(
            f"Financial Year: {form16.part_a.financial_year} | Assessment Year: {form16.part_a.assessment_year}",
            subtitle_style
        )],
    ]
    header_table = Table(header_data, colWidths=[17.5 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3 * cm))

    part_a_header = Table(
        [[Paragraph("PART A – TDS DETAILS", _header_style(10))]],
        colWidths=[17.5 * cm]
    )
    part_a_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2E86AB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(part_a_header)

    pa = form16.part_a
    part_a_data = [
        ["Name & Address of Employer", pa.employer_name, "TAN of Employer", pa.employer_tan],
        ["PAN of Employer", pa.employer_pan, "PAN of Employee", pa.employee_pan],
        ["Name of Employee", pa.employee_name, "Designation", pa.employee_designation],
        ["Period of Employment", f"{pa.period_from} to {pa.period_to}", "Assessment Year", pa.assessment_year],
        [f"Total TDS Deducted ({_RUPEE})", f"{_RUPEE} {pa.total_tds_deducted:,.2f}", f"Total TDS Deposited ({_RUPEE})", f"{_RUPEE} {pa.total_tds_deposited:,.2f}"],
    ]

    part_a_table = Table(part_a_data, colWidths=[5 * cm, 4 * cm, 4 * cm, 4.5 * cm])
    part_a_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
        ("FONTNAME", (0, 0), (0, -1), _FONTB),
        ("FONTNAME", (2, 0), (2, -1), _FONTB),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(part_a_table)
    story.append(Spacer(1, 0.4 * cm))

    part_b_header = Table(
        [[Paragraph("PART B – SALARY DETAILS & COMPUTATION OF TAX", _header_style(10))]],
        colWidths=[17.5 * cm]
    )
    part_b_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2E86AB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(part_b_header)

    pb = form16.part_b

    def salary_row(label, amount, is_subtotal=False, indent=0):
        prefix = " " * (indent * 4)
        lbl = Paragraph(
            f"{prefix}{label}",
            ParagraphStyle("r", fontName=_FONTB if is_subtotal else "Helvetica",
                           fontSize=9, textColor=NAVY if is_subtotal else colors.black)
        )
        amt = Paragraph(
            f"{_RUPEE} {amount:,.2f}",
            ParagraphStyle("r", fontName=_FONTB if is_subtotal else "Helvetica",
                           fontSize=9, alignment=TA_RIGHT,
                           textColor=NAVY if is_subtotal else colors.black)
        )
        return [lbl, amt]

    salary_data = [
        [Paragraph("PARTICULARS", _header_style(9, color=NAVY)), Paragraph(f"AMOUNT ({_RUPEE})", _header_style(9, color=NAVY, align=TA_RIGHT))],
        salary_row("A. GROSS SALARY", pb.gross_salary, True),
        salary_row("(i) Basic Salary", pb.basic_salary, indent=1),
        salary_row("(ii) House Rent Allowance", pb.hra_received, indent=1),
        salary_row("(iii) Special Allowance", pb.special_allowance, indent=1),
        salary_row("(iv) Leave Travel Allowance", pb.lta, indent=1),
        salary_row("(v) Medical Allowance", pb.medical_allowance, indent=1),
        salary_row("(vi) Other Allowances", pb.other_allowances, indent=1),
        salary_row("B. LESS: EXEMPTIONS", 0, True),
        salary_row("(i) HRA Exemption u/s 10(13A)", pb.hra_exemption, indent=1),
        salary_row("(ii) LTA Exemption u/s 10(5)", pb.lta_exemption, indent=1),
        salary_row("C. BALANCE (A - B)", pb.gross_salary - pb.hra_exemption - pb.lta_exemption, True),
        salary_row("D. Standard Deduction u/s 16(ia)", pb.standard_deduction),
        salary_row("E. Professional Tax u/s 16(iii)", pb.professional_tax),
        salary_row("F. INCOME FROM SALARY (C - D - E)", pb.income_from_salary, True),
    ]

    salary_table = Table(salary_data, colWidths=[13 * cm, 4.5 * cm])
    salary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("FONTNAME", (0, 0), (-1, 0), _FONTB),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GRAY),
        ("BACKGROUND", (0, 8), (-1, 8), LIGHT_GRAY),
        ("BACKGROUND", (0, 11), (-1, 11), LIGHT_GRAY),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
    ]))
    story.append(salary_table)
    story.append(Spacer(1, 0.3 * cm))

    ded_header = Table(
        [[Paragraph("CHAPTER VI-A DEDUCTIONS", _header_style(9))]],
        colWidths=[17.5 * cm]
    )
    ded_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#117A65")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ded_header)

    ded_data = [
        [Paragraph("SECTION", _header_style(9, color=NAVY)), Paragraph("PARTICULARS", _header_style(9, color=NAVY)), Paragraph(f"AMOUNT ({_RUPEE})", _header_style(9, color=NAVY))],
        ["80C", "Investments (LIC, PPF, ELSS, NSC, etc.)", f"{_RUPEE} {pb.section_80c:,.2f}"],
        ["80CCC", "Pension Fund Contribution", f"{_RUPEE} {pb.section_80ccc:,.2f}"],
        ["80CCD(1)", "NPS Employee Contribution", f"{_RUPEE} {pb.section_80ccd:,.2f}"],
        ["80D", "Medical Insurance Premium", f"{_RUPEE} {pb.section_80d:,.2f}"],
        ["80E", "Education Loan Interest", f"{_RUPEE} {pb.section_80e:,.2f}"],
        ["80G", "Donations to Charitable Institutions", f"{_RUPEE} {pb.section_80g:,.2f}"],
        ["80TTA", "Interest on Savings Account", f"{_RUPEE} {pb.section_80tta:,.2f}"],
        [Paragraph("TOTAL DEDUCTIONS", _header_style(9, color=NAVY, bold=True)), "", Paragraph(f"{_RUPEE} {pb.total_deductions:,.2f}", _header_style(9, color=NAVY, bold=True))],
    ]

    ded_table = Table(ded_data, colWidths=[3 * cm, 10.5 * cm, 4 * cm])
    ded_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("FONTNAME", (0, 0), (-1, 0), _FONTB),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
        ("FONTNAME", (0, -1), (-1, -1), _FONTB),
        ("SPAN", (0, -1), (1, -1)),
    ]))
    story.append(ded_table)
    story.append(Spacer(1, 0.3 * cm))

    tax_header = Table(
        [[Paragraph("TAX COMPUTATION", _header_style(9))]],
        colWidths=[17.5 * cm]
    )
    tax_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#884EA0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tax_header)

    tax_data = [
        [Paragraph("PARTICULARS", _header_style(9, color=NAVY)), Paragraph(f"AMOUNT ({_RUPEE})", _header_style(9, color=NAVY))],
        ["Net Taxable Income (Salary - Deductions)", f"{_RUPEE} {pb.net_taxable_income:,.2f}"],
        [f"Tax on Income ({pb.regime} Tax Regime)", f"{_RUPEE} {pb.tax_on_income:,.2f}"],
        ["Surcharge (if applicable)", f"{_RUPEE} {pb.surcharge:,.2f}"],
        ["Health & Education Cess @ 4%", f"{_RUPEE} {pb.health_education_cess:,.2f}"],
        [Paragraph("Total Tax Liability", label_style), Paragraph(f"{_RUPEE} {pb.total_tax_liability:,.2f}", _cell_style(9, True, TA_RIGHT))],
        ["Relief u/s 87A", f"{_RUPEE} {pb.relief_u87a:,.2f}"],
        [Paragraph("TDS Deducted by Employer", label_style), Paragraph(f"{_RUPEE} {pb.tds_deducted:,.2f}", _cell_style(9, True, TA_RIGHT))],
        [
            Paragraph(
                "Tax Payable / (Refundable)" if pb.tax_payable_or_refund >= 0 else "Tax Refundable",
                ParagraphStyle("p", fontName=_FONTB, fontSize=10, textColor=RED if pb.tax_payable_or_refund > 0 else GREEN)
            ),
            Paragraph(
                f"{_RUPEE} {abs(pb.tax_payable_or_refund):,.2f}",
                ParagraphStyle("p", fontName=_FONTB, fontSize=10,
                               textColor=RED if pb.tax_payable_or_refund > 0 else GREEN, alignment=TA_RIGHT)
            )
        ],
    ]

    tax_table = Table(tax_data, colWidths=[13 * cm, 4.5 * cm])
    tax_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("FONTNAME", (0, 0), (-1, 0), _FONTB),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, 5), (-1, 5), LIGHT_GRAY),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
        ("FONTNAME", (0, -1), (-1, -1), _FONTB),
    ]))
    story.append(tax_table)

    company_name = form16.part_a.employer_name or "Employer"
    for elem in _signature_block(company_name, form16.part_a.employer_pan,
                                 form16.generated_on or datetime.now().strftime("%d-%m-%Y")):
        story.append(elem)

    note_style = ParagraphStyle("fn", fontName=_FONT, fontSize=7.5, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"Employee ID: {form16.employee_id}  |  "
        "This is a computer-generated Form 16.  |  Generated by Financial Audit AI",
        note_style
    ))

    wm_cb = _watermark_callback(company_name)
    doc.build(story, onFirstPage=wm_cb, onLaterPages=wm_cb)
    return buffer.getvalue()


def generate_gst_report_pdf(gstr1: GSTR1Summary) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm
    )
    styles = getSampleStyleSheet()
    story = []

    header_data = [[Paragraph("GSTR-1 SUMMARY REPORT", _header_style(14))]]
    header_table = Table(header_data, colWidths=[17.5 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)

    meta_data = [
        ["GSTIN", gstr1.gstin, "Trade Name", gstr1.trade_name],
        ["Financial Year", gstr1.financial_year, "Period", gstr1.period],
        ["Total Invoices", str(gstr1.invoice_count), "Total Taxable Value", f"{_RUPEE} {gstr1.total_taxable_value:,.2f}"],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, 5 * cm, 4 * cm, 4.5 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
        ("FONTNAME", (0, 0), (0, -1), _FONTB),
        ("FONTNAME", (2, 0), (2, -1), _FONTB),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(meta_table)
    story.append(Spacer(1, 0.3 * cm))

    tax_summary_data = [
        [Paragraph("TAX SUMMARY", _header_style(9, color=NAVY)), "", "", "", ""],
        [
            Paragraph("Total Taxable Value", _cell_style(9, True)),
            Paragraph("CGST", _cell_style(9, True)),
            Paragraph("SGST/UTGST", _cell_style(9, True)),
            Paragraph("IGST", _cell_style(9, True)),
            Paragraph("Total Tax", _cell_style(9, True)),
        ],
        [
            f"{_RUPEE} {gstr1.total_taxable_value:,.2f}",
            f"{_RUPEE} {gstr1.total_cgst:,.2f}",
            f"{_RUPEE} {gstr1.total_sgst:,.2f}",
            f"{_RUPEE} {gstr1.total_igst:,.2f}",
            Paragraph(f"{_RUPEE} {gstr1.total_tax:,.2f}", ParagraphStyle("t", fontName=_FONTB, fontSize=9, textColor=NAVY)),
        ],
    ]
    tax_summary_table = Table(tax_summary_data, colWidths=[3.5 * cm] * 5)
    tax_summary_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GRAY),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tax_summary_table)

    if gstr1.b2b:
        story.append(Spacer(1, 0.3 * cm))
        b2b_title = Table(
            [[Paragraph("B2B INVOICES (Business to Business)", _header_style(9))]],
            colWidths=[17.5 * cm]
        )
        b2b_title.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2E86AB")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(b2b_title)

        b2b_rows = [["GSTIN", "Party Name", "Invoices", "Taxable Value", "CGST", "SGST", "IGST"]]
        for entry in gstr1.b2b[:20]:
            b2b_rows.append([
                entry.get("gstin", ""),
                entry.get("party_name", "")[:20],
                str(len(entry.get("invoices", []))),
                f"{_RUPEE}{entry.get('total_taxable_value', 0):,.0f}",
                f"{_RUPEE}{entry.get('total_cgst', 0):,.0f}",
                f"{_RUPEE}{entry.get('total_sgst', 0):,.0f}",
                f"{_RUPEE}{entry.get('total_igst', 0):,.0f}",
            ])

        b2b_table = Table(b2b_rows, colWidths=[3.5 * cm, 3 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2 * cm])
        b2b_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
            ("FONTNAME", (0, 0), (-1, 0), _FONTB),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(b2b_table)

    company_name = gstr1.trade_name or "Company"
    for elem in _signature_block(company_name, gstr1.gstin):
        story.append(elem)

    note_style = ParagraphStyle("fn", fontName=_FONT, fontSize=7.5, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}  |  Financial Audit AI",
        note_style
    ))

    wm_cb = _watermark_callback(company_name)
    doc.build(story, onFirstPage=wm_cb, onLaterPages=wm_cb)
    return buffer.getvalue()


def generate_ledger_report_pdf(summary: dict, anomalies: list, company_name: str = "Financial Audit AI") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm
    )
    story = []

    header_data = [[Paragraph("ACCOUNTING LEDGER AUDIT REPORT", _header_style(14))]]
    header_table = Table(header_data, colWidths=[17.5 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3 * cm))

    metrics = [
        ["Total Entries", str(summary.get("total_entries", 0))],
        ["Total Debit", f"{_RUPEE} {summary.get('total_debit', 0):,.2f}"],
        ["Total Credit", f"{_RUPEE} {summary.get('total_credit', 0):,.2f}"],
        ["Net Balance", f"{_RUPEE} {summary.get('net_balance', 0):,.2f}"],
        ["Anomalies Found", str(len(anomalies))],
    ]
    metrics_table = Table(metrics, colWidths=[8 * cm, 9.5 * cm])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("FONTNAME", (0, 0), (0, -1), _FONTB),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(metrics_table)

    if anomalies:
        story.append(Spacer(1, 0.3 * cm))
        anomaly_header = Table(
            [[Paragraph("ANOMALIES DETECTED", _header_style(10))]],
            colWidths=[17.5 * cm]
        )
        anomaly_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), RED),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(anomaly_header)

        anomaly_rows = [["#", "Voucher No", "Type", "Description", "Severity"]]
        for i, a in enumerate(anomalies[:50], 1):
            anomaly_rows.append([
                str(i),
                a.get("voucher_no", ""),
                a.get("anomaly_type", ""),
                a.get("description", "")[:50],
                a.get("severity", "Medium"),
            ])

        anomaly_table = Table(anomaly_rows, colWidths=[1 * cm, 3 * cm, 3.5 * cm, 7.5 * cm, 2.5 * cm])
        anomaly_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
            ("FONTNAME", (0, 0), (-1, 0), _FONTB),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(anomaly_table)

    for elem in _signature_block(company_name):
        story.append(elem)

    note_style = ParagraphStyle("fn", fontName=_FONT, fontSize=7.5, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Report generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}  |  Financial Audit AI",
        note_style
    ))

    wm_cb = _watermark_callback(company_name)
    doc.build(story, onFirstPage=wm_cb, onLaterPages=wm_cb)
    return buffer.getvalue()
