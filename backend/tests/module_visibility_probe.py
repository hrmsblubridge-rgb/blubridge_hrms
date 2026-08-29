"""Module Visibility — sidebar/API parity test.

Uses the real admin endpoints to reconfigure a module, then checks that the
employee visibility list AND the employee API agree for both an authorised and
an unauthorised employee. Restores the original configuration at the end.
"""
import json
import sys
import urllib.error
import urllib.request

API = sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (mv-probe)"}
MODULE = "payslips"


def call(method, path, token=None, body=None):
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
    if body is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(API + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers=h)
    try:
        resp = urllib.request.urlopen(r, timeout=120)
        return resp.status, resp.read().decode()[:600]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def login(u, p):
    d = json.loads(urllib.request.urlopen(urllib.request.Request(
        API + "/auth/login", method="POST",
        data=json.dumps({"username": u, "password": p}).encode(),
        headers={**UA, "Content-Type": "application/json"}), timeout=120).read())
    return d["token"], d["user"].get("employee_id")


def visible(token):
    st, b = call("GET", "/employee/module-visibility", token)
    return st, json.loads(b).get("visible_modules", []) if st == 200 else b


admin, _ = login("admin", "HrAdmin786$")
b_tok, b_id = login("madhan.s", "Vigil@123")
c_tok, c_id = login("dinesh.t", "Vigil@123")
print("employee B:", b_id, "| employee C:", c_id)

orig_setting = json.loads(call("GET", "/settings/module-visibility", admin)[1] if False else
                          urllib.request.urlopen(urllib.request.Request(
                              API + "/settings/module-visibility",
                              headers={**UA, "Authorization": f"Bearer {admin}"}), timeout=120).read().decode())
orig = next(m for m in orig_setting if m["module_key"] == MODULE)
orig_sel = json.loads(call("GET", f"/settings/module-visibility/{MODULE}/employees", admin)[1])["employee_ids"]
print("original:", orig["enabled"], orig["visibility_mode"], "selections:", len(orig_sel))

print("\n--- CASE 1: SELECTED_ONLY = [B] ---")
print("set selection:", call("PUT", f"/settings/module-visibility/{MODULE}/employees", admin, {"employee_ids": [b_id]})[0])
print("set mode:", call("PUT", f"/settings/module-visibility/{MODULE}", admin, {"visibility_mode": "SELECTED_ONLY", "enabled": True})[0])
print("B sees module in sidebar list:", MODULE in visible(b_tok)[1])
print("C sees module in sidebar list:", MODULE in visible(c_tok)[1], "(expect False)")
print("B API /payslips/my:", call("GET", "/payslips/my", b_tok)[0], "(expect 200)")
print("C API /payslips/my:", call("GET", "/payslips/my", c_tok), "(expect 403)")

print("\n--- CASE 2: ALL_EXCEPT_SELECTED = [C] ---")
print("set selection:", call("PUT", f"/settings/module-visibility/{MODULE}/employees", admin, {"employee_ids": [c_id]})[0])
print("set mode:", call("PUT", f"/settings/module-visibility/{MODULE}", admin, {"visibility_mode": "ALL_EXCEPT_SELECTED"})[0])
print("B in sidebar list:", MODULE in visible(b_tok)[1], "(expect True)")
print("C in sidebar list:", MODULE in visible(c_tok)[1], "(expect False)")
print("C API /payslips/my:", call("GET", "/payslips/my", c_tok)[0], "(expect 403)")

print("\n--- CASE 3: module OFF ---")
print("set:", call("PUT", f"/settings/module-visibility/{MODULE}", admin, {"enabled": False, "visibility_mode": "ALL"})[0])
print("B in sidebar list:", MODULE in visible(b_tok)[1], "(expect False)")
print("B API /payslips/my:", call("GET", "/payslips/my", b_tok)[0], "(expect 403)")
print("admin unaffected — /payslips/templates (needs payslip auth code, expect 403 payslip_auth_required or 200):",
      call("GET", "/payslips/templates", admin)[0])
print("admin module list still full:", len(visible(admin)[1]))

print("\n--- CASE 4: back to ALL ---")
print("set:", call("PUT", f"/settings/module-visibility/{MODULE}", admin, {"enabled": True, "visibility_mode": "ALL"})[0])
print("B in sidebar list:", MODULE in visible(b_tok)[1], "(expect True)")
print("C in sidebar list:", MODULE in visible(c_tok)[1], "(expect True)")
print("C API /payslips/my:", call("GET", "/payslips/my", c_tok)[0], "(expect 200)")

print("\n--- restore original configuration ---")
print(call("PUT", f"/settings/module-visibility/{MODULE}/employees", admin, {"employee_ids": orig_sel})[0])
print(call("PUT", f"/settings/module-visibility/{MODULE}", admin,
           {"enabled": orig["enabled"], "visibility_mode": orig["visibility_mode"]})[0])
