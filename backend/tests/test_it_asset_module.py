import asyncio, os, io, httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
API = "http://localhost:8001"
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
results = []
def ck(n, c, extra=""):
    results.append(bool(c)); print(("PASS" if c else "FAIL"), "-", n, extra)

async def main():
    emp = await db.employees.find_one({"is_deleted": {"$ne": True}, "employee_status": "Active"}, {"_id":0,"id":1,"full_name":1})
    emp2 = await db.employees.find_one({"is_deleted": {"$ne": True}, "employee_status": "Active", "id": {"$ne": emp["id"]}}, {"_id":0,"id":1,"full_name":1})
    EID, EID2 = emp["id"], emp2["id"]
    async with httpx.AsyncClient(base_url=API, timeout=40) as c:
        tok = (await c.post("/api/auth/login", json={"username":"admin","password":"HrAdmin@2109"})).json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        # meta
        meta = (await c.get("/api/it/meta", headers=H)).json()
        ck("meta categories seeded", len(meta.get("categories",[])) > 10)
        # create asset auto-id (Laptop -> LAP-XXXX)
        r = await c.post("/api/it/assets", headers=H, json={"category":"Laptop","brand":"Dell","model":"L5420","status":"Available","serial_number":"ZZTEST-SN-1"})
        ck("create asset 200", r.status_code==200, r.text[:120])
        aid = r.json()["asset_id"]
        ck("auto asset_id LAP- prefix", aid.startswith("LAP-"), aid)
        # duplicate serial rejected
        rd = await c.post("/api/it/assets", headers=H, json={"category":"Laptop","status":"Available","serial_number":"ZZTEST-SN-1"})
        ck("duplicate serial rejected", rd.status_code==400)
        # manual id + legacy (no purchase info)
        r2 = await c.post("/api/it/assets", headers=H, json={"asset_id":"ZZ-LEGACY-1","category":"Monitor","status":"Available","source":"Existing / Legacy Asset"})
        ck("legacy asset (no purchase) saved", r2.status_code==200, r2.text[:120])
        # list + filter
        lst = (await c.get("/api/it/assets", headers=H, params={"category":"Laptop"}).__await__().__next__() if False else await c.get("/api/it/assets", headers=H, params={"category":"Laptop"})).json()
        ck("list returns items+total", "items" in lst and lst["total"]>=1)
        # assign
        ra = await c.post(f"/api/it/assets/{aid}/assign", headers=H, json={"employee_id":EID})
        ck("assign 200", ra.status_code==200, ra.text[:120])
        det = (await c.get(f"/api/it/assets/{aid}", headers=H)).json()
        ck("assigned_to set + status Assigned", det["asset"]["assigned_to"]["employee_id"]==EID and det["asset"]["status"]=="Assigned")
        ck("history has Created+Assigned", any(h["action"]=="Assigned" for h in det["history"]) and any(h["action"]=="Created" for h in det["history"]))
        # assign again blocked
        rb = await c.post(f"/api/it/assets/{aid}/assign", headers=H, json={"employee_id":EID2})
        ck("re-assign blocked without transfer/return", rb.status_code==400)
        # transfer
        rt = await c.post(f"/api/it/assets/{aid}/transfer", headers=H, json={"employee_id":EID2})
        ck("transfer 200", rt.status_code==200, rt.text[:120])
        det2 = (await c.get(f"/api/it/assets/{aid}", headers=H)).json()
        ck("transfer updates holder", det2["asset"]["assigned_to"]["employee_id"]==EID2)
        ck("history has Transferred", any(h["action"]=="Transferred" for h in det2["history"]))
        # return
        rr = await c.post(f"/api/it/assets/{aid}/return", headers=H, json={"status":"Available","condition":"Good"})
        ck("return 200", rr.status_code==200)
        det3 = (await c.get(f"/api/it/assets/{aid}", headers=H)).json()
        ck("returned -> assigned_to None, Available", det3["asset"]["assigned_to"] is None and det3["asset"]["status"]=="Available")
        # dashboard
        dash = (await c.get("/api/it/dashboard", headers=H)).json()
        ck("dashboard total>=2", dash["total"]>=2 and "by_category" in dash and "alerts" in dash)
        # import preview (CSV with 1 valid legacy + 1 error dup id + 1 error bad category)
        csv_body = ("asset_id,category,name,status,serial_number\n"
                    ",Laptop,Imported One,Available,ZZIMP-1\n"
                    f"{aid},Laptop,DupId,Available,ZZIMP-2\n"
                    ",NotACategory,Bad,Available,ZZIMP-3\n")
        files = {"file": ("assets.csv", csv_body, "text/csv")}
        pv = (await c.post("/api/it/import/preview", headers=H, files=files)).json()
        ck("preview total=3 valid=1 errors=2", pv["total"]==3 and pv["valid"]==1 and pv["errors"]==2, str({k:pv[k] for k in ('total','valid','errors')}))
        # confirm import only valid rows
        cf = (await c.post("/api/it/import/confirm", headers=H, json={"rows": pv["rows"]})).json()
        ck("confirm created=1 skipped=2", cf["created"]==1 and cf["skipped"]==2, str(cf))
        # export respects filter
        ex = await c.get("/api/it/export", headers=H, params={"category":"Monitor"})
        ck("export csv 200", ex.status_code==200 and "asset_id" in ex.text)
        # soft delete
        rdel = await c.delete(f"/api/it/assets/ZZ-LEGACY-1", headers=H)
        ck("soft delete 200", rdel.status_code==200)
        gone = await c.get("/api/it/assets/ZZ-LEGACY-1", headers=H)
        ck("archived asset -> 404 on detail", gone.status_code==404)

        # SECURITY: normal employee blocked on /it/*, allowed on /employee/it-assets
        etok = (await c.post("/api/auth/login", json={"username":"user","password":"pass123"})).json()["token"]
        EH = {"Authorization": f"Bearer {etok}"}
        emp_block = await c.get("/api/it/assets", headers=EH)
        ck("employee blocked from /it/assets (403)", emp_block.status_code==403, str(emp_block.status_code))
        emp_self = await c.get("/api/employee/it-assets", headers=EH)
        ck("employee self /employee/it-assets 200", emp_self.status_code==200 and "items" in emp_self.json())

    # cleanup test assets
    await db.it_assets.delete_many({"$or":[{"serial_number":{"$in":["ZZTEST-SN-1","ZZIMP-1"]}},{"asset_id":{"$in":[aid,"ZZ-LEGACY-1"]}},{"name":"Imported One"}]})
    await db.it_asset_history.delete_many({"asset_id":{"$in":[aid,"ZZ-LEGACY-1"]}})
    p = sum(results); print(f"\n==== {p}/{len(results)} PASSED ====")
    if p != len(results): raise SystemExit(1)

asyncio.run(main())
