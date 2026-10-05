"""BRSF Iteration 73 — regression tests for the four new changes:

1. Completed-month control (backend guard on mutating endpoints)
2. P05/N04 weekly child overrides (0 or +/-1 only, parent aggregates)
3. N01 per-leave children with `applicable` + `leave_reason` + `key`
4. Month-effective active-employee eligibility

Runs against localhost:8001 (the preview URL blocks python-requests via Cloudflare).
Uses admin/HrAdmin786$ from /app/memory/test_credentials.md.

All probe writes are reverted in the same test / teardown_module.
"""
import os
from datetime import datetime

import pytest
import requests

API = os.environ.get("BRSF_API", "http://localhost:8001")

# "Today" per system prompt = 03-Sep-2026 (IST). August is latest completed month.
CURR_MONTH = "2026-09"
COMPLETED_MONTH = "2026-08"
FUTURE_MONTH = "2026-11"


def _login(u, p):
    r = requests.post(f"{API}/api/auth/login",
                      json={"username": u, "password": p}, timeout=90)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {u}: {r.status_code} {r.text[:120]}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def H():
    return _login("admin", "HrAdmin786$")


@pytest.fixture(scope="module")
def EH():
    return _login("user", "pass123")


# ============================================================
# 1. COMPLETED-MONTH GUARD
# ============================================================
class TestCompletedMonthGuard:
    def test_recalculate_current_month_rejected(self, H):
        r = requests.post(f"{API}/api/brsf/recalculate",
                          json={"month": CURR_MONTH}, headers=H, timeout=60)
        assert r.status_code == 400
        assert "completed month" in r.text.lower()
        assert "september" in r.text.lower()

    def test_recalculate_future_month_rejected(self, H):
        r = requests.post(f"{API}/api/brsf/recalculate",
                          json={"month": FUTURE_MONTH}, headers=H, timeout=60)
        assert r.status_code == 400
        assert "completed month" in r.text.lower()

    def test_recalculate_completed_month_accepted(self, H):
        # scope to a single employee to keep this test fast
        emps = requests.get(f"{API}/api/brsf/eligible-employees",
                            params={"month": COMPLETED_MONTH}, headers=H, timeout=60).json()["employees"]
        eid = emps[0]["id"]
        r = requests.post(f"{API}/api/brsf/recalculate",
                          json={"month": COMPLETED_MONTH, "employee_id": eid},
                          headers=H, timeout=180)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["success"] is True
        assert j["recalculated"] == 1

    def test_summary_reports_month_completed_flag(self, H):
        r = requests.get(f"{API}/api/brsf/summary",
                         params={"month": CURR_MONTH}, headers=H, timeout=60)
        assert r.status_code == 200
        assert r.json()["month_completed"] is False

        r2 = requests.get(f"{API}/api/brsf/summary",
                          params={"month": COMPLETED_MONTH}, headers=H, timeout=60)
        assert r2.status_code == 200
        assert r2.json()["month_completed"] is True

    def test_stars_endpoint_returns_month_completed(self, H):
        emps = requests.get(f"{API}/api/brsf/eligible-employees",
                            params={"month": CURR_MONTH}, headers=H, timeout=60).json()["employees"]
        assert emps
        eid = emps[0]["id"]
        r = requests.get(f"{API}/api/brsf/stars",
                         params={"employee_id": eid, "month": CURR_MONTH},
                         headers=H, timeout=120)
        assert r.status_code == 200
        j = r.json()
        assert j["month_completed"] is False
        # Each line has limits/validation shape from prior iterations
        assert len(j["lines"]) == 14

    def test_mutating_endpoints_blocked_on_current_month(self, H):
        """Every mutating line endpoint must 400 for a current-month line."""
        emps = requests.get(f"{API}/api/brsf/eligible-employees",
                            params={"month": CURR_MONTH}, headers=H, timeout=60).json()["employees"]
        eid = emps[0]["id"]
        lines = requests.get(f"{API}/api/brsf/stars",
                             params={"employee_id": eid, "month": CURR_MONTH},
                             headers=H, timeout=120).json()["lines"]
        line_by_code = {l["code"]: l for l in lines}

        p01 = line_by_code["P01"]  # automated, override target
        p02 = line_by_code["P02"]  # manual monthly/weekly
        p05 = line_by_code["P05"]  # child-driven
        n07 = line_by_code["N07"]  # instance

        endpoints = [
            ("PUT", f"/brsf/stars/{p01['id']}/override", {"value": 1}),
            ("POST", f"/brsf/stars/{p01['id']}/reset-override", {}),
            ("PUT", f"/brsf/stars/{p02['id']}/manual",
             {"entry_mode": "monthly", "value": 2}),
            ("POST", f"/brsf/stars/{n07['id']}/instances",
             {"value": -3, "date": f"{CURR_MONTH}-05", "reason": "t"}),
            ("PUT", f"/brsf/stars/{p05['id']}/child-override",
             {"key": "week:2026-09-07", "value": 1, "note": "t"}),
            ("POST", f"/brsf/stars/{p05['id']}/child-override/reset",
             {"key": "week:2026-09-07"}),
        ]
        for method, path, body in endpoints:
            r = requests.request(method, f"{API}/api{path}",
                                 json=body, headers=H, timeout=60)
            assert r.status_code == 400, f"{method} {path} => {r.status_code} {r.text[:120]}"
            assert "completed month" in r.text.lower(), \
                f"{path} rejected but wrong message: {r.text[:120]}"

    def test_import_blocked_on_current_month(self, H):
        # Build a minimal file: just export the current month (view allowed) and try to preview it back.
        exp = requests.get(f"{API}/api/brsf/export",
                           params={"month": CURR_MONTH, "format": "xlsx"},
                           headers=H, timeout=60)
        assert exp.status_code == 200  # export/view still works
        files = {"file": ("curr.xlsx", exp.content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/api/brsf/import/preview",
                          data={"month": CURR_MONTH}, files=files,
                          headers=H, timeout=90)
        assert r.status_code == 400
        assert "completed month" in r.text.lower()


# ============================================================
# 2. P05 WEEKLY CHILD OVERRIDE
# ============================================================
class TestP05WeeklyChildOverride:
    @pytest.fixture(scope="class")
    def p05(self, H):
        emps = requests.get(f"{API}/api/brsf/eligible-employees",
                            params={"month": COMPLETED_MONTH}, headers=H, timeout=60).json()["employees"]
        eid = emps[0]["id"]
        lines = requests.get(f"{API}/api/brsf/stars",
                             params={"employee_id": eid, "month": COMPLETED_MONTH},
                             headers=H, timeout=180).json()["lines"]
        p05 = next(l for l in lines if l["code"] == "P05")
        yield {"emp_id": eid, "line": p05}
        # teardown — clear any overrides we left behind
        for k in list((p05.get("child_overrides") or {}).keys()):
            requests.post(f"{API}/api/brsf/stars/{p05['id']}/child-override/reset",
                          json={"key": k}, headers=H, timeout=30)
        requests.post(f"{API}/api/brsf/stars/{p05['id']}/reset-override",
                      headers=H, timeout=30)

    def test_children_carry_stable_keys(self, p05):
        children = p05["line"].get("system_children") or []
        assert children, "P05 must have weekly children"
        for c in children:
            assert c.get("key", "").startswith("week:"), c
            assert "system_value" in c
            assert "final" in c

    def test_bogus_key_404(self, H, p05):
        r = requests.put(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override",
                         json={"key": "week:1999-01-01", "value": 1, "note": "x"},
                         headers=H, timeout=30)
        assert r.status_code == 404

    def test_invalid_values_rejected(self, H, p05):
        first_key = (p05["line"]["system_children"] or [{}])[0].get("key")
        assert first_key
        for bad in (2, -1, 0.5):
            r = requests.put(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override",
                             json={"key": first_key, "value": bad, "note": "t"},
                             headers=H, timeout=30)
            assert r.status_code == 400, f"value={bad} => {r.status_code}"

    def test_valid_override_flows_to_parent(self, H, p05):
        children = p05["line"]["system_children"] or []
        assert len(children) >= 2
        k1, k2 = children[0]["key"], children[1]["key"]
        base_final = p05["line"]["final_value"]
        base_sys = p05["line"].get("system_value") or 0

        # +1 on first week
        r = requests.put(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override",
                         json={"key": k1, "value": 1, "note": "test iter73"},
                         headers=H, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        # Verify parent reflects child aggregate
        assert j["child_aggregate"] is not None
        # Also confirm on GET
        lines = requests.get(f"{API}/api/brsf/stars",
                             params={"employee_id": p05["emp_id"], "month": COMPLETED_MONTH},
                             headers=H, timeout=120).json()["lines"]
        p05_now = next(l for l in lines if l["code"] == "P05")
        # child_aggregate is what parent uses when no parent override
        agg_after_one = p05_now["child_aggregate"]
        # The overridden week should show override=1, final=1
        child_after = next(c for c in p05_now["system_children"] if c["key"] == k1)
        assert child_after["override"] == 1
        assert child_after["final"] == 1

        # +1 on second week — aggregate should go up by 1
        r = requests.put(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override",
                         json={"key": k2, "value": 1, "note": "test iter73"},
                         headers=H, timeout=30)
        assert r.status_code == 200
        lines = requests.get(f"{API}/api/brsf/stars",
                             params={"employee_id": p05["emp_id"], "month": COMPLETED_MONTH},
                             headers=H, timeout=120).json()["lines"]
        p05_now = next(l for l in lines if l["code"] == "P05")
        assert p05_now["child_aggregate"] == agg_after_one + 1

        # Parent override wins over aggregate
        agg_two = p05_now["child_aggregate"]
        r = requests.put(f"{API}/api/brsf/stars/{p05['line']['id']}/override",
                         json={"value": 0, "reason": "iter73 parent"},
                         headers=H, timeout=30)
        assert r.status_code == 200
        pj = r.json()
        assert pj["final_value"] == 0
        assert pj["child_aggregate"] == agg_two  # aggregate preserved

        # Reset parent override -> back to aggregate
        r = requests.post(f"{API}/api/brsf/stars/{p05['line']['id']}/reset-override",
                          headers=H, timeout=30)
        assert r.status_code == 200
        assert r.json()["final_value"] == agg_two

        # Reset child override on k2 -> aggregate goes down by 1
        r = requests.post(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override/reset",
                          json={"key": k2}, headers=H, timeout=30)
        assert r.status_code == 200
        # Cleanup k1 too
        requests.post(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override/reset",
                      json={"key": k1}, headers=H, timeout=30)

    def test_child_override_survives_recalculate(self, H, p05):
        children = p05["line"]["system_children"] or []
        k = children[0]["key"]
        requests.put(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override",
                     json={"key": k, "value": 1, "note": "survive"}, headers=H, timeout=30)
        r = requests.post(f"{API}/api/brsf/recalculate",
                          json={"month": COMPLETED_MONTH,
                                "employee_id": p05["emp_id"]}, headers=H, timeout=120)
        assert r.status_code == 200
        lines = requests.get(f"{API}/api/brsf/stars",
                             params={"employee_id": p05["emp_id"], "month": COMPLETED_MONTH},
                             headers=H, timeout=120).json()["lines"]
        p05_now = next(l for l in lines if l["code"] == "P05")
        # no duplicate children
        keys = [c["key"] for c in p05_now["system_children"]]
        assert len(keys) == len(set(keys))
        # exactly 14 lines still
        assert len(lines) == 14
        # override preserved
        child = next(c for c in p05_now["system_children"] if c["key"] == k)
        assert child["override"] == 1
        # audit contains child-override entry
        aud = requests.get(f"{API}/api/brsf/audit",
                           params={"employee_id": p05["emp_id"], "month": COMPLETED_MONTH},
                           headers=H, timeout=60).json()
        entries = aud.get("audit") or aud.get("entries") or []
        assert any("child override" in (e.get("action") or "").lower()
                   and k in (e.get("action") or "") for e in entries), \
            f"Expected child-override audit entry for {k}"
        # cleanup
        requests.post(f"{API}/api/brsf/stars/{p05['line']['id']}/child-override/reset",
                      json={"key": k}, headers=H, timeout=30)


# ============================================================
# 3. N01 PER-LEAVE CHILDREN
# ============================================================
class TestN01LeaveChildren:
    @pytest.fixture(scope="class")
    def n01(self, H):
        # Find Adwaid Suresh (per agent notes) or any employee with leaves.
        emps = requests.get(f"{API}/api/brsf/eligible-employees",
                            params={"month": COMPLETED_MONTH}, headers=H, timeout=60).json()["employees"]
        adwaid = next((e for e in emps if "adwaid" in (e.get("full_name") or "").lower()), None)
        target = adwaid or emps[0]
        lines = requests.get(f"{API}/api/brsf/stars",
                             params={"employee_id": target["id"], "month": COMPLETED_MONTH},
                             headers=H, timeout=180).json()["lines"]
        n01 = next(l for l in lines if l["code"] == "N01")
        yield {"emp_id": target["id"], "line": n01, "name": target.get("full_name")}
        # cleanup any child overrides
        for k in list((n01.get("child_overrides") or {}).keys()):
            requests.post(f"{API}/api/brsf/stars/{n01['id']}/child-override/reset",
                          json={"key": k}, headers=H, timeout=30)

    def test_every_leave_is_listed(self, n01):
        children = n01["line"].get("system_children") or []
        # Adwaid Suresh Aug-2026 should have Preplanned + Paid + Emergency
        # We only assert the shape: keys, applicable flag exist
        if not children:
            pytest.skip(f"No leaves in {COMPLETED_MONTH} for {n01['name']}")
        for c in children:
            assert c.get("key", "").startswith("leave:"), c
            assert "applicable" in c
            assert "system_value" in c
            assert "final" in c
            # non-applicable children must have system_value == 0
            if c["applicable"] is False:
                assert (c.get("system_value") or 0) == 0

    def test_not_applicable_leave_rejects_override(self, H, n01):
        children = n01["line"].get("system_children") or []
        na = next((c for c in children if c.get("applicable") is False), None)
        if not na:
            pytest.skip("No non-applicable leave to test")
        r = requests.put(f"{API}/api/brsf/stars/{n01['line']['id']}/child-override",
                         json={"key": na["key"], "value": -1, "note": "t"},
                         headers=H, timeout=30)
        assert r.status_code == 400
        assert "not covered" in r.text.lower() or "n01" in r.text.lower()

    def test_applicable_leave_only_accepts_0_or_minus1(self, H, n01):
        children = n01["line"].get("system_children") or []
        applicable = next((c for c in children if c.get("applicable") is not False), None)
        if not applicable:
            pytest.skip("No applicable leave")
        for bad in (-2, 1, 0.5):
            r = requests.put(f"{API}/api/brsf/stars/{n01['line']['id']}/child-override",
                             json={"key": applicable["key"], "value": bad, "note": "t"},
                             headers=H, timeout=30)
            assert r.status_code == 400, f"value={bad} => {r.status_code}"

        # -1 should succeed
        base = requests.get(f"{API}/api/brsf/stars",
                            params={"employee_id": n01["emp_id"], "month": COMPLETED_MONTH},
                            headers=H, timeout=120).json()["lines"]
        p_final_before = next(l for l in base if l["code"] == "N01")["final_value"]

        r = requests.put(f"{API}/api/brsf/stars/{n01['line']['id']}/child-override",
                         json={"key": applicable["key"], "value": -1, "note": "iter73"},
                         headers=H, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        # parent aggregates the child final of -1
        assert j["child_aggregate"] is not None
        # reset
        r2 = requests.post(f"{API}/api/brsf/stars/{n01['line']['id']}/child-override/reset",
                           json={"key": applicable["key"]}, headers=H, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["final_value"] == p_final_before


# ============================================================
# 4. MONTH-EFFECTIVE ELIGIBILITY
# ============================================================
class TestMonthEffectiveEligibility:
    def test_counts_match_agent_probe(self, H):
        """Per main agent's probe: Jun=24, Jul=22, Aug=21, Sep=21."""
        expected = {"2026-06": 24, "2026-07": 22, "2026-08": 21, "2026-09": 21}
        for m, exp in expected.items():
            r = requests.get(f"{API}/api/brsf/eligible-employees",
                             params={"month": m}, headers=H, timeout=60)
            assert r.status_code == 200
            emps = r.json()["employees"]
            assert len(emps) == exp, f"{m}: got {len(emps)}, expected {exp}"

    def test_sai_rupesh_drops_after_july(self, H):
        def has(m, needle):
            emps = requests.get(f"{API}/api/brsf/eligible-employees",
                                params={"month": m}, headers=H, timeout=60).json()["employees"]
            return any(needle.lower() in (e.get("full_name") or "").lower() for e in emps)

        assert has("2026-06", "sai rupesh") is True, "Sai Rupesh must be eligible in June"
        assert has("2026-07", "sai rupesh") is False, "Sai Rupesh inactive 2026-07-15 — NOT eligible in Jul"
        assert has("2026-08", "sai rupesh") is False

    def test_anuj_kumar_drops_after_august(self, H):
        def has(m, needle):
            emps = requests.get(f"{API}/api/brsf/eligible-employees",
                                params={"month": m}, headers=H, timeout=60).json()["employees"]
            return any(needle.lower() in (e.get("full_name") or "").lower() for e in emps)

        assert has("2026-06", "anuj kumar") is True
        assert has("2026-07", "anuj kumar") is True
        assert has("2026-08", "anuj kumar") is False, "Anuj Kumar inactive 2026-08-07 — NOT eligible in Aug"

    def test_confirmation_month_gate(self, H):
        """Harshini V M, confirmed 08-Apr-2026: absent in March, present in April."""
        def has(m, needle):
            emps = requests.get(f"{API}/api/brsf/eligible-employees",
                                params={"month": m}, headers=H, timeout=60).json()["employees"]
            return any(needle.lower() in (e.get("full_name") or "").lower() for e in emps)

        assert has("2026-03", "harshini") is False
        assert has("2026-04", "harshini") is True

    def test_summary_matches_eligibility(self, H):
        for m in ("2026-06", "2026-07", "2026-08"):
            emps = requests.get(f"{API}/api/brsf/eligible-employees",
                                params={"month": m}, headers=H, timeout=60).json()["employees"]
            summ = requests.get(f"{API}/api/brsf/summary",
                                params={"month": m}, headers=H, timeout=90).json()
            assert len(summ["rows"]) == len(emps), f"{m}: summary rows != eligibility count"

    def test_export_respects_eligibility(self, H):
        """June must include Sai Rupesh; July/Aug must NOT."""
        for m, should_include in (("2026-06", True), ("2026-07", False), ("2026-08", False)):
            r = requests.get(f"{API}/api/brsf/export",
                             params={"month": m, "format": "csv"},
                             headers=H, timeout=90)
            assert r.status_code == 200, f"{m}: export {r.status_code}"
            body = r.text.lower()
            present = "sai rupesh" in body
            assert present == should_include, \
                f"{m}: Sai Rupesh present={present}, expected={should_include}"
