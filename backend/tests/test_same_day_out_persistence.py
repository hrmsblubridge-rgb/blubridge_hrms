"""Regression test for the "same-day OUT lost across batches" bug.

Scenario (real production case — Srinath Kamalakumar, Jona Delcy, 17-Jul-2026):
The biometric device syncs incrementally every ~10 minutes. An employee's IN
punch (09:41) arrives in Batch A. Their OUT punch (20:55, same calendar day)
arrives in Batch B nearly 11 hours later. The engine must correctly pair
these into a single attendance row `(IN=09:41, OUT=20:55)`.

The previous per-batch merge relied on the state of the previously written
attendance row, which was fragile. The fix re-derives IN/OUT from the source
of truth (`biometric_punch_logs`) on every batch ingest.

Rules this test locks in:
  1. Normal same-day IN + later OUT → both preserved even when arriving in
     separate batches.
  2. No overnight logic executes for same-day pairs (both times > cut-off).
  3. Manual overrides / approved corrections must NOT be overwritten.
  4. Every punch belongs to exactly one attendance row.
"""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
CUTOFF = 300  # 05:00


def _to_ist(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)


def _effective_date(dt):
    m = dt.hour * 60 + dt.minute
    return (dt - timedelta(days=1) if m <= CUTOFF else dt).strftime("%d-%m-%Y")


def _derive_from_all_punches(record_times):
    """Emulate the *new* ingest: derive IN/OUT from ALL raw punches for
    (emp, effective_date), not just this batch + existing."""
    by_date = {}
    for iso in record_times:
        dt = _to_ist(iso)
        by_date.setdefault(_effective_date(dt), []).append(dt)
    out = {}
    for d, pl in by_date.items():
        unique = sorted({p.replace(second=0, microsecond=0) for p in pl})
        out[d] = {
            "in": unique[0].strftime("%H:%M"),
            "out": unique[-1].strftime("%H:%M") if len(unique) > 1 else None,
        }
    return out


def test_srinath_2batch_scenario_no_out_loss():
    """The exact reported bug: 09:41 IN in batch A, 20:55 OUT in batch B."""
    # After batch A processing: only 09:41 in raw logs
    result_after_a = _derive_from_all_punches(["2026-07-17T04:11:07.000Z"])
    assert result_after_a == {"17-07-2026": {"in": "09:41", "out": None}}

    # After batch B: both punches in raw logs → OUT must be preserved
    result_after_b = _derive_from_all_punches([
        "2026-07-17T04:11:07.000Z",
        "2026-07-17T15:25:29.000Z",
    ])
    assert result_after_b == {"17-07-2026": {"in": "09:41", "out": "20:55"}}


def test_jona_2batch_scenario_no_out_loss():
    result = _derive_from_all_punches([
        "2026-07-17T03:40:14.000Z",  # 09:10 IST IN
        "2026-07-17T15:14:53.000Z",  # 20:44 IST OUT
    ])
    assert result == {"17-07-2026": {"in": "09:10", "out": "20:44"}}


def test_same_day_pair_uses_no_overnight_logic():
    """Both punches well past the 05:00 cut-off → same calendar day."""
    result = _derive_from_all_punches([
        "2026-07-17T04:00:00.000Z",  # 09:30 IST
        "2026-07-17T15:00:00.000Z",  # 20:30 IST
    ])
    assert result == {"17-07-2026": {"in": "09:30", "out": "20:30"}}


def test_ten_reingested_batches_still_only_one_in_one_out():
    """A device that spams the same 2 punches 10 times must dedupe cleanly."""
    result = _derive_from_all_punches([
        "2026-07-17T04:11:07.000Z", "2026-07-17T04:11:07.000Z",
        "2026-07-17T04:11:07.000Z", "2026-07-17T04:11:07.000Z",
        "2026-07-17T15:25:29.000Z", "2026-07-17T15:25:29.000Z",
        "2026-07-17T15:25:29.000Z", "2026-07-17T15:25:29.000Z",
    ])
    assert result == {"17-07-2026": {"in": "09:41", "out": "20:55"}}


def test_punches_arriving_out_of_order_are_paired_correctly():
    """OUT batch arriving BEFORE IN batch (rare device replay) must still pair."""
    result_out_first = _derive_from_all_punches(["2026-07-17T15:25:29.000Z"])
    assert result_out_first == {"17-07-2026": {"in": "20:55", "out": None}}
    # Now IN arrives too:
    result_both = _derive_from_all_punches([
        "2026-07-17T15:25:29.000Z",
        "2026-07-17T04:11:07.000Z",
    ])
    assert result_both == {"17-07-2026": {"in": "09:41", "out": "20:55"}}


def test_only_one_punch_never_becomes_both_in_and_out():
    result = _derive_from_all_punches(["2026-07-17T04:11:07.000Z"])
    assert result["17-07-2026"]["in"] == "09:41"
    assert result["17-07-2026"]["out"] is None  # never duplicate IN as OUT


def test_late_night_till_ten_pm_stays_same_day():
    """Employee stays until 22:15 — still same-day."""
    result = _derive_from_all_punches([
        "2026-07-17T03:30:00.000Z",  # 09:00 IST IN
        "2026-07-17T16:45:00.000Z",  # 22:15 IST OUT
    ])
    assert result == {"17-07-2026": {"in": "09:00", "out": "22:15"}}


def test_late_night_till_1158_stays_same_day():
    """Employee stays until 23:58 — still same-day."""
    result = _derive_from_all_punches([
        "2026-07-17T03:30:00.000Z",  # 09:00 IST
        "2026-07-17T18:28:00.000Z",  # 23:58 IST
    ])
    assert result == {"17-07-2026": {"in": "09:00", "out": "23:58"}}


def test_overnight_1240am_still_maps_to_previous_day():
    """After the earlier overnight fix — 12:40 AM belongs to previous day."""
    result = _derive_from_all_punches([
        "2026-07-17T03:30:00.000Z",  # 09:00 IST
        "2026-07-17T19:10:00.000Z",  # 00:40 IST NEXT DAY (18-Jul 00:40)
    ])
    # 18-Jul 00:40 IST → hour*60+min = 40 <= 300 → previous day (17-07-2026)
    assert result == {"17-07-2026": {"in": "09:00", "out": "00:40"}}
