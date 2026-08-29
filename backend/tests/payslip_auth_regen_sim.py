"""Safe checks for the payslip auth layer:

1. Resend deliverability probe to the fixed recipient (contains NO auth code) —
   tells us whether a REAL regeneration would succeed.
2. Simulated regeneration: activate a known code + bump the version WITHOUT
   sending mail, assert old code dies / new code works / verified sessions are
   invalidated, then restore the initial 082026 configuration.
"""
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from email_service import send_hrms_email  # noqa: E402
from payslip_security import _hash_code, _new_salt, CONFIG_ID  # noqa: E402

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api" if "REACT_APP_BACKEND_URL" in os.environ else sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (payslip-probe)"}
RECIPIENT = "hrrecruiter@blubridge.com"


def call(method, path, token=None, body=None):
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
            return resp.status, resp.read().decode()[:300]
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and e.code != 502:
                time.sleep(3)
                continue
            return e.code, e.read().decode()[:300]
    return 599, "gateway"


def login(u, p):
    st, b = call("POST", "/auth/login", body={"username": u, "password": p})
    assert st == 200, (st, b)
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        API + "/auth/login", method="POST",
        data=json.dumps({"username": u, "password": p}).encode(),
        headers={**UA, "Content-Type": "application/json"}), timeout=120).read())["token"]


async def main():
    print("=== 1. Resend deliverability probe (no auth code inside) ===")
    ok = await send_hrms_email(
        db,
        email_type="payslip_auth_delivery_test",
        scope_key=f"delivery_test:{time.time()}",
        to_email=RECIPIENT,
        subject="HRMS Payslip Security — delivery test",
        html="<p>Delivery test for the HRMS Payslip authorization-code mailbox. No code included.</p>",
        force=True,
    )
    print("send_hrms_email ->", ok)
    audit = await db.email_audit.find_one(
        {"email_type": "payslip_auth_delivery_test"}, {"_id": 0}, sort=[("created_at", -1)]
    )
    print("audit:", audit)

    print("\n=== 2. Simulated regeneration (no email) ===")
    before = await db.payslip_security_settings.find_one({"id": CONFIG_ID}, {"_id": 0})
    admin = login("admin", "HrAdmin786$")
    print("verify 082026 ->", call("POST", "/payslip-security/verify", admin, {"code": "082026"}))
    print("templates    ->", call("GET", "/payslips/templates", admin)[0])

    new_code = "424242"
    salt = _new_salt()
    await db.payslip_security_settings.update_one(
        {"id": CONFIG_ID},
        {"$set": {"auth_code_salt": salt, "auth_code_hash": _hash_code(new_code, salt),
                  "auth_code_version": int(before["auth_code_version"]) + 1}},
    )
    print("-- version bumped (simulating a successful regeneration)")
    print("existing verified session now ->", call("GET", "/payslips/templates", admin)[0], "(expect 403)")
    print("old code 082026 ->", call("POST", "/payslip-security/verify", admin, {"code": "082026"}))
    print("new code 424242 ->", call("POST", "/payslip-security/verify", admin, {"code": new_code}))
    print("templates after new verify ->", call("GET", "/payslips/templates", admin)[0], "(expect 200)")

    # restore initial state
    salt = _new_salt()
    await db.payslip_security_settings.update_one(
        {"id": CONFIG_ID},
        {"$set": {"auth_code_salt": salt, "auth_code_hash": _hash_code("082026", salt),
                  "auth_code_version": before["auth_code_version"],
                  "last_regenerated_at": before.get("last_regenerated_at"),
                  "last_regenerated_by": before.get("last_regenerated_by")}},
    )
    await db.payslip_auth_sessions.delete_many({})
    await db.payslip_auth_attempts.delete_many({})
    print("-- restored: version", before["auth_code_version"], "code 082026, sessions cleared")


asyncio.run(main())
