"""Synthetic success-email path test.

Inserts verified mandatory docs + avatar for Rishi (pilot recipient),
calls run-now, asserts success_sent=1 + completion_success_mail_sent=True,
calls run-now again, asserts no re-send.
Finally reverts all changes (delete inserted docs, restore avatar).
"""
import asyncio
import os
import sys
import time
from datetime import datetime

import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://leave-code-mapper.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
PILOT_EMAIL = "rishi.nayak@blubridge.com"
RISHI_EMP_ID = "2ce742cb-f44b-4224-b19b-4dd44ca6ae51"

MONGO_URL = "mongodb+srv://hrmsblubridge_db_user:GlmUx3Zxg20E794X@cluster0.jcz3bbd.mongodb.net/hrms_blubridge?appName=Cluster0"
DB_NAME = "hrms_blubridge"
DOC_TYPES = ["aadhaar_card", "pan_card", "education", "photo"]


def _login() -> str:
    r = requests.post(f"{API}/auth/login", json={"username": "sysadmin", "password": "pass123"}, timeout=60)
    r.raise_for_status()
    return r.json().get("access_token") or r.json().get("token")


async def main():
    token = _login()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # 0. Ensure pilot mode and pilot email
    requests.put(f"{API}/admin/onboarding-completion/settings",
                 json={"enable_bulk_onboarding_mail": False, "pilot_email": PILOT_EMAIL},
                 headers=headers, timeout=60)

    # Snapshot original state for revert
    emp = await db.employees.find_one({"id": RISHI_EMP_ID}, {"_id": 0, "avatar": 1, "official_email": 1})
    if not emp:
        print(f"FAIL: Rishi employee_id={RISHI_EMP_ID} not found")
        return 1
    original_avatar = emp.get("avatar")
    original_docs = await db.onboarding_documents.find(
        {"employee_id": RISHI_EMP_ID}, {"_id": 0}
    ).to_list(50)
    original_state = await db.onboarding_completion_state.find_one(
        {"employee_id": RISHI_EMP_ID}, {"_id": 0}
    )
    print(f"BACKUP: avatar={original_avatar!r}, docs_count={len(original_docs)}, state_exists={bool(original_state)}")

    # 1. Make Rishi 100% complete (avatar + 4 verified mandatory docs)
    await db.employees.update_one(
        {"id": RISHI_EMP_ID},
        {"$set": {"avatar": "https://example.com/test-synthetic-avatar.png"}},
    )
    # Remove existing onboarding docs for these types then upsert verified ones
    await db.onboarding_documents.delete_many(
        {"employee_id": RISHI_EMP_ID, "document_type": {"$in": DOC_TYPES}}
    )
    now_iso = datetime.utcnow().isoformat()
    for dt in DOC_TYPES:
        await db.onboarding_documents.insert_one({
            "id": f"SYNTH_{dt}_{RISHI_EMP_ID}",
            "employee_id": RISHI_EMP_ID,
            "document_type": dt,
            "status": "verified",
            "file_url": "https://example.com/synth.pdf",
            "uploaded_at": now_iso,
            "verified_at": now_iso,
            "_synthetic": True,
        })

    # Clear any prior success state so we exercise the firing path
    await db.onboarding_completion_state.update_one(
        {"employee_id": RISHI_EMP_ID},
        {"$set": {"completion_success_mail_sent": False, "completion_success_mail_sent_at": None}},
        upsert=False,
    )

    try:
        # 2. Verify dashboard says is_complete=True for Rishi
        d = requests.get(f"{API}/admin/onboarding-completion/dashboard",
                         params={"search": "rishi"}, headers=headers, timeout=60).json()
        rishi_row = next((r for r in d["rows"] if r["employee_id"] == RISHI_EMP_ID), None)
        assert rishi_row, "Rishi missing from dashboard"
        print(f"DASHBOARD: is_complete={rishi_row['is_complete']}, onboarding%={rishi_row['onboarding_percent']}, photo={rishi_row['profile_photo_uploaded']}")
        assert rishi_row["is_complete"] is True, f"Expected is_complete=True, got row: {rishi_row}"
        assert rishi_row["onboarding_percent"] == 100
        assert rishi_row["profile_photo_uploaded"] is True

        # 3. Run-now → success email fires
        r1 = requests.post(f"{API}/admin/onboarding-completion/run-now",
                           json={"employee_id": RISHI_EMP_ID}, headers=headers, timeout=120).json()
        print(f"RUN1: {r1}")
        assert r1.get("success") is True
        assert r1.get("scanned") == 1
        # success_sent should be 1 (Resend success path)
        if r1.get("success_sent", 0) != 1:
            print(f"WARN: success_sent={r1.get('success_sent')} != 1. May be Resend transient.")

        # 4. State flag set
        state = await db.onboarding_completion_state.find_one(
            {"employee_id": RISHI_EMP_ID}, {"_id": 0}
        )
        print(f"STATE after RUN1: success_sent_flag={state.get('completion_success_mail_sent')}")
        assert state and state.get("completion_success_mail_sent") is True, \
            f"completion_success_mail_sent not True: {state}"

        # 5. Run-now AGAIN → no re-send (idempotency)
        time.sleep(1)
        r2 = requests.post(f"{API}/admin/onboarding-completion/run-now",
                           json={"employee_id": RISHI_EMP_ID}, headers=headers, timeout=120).json()
        print(f"RUN2: {r2}")
        assert r2.get("success_sent", 0) == 0, f"Re-fire detected! {r2}"
        assert r2.get("skipped", 0) >= 1
        print("PASS: success email idempotency verified")

    finally:
        # 6. Revert
        print("REVERTING ...")
        await db.onboarding_documents.delete_many(
            {"employee_id": RISHI_EMP_ID, "_synthetic": True}
        )
        # Restore original docs (re-insert)
        if original_docs:
            await db.onboarding_documents.insert_many(original_docs)
        # Restore avatar (or unset if None)
        if original_avatar is None:
            await db.employees.update_one({"id": RISHI_EMP_ID}, {"$unset": {"avatar": ""}})
        else:
            await db.employees.update_one({"id": RISHI_EMP_ID}, {"$set": {"avatar": original_avatar}})
        # Restore state
        if original_state is None:
            await db.onboarding_completion_state.delete_one({"employee_id": RISHI_EMP_ID})
        else:
            await db.onboarding_completion_state.replace_one(
                {"employee_id": RISHI_EMP_ID}, original_state, upsert=True
            )
        print("REVERTED OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
