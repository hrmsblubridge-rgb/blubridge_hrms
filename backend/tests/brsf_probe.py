import json, sys, time, urllib.error, urllib.request
API = sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (brsf-probe)"}


def call(method, path, token=None, body=None):
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
    if body is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(API + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None, headers=h)
    for _ in range(4):
        try:
            resp = urllib.request.urlopen(r, timeout=240)
            return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504):
                time.sleep(5); continue
            return e.code, e.read().decode()[:300]
        except Exception as e:
            time.sleep(5)
            last = e
    return 599, f"gateway {last}"


tok = call("POST", "/auth/login", body={"username": "admin", "password": "HrAdmin786$"})[1]["token"]
MONTH = sys.argv[2] if len(sys.argv) > 2 else "2026-06"
st, d = call("GET", f"/brsf/eligible-employees?month={MONTH}", tok)
emps = d["employees"]
print(f"eligible ({MONTH}): {len(emps)}")
eid = emps[0]["id"]
st, d = call("GET", f"/brsf/stars?employee_id={eid}&month={MONTH}", tok)
print("stars status:", st)
if st != 200:
    print(d); sys.exit(1)
print("EMPLOYEE:", d["employee"]["full_name"], "| lines:", len(d["lines"]), "| totals:", d["totals"])
for l in d["lines"]:
    ch = l["system_children"] or l.get("instances") or l.get("weekly") or []
    print(f"{l['code']} {l['name'][:24]:<25} {l['type']:<9} {l['frequency']:<8} "
          f"sys={str(l['system_value']):>5} final={l['final_value']:>5} {l['status']:<19} children={len(ch)}")
p5 = next(l for l in d["lines"] if l["code"] == "P05")
print("P05 weeks:", [(c["week"], c["start"], c["end"], c["eligible_days"], c["avg_hhmm"], c["value"])
                     for c in p5["system_children"]])
n4 = next(l for l in d["lines"] if l["code"] == "N04")
print("N04 weeks:", [(c["week"], c["avg_hhmm"], c["value"]) for c in n4["system_children"]])
for code in ("P01", "N03", "N06", "P06"):
    l = next(x for x in d["lines"] if x["code"] == code)
    print(code, "->", l["system_value"], "|", l.get("system_note"), "| children:", l["system_children"][:3])

# ---- override + idempotency + manual entry + instances
n3 = next(l for l in d["lines"] if l["code"] == "N03")
print("\noverride N03 to 0:", call("PUT", f"/brsf/stars/{n3['id']}/override", tok,
                                   {"value": 0, "reason": "Evidence accepted"})[1].get("status"))
print("positive-value guard on N03:", call("PUT", f"/brsf/stars/{n3['id']}/override", tok, {"value": 2})[0], "(expect 400)")
p2 = next(l for l in d["lines"] if l["code"] == "P02")
print("P02 monthly +4:", call("PUT", f"/brsf/stars/{p2['id']}/manual", tok,
                              {"entry_mode": "monthly", "monthly_value": 4})[1]["final_value"])
print("P02 cap guard (+7):", call("PUT", f"/brsf/stars/{p2['id']}/manual", tok,
                                  {"entry_mode": "monthly", "monthly_value": 7})[0], "(expect 400)")
print("P02 weekly mode:", call("PUT", f"/brsf/stars/{p2['id']}/manual", tok,
                               {"entry_mode": "weekly",
                                "weekly": [{"week": i, "value": v} for i, v in enumerate([1, 1, 0, 1, 1], 1)]})[1]["final_value"], "(expect 4)")
n7 = next(l for l in d["lines"] if l["code"] == "N07")
r = call("POST", f"/brsf/stars/{n7['id']}/instances", tok, {"date": f"{MONTH}-02", "remarks": "No response by 10:30"})[1]
r2 = call("POST", f"/brsf/stars/{n7['id']}/instances", tok, {"date": f"{MONTH}-20", "remarks": "Unreachable"})[1]
print("N07 after 2 instances:", r2["final_value"], "(expect -6)")
inst_id = r2["instances"][0]["id"]
print("N07 after deleting 1:", call("DELETE", f"/brsf/stars/{n7['id']}/instances/{inst_id}", tok)[1]["final_value"], "(expect -3)")

print("\nrecalculate (idempotency + override survival):",
      call("POST", "/brsf/recalculate", tok, {"employee_id": eid, "month": MONTH})[1]["message"])
st, d2 = call("GET", f"/brsf/stars?employee_id={eid}&month={MONTH}", tok)
print("lines after recalc:", len(d2["lines"]), "(expect 14)")
n3b = next(l for l in d2["lines"] if l["code"] == "N03")
print("N03 system:", n3b["system_value"], "override:", n3b["override_value"], "final:", n3b["final_value"],
      "status:", n3b["status"], "(override must survive)")
p2b = next(l for l in d2["lines"] if l["code"] == "P02")
print("P02 preserved:", p2b["entry_mode"], p2b["final_value"], "monthly history kept:", p2b["manual_value"])
print("reset override:", call("POST", f"/brsf/stars/{n3['id']}/reset-override", tok)[1]["final_value"],
      "(back to system", n3b["system_value"], ")")
print("audit rows:", len(call("GET", f"/brsf/audit?employee_id={eid}&month={MONTH}", tok)[1]["audit"]))
print("totals:", d2["totals"])

# employee must not reach it
etok = call("POST", "/auth/login", body={"username": "madhan.s", "password": "Vigil@123"})[1]["token"]
print("employee access to /brsf/stars:", call("GET", f"/brsf/stars?employee_id={eid}&month={MONTH}", etok)[0], "(expect 403)")
print("intern/ineligible guard:", call("GET", f"/brsf/stars?employee_id=00000000-0000-0000-0000-000000000000&month={MONTH}", tok)[0], "(expect 400)")
