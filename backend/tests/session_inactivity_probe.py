"""Sliding 30-minute inactivity timeout — behavioural test.

Manipulates `last_activity_at` in mongo (instead of waiting 30 real minutes)
to prove: activity slides the window, a fresh login is never expired, 29 min
idle still works, 31 min idle is rejected + session revoked, and a background
refresh cannot resurrect an idle session.
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
API = sys.argv[1].rstrip("/") + "/api"
UA = {"User-Agent": "Mozilla/5.0 (session-probe)"}
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


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
        return resp.status, resp.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def login(u, p):
    st, b = call("POST", "/auth/login", body={"username": u, "password": p})
    assert st == 200, (st, b)
    d = json.loads(urllib.request.urlopen(urllib.request.Request(
        API + "/auth/login", method="POST",
        data=json.dumps({"username": u, "password": p}).encode(),
        headers={**UA, "Content-Type": "application/json"}), timeout=120).read())
    return d["token"], d["refresh_token"]


async def session_for(token):
    import jwt
    payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    return payload["session_id"]


async def set_idle(session_id, minutes):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    await db.auth_sessions.update_one({"session_id": session_id}, {"$set": {"last_activity_at": ts}})


async def get_session(session_id):
    return await db.auth_sessions.find_one({"session_id": session_id}, {"_id": 0})


async def main():
    tok, rtok = login("madhan.s", "Vigil@123")
    sid = await session_for(tok)
    print("A. fresh login -> /auth/me:", call("GET", "/auth/me", tok)[0], "(expect 200)")
    s = await get_session(sid)
    print("   last_activity_at set at login:", bool(s.get("last_activity_at")))

    await set_idle(sid, 29)
    st, b = call("GET", "/employee/dashboard", tok)
    print("B. idle 29 min -> request:", st, "(expect 200)")
    s = await get_session(sid)
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(s["last_activity_at"])).total_seconds()
    print("   window slid forward, last_activity age =", round(age, 1), "s (expect < 5)")

    await set_idle(sid, 29)
    print("C. background poll (unread-count) at 29 min:", call("GET", "/notifications/unread-count", tok)[0])
    s = await get_session(sid)
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(s["last_activity_at"])).total_seconds() / 60
    print("   poll did NOT slide window, idle still ~", round(age, 1), "min (expect ~29)")

    await set_idle(sid, 31)
    st, b = call("GET", "/employee/dashboard", tok)
    print("D. idle 31 min -> request:", st, b)
    s = await get_session(sid)
    print("   session revoked:", s.get("revoked_at") is not None, "reason:", s.get("revoke_reason"))
    print("   any later request:", call("GET", "/auth/me", tok))

    print("E. refresh token on the dead session:", call("POST", "/auth/refresh", None, {"refresh_token": rtok}))

    tok2, rtok2 = login("madhan.s", "Vigil@123")
    sid2 = await session_for(tok2)
    await set_idle(sid2, 31)
    print("F. refresh alone cannot resurrect an idle session:",
          call("POST", "/auth/refresh", None, {"refresh_token": rtok2}))
    s2 = await get_session(sid2)
    print("   session revoked by refresh check:", s2.get("revoke_reason"))

    tok3, _ = login("admin", "HrAdmin786$")
    sid3 = await session_for(tok3)
    print("G. admin same rules -> now:", call("GET", "/auth/me", tok3)[0])
    await set_idle(sid3, 31)
    print("   admin idle 31 min:", call("GET", "/auth/me", tok3))


asyncio.run(main())
