"""Payslip module regression tests — Phase 1 (templates, assignments, calc) & Phase 2 (generate, confirm, PDF, visibility)."""
import os
import time
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER, ADMIN_PASS = "admin", "HrAdmin786$"
EMP_USER, EMP_PASS = "user", "pass123"

# ----------------- Auth helpers -----------------

def _login(username, password):
    last = None
    for i in range(5):
        try:
            r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=90)
            if r.status_code == 200:
                tok = r.json().get("token")
                assert tok, f"no token: {r.json()}"
                return tok
            last = f"{r.status_code} {r.text[:200]}"
        except Exception as ex:
            last = str(ex)
        time.sleep(5)
    raise AssertionError(f"login failed for {username}: {last}")


@pytest.fixture(scope="session")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_USER, ADMIN_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def emp_headers():
    return {"Authorization": f"Bearer {_login(EMP_USER, EMP_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def rishi_emp_id(admin_headers):
    r = requests.get(f"{API}/employees", headers=admin_headers, params={"limit": 500}, timeout=60)
    assert r.status_code == 200
    lst = r.json().get("employees", [])
    for e in lst:
        if (e.get("full_name") or "").lower().startswith("rishi"):
            return e["id"]
    pytest.skip("Rishi employee not found")


@pytest.fixture(scope="session")
def older_joiner_ids(admin_headers):
    """Employees joined before 2026-05 — payroll available for May 2026."""
    r = requests.get(f"{API}/employees", headers=admin_headers, params={"limit": 500, "status": "Active"}, timeout=60)
    assert r.status_code == 200
    lst = r.json().get("employees", [])
    ids = []
    for e in lst:
        doj = e.get("date_of_joining") or ""
        if doj and doj < "2026-05-01":
            ids.append(e["id"])
    assert len(ids) >= 3, f"need at least 3 older joiners, got {len(ids)}"
    return ids


# ----------------- Cleanup tracker -----------------
_created = {"templates": [], "payslips_months": set()}
STATE = {}


@pytest.fixture(scope="session", autouse=True)
def cleanup(admin_headers):
    yield
    # delete generated payslips for tracked months
    for month in list(_created["payslips_months"]):
        try:
            g = requests.get(f"{API}/payslips/generated", headers=admin_headers, params={"month": month}, timeout=30)
            if g.status_code == 200:
                for s in g.json():
                    # unconfirm confirmed then delete
                    if s.get("status") == "confirmed":
                        requests.post(f"{API}/payslips/{s['id']}/unconfirm", headers=admin_headers, timeout=30)
                    requests.delete(f"{API}/payslips/{s['id']}", headers=admin_headers, timeout=30)
        except Exception as ex:
            print(f"cleanup payslip {month} failed: {ex}")
    # delete assignments (via mongo direct not available - close by re-assign or leave; API has no direct delete)
    # We instead null-out via mongo shell? Not possible from here. Best-effort: delete templates -> assignments block delete.
    # Unassign not exposed via API. Skip; note in report.
    # delete templates last: need to clear active assignments first — mongo direct via server not available.
    for tid in _created["templates"]:
        try:
            requests.delete(f"{API}/payslips/templates/{tid}", headers=admin_headers, timeout=30)
        except Exception:
            pass


# ================== PHASE 1 TESTS ==================

class TestTemplates:
    def test_create_template_ok(self, admin_headers):
        payload = {
            "name": f"TEST_STD_{int(time.time())}",
            "description": "TEST template",
            "status": "Active",
            "components": [
                {"name": "Basic", "component_type": "earning", "operation": "add", "calc_type": "percentage",
                 "percentage_value": 60, "calc_base": "monthly_pay", "proratable": True, "display_order": 0},
                {"name": "HRA", "component_type": "earning", "operation": "add", "calc_type": "percentage",
                 "percentage_value": 40, "calc_base": "Basic", "proratable": True, "display_order": 1},
                {"name": "PF", "component_type": "deduction", "operation": "deduct", "calc_type": "fixed",
                 "fixed_amount": 1800, "proratable": False, "display_order": 2},
                {"name": "Extra Pay", "component_type": "earning", "operation": "add",
                 "calc_type": "payroll_extra_pay", "display_order": 3},
            ],
        }
        r = requests.post(f"{API}/payslips/templates", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == payload["name"]
        assert len(doc["components"]) == 4
        assert doc["id"]
        _created["templates"].append(doc["id"])
        STATE['tpl_id'] = doc["id"]
        STATE['tpl_name'] = doc["name"]

    def test_empty_name_400(self, admin_headers):
        r = requests.post(f"{API}/payslips/templates",
                          json={"name": "", "components": [{"name": "X", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 100, "display_order": 0}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_no_components_400(self, admin_headers):
        r = requests.post(f"{API}/payslips/templates",
                          json={"name": f"TEST_EMPTY_{int(time.time())}", "components": []}, headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_duplicate_name_409(self, admin_headers):
        r = requests.post(f"{API}/payslips/templates",
                          json={"name": STATE['tpl_name'], "components": [
                              {"name": "X", "component_type": "earning", "operation": "add",
                               "calc_type": "fixed", "fixed_amount": 100, "display_order": 0}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 409

    def test_percentage_over_100_rejected(self, admin_headers):
        r = requests.post(f"{API}/payslips/templates",
                          json={"name": f"TEST_PCT_{int(time.time())}", "components": [
                              {"name": "X", "component_type": "earning", "operation": "add",
                               "calc_type": "percentage", "percentage_value": 150, "display_order": 0}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_duplicate_display_order_rejected(self, admin_headers):
        r = requests.post(f"{API}/payslips/templates",
                          json={"name": f"TEST_DUP_{int(time.time())}", "components": [
                              {"name": "A", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 10, "display_order": 0},
                              {"name": "B", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 20, "display_order": 0}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_list_templates(self, admin_headers):
        r = requests.get(f"{API}/payslips/templates", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        names = [t["name"] for t in r.json()]
        assert STATE['tpl_name'] in names

    def test_update_template(self, admin_headers):
        new_name = STATE['tpl_name'] + "_upd"
        r = requests.put(f"{API}/payslips/templates/{STATE['tpl_id']}",
                         json={"name": new_name}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        STATE['tpl_name'] = new_name


# ================== ASSIGNMENTS ==================

class TestAssignments:
    def test_single_assign(self, admin_headers, older_joiner_ids):
        emp_id = older_joiner_ids[0]
        r = requests.post(f"{API}/payslips/assignments",
                          json={"employee_id": emp_id, "template_id": STATE['tpl_id'],
                                "monthly_pay": 45000, "effective_from": "2025-01-01"},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["monthly_pay"] == 45000
        STATE['emp1'] = emp_id

    def test_reassign_closes_old(self, admin_headers):
        r = requests.post(f"{API}/payslips/assignments",
                          json={"employee_id": STATE['emp1'], "template_id": STATE['tpl_id'],
                                "monthly_pay": 50000, "effective_from": "2025-06-01"},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200
        h = requests.get(f"{API}/payslips/assignments/{STATE['emp1']}/history", headers=admin_headers, timeout=30)
        assert h.status_code == 200
        hist = h.json()
        assert len(hist) >= 2
        closed = [x for x in hist if x.get("effective_to")]
        assert closed, "old assignment not closed"

    def test_list_assignments(self, admin_headers):
        r = requests.get(f"{API}/payslips/assignments", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        me = [x for x in rows if x["id"] == STATE['emp1']]
        assert me and me[0]["assignment"]["monthly_pay"] == 50000

    def test_bulk_assign(self, admin_headers, older_joiner_ids):
        items = [{"employee_id": e, "monthly_pay": 40000 + i * 1000}
                 for i, e in enumerate(older_joiner_ids[1:3])]
        r = requests.post(f"{API}/payslips/assignments/bulk",
                          json={"template_id": STATE['tpl_id'], "items": items, "effective_from": "2025-01-01"},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["assigned"] == len(items)

    def test_delete_template_in_use_409(self, admin_headers):
        r = requests.delete(f"{API}/payslips/templates/{STATE['tpl_id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 409


# ================== CALCULATION ==================

class TestCalculate:
    def test_calculate_may_2026(self, admin_headers):
        r = requests.post(f"{API}/payslips/calculate",
                          json={"employee_id": STATE['emp1'], "month": "2026-05"},
                          headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["monthly_pay"] == 50000
        assert d["calendar_days"] == 31
        # Basic = 60% × 50000 = 30000 (monthly), prorated by payable/31
        basic = next(c for c in d["components"] if c["name"] == "Basic")
        assert basic["monthly_amount"] == 30000.0
        # HRA = 40% of Basic monthly = 12000 monthly
        hra = next(c for c in d["components"] if c["name"] == "HRA")
        assert hra["monthly_amount"] == 12000.0
        # PF fixed non-proratable = 1800 always
        pf = next(c for c in d["components"] if c["name"] == "PF")
        assert pf["amount"] == 1800.0
        assert pf["monthly_amount"] == 1800.0
        # Net = gross - deductions
        assert d["net_pay"] == round(d["gross_earnings"] - d["total_deductions"], 2)

    def test_calculate_bad_month(self, admin_headers):
        r = requests.post(f"{API}/payslips/calculate",
                          json={"employee_id": STATE['emp1'], "month": "bad"}, headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ================== PHASE 2: GENERATE & CONFIRM ==================

class TestGenerateConfirm:
    def test_generate_may_2026(self, admin_headers):
        _created["payslips_months"].add("2026-05")
        r = requests.post(f"{API}/payslips/generate",
                          json={"month": "2026-05", "employee_ids": [STATE['emp1']]},
                          headers=admin_headers, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["generated"] >= 1
        assert d["month"] == "2026-05"

    def test_list_generated(self, admin_headers):
        r = requests.get(f"{API}/payslips/generated", headers=admin_headers,
                         params={"month": "2026-05"}, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        mine = [s for s in rows if s["employee_id"] == STATE['emp1']]
        assert mine and mine[0]["status"] == "draft"
        assert "calc" in mine[0] and "payroll_meta" in mine[0]
        STATE['slip_id'] = mine[0]["id"]

    def test_confirm_slip(self, admin_headers):
        r = requests.post(f"{API}/payslips/{STATE['slip_id']}/confirm", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # verify status
        g = requests.get(f"{API}/payslips/generated", headers=admin_headers, params={"month": "2026-05"}, timeout=30)
        s = next(x for x in g.json() if x["id"] == STATE['slip_id'])
        assert s["status"] == "confirmed"

    def test_regenerate_skips_confirmed(self, admin_headers):
        r = requests.post(f"{API}/payslips/generate",
                          json={"month": "2026-05", "employee_ids": [STATE['emp1']]},
                          headers=admin_headers, timeout=90)
        assert r.status_code == 200
        assert r.json()["skipped_confirmed"] >= 1

    def test_delete_confirmed_409(self, admin_headers):
        r = requests.delete(f"{API}/payslips/{STATE['slip_id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 409

    def test_unconfirm(self, admin_headers):
        r = requests.post(f"{API}/payslips/{STATE['slip_id']}/unconfirm", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_confirm_all(self, admin_headers):
        r = requests.post(f"{API}/payslips/confirm-all", json={"month": "2026-05"},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["confirmed"] >= 1

    def test_pdf_download(self, admin_headers):
        r = requests.get(f"{API}/payslips/{STATE['slip_id']}/pdf", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# ================== EMPLOYEE VISIBILITY & RBAC ==================

class TestEmployeeVisibility:
    def test_my_payslips_visibility(self, emp_headers, admin_headers, rishi_emp_id):
        # assign template to Rishi and generate for 2026-05 (should be visible today)
        requests.post(f"{API}/payslips/assignments",
                      json={"employee_id": rishi_emp_id, "template_id": STATE['tpl_id'],
                            "monthly_pay": 45000, "effective_from": "2025-01-01"},
                      headers=admin_headers, timeout=30)
        _created["payslips_months"].add("2026-05")
        _created["payslips_months"].add("2026-08")
        # May 2026 — should become visible (today is post Jun 5 2026)
        g1 = requests.post(f"{API}/payslips/generate",
                           json={"month": "2026-05", "employee_ids": [rishi_emp_id]},
                           headers=admin_headers, timeout=90)
        assert g1.status_code == 200, g1.text
        # confirm rishi's may slip
        list_may = requests.get(f"{API}/payslips/generated", headers=admin_headers, params={"month": "2026-05"}, timeout=30).json()
        rmay = next((s for s in list_may if s["employee_id"] == rishi_emp_id), None)
        if rmay:
            requests.post(f"{API}/payslips/{rmay['id']}/confirm", headers=admin_headers, timeout=30)
        # Aug 2026 — even if confirmed, publish gate = Sep 5 2026, must be HIDDEN if today < Sep 5
        g2 = requests.post(f"{API}/payslips/generate",
                           json={"month": "2026-08", "employee_ids": [rishi_emp_id]},
                           headers=admin_headers, timeout=90)
        # Aug may or may not produce (depending on payroll); if produced confirm it
        if g2.status_code == 200 and g2.json().get("generated"):
            aug = requests.get(f"{API}/payslips/generated", headers=admin_headers, params={"month": "2026-08"}, timeout=30).json()
            raug = next((s for s in aug if s["employee_id"] == rishi_emp_id), None)
            if raug:
                requests.post(f"{API}/payslips/{raug['id']}/confirm", headers=admin_headers, timeout=30)

        my = requests.get(f"{API}/payslips/my", headers=emp_headers, timeout=30)
        assert my.status_code == 200
        months = [s["month"] for s in my.json()]
        # check that any returned months satisfy today >= 5th of following month
        today = datetime.now().date()
        for m in months:
            y, mo = int(m[:4]), int(m[5:7])
            ny, nm = (y + 1, 1) if mo == 12 else (y, mo + 1)
            from datetime import date as _d
            assert today >= _d(ny, nm, 5), f"month {m} shown but publish date not reached"
        # draft should never appear — no draft assertion needed since we only confirm

    def test_employee_forbidden_on_admin_endpoints(self, emp_headers):
        for path, method in [("/payslips/templates", "get"),
                              ("/payslips/assignments", "get"),
                              ("/payslips/generated?month=2026-05", "get")]:
            r = getattr(requests, method)(f"{API}{path}", headers=emp_headers, timeout=30)
            assert r.status_code == 403, f"{path} returned {r.status_code}"
        r = requests.post(f"{API}/payslips/generate", json={"month": "2026-05"}, headers=emp_headers, timeout=30)
        assert r.status_code == 403
