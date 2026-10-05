"""Negative + positive RBAC probe (manual run, not pytest)."""
import json
import os
import sys
import urllib.error
import urllib.request

API = sys.argv[1].rstrip("/")


def _retry(fn, tries=5):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504):
                last = e
                import time as _t; _t.sleep(3)
                continue
            raise
        except Exception as e:
            last = e
            import time as _t; _t.sleep(3)
    raise last


def login(u, p):
    req = urllib.request.Request(
        f"{API}/api/auth/login", method="POST",
        data=json.dumps({"username": u, "password": p}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (rbac-probe)"})
    d = _retry(lambda: json.load(urllib.request.urlopen(req, timeout=90)))
    return d["token"], d.get("user", {})


def call(tok, path, method="GET"):
    req = urllib.request.Request(f"{API}/api{path}", method=method,
                                 headers={"Authorization": f"Bearer {tok}", "User-Agent": "Mozilla/5.0 (rbac-probe)"})
    for _ in range(4):
        try:
            r = urllib.request.urlopen(req, timeout=120)
            return r.status, r.read().decode()[:400000]
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504):
                import time as _t; _t.sleep(3)
                continue
            return e.code, e.read().decode()[:400]
    return 599, "gateway error"


EMP_PATHS = [
    "/dashboard/stats",
    "/leaves",
    "/employees/all",
    "/attendance?from_date=24-08-2026&to_date=28-08-2026",
    "/dashboard/leave-list",
    "/departments",
    "/teams",
    "/employee-avatars",
    "/dashboard/birthdays",
    "/employees",
    "/attendance/stats",
    "/payroll",
    "/reports/attendance",
    "/employees/autocomplete?q=a",
    "/star-rewards",
    "/onboarding/list",
]

emp_tok, emp_user = login(os.environ["EMP_USER"], os.environ["EMP_PASS"])
emp2_tok, emp2_user = login(os.environ["EMP2_USER"], os.environ["EMP2_PASS"])
adm_tok, adm_user = login(os.environ["ADM_USER"], os.environ["ADM_PASS"])
emp_id = emp_user.get("employee_id")
emp2_id = emp2_user.get("employee_id")
print(f"employee={emp_user.get('username')} id={emp_id}")
print(f"employee2={emp2_user.get('username')} id={emp2_id}")
print(f"admin={adm_user.get('username')} role={adm_user.get('role')}\n")

print("=== EMPLOYEE probes ===")
for p in EMP_PATHS:
    st, body = call(emp_tok, p)
    leak = ""
    if st == 200 and emp2_id:
        leak = " *** LEAK: contains other employee id ***" if emp2_id in body else ""
    print(f"{st}  {p:60s} len={len(body):7d}{leak}")

print("\n=== EMPLOYEE tries to override ownership ===")
for p in [f"/attendance?employee_id={emp2_id}&from_date=24-08-2026&to_date=28-08-2026",
          f"/leaves?employee_id={emp2_id}",
          f"/employees/{emp2_id}",
          f"/payroll/{emp2_id}",
          f"/employees/{emp2_id}/salary",
          f"/employees/{emp2_id}/documents"]:
    st, body = call(emp_tok, p)
    leak = " *** LEAK ***" if st == 200 and emp2_id and emp2_id in body else ""
    print(f"{st}  {p:70s} len={len(body):6d}{leak}")

print("\n=== ADMIN regression ===")
for p in EMP_PATHS + ["/teams/x", "/employees/stats"]:
    st, body = call(adm_tok, p)
    print(f"{st}  {p:60s} len={len(body)}")
