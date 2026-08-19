"""BluBridge payslip PDF generator (reportlab)."""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

NAVY = colors.HexColor("#1e3a5f")
LIGHT = colors.HexColor("#f1f5f9")
BORDER = colors.HexColor("#cbd5e1")

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n):
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n):
    s = ""
    if n >= 100:
        s = _ONES[n // 100] + " Hundred"
        if n % 100:
            s += " " + _two(n % 100)
        return s
    return _two(n)


def amount_in_words(amount):
    n = int(round(amount))
    if n == 0:
        return "Zero Rupees Only"
    parts = []
    crore, n = divmod(n, 10000000)
    lakh, n = divmod(n, 100000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(_two(crore) + " Crore")
    if lakh:
        parts.append(_two(lakh) + " Lakh")
    if thousand:
        parts.append(_two(thousand) + " Thousand")
    if n:
        parts.append(_three(n))
    return " ".join(parts) + " Rupees Only"


def _inr(v):
    return f"Rs. {float(v or 0):,.2f}"


def build_payslip_pdf(slip: dict) -> bytes:
    emp = slip.get("employee", {})
    calc = slip.get("calc", {})
    pmeta = slip.get("payroll_meta", {})
    month = slip.get("month", "")
    month_label = datetime(int(month[:4]), int(month[5:7]), 1).strftime("%B %Y") if month else ""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)
    W = A4[0] - 30 * mm
    company = ParagraphStyle("company", fontName="Helvetica-Bold", fontSize=17, textColor=NAVY, alignment=TA_CENTER)
    addr = ParagraphStyle("addr", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#475569"), alignment=TA_CENTER)
    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=12, textColor=colors.white, alignment=TA_CENTER)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER)
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=9)
    cell_b = ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=9)

    story = [
        Paragraph("BluBridge Technologies Pvt Ltd", company),
        Spacer(1, 2 * mm),
        Paragraph("Chennai, Tamil Nadu, India", addr),
        Spacer(1, 5 * mm),
    ]

    tt = Table([[Paragraph(f"PAYSLIP — {month_label.upper()}", title)]], colWidths=[W])
    tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [tt, Spacer(1, 5 * mm)]

    info = [
        ["Employee Name", emp.get("full_name") or "-", "Employee ID", emp.get("custom_employee_id") or "-"],
        ["Designation", emp.get("designation") or "-", "Department", emp.get("department") or "-"],
        ["Employee Type", emp.get("employment_type") or "-", "Date of Joining", emp.get("date_of_joining") or "-"],
        ["Calendar Days", str(calc.get("calendar_days", "-")), "Payable Days", str(calc.get("payable_days", "-"))],
        ["LOP Days", str(pmeta.get("lop", 0)), "Extra Pay Days", str(calc.get("extra_pay_days", 0))],
    ]
    info = [[Paragraph(str(r[0]), cell_b), Paragraph(str(r[1]), cell),
             Paragraph(str(r[2]), cell_b), Paragraph(str(r[3]), cell)] for r in info]
    it = Table(info, colWidths=[W * 0.22, W * 0.28, W * 0.22, W * 0.28])
    it.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT), ("BACKGROUND", (2, 0), (2, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [it, Spacer(1, 6 * mm)]

    earnings = [c for c in calc.get("components", []) if c.get("operation") == "add"]
    deductions = [c for c in calc.get("components", []) if c.get("operation") == "deduct"]
    if calc.get("other_allowance"):
        earnings.append({"name": "Other Allowance (Extra Pay)", "amount": calc["other_allowance"]})

    rows = [["EARNINGS", "AMOUNT", "DEDUCTIONS", "AMOUNT"]]
    for i in range(max(len(earnings), len(deductions), 1)):
        e = earnings[i] if i < len(earnings) else {}
        d = deductions[i] if i < len(deductions) else {}
        rows.append([e.get("name", ""), _inr(e["amount"]) if e else "",
                     d.get("name", ""), _inr(d["amount"]) if d else ""])
    rows.append(["Gross Earnings", _inr(calc.get("gross_earnings")), "Total Deductions", _inr(calc.get("total_deductions"))])

    ct = Table(rows, colWidths=[W * 0.30, W * 0.20, W * 0.30, W * 0.20])
    ct.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [ct, Spacer(1, 6 * mm)]

    net = calc.get("net_pay", 0)
    net_style = ParagraphStyle("net", fontName="Helvetica-Bold", fontSize=12, textColor=NAVY, alignment=TA_RIGHT)
    nt = Table([[Paragraph("NET PAY", ParagraphStyle("nl", fontName="Helvetica-Bold", fontSize=12, textColor=NAVY)),
                 Paragraph(_inr(net), net_style)]], colWidths=[W * 0.5, W * 0.5])
    nt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 1, NAVY),
                            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    words = ParagraphStyle("words", fontName="Helvetica-Oblique", fontSize=9, textColor=colors.HexColor("#334155"))
    story += [nt, Spacer(1, 3 * mm),
              Paragraph(f"Amount in words: {amount_in_words(net)}", words),
              Spacer(1, 10 * mm),
              Paragraph("This is a computer-generated payslip and does not require a signature.", small)]

    doc.build(story)
    return buf.getvalue()
