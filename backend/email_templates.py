"""Centralized HRMS email template system — ONE base template, all emails reuse it.

Premium enterprise look: BluBridge branding, mobile-responsive, CTA buttons,
personalization, footer.
"""
from datetime import datetime

BRAND_PRIMARY = "#063c88"
BRAND_ACCENT = "#f59e0b"
BG = "#fffdf7"
CARD_BG = "#ffffff"
BORDER = "#e5e7eb"
TEXT = "#0f172a"
MUTED = "#64748b"
GOOD = "#10b981"
BAD = "#ef4444"


def _footer_html() -> str:
    year = datetime.now().year
    return f"""
    <tr>
      <td style="padding:24px 32px;background:{BRAND_PRIMARY};color:#dbe5f3;font-family:Arial,Helvetica,sans-serif;font-size:12px;text-align:center;border-radius:0 0 12px 12px;">
        <div style="font-weight:700;letter-spacing:2px;color:#fff;font-size:16px;margin-bottom:6px;">BluBridge HRMS</div>
        <div>Enterprise-grade HR &amp; Attendance Platform</div>
        <div style="margin-top:10px;color:#9db4d4;">© {year} BluBridge. This is an automated notification — please do not reply.</div>
      </td>
    </tr>
    """


def base_email_template(
    *,
    title: str,
    greeting: str,
    intro_html: str,
    body_html: str = "",
    cta: list | None = None,
    accent: str = BRAND_PRIMARY,
) -> str:
    """Wrap any content in the standard HRMS shell.

    cta: list of dicts {"label": str, "url": str, "style": "primary"|"secondary"}
    """
    buttons_html = ""
    if cta:
        btns = []
        for b in cta:
            is_primary = b.get("style", "primary") == "primary"
            bg = accent if is_primary else "#ffffff"
            color = "#ffffff" if is_primary else accent
            border = f"2px solid {accent}"
            btns.append(
                f'<a href="{b["url"]}" target="_blank" style="display:inline-block;padding:12px 28px;margin:6px;background:{bg};color:{color};text-decoration:none;border-radius:8px;font-weight:600;font-family:Arial,Helvetica,sans-serif;font-size:14px;border:{border};">{b["label"]}</a>'
            )
        buttons_html = f'<div style="text-align:center;margin:28px 0 8px 0;">{"".join(btns)}</div>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:{BG};font-family:Arial,Helvetica,sans-serif;color:{TEXT};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:28px 12px;">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;overflow:hidden;">
      <tr>
        <td style="padding:28px 32px;background:linear-gradient(135deg,{BRAND_PRIMARY} 0%, #0a56c2 100%);color:#fff;">
          <div style="font-weight:700;letter-spacing:3px;font-size:20px;">BLU<span style="color:{BRAND_ACCENT};">B</span>RIDGE</div>
          <div style="font-size:12px;color:#c9d6ea;letter-spacing:2px;margin-top:2px;">HRMS PLATFORM</div>
        </td>
      </tr>
      <tr>
        <td style="padding:32px;">
          <h1 style="margin:0 0 8px 0;color:{TEXT};font-size:22px;font-weight:700;">{title}</h1>
          <p style="margin:0 0 18px 0;color:{MUTED};font-size:14px;">{greeting}</p>
          <div style="color:{TEXT};font-size:14px;line-height:1.6;">{intro_html}</div>
          {body_html}
          {buttons_html}
        </td>
      </tr>
      {_footer_html()}
    </table>
    <div style="max-width:600px;margin:16px auto 0;color:{MUTED};font-size:11px;text-align:center;font-family:Arial,Helvetica,sans-serif;">
      Generated at {datetime.now().strftime('%d-%m-%Y %H:%M')} IST
    </div>
  </td></tr>
</table>
</body></html>"""


# ---------- Stat card helper used by admin summary ---------------------------
def stat_card(label: str, value, color: str = BRAND_PRIMARY) -> str:
    return f"""
    <td style="padding:10px;">
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px;text-align:center;">
        <div style="color:{color};font-size:28px;font-weight:700;line-height:1;">{value}</div>
        <div style="color:{MUTED};font-size:12px;margin-top:6px;letter-spacing:.5px;">{label}</div>
      </div>
    </td>
    """


def stat_grid(cells: list[str]) -> str:
    """Build a responsive 3-col grid of stat_card()s."""
    rows_html = []
    for i in range(0, len(cells), 3):
        row = cells[i:i + 3]
        while len(row) < 3:
            row.append('<td style="padding:10px;"></td>')
        rows_html.append("<tr>" + "".join(row) + "</tr>")
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;">{"".join(rows_html)}</table>'


def simple_table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return f'<p style="color:{MUTED};font-size:13px;">No records.</p>'
    th = "".join(
        f'<th style="padding:10px 12px;text-align:left;background:#f1f5f9;color:{TEXT};font-size:12px;border-bottom:1px solid {BORDER};">{h}</th>'
        for h in headers
    )
    tr_html = []
    for r in rows:
        tds = "".join(
            f'<td style="padding:10px 12px;font-size:13px;color:{TEXT};border-bottom:1px solid {BORDER};">{c}</td>'
            for c in r
        )
        tr_html.append(f"<tr>{tds}</tr>")
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {BORDER};border-radius:8px;overflow:hidden;margin:12px 0;">
      <thead><tr>{th}</tr></thead>
      <tbody>{"".join(tr_html)}</tbody>
    </table>
    """


# ---------- Colored section helper (used by detailed admin summary) ----------
def _section_header(title: str, count: int, color: str) -> str:
    return (
        f'<div style="margin:22px 0 8px 0;padding:10px 14px;border-left:4px solid {color};'
        f'background:{color}15;border-radius:4px;">'
        f'<span style="font-size:15px;font-weight:700;color:{color};">{title}</span>'
        f'<span style="font-size:13px;color:{MUTED};margin-left:10px;">({count})</span>'
        f'</div>'
    )


def _colored_table(headers: list, rows: list, color: str, empty_msg: str = "No records.") -> str:
    """Like simple_table but with a colored header band matching the section."""
    if not rows:
        return f'<p style="color:{MUTED};font-size:13px;margin:6px 0 0 14px;">{empty_msg}</p>'
    th = "".join(
        f'<th style="padding:10px 12px;text-align:left;background:{color}12;color:{color};'
        f'font-size:12px;border-bottom:2px solid {color};font-weight:700;">{h}</th>'
        for h in headers
    )
    tr_html = []
    for idx, r in enumerate(rows):
        bg = "#ffffff" if idx % 2 == 0 else "#fafafa"
        tds = "".join(
            f'<td style="padding:9px 12px;font-size:13px;color:{TEXT};border-bottom:1px solid {BORDER};">{c}</td>'
            for c in r
        )
        tr_html.append(f'<tr style="background:{bg};">{tds}</tr>')
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid {BORDER};border-radius:8px;overflow:hidden;margin:4px 0 0 0;">'
        f'<thead><tr>{th}</tr></thead>'
        f'<tbody>{"".join(tr_html)}</tbody>'
        f'</table>'
    )


def admin_summary_email_detailed(
    *,
    date_str: str,
    logged_in_rows: list,
    late_login_rows: list,
    not_logged_rows: list,
    on_leave_rows: list,
) -> str:
    """Employee-wise detailed daily attendance report.

    Shows FULL LISTS (not counts) across 4 colored sections:
      • Logged In (green) — Name, Login Time
      • Late Logins (orange) — Name, Login Time, Late Duration
      • Not Logged In (red) — Name
      • On Leave (blue) — Name, Date, Leave Type, Status, Reason
    """
    GREEN = "#10b981"
    ORANGE = "#f59e0b"
    RED = "#ef4444"
    BLUE = "#0ea5e9"

    intro = (
        f'Detailed attendance snapshot for <b>{date_str}</b>. '
        f'Employee-level breakdown across 4 mutually-exclusive sections below.'
    )

    body = (
        _section_header("Logged In", len(logged_in_rows), GREEN)
        + _colored_table(
            ["Employee Name", "Login Time"],
            logged_in_rows,
            GREEN,
            empty_msg="No employees logged in yet.",
        )
        + _section_header("Late Login", len(late_login_rows), ORANGE)
        + _colored_table(
            ["Employee Name", "Login Time", "Late Duration"],
            late_login_rows,
            ORANGE,
            empty_msg="No late logins.",
        )
        + _section_header("Not Logged In", len(not_logged_rows), RED)
        + _colored_table(
            ["Employee Name"],
            not_logged_rows,
            RED,
            empty_msg="All expected employees have logged in.",
        )
        + _section_header("On Leave", len(on_leave_rows), BLUE)
        + _colored_table(
            ["Employee Name", "Date", "Leave Type", "Status", "Reason"],
            on_leave_rows,
            BLUE,
            empty_msg="No employees on leave.",
        )
    )

    return base_email_template(
        title=f"Daily Attendance Report — {date_str}",
        greeting="Hi HR team,",
        intro_html=intro,
        body_html=body,
    )


# ---------- Specific email generators ---------------------------------------
def admin_summary_email(summary: dict, dept_rows: list, shift_rows: list, top_delayed: list, date_str: str) -> str:
    cells = [
        stat_card("Total Employees", summary.get("total_employees", 0)),
        stat_card("Logged In", summary.get("logged_in", 0), GOOD),
        stat_card("Present", summary.get("present", 0), GOOD),
        stat_card("Not Logged / Leaves", summary.get("not_logged", 0), BRAND_ACCENT),
        stat_card("Late Logins", summary.get("late_login", 0), "#8b5cf6"),
        stat_card("Early Out", summary.get("early_out", 0), BAD),
        stat_card("Half Day", summary.get("half_day", 0), BRAND_ACCENT),
        stat_card("Missed Punch", summary.get("missed_punch", 0), BAD),
        stat_card("On Leave", summary.get("on_leave", 0), "#0891b2"),
    ]
    attendance_pct = summary.get("attendance_pct", 0)
    intro = (
        f'Today\'s attendance snapshot for <b>{date_str}</b>. '
        f'Overall attendance is <b style="color:{GOOD};">{attendance_pct}%</b>.'
    )
    body = (
        '<h3 style="margin:20px 0 6px;font-size:15px;">Summary</h3>'
        + stat_grid(cells)
        + '<h3 style="margin:20px 0 6px;font-size:15px;">Department-wise</h3>'
        + simple_table(
            ["Department", "Total", "Present", "Leave", "Late", "Absent"],
            dept_rows,
        )
        + '<h3 style="margin:20px 0 6px;font-size:15px;">Shift-wise</h3>'
        + simple_table(["Shift", "Total", "Logged In", "Not Logged"], shift_rows)
        + '<h3 style="margin:20px 0 6px;font-size:15px;">Top Delayed Employees</h3>'
        + simple_table(["Employee", "Team", "Check-in", "Late By"], top_delayed)
    )
    return base_email_template(
        title=f"Daily Attendance Report — {date_str}",
        greeting="Hi HR team,",
        intro_html=intro,
        body_html=body,
    )


def late_login_email(emp_name: str, shift_start: str, punch_time: str, late_by_mins: int, action_url: str) -> str:
    intro = (
        f'Our system has detected that you clocked in late today. '
        f'You are late by <b style="color:{BAD};">{late_by_mins} minute(s)</b> from your assigned shift.'
    )
    body = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;border:1px solid {BORDER};border-radius:10px;">
        <tr><td style="padding:14px 18px;border-bottom:1px solid {BORDER};"><b>Shift Start Time:</b> {shift_start}</td></tr>
        <tr><td style="padding:14px 18px;border-bottom:1px solid {BORDER};"><b>Actual Punch Time:</b> {punch_time}</td></tr>
        <tr><td style="padding:14px 18px;"><b>Late Duration:</b> <span style="color:{BAD};">{late_by_mins} min</span></td></tr>
      </table>
      <p style="color:{MUTED};font-size:13px;">If this was due to a genuine reason, please raise a late request with proper justification.</p>
    """
    return base_email_template(
        title="Late Login Notification",
        greeting=f"Hi {emp_name},",
        intro_html=intro,
        body_html=body,
        cta=[{"label": "Raise Late Request", "url": action_url, "style": "primary"}],
    )


def missed_punch_email(emp_name: str, date_str: str, missing: str, action_url: str) -> str:
    intro = (
        f'During yesterday\'s attendance audit for <b>{date_str}</b>, we found a missing punch '
        f'on your record — <b style="color:{BAD};">Missing {missing}</b>. '
        f'Please regularize this at the earliest.'
    )
    return base_email_template(
        title="Missing Punch Detected",
        greeting=f"Hi {emp_name},",
        intro_html=intro,
        cta=[{"label": "Apply Missed Punch Request", "url": action_url, "style": "primary"}],
    )


def early_out_email(emp_name: str, date_str: str, worked: str, expected: str, action_url: str) -> str:
    intro = (
        f'Your attendance for <b>{date_str}</b> shows working hours <b style="color:{BAD};">{worked}</b> '
        f'against the expected <b>{expected}</b> for your shift. Please raise an attendance request if this was planned.'
    )
    return base_email_template(
        title="Early Out Detected",
        greeting=f"Hi {emp_name},",
        intro_html=intro,
        cta=[{"label": "Raise Attendance Request", "url": action_url, "style": "primary"}],
    )


def no_login_email(emp_name: str, date_str: str, leave_url: str, missed_punch_url: str) -> str:
    intro = (
        f'No attendance punches were recorded for you on <b>{date_str}</b>. '
        'If you were absent, please apply for leave. If you forgot your biometric punches, '
        'please raise a missed punch request instead.'
    )
    return base_email_template(
        title="No Attendance Recorded",
        greeting=f"Hi {emp_name},",
        intro_html=intro,
        cta=[
            {"label": "Apply Leave", "url": leave_url, "style": "primary"},
            {"label": "Apply Missed Punch", "url": missed_punch_url, "style": "secondary"},
        ],
    )



def password_reset_email(emp_name: str, reset_url: str, expires_minutes: int = 30) -> str:
    """Self-service password reset email — sent ONLY to the registered email."""
    intro = (
        f'We received a request to reset your BluBridge HRMS account password. '
        f'Click the button below to choose a new password. '
        f'This link will expire in <b>{expires_minutes} minutes</b> and can only be used once.'
    )
    body = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0;border:1px solid {BORDER};border-radius:10px;background:#f8fafc;">
        <tr><td style="padding:14px 18px;font-size:13px;color:{MUTED};">
          <b style="color:{TEXT};">Didn't request this?</b> You can safely ignore this email — your password will remain unchanged. For security, the reset link expires in {expires_minutes} minutes.
        </td></tr>
      </table>
      <p style="color:{MUTED};font-size:12px;margin:18px 0 0 0;">If the button above doesn't work, copy and paste this link into your browser:</p>
      <p style="word-break:break-all;font-size:12px;color:{BRAND_PRIMARY};margin:6px 0 0 0;">{reset_url}</p>
    """
    return base_email_template(
        title="Reset Your Password",
        greeting=f"Hi {emp_name},",
        intro_html=intro,
        body_html=body,
        cta=[{"label": "Reset Password", "url": reset_url, "style": "primary"}],
    )



def onboarding_reminder_email(
    *,
    employee_name: str,
    overall_percent: int,
    onboarding_percent: int,
    profile_photo_uploaded: bool,
    missing_sections: list,
    cta_url: str,
) -> str:
    """Reminder email — sent every 48 hours until both onboarding & photo
    reach 100%. Premium, mobile-responsive, action-oriented."""
    first_name = (employee_name or "there").split()[0]

    bar_color = GOOD if overall_percent >= 75 else (BRAND_ACCENT if overall_percent >= 40 else BAD)

    missing_html = ""
    if missing_sections or not profile_photo_uploaded:
        items = []
        if not profile_photo_uploaded:
            items.append(
                f"<li style=\"padding:6px 0;color:{TEXT};font-size:14px;\">"
                f"<b style=\"color:{BAD};\">·</b> Profile photo — not uploaded yet"
                f"</li>"
            )
        for m in (missing_sections or []):
            items.append(
                f"<li style=\"padding:6px 0;color:{TEXT};font-size:14px;\">"
                f"<b style=\"color:{BAD};\">·</b> {m.get('label')}"
                f"</li>"
            )
        missing_html = (
            f"<div style=\"margin:18px 0;padding:18px;border:1px solid {BORDER};"
            f"border-left:4px solid {BAD};border-radius:10px;background:#fff8f8;\">"
            f"<div style=\"font-size:13px;font-weight:700;color:{BAD};letter-spacing:.5px;text-transform:uppercase;margin-bottom:8px;\">"
            f"Still pending</div>"
            f"<ul style=\"margin:0;padding:0;list-style:none;\">{''.join(items)}</ul>"
            f"</div>"
        )

    progress_html = f"""
      <div style="margin:8px 0 18px 0;">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:{MUTED};margin-bottom:6px;">
          <span>Overall completion</span><span style="font-weight:700;color:{TEXT};">{overall_percent}%</span>
        </div>
        <div style="height:10px;border-radius:999px;background:#eef2f7;overflow:hidden;">
          <div style="width:{overall_percent}%;height:10px;background:{bar_color};border-radius:999px;"></div>
        </div>
        <div style="margin-top:10px;font-size:12px;color:{MUTED};">
          Onboarding documents: <b style="color:{TEXT};">{onboarding_percent}%</b>
          &nbsp;·&nbsp;
          Profile photo: <b style="color:{TEXT};">{'Uploaded' if profile_photo_uploaded else 'Not uploaded'}</b>
        </div>
      </div>
    """

    intro = (
        "This is a friendly reminder to finish setting up your BluBridge HRMS profile. "
        "It only takes a few minutes and unlocks the full HRMS experience for you — attendance, "
        "leave, payroll, and more."
    )

    body = progress_html + missing_html + f"""
      <p style="color:{MUTED};font-size:13px;line-height:1.6;margin:12px 0 0 0;">
        You'll continue to receive a reminder every 48 hours until you complete onboarding
        and upload your profile picture. Once you're done, the reminders stop and you'll
        receive a quick confirmation email.
      </p>
    """

    return base_email_template(
        title="Complete Your BluBridge Profile",
        greeting=f"Hi {first_name},",
        intro_html=intro,
        body_html=body,
        cta=[{"label": "Complete Now", "url": cta_url, "style": "primary"}],
        accent=BRAND_PRIMARY,
    )


def onboarding_success_email(*, employee_name: str) -> str:
    """One-time congratulations email — sent ONLY after both onboarding (100%)
    and profile photo (uploaded) are complete."""
    first_name = (employee_name or "there").split()[0]

    intro = (
        "Congratulations — your BluBridge HRMS profile is now <b>100% complete</b>. "
        "All onboarding documents are in place and your profile picture is live across "
        "the platform."
    )

    body = f"""
      <div style="margin:20px 0;padding:24px;border-radius:14px;background:linear-gradient(135deg,#dcfce7 0%,#bbf7d0 100%);border:1px solid #86efac;text-align:center;">
        <div style="font-size:42px;line-height:1;margin-bottom:6px;">✅</div>
        <div style="font-size:18px;font-weight:700;color:{TEXT};margin-bottom:4px;">All set!</div>
        <div style="font-size:13px;color:#166534;">Your profile is verified and visible across the HRMS.</div>
      </div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0 0 0;border:1px solid {BORDER};border-radius:12px;">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {BORDER};">
            <div style="font-size:12px;color:{MUTED};text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px;">Onboarding documents</div>
            <div style="font-size:14px;font-weight:700;color:{GOOD};">100% verified</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;">
            <div style="font-size:12px;color:{MUTED};text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px;">Profile picture</div>
            <div style="font-size:14px;font-weight:700;color:{GOOD};">Uploaded &amp; live</div>
          </td>
        </tr>
      </table>
      <p style="color:{MUTED};font-size:13px;line-height:1.7;margin:20px 0 0 0;">
        You'll no longer receive completion reminders — this is the final email of the
        onboarding sequence. If you ever need to update your photo or documents, head to
        your profile from the HRMS sidebar at any time.
      </p>
    """

    return base_email_template(
        title="🎉 Onboarding Complete",
        greeting=f"Hi {first_name},",
        intro_html=intro,
        body_html=body,
        accent=GOOD,
    )
