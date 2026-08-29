"""Payslip 6-digit authorization layer — functional probe."""
import json
import sys
import time
import urllib.error
import urllib.request

API = sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (payslip-probe)"}


def req(method, path, token=None, body=None):
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(API + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=headers)
    for _ in range(4):
        try:
            resp = urllib.request.urlopen(r, timeout=120)
            return resp.status, resp.read().decode()[:400]
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504):
                time.sleep(3)
                continue
            return e.code, e.read().decode()[:300]
    return 599, "gateway"


def login(u, p):
    st, body = req("POST", "/auth/login", body={"username": u, "password": p})
    assert st == 200, (st, body)
    return json.loads(body if len(body) > 300 else body)["token"] if False else json.loads(
        urllib.request.urlopen(urllib.request.Request(
            API + "/auth/login", method="POST",
            data=json.dumps({"username": u, "password": p}).encode(),
            headers={**UA, "Content-Type": "application/json"}), timeout=120).read()
    )["token"]


admin = login("admin", "HrAdmin786$")
emp = login("madhan.s", "Vigil@123")

PAYSLIP_PATHS = [
    ("GET", "/payslips/templates"),
    ("GET", "/payslips/assignments"),
    ("GET", "/payslips/generated?month=2026-07"),
    ("GET", "/payslips/adjustments/summary?month=2026-07"),
]

print("=== 1. admin BEFORE verification (expect 403 payslip_auth_required) ===")
for m, p in PAYSLIP_PATHS:
    st, b = req(m, p, admin)
    print(f"{st}  {m} {p}  {b[:90]}")

print("\n=== 2. status + wrong code + bad length ===")
print(req("GET", "/payslip-security/status", admin))
print("wrong  ->", req("POST", "/payslip-security/verify", admin, {"code": "111111"}))
print("short  ->", req("POST", "/payslip-security/verify", admin, {"code": "1234"}))

print("\n=== 3. verify with initial code 082026 ===")
print(req("POST", "/payslip-security/verify", admin, {"code": "082026"}))
print("status ->", req("GET", "/payslip-security/status", admin))

print("\n=== 4. admin AFTER verification (expect 200) ===")
for m, p in PAYSLIP_PATHS:
    st, b = req(m, p, admin)
    print(f"{st}  {m} {p}")

print("\n=== 5. employee token on admin payslip endpoints (expect 403, never salary) ===")
for m, p in PAYSLIP_PATHS + [("GET", "/payslip-security/status"), ("POST", "/payslip-security/regenerate")]:
    st, b = req(m, p, emp)
    print(f"{st}  {m} {p}  {b[:80]}")

print("\n=== 6. employee self payslips still work ===")
print(req("GET", "/payslips/my", emp))

print("\n=== 7. settings panel (never exposes the code) ===")
st, b = req("GET", "/payslip-security/settings", admin)
print(st, b)
assert "082026" not in b
