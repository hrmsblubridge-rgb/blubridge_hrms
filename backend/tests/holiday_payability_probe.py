"""Holiday payability + Holidays↔Payroll synchronisation test.

Uses the real admin Holidays API (single source of truth) and the real payroll
endpoint. Creates temporary holidays, asserts payability, then deletes them and
verifies the payroll snapshot returns EXACTLY to the baseline (regression).
"""
import json
import sys
import urllib.error
import urllib.request

API = sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (holiday-probe)"}
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


def login(u, p):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        API + "/auth/login", method="POST",
        data=json.dumps({"username": u, "password": p}).encode(),
        headers={**UA, "Content-Type": "application/json"}), timeout=120).read())["token"]


admin = login("admin", "HrAdmin786$")


def payroll():
    st, b = call("GET", f"/payroll?month={MONTH}", admin)
    assert st == 200, (st, b[:200])
    return {r["employee_id"]: r for r in json.loads(b)}


def day(row, dd):
    return next((d for d in row["attendance_details"] if d["date"] == dd), None)


def add_holiday(name, iso):
    import datetime as _dt
    dname = _dt.date(*[int(x) for x in iso.split("-")]).strftime("%A")
    st, b = call("POST", "/holidays", admin,
                 {"name": name, "date": iso, "day": dname, "type": "company"})
    assert st == 200, (st, b)
    return json.loads(b).get("id") or json.loads(b).get("holiday", {}).get("id")


def del_holiday(hid):
    print("   delete holiday:", call("DELETE", f"/holidays/{hid}", admin)[0])


base = payroll()
print(f"baseline: {len(base)} employees for {MONTH}")

# pick an employee with a full-day 'P' on 03-08 and one with 'HD' anywhere
fd_emp = next((e for e in base.values() if (day(e, "03-08-2026") or {}).get("status") == "P"), None)
hd_pair = None
for e in base.values():
    for d in e["attendance_details"]:
        if d["status"] == "HD" and not d["is_sunday"] and not d["is_holiday"]:
            hd_pair = (e, d["date"])
            break
    if hd_pair:
        break
print("FD candidate:", fd_emp["emp_name"], "| HD candidate:",
      hd_pair[0]["emp_name"] if hd_pair else None, hd_pair[1] if hd_pair else None)

print("\n=== TEST 1 — Full day worked on a (new) holiday: FD, +1.0 payable ===")
hid = add_holiday("TEST Holiday Payability", "2026-08-03")
after = payroll()
b_, a_ = base[fd_emp["employee_id"]], after[fd_emp["employee_id"]]
d_ = day(a_, "03-08-2026")
print(f"   status: {day(b_,'03-08-2026')['status']} -> {d_['status']} (expect FD)")
print(f"   holiday_pay: {b_.get('holiday_pay')} -> {a_.get('holiday_pay')} (expect +1)")
print(f"   working_days: {b_['working_days']} -> {a_['working_days']} (expect -1)")
print(f"   extra_pay: {b_['extra_pay']} -> {a_['extra_pay']} (expect unchanged)")
print(f"   PAYABLE DAYS: {b_['final_payable_days']} -> {a_['final_payable_days']} "
      f"(expect UNCHANGED — the worked holiday is still fully paid)")
print(f"   net_salary: {b_['net_salary']} -> {a_['net_salary']}")

print("\n=== TEST 3 — employee who did NOT work that holiday keeps old behaviour ===")
noshow = next((e for e in base.values()
               if (day(e, "03-08-2026") or {}).get("status") in ("A", "WO", "NA", "PF", "SF")), None)
if noshow:
    nb, na = base[noshow["employee_id"]], after[noshow["employee_id"]]
    print(f"   {noshow['emp_name']}: {day(nb,'03-08-2026')['status']} -> {day(na,'03-08-2026')['status']}, "
          f"holiday_pay={na.get('holiday_pay')}, payable {nb['final_payable_days']} -> {na['final_payable_days']}")
del_holiday(hid)

if hd_pair:
    emp, dd = hd_pair
    iso = "-".join(reversed(dd.split("-")))
    print(f"\n=== TEST 2 — Half day worked on a (new) holiday {dd}: HD, +0.5 payable ===")
    hid2 = add_holiday("TEST Holiday Half Day", iso)
    after2 = payroll()
    b2, a2 = base[emp["employee_id"]], after2[emp["employee_id"]]
    print(f"   status: {day(b2,dd)['status']} -> {day(a2,dd)['status']} (expect HD)")
    print(f"   holiday_pay: {b2.get('holiday_pay')} -> {a2.get('holiday_pay')} (expect +0.5)")
    print(f"   lop: {b2['lop']} -> {a2['lop']} | working_days: {b2['working_days']} -> {a2['working_days']}")
    print(f"   PAYABLE DAYS: {b2['final_payable_days']} -> {a2['final_payable_days']} (expect UNCHANGED)")
    del_holiday(hid2)

print("\n=== TEST 4 — holiday date changed (01-Aug -> 02-Aug), no hardcoding ===")
h1 = add_holiday("TEST Movable Holiday", "2026-08-01")
p1 = payroll()
h_row = next(iter(p1.values()))
print("   01-08 is_holiday:", day(h_row, "01-08-2026")["is_holiday"],
      "| 02-08 is_holiday:", day(h_row, "02-08-2026")["is_holiday"])
print("   update date:", call("PUT", f"/holidays/{h1}", admin, {"date": "2026-08-02"})[0])
p2 = payroll()
h_row2 = next(iter(p2.values()))
print("   after change -> 01-08 is_holiday:", day(h_row2, "01-08-2026")["is_holiday"],
      "(expect False) | 02-08 is_holiday:", day(h_row2, "02-08-2026")["is_holiday"], "(expect True)")

print("\n=== TEST 6 — holiday removed ===")
del_holiday(h1)
p3 = payroll()
h_row3 = next(iter(p3.values()))
print("   02-08 is_holiday:", day(h_row3, "02-08-2026")["is_holiday"], "(expect False)")

print("\n=== TEST 7 — full regression: payroll identical to baseline after cleanup ===")
final = payroll()
fields = ("total_days", "working_days", "weekoff_pay", "extra_pay", "oh_pay",
          "holiday_pay", "lop", "final_payable_days", "net_salary",
          "present_days", "leave_days", "absent_days")
diffs = []
for eid, row in final.items():
    b_row = base.get(eid)
    if not b_row:
        continue
    for f in fields:
        if row.get(f) != b_row.get(f):
            diffs.append((row["emp_name"], f, b_row.get(f), row.get(f)))
    if [d["status"] for d in row["attendance_details"]] != [d["status"] for d in b_row["attendance_details"]]:
        diffs.append((row["emp_name"], "day_statuses", "changed", "changed"))
print(f"   employees compared: {len(final)} | differences: {len(diffs)}")
for d in diffs[:10]:
    print("   DIFF:", d)
print("   RESULT:", "PASS — no unrelated change" if not diffs else "FAIL — see diffs")
