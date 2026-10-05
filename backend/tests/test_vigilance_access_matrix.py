"""
(1) Reset the `admin` account password to HrAdmin@2109 (per explicit user
    instruction 2026-09-21, overriding the older pin).
(2) Verify the Vigilance access matrix end-to-end:
    - admin (new pw)            -> full access, entries mode=admin
    - normal employee 'user'    -> /access has_access False, /entries 403
    - TEMP team=Vigilance user   -> is_vigilance True, entries mode=vigilance  (NEW path)
    - designation=Vigilance 'madhan.s' -> is_vigilance True, mode=vigilance    (existing path)
Creates + cleans up the temp team-only employee & login.
"""
import asyncio, os, hashlib
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
API = "http://localhost:8001"
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

def sha(p): return hashlib.sha256(p.encode()).hexdigest()

TEMP_EMP = "zz-vig-team-emp"
TEMP_USER = "zz-vig-team-user"
TEMP_UNAME = "zz.vigteam"
results = []
def check(n, c, extra=""):
    results.append(bool(c)); print(("PASS" if c else "FAIL"), "-", n, extra)


async def login(c, u, p):
    r = await c.post("/api/auth/login", json={"username": u, "password": p})
    if r.status_code != 200:
        return None, r.status_code
    return r.json()["token"], 200


async def main():
    # (1) reset admin password
    await db.users.update_one({"username": "admin"}, {"$set": {
        "password_hash": sha("HrAdmin@2109"),
        "password_updated_method": "user_fixed_credential_2026_09_21",
    }})
    # re-sync madhan.s (drifts) to Vigil@123
    await db.users.update_one({"username": "madhan.s"}, {"$set": {"password_hash": sha("Vigil@123")}})

    # temp team=Vigilance employee (designation NOT vigilance) + login
    await db.employees.delete_many({"id": TEMP_EMP})
    await db.users.delete_many({"id": TEMP_USER})
    await db.employees.insert_one({"id": TEMP_EMP, "full_name": "ZZ VigTeam Only", "team": "Vigilance",
        "designation": "Research Analyst", "department": "Research", "employee_status": "Active",
        "is_deleted": False, "official_email": "zz.vigteam@example.com"})
    await db.users.insert_one({"id": TEMP_USER, "username": TEMP_UNAME, "email": "zz.vigteam@example.com",
        "name": "ZZ VigTeam Only", "role": "employee", "employee_id": TEMP_EMP, "is_active": True,
        "onboarding_status": "approved", "password_hash": sha("Test@123")})

    async with httpx.AsyncClient(base_url=API, timeout=30) as c:
        # --- admin with NEW password ---
        tok, st = await login(c, "admin", "HrAdmin@2109")
        check("admin logs in with HrAdmin@2109", tok is not None, f"status={st}")
        check("old admin password HrAdmin786$ now REJECTED", (await login(c, "admin", "HrAdmin786$"))[0] is None)
        if tok:
            H = {"Authorization": f"Bearer {tok}"}
            acc = (await c.get("/api/vigilance/access", headers=H)).json()
            check("admin has_access + is_admin", acc.get("has_access") and acc.get("is_admin"))
            ent = await c.get("/api/vigilance/entries", headers=H, params={"from_date": "01-Sep-2026", "to_date": "30-Sep-2026"})
            check("admin /entries mode=admin", ent.status_code == 200 and ent.json().get("mode") == "admin", str(ent.status_code))

        # --- normal employee ---
        tok, st = await login(c, "user", "pass123")
        check("normal employee logs in", tok is not None, f"status={st}")
        if tok:
            H = {"Authorization": f"Bearer {tok}"}
            r = await c.get("/api/vigilance/access", headers=H)
            denied = r.status_code == 403 or (r.status_code == 200 and r.json().get("has_access") is False)
            check("normal employee DENIED vigilance access", denied, f"status={r.status_code} body={r.text[:80]}")
            ent = await c.get("/api/vigilance/entries", headers=H, params={"from_date": "01-Sep-2026", "to_date": "30-Sep-2026"})
            check("normal employee /entries -> 403", ent.status_code == 403, str(ent.status_code))

        # --- TEMP team=Vigilance (designation != vigilance) : NEW path ---
        tok, st = await login(c, TEMP_UNAME, "Test@123")
        check("team-vigilance user logs in", tok is not None, f"status={st}")
        if tok:
            H = {"Authorization": f"Bearer {tok}"}
            acc = (await c.get("/api/vigilance/access", headers=H)).json()
            check("TEAM=Vigilance -> is_vigilance True (NEW path)", acc.get("has_access") and acc.get("is_vigilance"), str(acc))
            ent = await c.get("/api/vigilance/entries", headers=H, params={"from_date": "01-Sep-2026", "to_date": "30-Sep-2026"})
            check("team-vigilance /entries mode=vigilance", ent.status_code == 200 and ent.json().get("mode") == "vigilance", str(ent.status_code))

        # --- designation=Vigilance (existing path still works) ---
        tok, st = await login(c, "madhan.s", "Vigil@123")
        check("designation-vigilance user logs in", tok is not None, f"status={st}")
        if tok:
            H = {"Authorization": f"Bearer {tok}"}
            acc = (await c.get("/api/vigilance/access", headers=H)).json()
            check("designation=Vigilance -> is_vigilance True", acc.get("has_access") and acc.get("is_vigilance"))
            ent = await c.get("/api/vigilance/entries", headers=H, params={"from_date": "01-Sep-2026", "to_date": "30-Sep-2026"})
            check("designation /entries mode=vigilance", ent.status_code == 200 and ent.json().get("mode") == "vigilance")

    # cleanup temp
    await db.employees.delete_many({"id": TEMP_EMP})
    await db.users.delete_many({"id": TEMP_USER})

    p = sum(results)
    print(f"\n==== {p}/{len(results)} PASSED ====")
    if p != len(results):
        raise SystemExit(1)


asyncio.run(main())
