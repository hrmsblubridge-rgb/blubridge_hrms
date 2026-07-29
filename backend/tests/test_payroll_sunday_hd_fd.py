"""
Payroll Sunday HD/FD/WO/MP logic tests (READ-ONLY, no writes).

Rules under test (bug fix — Jan 2026 iteration 63):
- Working on a Sunday/holiday: if hours >= full_day_threshold -> FD (+1 extra pay)
  elif hours >= half_day_threshold -> HD (+0.5 extra pay)
  else -> WO (worked but below half threshold; extra 0)
- Incomplete punch on Sunday/holiday (only in or only out) -> MP (no extra pay)
- weekoff_value must still be 1 on every Sunday (even worked/HD/FD)
- final_payable_days = working + weekoff + oh - lop (extra_pay stays a separate column)

Dept thresholds (full/half):
  Research Unit       : 11 / 5   (half was 6 previously; fixed to 5)
  Business & Product  : 10 / 5
  Support Staff       :  9 / 4.5

Mandatory: Sanjay Krishna MV (EMP0022), Research Unit.
  - 19-07-2026 (Sun) 5h 1m worked -> HD, extra 0.5, weekoff_value 1
  - 12-07-2026 (Sun) 11.5h worked -> FD, extra 1
  - 05-07-2026 & 26-07-2026 (Sun, no attendance) -> WO
  - extra_pay total = 1.5, weekoff_pay = 4
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('PAYROLL_TEST_URL', 'http://127.0.0.1:8001').rstrip('/')
TIMEOUT = 240


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "admin", "password": "HrAdmin786$"},
                      timeout=120)
    assert r.status_code == 200, f"login {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def payroll_july(headers):
    r = requests.get(f"{BASE_URL}/api/payroll",
                     params={"month": "2026-07"},
                     headers=headers, timeout=TIMEOUT)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    payload = r.json()
    if isinstance(payload, dict):
        for k in ("data", "employees", "payroll", "results", "items"):
            if k in payload and isinstance(payload[k], list):
                return payload[k]
    if isinstance(payload, list):
        return payload
    pytest.fail(f"Unexpected payroll payload shape: {type(payload)}")


def _find(rows, name_substr):
    ns = name_substr.strip().lower()
    hits = [e for e in rows
            if ns in str(e.get("emp_name") or e.get("name") or e.get("employee_name") or "").strip().lower()]
    return hits


def _detail(emp, date_ddmmyyyy):
    for d in emp.get("attendance_details") or []:
        if d.get("date") == date_ddmmyyyy:
            return d
    return None


# ---------- MANDATORY: Sanjay Krishna MV ----------
class TestSanjay:
    @pytest.fixture(scope="class")
    def sanjay(self, payroll_july):
        hits = _find(payroll_july, "Sanjay Krishna")
        assert hits, "Sanjay Krishna MV not found in July payroll"
        # Prefer EMP0022 if multiple
        for e in hits:
            if str(e.get("employee_id") or e.get("emp_id") or "").upper() == "EMP0022":
                return e
        return hits[0]

    def test_extra_pay_total(self, sanjay):
        assert float(sanjay.get("extra_pay", 0) or 0) == 1.5, \
            f"Sanjay extra_pay={sanjay.get('extra_pay')} (expected 1.5); row={sanjay}"

    def test_weekoff_pay_preserved(self, sanjay):
        assert float(sanjay.get("weekoff_pay", 0) or 0) == 4, \
            f"Sanjay weekoff_pay={sanjay.get('weekoff_pay')} (expected 4)"

    def test_19jul_HD(self, sanjay):
        d = _detail(sanjay, "19-07-2026")
        assert d, "19-07-2026 row missing"
        assert str(d.get("status", "")).upper() == "HD", d
        assert float(d.get("extra_value", 0) or 0) == 0.5, d
        assert float(d.get("weekoff_value", 0) or 0) == 1, d

    def test_12jul_FD(self, sanjay):
        d = _detail(sanjay, "12-07-2026")
        assert d, "12-07-2026 row missing"
        assert str(d.get("status", "")).upper() == "FD", d
        assert float(d.get("extra_value", 0) or 0) == 1, d
        assert float(d.get("weekoff_value", 0) or 0) == 1, d

    def test_unworked_sundays_WO(self, sanjay):
        for dt in ("05-07-2026", "26-07-2026"):
            d = _detail(sanjay, dt)
            assert d, f"{dt} missing"
            assert str(d.get("status", "")).upper() == "WO", (dt, d)
            assert float(d.get("extra_value", 0) or 0) == 0, (dt, d)
            assert float(d.get("weekoff_value", 0) or 0) == 1, (dt, d)

    def test_extra_pay_sum_matches(self, sanjay):
        total = sum(float(d.get("extra_value", 0) or 0)
                    for d in sanjay.get("attendance_details") or [])
        assert abs(total - float(sanjay.get("extra_pay", 0) or 0)) < 0.01, \
            f"sum(extra_value)={total} vs extra_pay={sanjay.get('extra_pay')}"

    def test_extra_not_in_payable(self, sanjay):
        wd = float(sanjay.get("working_days", 0) or 0)
        wo = float(sanjay.get("weekoff_pay", 0) or 0)
        oh = float(sanjay.get("oh_pay", 0) or 0)
        lop = float(sanjay.get("lop", 0) or 0)
        pay = float(sanjay.get("final_payable_days", 0) or 0)
        assert abs(pay - (wd + wo + oh - lop)) < 0.01, \
            f"payable {pay} != wd+wo+oh-lop = {wd+wo+oh-lop} (extra should NOT be in payable)"


# ---------- Global Sunday rule sanity ----------
class TestGlobalSundayRules:
    @pytest.mark.parametrize("name_substr,expected_status,expected_extra", [
        ("Rishi S Nayak", "HD", 0.5),        # B&P, 7.83h, full 10 half 5 -> HD
        ("Kota Dhanakumar", "FD", 1.0),      # RU, 11.2h, full 11 -> FD
        ("Vedanth Reddy", "WO", 0.0),        # RU, 4.98h < 5 -> WO
    ])
    def test_19jul_by_name(self, payroll_july, name_substr, expected_status, expected_extra):
        hits = _find(payroll_july, name_substr)
        assert hits, f"{name_substr} not found"
        emp = hits[0]
        d = _detail(emp, "19-07-2026")
        assert d, f"{name_substr} 19-07-2026 missing"
        assert str(d.get("status", "")).upper() == expected_status, \
            f"{name_substr} 19-07 status={d.get('status')} (expected {expected_status}); row={d}"
        assert abs(float(d.get("extra_value", 0) or 0) - expected_extra) < 0.01, \
            f"{name_substr} 19-07 extra_value={d.get('extra_value')} (expected {expected_extra})"
        # weekoff preservation on Sunday regardless
        assert float(d.get("weekoff_value", 0) or 0) == 1, \
            f"{name_substr} weekoff_value not preserved: {d}"


# ---------- Incomplete punch -> MP on Sunday ----------
class TestIncompletePunchMP:
    def test_kota_12jul_mp(self, payroll_july):
        hits = _find(payroll_july, "Kota Dhanakumar")
        assert hits
        emp = hits[0]
        d = _detail(emp, "12-07-2026")
        assert d, "Kota 12-07-2026 missing"
        # Single-side punch -> MP
        assert str(d.get("status", "")).upper() == "MP", \
            f"Kota 12-07 expected MP, got {d.get('status')}; row={d}"
        assert float(d.get("extra_value", 0) or 0) == 0, d

    def test_adhitya_12jul_wo_not_mp(self, payroll_july):
        hits = _find(payroll_july, "Adhitya Charan")
        assert hits, "Adhitya Charan not found"
        emp = hits[0]
        d = _detail(emp, "12-07-2026")
        assert d, "Adhitya 12-07-2026 missing"
        # Both punches present but 0.33h < half threshold -> WO (NOT MP)
        assert str(d.get("status", "")).upper() == "WO", \
            f"Adhitya 12-07 expected WO (both punches, below half), got {d.get('status')}; row={d}"
        assert float(d.get("extra_value", 0) or 0) == 0, d


# ---------- Regressions: previous / future month & formula ----------
class TestRegressions:
    def test_june_full_month_payable_30(self, headers):
        r = requests.get(f"{BASE_URL}/api/payroll", params={"month": "2026-06"},
                         headers=headers, timeout=TIMEOUT)
        assert r.status_code == 200
        payload = r.json()
        rows = payload if isinstance(payload, list) else next(
            (payload[k] for k in ("data", "employees", "payroll", "results", "items")
             if isinstance(payload.get(k), list)), [])
        candidates = [e for e in rows
                      if float(e.get("lop", 0) or 0) == 0
                      and float(e.get("lop_days", 0) or 0) == 0
                      and not e.get("relieving_date")
                      and not e.get("date_of_relieving")]
        assert candidates
        assert any(float(e.get("final_payable_days", 0) or 0) == 30 for e in candidates), \
            "no active zero-LOP employee has payable=30 in June"

    def test_august_future_zero(self, headers):
        r = requests.get(f"{BASE_URL}/api/payroll", params={"month": "2026-08"},
                         headers=headers, timeout=TIMEOUT)
        assert r.status_code == 200
        payload = r.json()
        rows = payload if isinstance(payload, list) else next(
            (payload[k] for k in ("data", "employees", "payroll", "results", "items")
             if isinstance(payload.get(k), list)), [])
        bad = [e.get("emp_name") or e.get("name") for e in rows
               if float(e.get("final_payable_days", 0) or 0) != 0
               or float(e.get("working_days", 0) or 0) != 0
               or float(e.get("weekoff_pay", 0) or 0) != 0]
        assert not bad, f"August future rows not zero: {bad[:10]}"

    def test_july_cutoff_30_31_na(self, payroll_july):
        # Pick first employee with attendance_details
        emp = next((e for e in payroll_july if e.get("attendance_details")), None)
        assert emp
        by_date = {d.get("date"): d for d in emp["attendance_details"]}
        for dt in ("30-07-2026", "31-07-2026"):
            row = by_date.get(dt)
            assert row, f"{dt} missing"
            st = str(row.get("status", "")).upper()
            # Status either NA or Sunday-marker Su with zero values
            assert st in ("NA", "SU"), f"{dt} status={st} (expected NA/Su)"
            assert float(row.get("lop_value", 0) or 0) == 0
