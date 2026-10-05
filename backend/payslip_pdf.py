"""BluBridge payslip PDF generator — matches the standard BluBridge format
(header · info-box · earnings/deductions grid · perquisites/other-deductions grid
· net-pay-in-words · footer note)."""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image


def _fmt_dmy(v):
    """Format any ISO / date-like value as DD-MM-YYYY. Empty → '-'."""
    if not v:
        return "-"
    s = str(v)
    # Fast path: ISO YYYY-MM-DD prefix
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}-{s[5:7]}-{s[0:4]}"
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.strftime("%d-%m-%Y")
    except Exception:
        return s

_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "public", "logo.png")
_LOGO_PATH = os.path.normpath(_LOGO_PATH)

BLACK = colors.black
BORDER = colors.HexColor("#000000")
LIGHT_BG = colors.HexColor("#f5f5f5")

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n):
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n):
    if n >= 100:
        s = _ONES[n // 100] + " Hundred"
        if n % 100:
            s += " and " + _two(n % 100)
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
    return " ".join(parts) + " Rupees Only."


def _int_amt(v):
    """Whole-rupee integer formatting with Indian comma grouping (e.g. 20,581)."""
    n = int(round(float(v or 0)))
    s = str(abs(n))
    if len(s) <= 3:
        formatted = s
    else:
        tail = s[-3:]
        head = s[:-3]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        formatted = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + formatted


def build_payslip_pdf(slip: dict) -> bytes:
    emp = slip.get("employee", {})
    calc = slip.get("calc", {})
    month = slip.get("month", "")
    month_label = datetime(int(month[:4]), int(month[5:7]), 1).strftime("%B %Y") if month else ""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    W = A4[0] - 24 * mm

    # ---- Styles ----
    logo_style = ParagraphStyle("logo", fontName="Helvetica-Bold", fontSize=28, textColor=BLACK,
                                alignment=TA_LEFT, leading=30)
    title_style = ParagraphStyle("title", fontName="Helvetica", fontSize=13, textColor=BLACK,
                                 alignment=TA_RIGHT, leading=16)
    hdr_cell_b = ParagraphStyle("hcb", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, leading=13)
    hdr_cell = ParagraphStyle("hc", fontName="Helvetica", fontSize=9, alignment=TA_CENTER, leading=12)
    lbl_b = ParagraphStyle("lbb", fontName="Helvetica-Bold", fontSize=9, alignment=TA_LEFT, leading=12)
    val_l = ParagraphStyle("vl", fontName="Helvetica", fontSize=9, alignment=TA_LEFT, leading=12)
    val_r = ParagraphStyle("vr", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT, leading=12)
    val_r_b = ParagraphStyle("vrb", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT, leading=12)
    small = ParagraphStyle("sm", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#333333"), leading=11)
    words_style = ParagraphStyle("words", fontName="Helvetica-Bold", fontSize=10, alignment=TA_LEFT, leading=13)
    words_lbl = ParagraphStyle("wlbl", fontName="Helvetica-Bold", fontSize=9, alignment=TA_LEFT)

    story = []

    # ---- 1) Header: Logo (left) + Title (right) ----
    if os.path.exists(_LOGO_PATH):
        # Original logo is 246x33 px (7.45:1 ratio). Render ~52mm wide keeping aspect ratio.
        logo_w = 52 * mm
        logo_h = logo_w * 33.0 / 246.0
        logo = Image(_LOGO_PATH, width=logo_w, height=logo_h)
        logo.hAlign = "LEFT"
    else:
        logo = Paragraph('Blu<font color="#000000">B</font>ridge', logo_style)
    title = Paragraph(f"Payslip for {month_label}", title_style)
    hdr = Table([[logo, title]], colWidths=[W * 0.5, W * 0.5])
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [hdr, Spacer(1, 5 * mm)]

    # ---- 2) Info block: Company | Employee | Summary ----
    company_name = "Blubridge Technologies Pvt Ltd"
    company_addr = "Plot #E160 Tiger Varadhachari Road,<br/>Kalashetra Colony, Besant Nagar, Chennai-600090"

    net_rounded = int(round(calc.get("net_pay_rounded") if calc.get("net_pay_rounded") is not None else calc.get("net_pay", 0)))
    monthly_pay = int(round(calc.get("monthly_pay", 0)))
    annual_pay = monthly_pay * 12
    payable_days = calc.get("payable_days", 0)
    cal_days = calc.get("calendar_days", 0)

    company_cell = [
        Paragraph("<b>Company</b>", hdr_cell_b),
        Spacer(1, 2 * mm),
        Paragraph(company_name, hdr_cell),
        Paragraph(company_addr, hdr_cell),
    ]
    employee_cell = [
        Paragraph("<b>Employee</b>", hdr_cell_b),
        Spacer(1, 2 * mm),
        Paragraph(emp.get("full_name") or "-", hdr_cell),
        Paragraph(f"Code: {emp.get('custom_employee_id') or '-'}", hdr_cell),
        Paragraph(f"Desg: {emp.get('designation') or '-'}", hdr_cell),
        Paragraph(f"DOJ: {_fmt_dmy(emp.get('date_of_joining'))}", hdr_cell),
    ]
    def _fmt_days(d):
        try:
            return f"{float(d):.2f}"
        except Exception:
            return str(d)
    summary_cell = [
        Paragraph("<b>Summary</b>", hdr_cell_b),
        Spacer(1, 2 * mm),
        Paragraph(f"Net Salary: {_int_amt(net_rounded)}", hdr_cell),
        Paragraph(f"Gross/Actual CTC : {_int_amt(monthly_pay)}/{_int_amt(annual_pay)}", hdr_cell),
        Paragraph(f"Paid / Total Days : {_fmt_days(payable_days)}/{_fmt_days(cal_days)}", hdr_cell),
    ]

    info_tbl = Table([[company_cell, employee_cell, summary_cell]], colWidths=[W * 0.36, W * 0.30, W * 0.34])
    info_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [info_tbl, Spacer(1, 5 * mm)]

    # ---- 3) Earnings (left) + Deductions (right) ----
    # Earning rows: template split components (add, non-extra_pay).
    earnings = [c for c in calc.get("components", []) if c.get("operation") == "add"
                and c.get("calc_type") != "payroll_extra_pay"]
    # Deduction rows: from computed components (PF, Gratuity) + fixed Professional Tax = 0.
    ded_components = [c for c in calc.get("components", []) if c.get("operation") == "deduct"]
    pf_comp = next((c for c in ded_components if "pf" in (c.get("name") or "").lower()
                    or "provident" in (c.get("name") or "").lower()), None)
    gr_comp = next((c for c in ded_components if "gratuity" in (c.get("name") or "").lower()), None)
    other_deds = [c for c in ded_components if c is not pf_comp and c is not gr_comp]

    ded_rows = [
        ("PF Contribution", pf_comp.get("amount") if pf_comp else 0),
        ("Professional Tax", 0),
        ("Gratuity", gr_comp.get("amount") if gr_comp else 0),
        ("Other Deductions", sum((c.get("amount") or 0) for c in other_deds)),
    ]

    total_a = sum((c.get("amount") or 0) for c in earnings)
    total_b = sum(v for _, v in ded_rows)
    net_ab = total_a - total_b + (calc.get("other_allowance") or 0) - 0  # note: perquisites row below adds extra_pay separately

    # Pad earnings to at least len(ded_rows) rows for alignment
    n_rows = max(len(earnings), len(ded_rows))
    earning_padded = earnings + [None] * (n_rows - len(earnings))
    ded_padded = list(ded_rows) + [None] * (n_rows - len(ded_rows))

    # Build split table body:
    grid = [[Paragraph("<b>Earnings</b>", lbl_b), Paragraph("<b>Amount</b>", val_r_b),
             Paragraph("<b>Deductions</b>", lbl_b), Paragraph("<b>Amount</b>", val_r_b)]]
    for i in range(n_rows):
        e = earning_padded[i]
        d = ded_padded[i]
        left_name = Paragraph(e.get("name"), val_l) if e else ""
        left_amt = Paragraph(_int_amt(e.get("amount") or 0), val_r) if e else ""
        right_name = Paragraph(d[0], val_l) if d else ""
        right_amt = Paragraph(_int_amt(d[1]), val_r) if d else ""
        grid.append([left_name, left_amt, right_name, right_amt])
    grid.append([Paragraph("<b>Total - (A)</b>", lbl_b), Paragraph(f"<b>{_int_amt(total_a)}</b>", val_r_b),
                 Paragraph("<b>Total - (B)</b>", lbl_b), Paragraph(f"<b>{_int_amt(total_b)}</b>", val_r_b)])
    # Net Pay (A-B) row — spans only the LEFT half in the reference layout
    net_ab_display = total_a - total_b
    grid.append([Paragraph("<b>Net Pay ( A - B )</b>", ParagraphStyle("nab", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER)),
                 Paragraph(f"<b>{_int_amt(net_ab_display)}</b>", val_r_b), "", ""])

    grid_tbl = Table(grid, colWidths=[W * 0.30, W * 0.20, W * 0.30, W * 0.20])
    grid_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (1, -2), 0.75, BORDER),           # left box (Earnings + Total(A) + NetPay row)
        ("BOX", (2, 0), (3, -3), 0.75, BORDER),           # right box (Deductions + Total(B))
        ("INNERGRID", (0, 0), (1, -2), 0.4, BORDER),
        ("INNERGRID", (2, 0), (3, -3), 0.4, BORDER),
        ("BACKGROUND", (0, -1), (1, -1), LIGHT_BG),       # Net Pay row background
        ("BACKGROUND", (0, -2), (-1, -2), LIGHT_BG),      # Totals row background
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [grid_tbl, Spacer(1, 4 * mm)]

    # ---- 4) Other Perquisites (left) + Other Deductions (right) ----
    extra_pay = calc.get("other_allowance") or 0
    manual_add = float(calc.get("manual_additions_total") or 0)
    manual_ded = float(calc.get("manual_deductions_total") or 0)
    perquisite_rows = [
        ("Other Allowance", manual_add),
        ("Additional Pay on weekends", extra_pay),
    ]
    net_payment = int(round(net_ab_display + extra_pay + manual_add - manual_ded))

    perq_grid = [[Paragraph("<b>Other Perquisites</b>", lbl_b), Paragraph("<b>Amount</b>", val_r_b),
                  Paragraph("<b>Other Deductions</b>", lbl_b), Paragraph("<b>Amount</b>", val_r_b)]]
    for i, (nm, val) in enumerate(perquisite_rows):
        right_name = Paragraph("Other Deductions", val_l) if i == 0 else ""
        right_amt = Paragraph(_int_amt(manual_ded), val_r) if i == 0 else ""
        perq_grid.append([Paragraph(nm, val_l), Paragraph(_int_amt(val), val_r), right_name, right_amt])
    # Final "Net Payment in Rupees" row (spans left half)
    perq_grid.append([Paragraph("<b>Net Payment in Rupees</b>", ParagraphStyle("npr", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER)),
                      Paragraph(f"<b>{_int_amt(net_payment)}</b>", val_r_b), "", ""])
    perq_tbl = Table(perq_grid, colWidths=[W * 0.30, W * 0.20, W * 0.30, W * 0.20])
    perq_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (1, -1), 0.75, BORDER),
        ("BOX", (2, 0), (3, -2), 0.75, BORDER),
        ("INNERGRID", (0, 0), (1, -1), 0.4, BORDER),
        ("INNERGRID", (2, 0), (3, -2), 0.4, BORDER),
        ("BACKGROUND", (0, -1), (1, -1), LIGHT_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [perq_tbl, Spacer(1, 6 * mm)]

    # ---- 5) Net Pay in Words ----
    words_row = Table([[Paragraph("Net Pay In Words :", words_lbl),
                        Paragraph(amount_in_words(net_payment), words_style)]],
                      colWidths=[W * 0.22, W * 0.78])
    words_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [words_row, Spacer(1, 8 * mm)]

    # ---- 6) Footer note ----
    story += [Paragraph("<b>Note</b> : This is a system generated payslip hence signature is not required.", small)]

    doc.build(story)
    return buf.getvalue()
