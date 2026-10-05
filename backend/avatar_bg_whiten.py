"""Avatar White-Background Retro-Fit — rewrites every existing Cloudinary
avatar URL to include the AI background-removal transformation, giving a
pure #FFFFFF backdrop across the Photo Wall, employee cards, avatars, PDFs
and any surface that reads `employee.avatar`.

Cloudinary applies the transformation on-the-fly, so no image re-upload is
needed — the stored URL is simply rewritten.

Idempotent: skips URLs that already contain `e_background_removal`.
"""
import re
from typing import Optional

from fastapi import Depends, HTTPException

from server import api_router, db, get_current_user, ALL_ADMIN_ROLES, log_audit

# Full transformation the app now standardises on for every avatar.
STRICT_TRANSFORM = (
    "e_background_removal,b_rgb:ffffff,c_fill,g_face,w_512,h_512,q_auto,f_auto"
)

# Any of these older/lighter transform segments should be REPLACED by the
# strict one when we retro-fit. Order matters (longest first).
_LEGACY_TRANSFORM_SEGMENTS = [
    "c_fill,g_face,w_512,h_512,b_rgb:ffffff,q_auto,f_auto",
    "c_fill,g_face,w_512,h_512,q_auto,f_auto",
    "b_rgb:ffffff,c_fill,g_face,w_512,h_512,q_auto,f_auto",
    "c_fill,g_face,w_512,h_512",
]

# Matches "/upload/<anything up to next '/'>/" — used when the URL has an
# unknown transformation string we still want to normalise.
_UPLOAD_TRANSFORM_RE = re.compile(r"(/upload/)([^/]+)(/)")


def _require_admin(user):
    if user.get("role") not in ALL_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")


def _rewrite_avatar_url(url: str) -> Optional[str]:
    """Return the strict-transform URL if a rewrite is required, else None."""
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return None
    if "e_background_removal" in url:
        return None  # already strict

    # 1) Replace a known legacy transform segment (fast path).
    for seg in _LEGACY_TRANSFORM_SEGMENTS:
        needle = f"/upload/{seg}/"
        if needle in url:
            return url.replace(needle, f"/upload/{STRICT_TRANSFORM}/", 1)

    # 2) URL has NO transformation between /upload/ and the version segment:
    #    ".../upload/v1787.../filename.jpg" — insert the strict transform.
    m = re.search(r"/upload/(v\d+/|[a-z]+/)", url)
    if m:
        return url.replace("/upload/", f"/upload/{STRICT_TRANSFORM}/", 1)

    # 3) URL has an unrecognised transformation string — swap it out.
    replaced, n = _UPLOAD_TRANSFORM_RE.subn(
        rf"\1{STRICT_TRANSFORM}\3", url, count=1
    )
    return replaced if n else None


@api_router.post("/admin/avatars/whiten-all")
async def whiten_all_avatars(current_user: dict = Depends(get_current_user)):
    """Rewrite every employee avatar to use the strict white-background
    transformation. Safe to re-run — already-strict URLs are skipped."""
    _require_admin(current_user)

    total = 0
    updated = 0
    skipped_no_avatar = 0
    already_strict = 0
    failed = 0
    async for emp in db.employees.find(
        {}, {"_id": 0, "id": 1, "avatar": 1, "full_name": 1}
    ):
        total += 1
        url = emp.get("avatar")
        if not url:
            skipped_no_avatar += 1
            continue
        if "e_background_removal" in url:
            already_strict += 1
            continue
        new_url = _rewrite_avatar_url(url)
        if not new_url or new_url == url:
            failed += 1
            continue
        try:
            await db.employees.update_one(
                {"id": emp["id"]},
                {"$set": {"avatar": new_url, "avatar_bg_whitened_at": True}},
            )
            updated += 1
        except Exception:
            failed += 1

    await log_audit(
        current_user["id"], "avatars_bg_whiten_all", "employee_avatar", "",
        f"total={total} updated={updated} already={already_strict} "
        f"no_avatar={skipped_no_avatar} failed={failed}",
    )
    return {
        "total_employees": total,
        "updated": updated,
        "already_strict": already_strict,
        "no_avatar": skipped_no_avatar,
        "failed": failed,
    }


@api_router.post("/admin/avatars/whiten/{employee_id}")
async def whiten_one_avatar(employee_id: str, current_user: dict = Depends(get_current_user)):
    """Apply the strict white-bg transform to a single employee's avatar."""
    _require_admin(current_user)
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0, "avatar": 1})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    url = emp.get("avatar")
    if not url:
        raise HTTPException(status_code=400, detail="Employee has no avatar")
    new_url = _rewrite_avatar_url(url)
    if not new_url or new_url == url:
        return {"changed": False, "avatar": url}
    await db.employees.update_one(
        {"id": employee_id},
        {"$set": {"avatar": new_url, "avatar_bg_whitened_at": True}},
    )
    await log_audit(
        current_user["id"], "avatar_bg_whiten", "employee_avatar", employee_id,
        f"rewritten to strict white-bg transform",
    )
    return {"changed": True, "avatar": new_url}
