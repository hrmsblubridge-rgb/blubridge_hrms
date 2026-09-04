"""Iteration 77 BRSF regression - N06 Frequent Absences.

Verifies via localhost:8001 (preview blocks python-requests via Cloudflare):
  * N06 system_note format: 'X absence-equivalent day(s) from leave + absent
    (Full Day 1.0 / Half Day 0.5); up to 4.0 allowed'
  * value strictly 0 when equiv <= 4.0 and exactly -3 when > 4.0 (never -6/-9)
  * Combined leave + attendance (source both 'Leave' and 'Attendance')
  * No double counting: any date appears at most once, equivalent <= 1.0
  * Zero case: no leave + no absence -> total 0.0, value 0, empty children
  * Manual override: PUT /override with 0 and -3 succeed; -1,-2,-4,+1,+3,0.5 rejected 400
  * Override preserved across POST /recalculate until reset-override
  * Named canonical fixtures: Adwaid Suresh 7.0 -> -3, Aparna A 1.0 -> 0
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:8001")
UA = {"User-Agent": "Mozilla/5.0 (brsf-iter77)"}
ADMIN = ("admin", "HrAdmin786$")
MONTH = "2026-08"


@pytest.fixture(scope="module")
def sess():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": ADMIN[0], "password": ADMIN[1]},
                      headers=UA, timeout=180)
    assert r.status_code == 200, r.text[:300]
    tok = r.json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", **UA})
    return s


@pytest.fixture(scope="module")
def summary(sess):
    r = sess.get(f"{BASE_URL}/api/brsf/summary", params={"month": MONTH}, timeout=180)
    assert r.status_code == 200, r.text[:500]
    return r.json()


def _stars(sess, eid):
    r = sess.get(f"{BASE_URL}/api/brsf/stars",
                 params={"employee_id": eid, "month": MONTH}, timeout=180)
    assert r.status_code == 200, r.text[:400]
    return r.json()


def _line(stars, code):
    return next(ln for ln in stars["lines"] if ln["code"] == code)


def _sum_equiv(children):
    return round(sum((c.get("equivalent") or 0) for c in children), 2)


# ------------- Broad scan: value must match rule for every employee -------------
def test_n06_value_matches_rule_across_employees(sess, summary):
    rows = summary["rows"][:20]
    scanned = 0
    for r in rows:
        try:
            st = _stars(sess, r["id"])
        except AssertionError:
            continue
        n06 = _line(st, "N06")
        equiv = _sum_equiv(n06.get("system_children") or [])
        expected = -3 if equiv > 4.0 else 0
        assert n06["system_value"] == expected, (
            f"{r.get('full_name')} equiv={equiv} system_value={n06['system_value']} expected={expected}")
        # Value must NEVER be -6/-9 regardless of total
        assert n06["system_value"] in (0, -3), f"{r.get('full_name')} bad system_value {n06['system_value']}"
        # Note format
        note = n06.get("system_note") or ""
        assert "absence-equivalent day(s) from leave + absent" in note
        assert "Full Day 1.0 / Half Day 0.5" in note
        assert "up to 4.0 allowed" in note
        assert f"{equiv} " in note, f"note missing equiv value: {note}"
        scanned += 1
    assert scanned >= 5, f"only {scanned} employees scanned"


# ------------- Canonical fixtures -------------
def _find(summary, name_substr):
    for r in summary["rows"]:
        if name_substr.lower() in (r.get("full_name") or "").lower():
            return r
    return None


def test_adwaid_suresh_high_total_gives_single_minus_three(sess, summary):
    emp = _find(summary, "Adwaid Suresh")
    if not emp:
        pytest.skip("Adwaid Suresh not in eligible list")
    st = _stars(sess, emp["id"])
    n06 = _line(st, "N06")
    equiv = _sum_equiv(n06["system_children"])
    assert equiv > 4.0, f"Adwaid equiv={equiv} expected > 4.0"
    assert n06["system_value"] == -3, f"expected -3 got {n06['system_value']}"


def test_aparna_a_low_total_gives_zero(sess, summary):
    emp = _find(summary, "Aparna A")
    if not emp:
        pytest.skip("Aparna A not in eligible list")
    st = _stars(sess, emp["id"])
    n06 = _line(st, "N06")
    equiv = _sum_equiv(n06["system_children"])
    assert equiv <= 4.0
    assert n06["system_value"] == 0


# ------------- No double counting / per-date <=1.0 -------------
def test_no_double_counting_any_date_at_most_one_row_and_one_equivalent(sess, summary):
    """Every date across all N06 children (all employees scanned) must appear
    at most once per employee and contribute at most 1.0."""
    violations = []
    for r in summary["rows"][:20]:
        try:
            st = _stars(sess, r["id"])
        except AssertionError:
            continue
        n06 = _line(st, "N06")
        by_date = {}
        for c in n06.get("system_children") or []:
            d = c.get("date")
            by_date.setdefault(d, []).append(c)
        for d, rows in by_date.items():
            if len(rows) > 1:
                violations.append(f"{r.get('full_name')} {d} duplicated {len(rows)}x")
            total = sum(x.get("equivalent") or 0 for x in rows)
            if total > 1.0 + 1e-9:
                violations.append(f"{r.get('full_name')} {d} equiv total {total} > 1.0")
    assert not violations, "double-count issues: " + "; ".join(violations[:10])


# ------------- Children carry source/leave_type/duration/equivalent -------------
def test_children_have_all_required_fields(sess, summary):
    saw_leave = saw_attendance = False
    for r in summary["rows"][:20]:
        try:
            st = _stars(sess, r["id"])
        except AssertionError:
            continue
        n06 = _line(st, "N06")
        for c in n06.get("system_children") or []:
            for f in ("date", "source", "leave_type", "duration", "equivalent"):
                assert f in c, f"child missing {f}: {c}"
            assert c["source"] in ("Leave", "Attendance")
            assert c["equivalent"] in (0.5, 1.0), f"bad equivalent {c['equivalent']}"
            assert c["duration"] in ("Full Day", "First Half", "Second Half", "Half Day", None)
            if c["source"] == "Leave":
                saw_leave = True
            else:
                saw_attendance = True
        if saw_leave and saw_attendance:
            break
    # At least one Leave source must exist in Aug-2026 (Adwaid etc have leaves)
    assert saw_leave, "no Leave-source children observed across sample"


# ------------- Zero case -------------
def test_zero_case_no_leave_no_absence(sess, summary):
    """Find any employee with equiv=0.0; must have value 0, empty children,
    and note '0 ... 0.0 absence-equivalent day(s)' or similar."""
    for r in summary["rows"][:25]:
        try:
            st = _stars(sess, r["id"])
        except AssertionError:
            continue
        n06 = _line(st, "N06")
        equiv = _sum_equiv(n06.get("system_children") or [])
        if equiv == 0.0:
            assert n06["system_value"] == 0
            assert (n06.get("system_children") or []) == [], \
                f"{r.get('full_name')} equiv=0 but children non-empty"
            assert "0 " in (n06.get("system_note") or "") or "0.0 " in (n06.get("system_note") or "")
            return
    pytest.skip("no zero-total employee found in first 25 rows")


# ------------- Manual override limits -------------
@pytest.fixture(scope="module")
def override_target(sess, summary):
    """Pick an employee to test parent override on N06 - use Aparna A (equiv <=4.0)
    to avoid interfering with -3 results."""
    emp = _find(summary, "Aparna A") or summary["rows"][0]
    st = _stars(sess, emp["id"])
    line = _line(st, "N06")
    return {"emp": emp, "line_id": line["id"], "original_override": line.get("override_value")}


def test_override_accepts_0_and_minus_3(sess, override_target):
    lid = override_target["line_id"]
    # 0
    r = sess.put(f"{BASE_URL}/api/brsf/stars/{lid}/override",
                 json={"value": 0, "reason": "iter77 test 0"}, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.json()["override_value"] == 0
    # -3
    r = sess.put(f"{BASE_URL}/api/brsf/stars/{lid}/override",
                 json={"value": -3, "reason": "iter77 test -3"}, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.json()["override_value"] == -3
    assert r.json()["final_value"] == -3


@pytest.mark.parametrize("bad", [-1, -2, -4, 1, 3, 0.5])
def test_override_rejects_disallowed_values(sess, override_target, bad):
    lid = override_target["line_id"]
    r = sess.put(f"{BASE_URL}/api/brsf/stars/{lid}/override",
                 json={"value": bad, "reason": f"iter77 bad {bad}"}, timeout=60)
    assert r.status_code == 400, f"expected 400 for {bad}, got {r.status_code}: {r.text[:200]}"
    msg = (r.json().get("detail") or "").lower()
    # Message should mention 0 or -3 (per the criterion message) OR whole-number rule for 0.5
    if bad == 0.5:
        assert "whole" in msg or "0 or -3" in msg
    else:
        assert "0 or -3" in msg or "frequent absences" in msg


def test_override_preserved_across_recalculate(sess, override_target):
    """After setting -3 override, POST /recalculate must NOT clear it."""
    lid = override_target["line_id"]
    emp_id = override_target["emp"]["id"]
    # Ensure override is -3
    sess.put(f"{BASE_URL}/api/brsf/stars/{lid}/override",
             json={"value": -3, "reason": "iter77 preserve"}, timeout=60)
    # Recalculate only this employee
    r = sess.post(f"{BASE_URL}/api/brsf/recalculate",
                  json={"month": MONTH, "employee_id": emp_id}, timeout=180)
    assert r.status_code == 200, r.text[:300]
    # Re-fetch
    st = _stars(sess, emp_id)
    n06 = _line(st, "N06")
    assert n06["override_value"] == -3, f"override cleared by recalculate: {n06['override_value']}"
    assert n06["final_value"] == -3


def test_reset_override_clears_it(sess, override_target):
    lid = override_target["line_id"]
    r = sess.post(f"{BASE_URL}/api/brsf/stars/{lid}/reset-override", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["override_value"] is None


# ------------- N06 parent limits shape -------------
def test_n06_parent_limits_are_0_and_minus_3(sess, summary):
    emp = summary["rows"][0]
    st = _stars(sess, emp["id"])
    n06 = _line(st, "N06")
    limits = n06.get("limits") or {}
    parent = limits.get("parent") or {}
    assert parent.get("allowed") == [0, -3], f"unexpected N06 parent allowed: {parent}"


# ------------- Recalculate must be idempotent for the month (net_total stable) -------------
def test_recalculate_idempotent_for_month(sess, summary):
    emp = _find(summary, "Aparna A") or summary["rows"][0]
    st1 = _stars(sess, emp["id"])
    net1 = st1["totals"]["net_total"]
    # Recalculate whole month
    r = sess.post(f"{BASE_URL}/api/brsf/recalculate", json={"month": MONTH}, timeout=240)
    assert r.status_code == 200
    st2 = _stars(sess, emp["id"])
    assert st2["totals"]["net_total"] == net1
