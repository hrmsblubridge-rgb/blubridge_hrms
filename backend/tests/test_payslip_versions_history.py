# Effective-dated template versions, historical assignments, auto-reconcile, employer PF & gratuity.
import os
import sys
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
load_dotenv('/app/frontend/.env')
sys.path.insert(0, '/app/backend')
from fastapi import HTTPException  # noqa: E402
from payslip_module import compute_payslip  # noqa: E402

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


def pc(n, p, o):
    return {"name": n, "component_type": "earning", "operation": "add", "calc_type": "percentage", "percentage_value": p, "display_order": o}


def comps(special=15.0):
    return [pc("Basic Pay", 37.5, 0), pc("HRA", 18.75, 1), pc("LTA", 5, 2), pc("Phone & Internet Reimbursement", 2.5, 3),
            pc("Bonus", 5, 4), pc("Stay & Travel Allowance", 10, 5), pc("Special Allowance", special, 6), pc("Food Reimbursement", 6.25, 7),
            {"name": "Other Allowance", "component_type": "earning", "operation": "add", "calc_type": "payroll_extra_pay", "display_order": 8},
            {"name": "Other Deduction", "component_type": "deduction", "operation": "deduct", "calc_type": "fixed", "fixed_amount": 500, "proratable": False, "display_order": 9}]


PF = {"enabled": True, "percentage": 12, "max_amount": 3000, "components": ["Basic Pay"]}
GR = {"enabled": True, "amount": 793, "prorate": True}


def line(r, n):
    return next(x for x in r["components"] if x["name"] == n)


class TestEngine:
    def test_full_month_reconciles_exactly(self):
        r = compute_payslip(44000, comps(), "2026-09", 30, 0, pf_config=PF)
        assert r["reconciliation"]["gross_template_total"] == 44000
        assert r["gross_earnings"] == 44000 and line(r, "PF")["amount"] == 1980  # 16500 × 12%

    def test_auto_reconcile_normalizes(self):
        r = compute_payslip(44000, comps(special=9.0), "2026-09", 30, 0, pf_config=PF, auto_reconcile=True)
        earn = [x for x in r["components"] if x["operation"] == "add" and x["calc_type"] == "percentage"]
        assert round(sum(x["monthly_amount"] for x in earn), 2) == 44000
        assert r["gross_earnings"] == 44000

    def test_strict_mismatch_errors(self):
        with pytest.raises(HTTPException) as ei:
            compute_payslip(44000, comps(special=9.0), "2026-09", 30, 0, pf_config=PF)
        assert "Auto Reconcile" in ei.value.detail

    def test_fixed_exceeds_gross(self):
        c = [{"name": "Basic Pay", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 45000, "display_order": 0}]
        with pytest.raises(HTTPException) as ei:
            compute_payslip(44000, c, "2026-09", 30, 0, pf_config=PF, auto_reconcile=True)
        assert "exceeds" in ei.value.detail

    def test_lop_gratuity_employer_pf(self):
        r = compute_payslip(44000, comps(), "2026-07", 26, 0, pf_config=PF, employer_pf_config=PF, gratuity_config=GR)
        assert r["regular_gross_payable"] == 36903.23
        er = {e["name"]: e["amount"] for e in r["employer_contributions"]}
        assert er["Gratuity (Employer Provision)"] == 665.10
        assert er["Employer PF Contribution"] == line(r, "PF")["amount"]
        assert r["net_pay"] == round(r["gross_earnings"] - line(r, "PF")["amount"] - 500, 2)

    def test_extra_pay_separate(self):
        r = compute_payslip(44000, comps(), "2026-09", 30, 2, pf_config=PF)
        assert r["regular_gross_payable"] == 44000 and r["gross_earnings"] == round(44000 + 44000 / 30 * 2, 2)
        assert line(r, "PF")["amount"] == 1980


@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    r = ss.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "pass123"})
    if r.status_code != 200:
        pytest.skip("login failed")
    ss.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    assert ss.post(f"{BASE_URL}/api/payslip-security/verify", json={"code": "082026"}).status_code == 200
    return ss


@pytest.fixture(scope="module")
def mdb():
    from pymongo import MongoClient
    return MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]


def mk_tpl(s, tag, cap):
    r = s.post(f"{BASE_URL}/api/payslips/templates", json={"name": f"TEST_VH_{tag}_{uuid.uuid4().hex[:5]}", "status": "Active",
               "components": comps(), "pf_config": {**PF, "max_amount": cap}})
    assert r.status_code == 200, r.text
    return r.json()["id"]


class TestVersionsAndHistory:
    def test_flow(self, s, mdb):
        eid = f"TEST_VH_emp_{uuid.uuid4().hex[:6]}"
        mdb.employees.insert_one({"id": eid, "full_name": "TEST_VH_Employee", "custom_employee_id": "TEST_VH_001",
                                  "employee_status": "Active", "is_deleted": False, "date_of_joining": "2026-01-15",
                                  "confirmation_date": "2026-07-10", "department": "Research", "employment_type": "Full-time"})
        a = mk_tpl(s, "A", 1800)
        b = mk_tpl(s, "B", 1800)
        # B gets version 2 from Sep 2026 with ₹3,000 cap; base version untouched
        r = s.put(f"{BASE_URL}/api/payslips/templates/{b}", json={"new_version_from": "2026-09", "pf_config": PF})
        assert r.status_code == 200, r.text
        assert s.put(f"{BASE_URL}/api/payslips/templates/{b}", json={"new_version_from": "2026-09", "pf_config": PF}).status_code == 409
        t = next(x for x in s.get(f"{BASE_URL}/api/payslips/templates").json() if x["id"] == b)
        assert t["pf_config"]["max_amount"] == 1800 and t["versions"][0]["pf_config"]["max_amount"] == 3000
        # Assign B ongoing from Sep 2026, then A historically Jan–Aug 2026
        r = s.post(f"{BASE_URL}/api/payslips/assignments", json={"employee_id": eid, "template_id": b, "monthly_pay": 50000,
                   "effective_from_type": "custom_month", "effective_from": "2026-09"})
        assert r.status_code == 200, r.text
        bad = s.post(f"{BASE_URL}/api/payslips/assignments", json={"employee_id": eid, "template_id": a, "monthly_pay": 44000,
                     "effective_from_type": "joining_date", "effective_to_month": "2026-09"})
        assert bad.status_code == 409, bad.text
        inv = s.post(f"{BASE_URL}/api/payslips/assignments", json={"employee_id": eid, "template_id": a, "monthly_pay": 44000,
                     "effective_from_type": "custom_month", "effective_from": "2026-09", "effective_to_month": "2026-08"})
        assert inv.status_code == 400
        r = s.post(f"{BASE_URL}/api/payslips/assignments", json={"employee_id": eid, "template_id": a, "monthly_pay": 44000,
                   "effective_from_type": "joining_date", "effective_to_month": "2026-08"})
        assert r.status_code == 200, r.text
        assert r.json()["effective_from_month"] == "2026-01"
        hist = s.get(f"{BASE_URL}/api/payslips/assignments/{eid}/history").json()
        assert len(hist) == 2
        # Preview per month uses that month's assignment, salary and version
        aug = s.post(f"{BASE_URL}/api/payslips/calculate", json={"employee_id": eid, "month": "2026-08"}).json()
        sep = s.post(f"{BASE_URL}/api/payslips/calculate", json={"employee_id": eid, "month": "2026-09"}).json()
        assert aug["template_id"] == a and aug["monthly_pay"] == 44000 and aug["reconciliation"]["pf_max_amount"] == 1800
        assert sep["template_id"] == b and sep["monthly_pay"] == 50000 and sep["reconciliation"]["pf_max_amount"] == 3000
        assert sep["template_version"]["version_no"] == 2
        dec25 = s.post(f"{BASE_URL}/api/payslips/calculate", json={"employee_id": eid, "month": "2025-12"})
        assert dec25.status_code == 400 and "No Payslip Template assignment" in dec25.json()["detail"]
        # Generate a past month == preview; confirm; new version must not change it
        g = s.post(f"{BASE_URL}/api/payslips/generate", json={"month": "2026-08", "employee_ids": [eid]}).json()
        assert g["generated"] == 1, g
        slip = next(x for x in s.get(f"{BASE_URL}/api/payslips/generated", params={"month": "2026-08"}).json() if x["employee_id"] == eid)
        assert slip["calc"]["net_pay"] == aug["net_pay"] and slip["template_snapshot"]["pf_config"]["max_amount"] == 1800
        assert s.post(f"{BASE_URL}/api/payslips/{slip['id']}/confirm").status_code == 200
        assert s.put(f"{BASE_URL}/api/payslips/templates/{a}", json={"new_version_from": "2026-05", "pf_config": {**PF, "percentage": 5}}).status_code == 200
        g2 = s.post(f"{BASE_URL}/api/payslips/generate", json={"month": "2026-08", "employee_ids": [eid]}).json()
        assert g2["skipped_confirmed"] == 1
        slip2 = next(x for x in s.get(f"{BASE_URL}/api/payslips/generated", params={"month": "2026-08"}).json() if x["employee_id"] == eid)
        assert slip2["calc"]["net_pay"] == slip["calc"]["net_pay"]
        # Period edit: overlap rejected, valid change accepted
        hist = s.get(f"{BASE_URL}/api/payslips/assignments/{eid}/history").json()
        a_row = next(h for h in hist if h["template_id"] == a)
        assert s.put(f"{BASE_URL}/api/payslips/assignments/{a_row['id']}/period", json={"effective_from_month": "2026-01", "effective_to_month": "2026-10"}).status_code == 409
        assert s.put(f"{BASE_URL}/api/payslips/assignments/{a_row['id']}/period", json={"effective_from_month": "2026-02", "effective_to_month": "2026-08"}).status_code == 200
        jan = s.post(f"{BASE_URL}/api/payslips/calculate", json={"employee_id": eid, "month": "2026-01"})
        assert jan.status_code == 400

    def test_config_validation(self, s):
        name = f"TEST_VH_val_{uuid.uuid4().hex[:5]}"
        gr_ded = comps() + [{"name": "Gratuity", "component_type": "deduction", "operation": "deduct", "calc_type": "fixed", "fixed_amount": 793, "display_order": 10}]
        r = s.post(f"{BASE_URL}/api/payslips/templates", json={"name": name, "components": gr_ded, "pf_config": PF, "gratuity_config": GR})
        assert r.status_code == 400 and "Gratuity" in r.json()["detail"]
        r = s.post(f"{BASE_URL}/api/payslips/templates", json={"name": name, "components": comps(), "gratuity_config": GR})
        assert r.status_code == 400
        r = s.post(f"{BASE_URL}/api/payslips/templates", json={"name": name, "components": comps(), "pf_config": PF,
                   "employer_pf_config": {**PF, "components": ["Nope"]}})
        assert r.status_code == 400 and "Employer PF" in r.json()["detail"]
