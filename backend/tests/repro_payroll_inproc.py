import asyncio, sys
sys.path.insert(0, "/app/backend")
import server
from datetime import datetime

async def main():
    month = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m")
    year, mn = map(int, month.split("-"))
    import calendar
    dim = calendar.monthrange(year, mn)[1]
    query = {"is_deleted": {"$ne": True}, "employee_status": {"$in": [server.EmployeeStatus.ACTIVE, server.EmployeeStatus.INACTIVE]}}
    emps = await server.db.employees.find(query, {"_id": 0}).to_list(1000)
    emp_ids = [e["id"] for e in emps]
    pf = await server._prefetch_payroll_data(emp_ids, year, mn, dim)
    present_codes = ("P","HD","PF","PH","SF","SH","EF","EH","PA","PP","OH","LC")
    mism = 0
    total = 0
    for e in emps:
        p = await server.calculate_payroll_for_employee(e["id"], month, employee=e, prefetched=pf)
        if not p:
            continue
        total += 1
        w, wo, ex, lop, pay = p["working_days"], p["weekoff_pay"], p["extra_pay"], p["lop"], p["final_payable_days"]
        details = p["attendance_details"]
        row_lop = sum(d.get("lop_value",0) for d in details)
        row_wo = sum(d.get("weekoff_value",0) for d in details)
        row_ex = sum(d.get("extra_value",0) for d in details)
        present_rows = sum(1 for d in details if d.get("status") in present_codes)
        expF = (w - lop) + wo + ex
        flags = []
        if abs(expF - pay) > 0.001: flags.append("PAY_FORMULA")
        if abs(row_lop - lop) > 0.001: flags.append(f"LOP_DESYNC(row{row_lop}!=acc{lop})")
        if abs(row_wo - wo) > 0.001: flags.append(f"WO_DESYNC(row{row_wo}!=acc{wo})")
        if abs(row_ex - ex) > 0.001: flags.append(f"EX_DESYNC(row{row_ex}!=acc{ex})")
        if flags:
            mism += 1
            if mism <= 20:
                print(f"{e.get('full_name')}: W={w} WO={wo} EX={ex} LOP={lop} PAY={pay} | expF={expF} presentRows={present_rows} :: {flags}")
    print(f"\nmonth={month} total={total} mismatches={mism}")

asyncio.run(main())
