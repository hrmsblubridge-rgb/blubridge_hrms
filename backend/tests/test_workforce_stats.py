"""Regression test for the additive 'workforce' block on /employees/stats.

Asserts existing keys remain intact (backward compatible) and that the
workforce distribution (Full-Time vs Intern, overall + per department)
reconciles with the active employee population.
"""
import httpx

API = "http://localhost:8001/api"
T = 60.0


def _token():
    r = httpx.post(f"{API}/auth/login", json={"username": "admin", "password": "HrAdmin786$"}, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_stats_backward_compatible_keys_present():
    h = {"Authorization": f"Bearer {_token()}"}
    d = httpx.get(f"{API}/employees/stats", headers=h, timeout=T).json()
    for k in ("total", "active", "inactive", "resigned", "by_department",
              "by_employment_type", "by_work_location"):
        assert k in d, f"missing legacy key {k}"


def test_workforce_block_reconciles():
    h = {"Authorization": f"Bearer {_token()}"}
    d = httpx.get(f"{API}/employees/stats", headers=h, timeout=T).json()
    wf = d["workforce"]
    bt = d["by_employment_type"]
    # Overall counts must match the existing by_employment_type aggregation.
    assert wf["full_time"] == bt.get("Full-time", 0)
    assert wf["intern"] == bt.get("Intern", 0)
    # Department sub-counts never exceed the overall.
    for dept in ("Research Unit", "Business & Product", "Support Staff"):
        assert dept in wf["by_department"]
        sub = wf["by_department"][dept]
        assert sub["full_time"] >= 0 and sub["intern"] >= 0
    sum_dept_ft = sum(v["full_time"] for v in wf["by_department"].values())
    sum_dept_intern = sum(v["intern"] for v in wf["by_department"].values())
    assert sum_dept_ft <= wf["full_time"]
    assert sum_dept_intern <= wf["intern"]
