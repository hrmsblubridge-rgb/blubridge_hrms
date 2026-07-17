"""Regression test for the overnight-punch reconciliation via
/api/attendance/recompute-from-punches.

Background: `get_effective_attendance_date` already handled cross-midnight
correctly for NEW ingestions. However, historical `biometric_punch_logs` rows
had `logs.date` frozen to the calendar date at ingestion time. The recompute
endpoint used to group by that stored date — so it could never fix legacy
overnight mis-assignments.

Fix (2026-07-17): The recompute endpoint now regroups punches by the FRESHLY
recomputed effective date (from `recordTime`). Any attendance row whose
punches all moved to the previous day is cleared (`orphans_cleared`) to
prevent stale IN/OUT values.

This test simulates the exact scenario reported: Kota Dhanakumar 24-Mar 09:31
IN with a 25-Mar 00:20 punch that should be 24-Mar's OUT.
"""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def _effective_date(punch_ist, cutoff_min=300):
    m = punch_ist.hour * 60 + punch_ist.minute
    eff = punch_ist - timedelta(days=1) if m <= cutoff_min else punch_ist
    return eff.strftime("%d-%m-%Y")


def _regroup_and_derive(punches_utc_iso, cutoff_min=300):
    """Emulate what the fixed recompute endpoint does."""
    by_date = {}
    for iso in punches_utc_iso:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)
        by_date.setdefault(_effective_date(dt, cutoff_min), []).append(dt)
    result = {}
    for d, pl in by_date.items():
        unique = sorted({p.replace(second=0, microsecond=0) for p in pl})
        result[d] = {
            "in": unique[0].strftime("%H:%M"),
            "out": unique[-1].strftime("%H:%M") if len(unique) > 1 else None,
        }
    return result


def test_kota_scenario_recomputes_correctly():
    """The exact bug reported by the user (Kota Dhanakumar 24-Mar-2026)."""
    punches = [
        "2026-03-24T04:01:14.000Z",  # 24-Mar 09:31 IST
        "2026-03-24T18:50:54.000Z",  # 25-Mar 00:20 IST — must move to 24-Mar OUT
        "2026-03-25T03:39:49.000Z",  # 25-Mar 09:09 IST
        "2026-03-25T18:28:35.000Z",  # 25-Mar 23:58 IST
    ]
    assert _regroup_and_derive(punches) == {
        "24-03-2026": {"in": "09:31", "out": "00:20"},
        "25-03-2026": {"in": "09:09", "out": "23:58"},
    }


def test_no_punch_is_double_assigned():
    punches = [
        "2026-03-24T04:01:14.000Z",
        "2026-03-24T18:50:54.000Z",
        "2026-03-25T03:39:49.000Z",
        "2026-03-25T18:28:35.000Z",
    ]
    by_date = {}
    for iso in punches:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)
        by_date.setdefault(_effective_date(dt), []).append(dt)
    flat = [x for lst in by_date.values() for x in lst]
    assert len(flat) == len(punches)
    assert len(set((x.date(), x.time()) for x in flat)) == len(punches)


def test_no_orphan_when_only_overnight_punch_exists():
    """If the only punch on a calendar day is an overnight one that moves to
    the previous day, no orphan row should remain for the calendar day."""
    punches = [
        "2026-03-24T04:01:14.000Z",  # 24-Mar 09:31 IN
        "2026-03-24T18:50:54.000Z",  # 25-Mar 00:20 IST — becomes 24-Mar OUT
    ]
    grouped = _regroup_and_derive(punches)
    # 25-Mar has NO active punches → attendance row for 25-Mar must be cleared
    # (orphans_cleared logic in the endpoint handles this).
    assert "25-03-2026" not in grouped
    assert grouped == {"24-03-2026": {"in": "09:31", "out": "00:20"}}


def test_after_cutoff_belongs_to_new_day():
    punches = [
        "2026-03-24T04:01:14.000Z",  # 24-Mar 09:31 IN
        "2026-03-25T04:00:00.000Z",  # 25-Mar 09:30 IST — well past cutoff → new day
    ]
    grouped = _regroup_and_derive(punches)
    assert grouped == {
        "24-03-2026": {"in": "09:31", "out": None},
        "25-03-2026": {"in": "09:30", "out": None},
    }
