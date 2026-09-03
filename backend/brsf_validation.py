"""BRSF star-value validation — strict per-criterion limits.

Single source of truth for every entry point (manual monthly, manual weekly,
per-instance, parent override) and for flagging historical values that violate
the rules. Values are always WHOLE stars: nothing is silently clamped or
converted, invalid input is rejected with a criterion-specific message.
"""
import math

from fastapi import HTTPException

# code -> (child/entry allowed values, monthly-mode range, parent range mode)
FIXED_INSTANCE_STAR = {"N07": -3, "N08": -4}

# Criteria whose monthly parent value is a single all-or-nothing penalty.
MONTHLY_FIXED = {"N03": (0, -3), "N06": (0, -3)}

# Static parent ranges (min, max) for criteria that are not instance driven.
STATIC_PARENT_RANGE = {
    "P01": (0, 2), "P02": (0, 5), "P03": (0, 3), "P04": (0, 5), "P05": (0, 5),
}

# Per-child / per-entry allowed values.
CHILD_ALLOWED = {
    "P02": [0, 1], "P04": [0, 1], "P05": [0, 1], "P06": [0, 1],
    "N01": [0, -1], "N02": [0, -2], "N03": [0, -3], "N04": [0, -1],
    "N05": [0, -3], "N06": [0, -3], "N07": [-3], "N08": [-4],
}

# Star magnitude carried by ONE instance/week/sequence of an instance-driven rule.
PER_INSTANCE_MAGNITUDE = {"P06": 1, "N01": 1, "N02": 2, "N04": 1, "N05": 3,
                          "N07": 3, "N08": 4}

MESSAGES = {
    "P01": "Full Attendance stars must be between 0 and +2.",
    "P02_weekly": "Performance weekly stars can only be 0 or +1.",
    "P02_monthly": "Performance monthly stars must be between 0 and +5.",
    "P03": "Innovation stars must be between 0 and +3 per month.",
    "P04_weekly": "Learning weekly stars can only be 0 or +1.",
    "P04_monthly": "Learning monthly stars must be between 0 and +5.",
    "P05": "Research Attendance weekly stars can only be 0 or +1.",
    "P05_parent": "Research Attendance cannot exceed +5 stars per month.",
    "P06": "Extra Effort allows a maximum of +1 per qualifying worked date.",
    "N01": "Invalid Leave penalty can only be 0 or -1 per leave instance.",
    "N02": "Emergency Leave Violation can only be 0 or -2 per instance.",
    "N03": "Frequent Emergencies can only be 0 or -3 for the selected month.",
    "N04": "Short Research Duration can only be 0 or -1 per week.",
    "N05": "No Proof / Verification can only be 0 or -3 per consecutive leave sequence.",
    "N06": "Frequent Absences can only be 0 or -3 for the selected month.",
    "N07": "No Show / Unreachable carries a fixed -3 stars per incident.",
    "N08": "Unsafe Conduct carries a fixed -4 stars per incident.",
}


def _bad(message: str):
    raise HTTPException(status_code=400, detail=message)


def as_star_int(raw, label="Star value") -> int:
    """Whole-number star parser: rejects blanks, text, NaN/Infinity and decimals."""
    if raw is None or isinstance(raw, bool) or (isinstance(raw, str) and not raw.strip()):
        _bad(f"{label} is required and must be a whole number.")
    try:
        num = float(raw)
    except (TypeError, ValueError):
        _bad(f"{label} must be a whole number.")
    if math.isnan(num) or math.isinf(num):
        _bad(f"{label} must be a whole number.")
    if abs(num - round(num)) > 1e-9:
        _bad(f"{label} must be a whole number — fractional stars are not allowed.")
    return int(round(num))


def _child_count(line: dict) -> int:
    code = line["code"]
    if code in FIXED_INSTANCE_STAR:
        return len(line.get("instances") or [])
    return len(line.get("system_children") or [])


def parent_bounds(line: dict) -> dict:
    """Allowed parent (override / final) values for this line, given its children."""
    code, sign = line["code"], line["sign"]
    if code in MONTHLY_FIXED:
        return {"allowed": list(MONTHLY_FIXED[code]), "min": -3, "max": 0}
    if code in STATIC_PARENT_RANGE:
        lo, hi = STATIC_PARENT_RANGE[code]
        return {"allowed": None, "min": lo, "max": hi}
    # instance-driven: bounded by number of qualifying children × per-instance star
    span = _child_count(line) * PER_INSTANCE_MAGNITUDE.get(code, 1)
    return {"allowed": None, "min": 0 if sign > 0 else -span,
            "max": span if sign > 0 else 0}


def child_limits(line: dict) -> dict:
    """Allowed per-week / per-instance / per-sequence values for this line."""
    code = line["code"]
    return {"allowed": CHILD_ALLOWED.get(code),
            "fixed": FIXED_INSTANCE_STAR.get(code)}


def monthly_entry_range(line: dict) -> dict:
    """Range for the single monthly manual value (P02 / P03 / P04)."""
    lo, hi = STATIC_PARENT_RANGE.get(line["code"], (0, line.get("cap") or 0))
    return {"min": lo, "max": hi}


def limits_for(line: dict) -> dict:
    """Everything the UI needs to restrict its inputs for this criterion."""
    code = line["code"]
    msg_key = code if code in MESSAGES else None
    return {
        "parent": parent_bounds(line),
        "child": child_limits(line),
        "monthly": monthly_entry_range(line) if line["type"] == "manual" else None,
        "child_count": _child_count(line),
        "message": MESSAGES.get(msg_key or "", ""),
        "weekly_message": MESSAGES.get(f"{code}_weekly", MESSAGES.get(code, "")),
        "monthly_message": MESSAGES.get(f"{code}_monthly", MESSAGES.get(code, "")),
    }


def _sign_guard(line: dict, value: int):
    if line["sign"] > 0 and value < 0:
        _bad(f"{line['name']} is a positive criterion — a negative star value is not allowed.")
    if line["sign"] < 0 and value > 0:
        _bad(f"{line['name']} is a negative criterion — a positive star value is not allowed.")


def validate_override(line: dict, raw) -> int:
    """Parent-level override: whole number, correct sign, within criterion limits."""
    value = as_star_int(raw, f"{line['name']} override")
    _sign_guard(line, value)
    b = parent_bounds(line)
    if b["allowed"] is not None:
        if value not in b["allowed"]:
            _bad(MESSAGES.get(line["code"], "Value not allowed for this criteria."))
        return value
    if value < b["min"] or value > b["max"]:
        code = line["code"]
        if code in STATIC_PARENT_RANGE:
            _bad(MESSAGES.get(f"{code}_parent") or MESSAGES.get(code)
                 or f"Allowed range is {b['min']} to {b['max']}.")
        n = _child_count(line)
        _bad(f"{line['name']} allows {b['min']} to {b['max']} star(s) this month — "
             f"{n} qualifying record(s) × {PER_INSTANCE_MAGNITUDE.get(code, 1)} star.")
    return value


def validate_monthly_entry(line: dict, raw) -> int:
    value = as_star_int(raw, f"{line['name']} monthly stars")
    _sign_guard(line, value)
    r = monthly_entry_range(line)
    if value < r["min"] or value > r["max"]:
        _bad(MESSAGES.get(f"{line['code']}_monthly")
             or MESSAGES.get(line["code"], f"Allowed range is {r['min']} to {r['max']}."))
    return value


def validate_weekly_entries(line: dict, weekly: list) -> list:
    if not isinstance(weekly, list):
        _bad("Weekly entries must be a list of week values.")
    allowed = CHILD_ALLOWED.get(line["code"]) or [0, 1]
    cleaned, total = [], 0
    for w in weekly:
        if not isinstance(w, dict):
            _bad("Each weekly entry must include a week number and a star value.")
        value = as_star_int(w.get("value", 0), f"{line['name']} week {w.get('week')}")
        if value not in allowed:
            _bad(MESSAGES.get(f"{line['code']}_weekly") or MESSAGES.get(line["code"], ""))
        total += value
        cleaned.append({"week": w.get("week"), "start": w.get("start"),
                        "end": w.get("end"), "value": value})
    cap = STATIC_PARENT_RANGE.get(line["code"], (0, line.get("cap") or 0))[1]
    if abs(total) > abs(cap):
        _bad(f"{line['name']} cannot exceed {cap} star(s) per month — "
             f"the weekly entries total {total}.")
    return cleaned


def validate_instance_value(line: dict, raw) -> int:
    """N07 / N08 incidents carry a fixed star value."""
    fixed = FIXED_INSTANCE_STAR.get(line["code"])
    if fixed is None:
        _bad("This criteria does not accept manual instances.")
    if raw is None:
        return fixed
    value = as_star_int(raw, f"{line['name']} incident stars")
    if value != fixed:
        _bad(MESSAGES.get(line["code"], f"A fixed value of {fixed} is required."))
    return value


def line_violation(line: dict):
    """Flag a stored value that breaks the rules — never auto-corrected."""
    code = line["code"]
    problems = []
    b = parent_bounds(line)
    ov = line.get("override_value")
    if ov is not None:
        bad = (ov not in b["allowed"]) if b["allowed"] is not None else (ov < b["min"] or ov > b["max"])
        if bad or abs(ov - round(ov)) > 1e-9:
            problems.append(f"Override {ov:+g} is outside the allowed range for {code}.")
    if line["type"] == "manual" and code not in FIXED_INSTANCE_STAR:
        r = monthly_entry_range(line)
        mv = line.get("manual_value") or 0
        if mv < r["min"] or mv > r["max"] or abs(mv - round(mv)) > 1e-9:
            problems.append(f"Monthly manual value {mv:+g} is outside {r['min']}..{r['max']}.")
        allowed = CHILD_ALLOWED.get(code) or [0, 1]
        for w in line.get("weekly") or []:
            if (w.get("value") or 0) not in allowed:
                problems.append(f"Week {w.get('week')} value {w.get('value'):+g} is not allowed.")
    fixed = FIXED_INSTANCE_STAR.get(code)
    if fixed is not None:
        for i in line.get("instances") or []:
            if i.get("value") != fixed:
                problems.append(f"Incident {i.get('date')} carries {i.get('value'):+g} "
                                f"instead of the fixed {fixed:+g}.")
    fv = line.get("final_value")
    if fv is not None:
        bad = (fv not in b["allowed"]) if b["allowed"] is not None else (fv < b["min"] or fv > b["max"])
        if bad:
            problems.append(f"Final stars {fv:+g} are outside the allowed range "
                            f"({b['min']} to {b['max']}) for {code}.")
    if not problems:
        return None
    return {"invalid": True, "reasons": problems,
            "hint": "Correct this value on the next manual save — historical data is never overwritten automatically."}
