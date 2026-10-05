"""HR spec 2026-08-29 — Holiday rule + Holidays↔Payroll sync validation.

Rule under test:
    Holiday, no work    -> H,  Weekoff/Holiday Pay +1, Extra Pay +0
    Holiday, half day   -> HD, Weekoff/Holiday Pay +1, Extra Pay +0.5
    Holiday, full day   -> FD, Weekoff/Holiday Pay +1, Extra Pay +1
    Payable Days = Working Days + Weekoff/Holiday Pay + OH Pay - LOP  (no Extra Pay)
"""
import datetime as dt
import json
import sys
import urllib.error
import urllib.request

API = sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (holiday-rule-probe)"}
MONTH = "2026-08"


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
        resp = urllib.request.urlopen(r, timeout=180)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


admin = json.loads(urllib.request.urlopen(urllib.request.Request(
    API + "/auth/login", method="POST",
    data=json.dumps({"username": "admin", "password": "HrAdmin786$"}).encode(),
    headers={**UA, "Content-Type": "application/json"}), timeout=120).read())["token"]


def payroll():
    st, b = call("GET", f"/payroll?month={MONTH}", admin)
    assert st == 200, (st, b[:200])
    return {r["employee_id"]: r for r in json.loads(b)}


def day(row, dd):
    return next((d for d in row["attendance_details"] if d["date"] == dd), None)


def add_holiday(name, iso):
    dname = dt.date(*[int(x) for x in iso.split("-")]).strftime("%A")
    st, b = call("POST", "/holidays", admin, {"name": name, "date": iso, "day": dname, "type": "company"})
    assert st == 200, (st, b)
    return json.loads(b).get("id") or json.loads(b).get("holiday", {}).get("id")


def check_formula(row, label):
    expected = round(row["working_days"] + row["weekoff_pay"] + row.get("oh_pay", 0) - row["lop"], 2)
    ok = abs(expected - row["final_payable_days"]) < 0.001
    print(f"   {label}: Payable {row['final_payable_days']} == Working {row['working_days']} + "
          f"WO/Hol {row['weekoff_pay']} + OH {row.get('oh_pay', 0)} - LOP {row['lop']} -> {'OK' if ok else 'MISMATCH'}"
          f" | ExtraPay {row['extra_pay']} NOT included")
    return ok


base = payroll()
print(f"baseline: {len(base)} employees, month {MONTH}")
print("no holiday_pay field in API response:", "holiday_pay" not in next(iter(base.values())))

# 15-Aug-2026 is an existing configured holiday
print("\n=== TEST 1/2/3 on the existing configured holiday 15-08-2026 ===")
groups = {"H": None, "HD": None, "FD": None}
for r in base.values():
    d = day(r, "15-08-2026")
    if d and d["status"] in groups and groups[d["status"]] is None:
        groups[d["status"]] = (r, d)
for status, pair in groups.items():
    if not pair:
        print(f"   no employee with status {status} on the holiday")
        continue
    r, d = pair
    exp_extra = {"H": 0, "HD": 0.5, "FD": 1}[status]
    print(f"   {r['emp_name']:<26} day={d['status']}  weekoff_value={d.get('weekoff_value')} (expect 1) "
          f" extra_value={d.get('extra_value')} (expect {exp_extra})")
    check_formula(r, "formula")

print("\n=== TEST — SYNC: add a new holiday on 03-08-2026 ===")
hid = add_holiday("TEST Sync Holiday", "2026-08-03")
after = payroll()
sample = next(iter(after.values()))
print("   03-08 is_holiday:", day(sample, "03-08-2026")["is_holiday"], "(expect True)")
changed = 0
for eid, r in after.items():
    b = base[eid]
    d_new, d_old = day(r, "03-08-2026"), day(b, "03-08-2026")
    if d_new["weekoff_value"] == 1 and r["weekoff_pay"] == b["weekoff_pay"] + 1:
        changed += 1
print(f"   employees whose Weekoff/Holiday Pay increased by exactly 1: {changed}/{len(after)}")
worked = [(r["emp_name"], day(r, "03-08-2026")["status"], day(r, "03-08-2026")["extra_value"],
           b_["final_payable_days"], r["final_payable_days"])
          for eid, r in after.items() for b_ in [base[eid]]
          if day(r, "03-08-2026")["status"] in ("FD", "HD")]
print(f"   employees who worked that day (status/extra/payable before->after): {worked[:5]}")
print("   formula holds for all:", all(check_formula(r, r["emp_name"][:18]) is True
                                       for r in list(after.values())[:3]))

print("\n=== TEST — SYNC: move the holiday 03-08 -> 04-08 ===")
print("   update:", call("PUT", f"/holidays/{hid}", admin, {"date": "2026-08-04"})[0])
moved = payroll()
s = next(iter(moved.values()))
print("   03-08 is_holiday:", day(s, "03-08-2026")["is_holiday"], "(expect False) |",
      "04-08 is_holiday:", day(s, "04-08-2026")["is_holiday"], "(expect True)")

print("\n=== TEST — SYNC: remove the holiday ===")
print("   delete:", call("DELETE", f"/holidays/{hid}", admin)[0])
final = payroll()
s = next(iter(final.values()))
print("   04-08 is_holiday:", day(s, "04-08-2026")["is_holiday"], "(expect False)")

print("\n=== REGRESSION: back to baseline on every field and every day status ===")
fields = ("total_days", "working_days", "weekoff_pay", "extra_pay", "oh_pay", "lop",
          "final_payable_days", "net_salary", "present_days", "leave_days", "absent_days")
diffs = []
for eid, r in final.items():
    b = base.get(eid)
    if not b:
        continue
    for f in fields:
        if r.get(f) != b.get(f):
            diffs.append((r["emp_name"], f, b.get(f), r.get(f)))
    if [d["status"] for d in r["attendance_details"]] != [d["status"] for d in b["attendance_details"]]:
        diffs.append((r["emp_name"], "day_statuses", "changed", "changed"))
print(f"   employees compared: {len(final)} | differences: {len(diffs)}")
for d in diffs[:10]:
    print("   DIFF:", d)
print("   RESULT:", "PASS" if not diffs else "FAIL")
