import requests, os, sys
from datetime import datetime

BASE = "https://blank-tab-debug.preview.emergentagent.com"

def login(u, p):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": u, "password": p}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"] if "access_token" in r.json() else r.json().get("token")

def main():
    tok = login("admin", "HrAdmin786$")
    h = {"Authorization": f"Bearer {tok}"}
    month = datetime.now().strftime("%Y-%m")
    r = requests.get(f"{BASE}/api/payroll", headers=h, params={"month": month}, timeout=180)
    print("status", r.status_code)
    data = r.json()
    rows = data.get("payroll") or data.get("data") or data
    if isinstance(rows, dict):
        rows = rows.get("payroll", [])
    print("count", len(rows))
    mism = 0
    for e in rows:
        w = e.get("working_days", 0)
        wo = e.get("weekoff_pay", 0)
        ex = e.get("extra_pay", 0)
        lop = e.get("lop", 0)
        pay = e.get("final_payable_days", 0)
        expected = (w - lop) + wo + ex
        # count present-type from rows
        details = e.get("attendance_details", [])
        present_codes = ("P","HD","PF","PH","SF","SH","EF","EH","PA","PP","OH","LC")
        present_rows = sum(1 for d in details if d.get("status") in present_codes)
        row_lop = sum(d.get("lop_value",0) for d in details)
        row_wo = sum(d.get("weekoff_value",0) for d in details)
        row_ex = sum(d.get("extra_value",0) for d in details)
        flag = ""
        if abs(expected - pay) > 0.001:
            flag += " PAYABLE_MISMATCH"
        if abs(row_lop - lop) > 0.001:
            flag += " LOP_ROW_DESYNC"
        if abs(row_wo - wo) > 0.001:
            flag += " WO_ROW_DESYNC"
        if abs(row_ex - ex) > 0.001:
            flag += " EX_ROW_DESYNC"
        if flag:
            mism += 1
            if mism <= 15:
                print(f"{e.get('emp_name')}: W={w} WO={wo} EX={ex} LOP={lop} PAY={pay} expF={expected} | rowLOP={row_lop} rowWO={row_wo} rowEX={row_ex} presentRows={present_rows} ::{flag}")
    print("total mismatches:", mism)

if __name__ == "__main__":
    main()
