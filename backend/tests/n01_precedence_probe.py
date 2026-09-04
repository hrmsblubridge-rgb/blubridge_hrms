"""N01 precedence + N03 equivalent unit probe (no DB)."""
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, "/app/backend")
from brsf_stars import calculate_invalid_leave_star  # noqa: E402


def leave(lt, split, applied, day="2026-08-12", validity=None, lid="x"):
    return {"id": lid, "leave_type": lt, "leave_split": split, "start_date": day,
            "end_date": day, "created_at": applied, "leave_validity": validity,
            "_start": date.fromisoformat(day), "_end": date.fromisoformat(day)}


cases = [
    ("Sick FD 06:30 / not set", leave("Sick", "Full Day", "2026-08-12T06:30:00+05:30"), 0),
    ("Sick FD 08:00 / not set", leave("Sick", "Full Day", "2026-08-12T08:00:00+05:30"), -1),
    ("Sick FD 08:00 / invalid", leave("Sick", "Full Day", "2026-08-12T08:00:00+05:30", validity="invalid"), -1),
    ("Sick FD 08:00 / valid", leave("Sick", "Full Day", "2026-08-12T08:00:00+05:30", validity="valid"), 0),
    ("Sick FD 06:30 / valid", leave("Sick", "Full Day", "2026-08-12T06:30:00+05:30", validity="valid"), 0),
    ("Sick FD 06:30 / invalid", leave("Sick", "Full Day", "2026-08-12T06:30:00+05:30", validity="invalid"), 0),
    ("Sick 1st half 08:00", leave("Sick", "First Half", "2026-08-12T08:00:00+05:30"), -1),
    ("Sick 2nd half same day 13:00", leave("Sick", "Second Half", "2026-08-12T13:00:00+05:30"), 0),
    ("Preplanned 4 days ahead", leave("Preplanned", "Full Day", "2026-08-08T10:00:00+05:30"), 0),
    ("Preplanned 2 days ahead", leave("Preplanned", "Full Day", "2026-08-10T10:00:00+05:30"), -1),
    ("Preplanned 2 days / valid", leave("Preplanned", "Full Day", "2026-08-10T10:00:00+05:30", validity="valid"), 0),
    ("Paid leave (no rule)", leave("Paid", "Full Day", "2026-08-12T09:20:00+05:30"), 0),
    ("Emergency (no N01 rule)", leave("Emergency", "Full Day", "2026-08-12T09:20:00+05:30"), 0),
]
ok = True
for label, lv, expected in cases:
    got = calculate_invalid_leave_star(lv)
    flag = "PASS" if got["value"] == expected else "FAIL"
    ok &= got["value"] == expected
    print(f"{flag} {label}: {got['value']} (exp {expected}) — {got['reason']}")

# N03 equivalents
def equiv(splits):
    return round(sum(0.5 if s in ("First Half", "Second Half") else 1.0 for s in splits), 2)


for splits, exp in [(["Full Day", "First Half", "Second Half"], 0),
                    (["Full Day", "Full Day"], 0),
                    (["Full Day", "Full Day", "First Half"], -3),
                    (["Full Day"] * 4, -3),
                    ([], 0)]:
    e = equiv(splits)
    star = -3 if e > 2.0 else 0
    flag = "PASS" if star == exp else "FAIL"
    ok &= star == exp
    print(f"{flag} N03 equivalent {e} -> {star} (exp {exp})")
print("ALL PASS" if ok else "FAILURES PRESENT")
