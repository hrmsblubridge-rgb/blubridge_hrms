"""
Tests for Payroll 'Payable Days' cutoff logic (IST-aware):
- Current month: only 1..today inclusive
- Previous month: full month
- Future month: 0
- LOP subtraction preserved
- extra_pay / oh_pay separate (only oh_pay is part of formula, extra_pay excluded)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('PAYROLL_TEST_URL', 'http://localhost:8001').rstrip('/')
TIMEOUT = 180  # payroll compute is slow


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "admin", "password": "HrAdmin786$"},
                      timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def payroll_july(headers):
    r = requests.get(f"{BASE_URL}/api/payroll", params={"month": "2026-07"},
                     headers=headers, timeout=TIMEOUT)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="module")
def payroll_june(headers):
    r = requests.get(f"{BASE_URL}/api/payroll", params={"month": "2026-06"},
                     headers=headers, timeout=TIMEOUT)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def payroll_august(headers):
    r = requests.get(f"{BASE_URL}/api/payroll", params={"month": "2026-08"},
                     headers=headers, timeout=TIMEOUT)
    assert r.status_code == 200
    return r.json()


def _rows(payload):
    if isinstance(payload, dict):
        for k in ("data", "employees", "payroll", "results", "items"):
            if k in payload and isinstance(payload[k], list):
                return payload[k]
    if isinstance(payload, list):
        return payload
    return []


def _is_active(emp):
    s = str(emp.get("status") or emp.get("employment_status") or "").lower()
    return s in ("", "active") and not emp.get("relieving_date") and not emp.get("date_of_relieving")


# ---------- CURRENT MONTH (July 2026, today=29-07-2026 IST) ----------
class TestCurrentMonthJuly:
    def test_active_zero_lop_payable_is_29(self, payroll_july):
        rows = _rows(payroll_july)
        assert rows, "no payroll rows returned"
        candidates = [e for e in rows
                      if _is_active(e)
                      and float(e.get("lop", 0) or 0) == 0
                      and float(e.get("lop_days", 0) or 0) == 0]
        assert candidates, "no active zero-LOP employee found for July"
        # At least one such employee should show 29
        payables = {e.get("employee_id") or e.get("emp_id") or e.get("name"):
                    float(e.get("final_payable_days", 0) or 0) for e in candidates}
        assert any(v == 29 for v in payables.values()), \
            f"Expected some active zero-LOP employee to have final_payable_days=29; sample: {list(payables.items())[:10]}"

        # Pick one and validate breakdown 25 + 4
        sample = next(e for e in candidates if float(e.get("final_payable_days", 0) or 0) == 29)
        assert float(sample.get("working_days", 0) or 0) == 25, sample
        assert float(sample.get("weekoff_pay", 0) or 0) == 4, sample

    def test_future_dates_status_na_not_counted(self, payroll_july):
        rows = _rows(payroll_july)
        # Find an employee with attendance_details
        emp = next((e for e in rows if e.get("attendance_details")), None)
        assert emp, "no employee has attendance_details"
        details = emp["attendance_details"]
        by_date = {d.get("date"): d for d in details}
        for dt in ("30-07-2026", "31-07-2026"):
            assert dt in by_date, f"missing {dt} row"
            row = by_date[dt]
            assert str(row.get("status", "")).upper() == "NA", f"{dt} status={row.get('status')}"
            assert float(row.get("lop_value", 0) or 0) == 0
            assert float(row.get("weekoff_value", 0) or 0) == 0


# ---------- PREVIOUS MONTH (June 2026 full) ----------
class TestPreviousMonthJune:
    def test_active_zero_lop_payable_is_30(self, payroll_june):
        rows = _rows(payroll_june)
        assert rows
        candidates = [e for e in rows
                      if _is_active(e)
                      and float(e.get("lop", 0) or 0) == 0
                      and float(e.get("lop_days", 0) or 0) == 0]
        assert candidates
        payables = [float(e.get("final_payable_days", 0) or 0) for e in candidates]
        assert any(v == 30 for v in payables), f"Expected final_payable_days=30 for full June; got sample {payables[:10]}"


# ---------- FUTURE MONTH (August 2026) ----------
class TestFutureMonthAugust:
    def test_all_employees_zero(self, payroll_august):
        rows = _rows(payroll_august)
        assert rows
        bad = [(e.get("employee_id") or e.get("name"),
                e.get("final_payable_days"),
                e.get("working_days"),
                e.get("weekoff_pay"))
               for e in rows
               if float(e.get("final_payable_days", 0) or 0) != 0
               or float(e.get("working_days", 0) or 0) != 0
               or float(e.get("weekoff_pay", 0) or 0) != 0]
        assert not bad, f"Future month must be all zeros. Offenders: {bad[:10]}"


# ---------- LOP regression: Harshitha P July 2026 ----------
class TestHarshithaLop:
    def test_harshitha_july(self, payroll_july):
        rows = _rows(payroll_july)
        target = None
        for e in rows:
            nm = str(e.get("emp_name") or e.get("name") or e.get("employee_name") or "").strip().lower()
            if "harshitha" in nm and nm.startswith("harshitha"):
                target = e
                break
        assert target, "Harshitha P not found in July payroll"
        assert float(target.get("lop_days", 0) or 0) == 2.5, target
        assert float(target.get("final_payable_days", 0) or 0) == 8.5, target


# ---------- Formula holds: payable == working_days + weekoff_pay + oh_pay - lop ----------
class TestFormula:
    def test_formula_sampled(self, payroll_july):
        rows = _rows(payroll_july)
        assert rows
        checked = 0
        mismatches = []
        for e in rows[:25]:
            wd = float(e.get("working_days", 0) or 0)
            wo = float(e.get("weekoff_pay", 0) or 0)
            oh = float(e.get("oh_pay", 0) or 0)
            lop = float(e.get("lop", 0) or 0)
            payable = float(e.get("final_payable_days", 0) or 0)
            expected = wd + wo + oh - lop
            if abs(payable - expected) > 0.01:
                mismatches.append((e.get("name") or e.get("employee_id"),
                                   {"wd": wd, "wo": wo, "oh": oh, "lop": lop,
                                    "payable": payable, "expected": expected,
                                    "extra_pay": e.get("extra_pay")}))
            checked += 1
        assert checked > 0
        assert not mismatches, f"Formula mismatch in {len(mismatches)} rows: {mismatches[:5]}"

    def test_extra_pay_not_in_payable(self, payroll_july):
        rows = _rows(payroll_july)
        # At least confirm extra_pay field exists as a separate key
        for e in rows[:5]:
            assert "extra_pay" in e, f"extra_pay field missing on {e.get('name')}"
