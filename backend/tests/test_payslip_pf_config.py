# Configurable template-level PF (pf_config) — engine unit tests + API tests + preview/generate consistency.
import os
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
load_dotenv('/app/frontend/.env')
import sys
sys.path.insert(0, '/app/backend')
from fastapi import HTTPException  # noqa: E402
from payslip_module import compute_payslip  # noqa: E402

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
MONTH = '2026-09'


def comps(other_ded=True, pf_comp=True, special=2000):
    c = [
        {"name": "Basic", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 20000, "display_order": 0},
        {"name": "DA", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 10000, "display_order": 1},
        {"name": "HRA", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 7000, "display_order": 2},
        {"name": "Phone Allowance", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 3000, "display_order": 3},
        {"name": "Food Allowance", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": 2000, "display_order": 4},
        {"name": "Special Allowance", "component_type": "earning", "operation": "add", "calc_type": "fixed", "fixed_amount": special, "display_order": 5},
    ]
    if pf_comp:
        c.append({"name": "PF", "component_type": "deduction", "operation": "deduct", "calc_type": "percentage", "percentage_value": 12, "display_order": 6})
    if other_ded:
        c.append({"name": "Other Deduction", "component_type": "deduction", "operation": "deduct", "calc_type": "fixed", "fixed_amount": 500, "proratable": False, "display_order": 7})
    return c


PFC = {"enabled": True, "percentage": 12, "max_amount": 3000, "components": ["Basic", "DA"]}


def line(r, n):
    return next(l for l in r["components"] if l["name"] == n)


# ---------- Engine ----------
class TestEngine:
    def test_full_month(self):
        r = compute_payslip(44000, comps(), MONTH, 30, 0, pf_config=PFC)
        assert line(r, "PF")["amount"] == 3000
        assert r["gross_earnings"] == 44000
        assert r["total_deductions"] == 3500
        assert r["net_pay"] == 40500

    def test_25_days(self):
        r = compute_payslip(44000, comps(), MONTH, 25, 0, pf_config=PFC)
        assert line(r, "PF")["amount"] == 3000  # 25000*12% = 3000

    def test_24_days(self):
        r = compute_payslip(44000, comps(), MONTH, 24, 0, pf_config=PFC)
        exp = {"Basic": 16000, "DA": 8000, "HRA": 5600, "Phone Allowance": 2400, "Food Allowance": 1600, "Special Allowance": 1600}
        for k, v in exp.items():
            assert line(r, k)["amount"] == v, k
        assert r["gross_earnings"] == 35200
        assert line(r, "PF")["amount"] == 2880
        assert r["net_pay"] == 31820

    def test_20_days(self):
        r = compute_payslip(44000, comps(), MONTH, 20, 0, pf_config=PFC)
        assert line(r, "PF")["amount"] == 2400

    def test_0_days(self):
        r = compute_payslip(44000, comps(), MONTH, 0, 0, pf_config=PFC)
        assert line(r, "PF")["amount"] == 0

    def test_pct10_max2500(self):
        cfg = {**PFC, "percentage": 10, "max_amount": 2500}
        assert line(compute_payslip(44000, comps(), MONTH, 30, 0, pf_config=cfg), "PF")["amount"] == 2500
        assert line(compute_payslip(44000, comps(), MONTH, 24, 0, pf_config=cfg), "PF")["amount"] == 2400
        assert line(compute_payslip(44000, comps(), MONTH, 15, 0, pf_config=cfg), "PF")["amount"] == 1500

    def test_disabled(self):
        r = compute_payslip(44000, comps(), MONTH, 30, 0, pf_config={"enabled": False})
        assert line(r, "PF")["amount"] == 0
        assert r["net_pay"] == 43500

    def test_legacy(self):
        r = compute_payslip(44000, comps(), MONTH, 30, 0)
        assert line(r, "PF")["amount"] == 1800
        assert "pf_model" not in r["reconciliation"]

    def test_reconciliation_mismatch(self):
        with pytest.raises(HTTPException) as ei:
            compute_payslip(44000, comps(special=0), MONTH, 30, 0, pf_config=PFC)
        assert ei.value.status_code == 400
        assert "Gross" in ei.value.detail

    def test_reconciliation_within_1(self):
        r = compute_payslip(44000.5, comps(), MONTH, 30, 0, pf_config=PFC)
        assert line(r, "PF")["amount"] == 3000

    def test_synthetic_pf_line(self):
        r = compute_payslip(44000, comps(pf_comp=False), MONTH, 24, 0, pf_config=PFC)
        pf = [l for l in r["components"] if l["name"] == "PF"]
        assert len(pf) == 1 and pf[0]["amount"] == 2880 and pf[0]["operation"] == "deduct"
        assert r["total_deductions"] == 3380

    def test_extra_pay_not_in_pf_base(self):
        c = comps() + [{"name": "Extra Pay", "component_type": "earning", "operation": "add", "calc_type": "payroll_extra_pay", "display_order": 8}]
        r = compute_payslip(44000, c, MONTH, 20, 3, pf_config=PFC)
        assert line(r, "PF")["amount"] == 2400
        assert r["other_allowance"] == round(44000 / 30 * 3, 2)
        assert r["net_pay"] == round(r["gross_earnings"] - 2400 - 500, 2)

    def test_rounding_half_up(self):
        # 23 days: Basic+DA payable = 30000*23/30 = 23000 → 2760 exact; use 12.5% on 7 days: 7000*12.5% = 875
        cfg = {**PFC, "percentage": 12.5}
        r = compute_payslip(44000, comps(), MONTH, 7, 0, pf_config=cfg)
        assert line(r, "PF")["amount"] == 875


# ---------- API ----------
@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    ss.headers.update({"User-Agent": "Mozilla/5.0 (pf-tests)"})
    r = ss.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "pass123"})
    if r.status_code != 200:
        pytest.skip("login failed")
    ss.headers.update({"Authorization": f"Bearer {r.json()['token']}", "User-Agent": "Mozilla/5.0 (pf-tests)"})
    v = ss.post(f"{BASE_URL}/api/payslip-security/verify", json={"code": "082026"})
    assert v.status_code == 200, v.text
    return ss


def tpl_payload(name, pf=None, c=None):
    p = {"name": name, "description": "TEST_PF_", "status": "Active", "components": c or comps()}
    if pf is not None:
        p["pf_config"] = pf
    return p


class TestTemplateAPI:
    def test_create_valid_and_persist(self, s):
        r = s.post(f"{BASE_URL}/api/payslips/templates", json=tpl_payload(f"TEST_PF_valid_{uuid.uuid4().hex[:6]}", PFC))
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        t = next(t for t in s.get(f"{BASE_URL}/api/payslips/templates").json() if t["id"] == tid)
        assert t["pf_config"] == {"enabled": True, "percentage": 12.0, "max_amount": 3000.0, "components": ["Basic", "DA"]}

    @pytest.mark.parametrize("bad", [
        {**PFC, "percentage": 0}, {**PFC, "percentage": 150}, {**PFC, "max_amount": 0},
        {**PFC, "components": []}, {**PFC, "components": ["Nope"]}, {**PFC, "components": ["Other Deduction"]},
        {**PFC, "components": ["PF"]}, {**PFC, "percentage": "abc"},
    ])
    def test_create_invalid(self, s, bad):
        r = s.post(f"{BASE_URL}/api/payslips/templates", json=tpl_payload(f"TEST_PF_bad_{uuid.uuid4().hex[:6]}", bad))
        assert r.status_code == 400, r.text

    def test_update_remove_selected_component(self, s):
        r = s.post(f"{BASE_URL}/api/payslips/templates", json=tpl_payload(f"TEST_PF_upd_{uuid.uuid4().hex[:6]}", PFC))
        tid = r.json()["id"]
        no_da = [c for c in comps() if c["name"] != "DA"]
        r = s.put(f"{BASE_URL}/api/payslips/templates/{tid}", json={"components": no_da})
        assert r.status_code == 400 and "DA" in r.json()["detail"]
        r = s.put(f"{BASE_URL}/api/payslips/templates/{tid}", json={"components": no_da, "pf_config": PFC})
        assert r.status_code == 400
        r = s.put(f"{BASE_URL}/api/payslips/templates/{tid}", json={"components": no_da, "pf_config": {**PFC, "components": ["Basic"]}})
        assert r.status_code == 200
        # pf_config only update
        r = s.put(f"{BASE_URL}/api/payslips/templates/{tid}", json={"pf_config": {**PFC, "percentage": 10, "max_amount": 2500, "components": ["Basic", "HRA"]}})
        assert r.status_code == 200
        t = next(t for t in s.get(f"{BASE_URL}/api/payslips/templates").json() if t["id"] == tid)
        assert t["pf_config"]["percentage"] == 10 and t["pf_config"]["components"] == ["Basic", "HRA"]
        assert len(t["components"]) == len(no_da)

    def test_legacy_untouched(self, s):
        r = s.post(f"{BASE_URL}/api/payslips/templates", json=tpl_payload(f"TEST_PF_legacy_{uuid.uuid4().hex[:6]}"))
        tid = r.json()["id"]
        r = s.put(f"{BASE_URL}/api/payslips/templates/{tid}", json={"description": "TEST_PF_changed"})
        assert r.status_code == 200
        t = next(t for t in s.get(f"{BASE_URL}/api/payslips/templates").json() if t["id"] == tid)
        assert "pf_config" not in t and t["description"] == "TEST_PF_changed"


class TestPreviewGenerate:
    def test_consistency_and_confirmed(self, s):
        from pymongo import MongoClient
        db = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
        eid = f"TEST_PF_emp_{uuid.uuid4().hex[:8]}"
        db.employees.insert_one({"id": eid, "full_name": "TEST_PF_Employee", "custom_employee_id": "TEST_PF_001",
                                 "employee_status": "Active", "is_deleted": False, "date_of_joining": "2025-01-01",
                                 "department": "Research", "team": "TEST_PF_team", "employment_type": "Full-time",
                                 "email": "test_pf_emp@example.invalid"})
        r = s.post(f"{BASE_URL}/api/payslips/templates", json=tpl_payload(f"TEST_PF_gen_{uuid.uuid4().hex[:6]}", PFC))
        tid = r.json()["id"]
        r = s.post(f"{BASE_URL}/api/payslips/assignments", json={"employee_id": eid, "template_id": tid, "monthly_pay": 44000,
                                                              "effective_from_type": "custom_date", "effective_from": "2026-01-01"})
        assert r.status_code == 200, r.text
        p = s.post(f"{BASE_URL}/api/payslips/calculate", json={"employee_id": eid, "month": MONTH})
        assert p.status_code == 200, p.text
        prev = p.json()
        print("payable", prev["payable_days"], "pf", line(prev, "PF")["amount"], prev["reconciliation"].get("pf_model"))
        assert prev["reconciliation"]["pf_model"] == "template_config"
        g = s.post(f"{BASE_URL}/api/payslips/generate", json={"month": MONTH, "employee_ids": [eid]})
        assert g.status_code == 200 and g.json()["generated"] == 1, g.text
        slip = next(x for x in s.get(f"{BASE_URL}/api/payslips/generated", params={"month": MONTH}).json() if x["employee_id"] == eid)
        assert line(slip["calc"], "PF")["amount"] == line(prev, "PF")["amount"]
        assert slip["calc"]["net_pay"] == prev["net_pay"]
        # confirm then change template & regenerate → unchanged
        assert s.post(f"{BASE_URL}/api/payslips/{slip['id']}/confirm").status_code == 200
        s.put(f"{BASE_URL}/api/payslips/templates/{tid}", json={"pf_config": {**PFC, "percentage": 5}})
        g2 = s.post(f"{BASE_URL}/api/payslips/generate", json={"month": MONTH, "employee_ids": [eid]})
        assert g2.json()["skipped_confirmed"] == 1
        slip2 = next(x for x in s.get(f"{BASE_URL}/api/payslips/generated", params={"month": MONTH}).json() if x["employee_id"] == eid)
        assert slip2["calc"]["net_pay"] == slip["calc"]["net_pay"] and slip2["status"] == "confirmed"
        # preview reflects new 5%
        p2 = s.post(f"{BASE_URL}/api/payslips/calculate", json={"employee_id": eid, "month": MONTH}).json()
        print("preview after 5%:", line(p2, "PF")["amount"])
