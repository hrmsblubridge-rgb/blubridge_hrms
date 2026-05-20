"""Pytest regression for the onboarding+profile-photo completion engine.

Validates the pure `compute_completion` function across the canonical states:
  • zero docs / no photo                       → pending, 0%
  • some uploaded, no photo                    → partial, photo missing
  • all verified, no photo                     → 100% onboarding but overall <100%
  • all verified + photo                       → fully complete (overall 100%)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from onboarding_completion import compute_completion  # noqa: E402


def _doc(t: str, s: str) -> dict:
    return {"document_type": t, "status": s}


def test_completion_zero_state():
    snap = compute_completion({"avatar": None}, [])
    assert snap["onboarding_status"] == "pending"
    assert snap["onboarding_percent"] == 0
    assert snap["profile_photo_uploaded"] is False
    assert snap["overall_percent"] == 0
    assert len(snap["missing_sections"]) == 4


def test_completion_partial_uploaded():
    docs = [
        _doc("aadhaar_card", "uploaded"),
        _doc("pan_card", "verified"),
    ]
    snap = compute_completion({"avatar": None}, docs)
    assert snap["onboarding_status"] == "partial"
    # 1 verified (1.0) + 1 uploaded (0.5) of 4 → 37.5% → 38 (rounded)
    assert snap["onboarding_percent"] in (37, 38)
    assert snap["profile_photo_uploaded"] is False
    assert snap["photo_missing"] is True


def test_completion_all_verified_no_photo():
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "verified"),
        _doc("education", "verified"),
        _doc("photo", "verified"),
    ]
    snap = compute_completion({"avatar": None}, docs)
    assert snap["onboarding_status"] == "complete"
    assert snap["onboarding_percent"] == 100
    assert snap["profile_photo_uploaded"] is False
    # 70% from onboarding only → overall 70%
    assert snap["overall_percent"] == 70


def test_completion_fully_complete():
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "verified"),
        _doc("education", "verified"),
        _doc("photo", "verified"),
    ]
    snap = compute_completion(
        {"avatar": "https://res.cloudinary.com/x/y.jpg"}, docs,
    )
    assert snap["onboarding_status"] == "complete"
    assert snap["onboarding_percent"] == 100
    assert snap["profile_photo_uploaded"] is True
    assert snap["overall_percent"] == 100
    assert snap["missing_sections"] == []


def test_completion_pending_review_caps_at_99():
    docs = [
        _doc("aadhaar_card", "uploaded"),
        _doc("pan_card", "uploaded"),
        _doc("education", "uploaded"),
        _doc("photo", "uploaded"),
    ]
    snap = compute_completion({"avatar": None}, docs)
    # All uploaded but none verified — strictly NOT complete.
    assert snap["onboarding_status"] == "partial"
    assert snap["onboarding_percent"] < 100
    assert snap["profile_photo_uploaded"] is False


def test_completion_rejected_counts_as_missing():
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "rejected"),
        _doc("education", "verified"),
        _doc("photo", "verified"),
    ]
    snap = compute_completion({"avatar": "x"}, docs)
    assert snap["onboarding_status"] == "partial"
    # rejected is treated as missing in `missing_sections`
    assert any(m["type"] == "pan_card" for m in snap["missing_sections"])
    # 3 of 4 verified → 75% raw, but with 1 missing it's still partial
    assert snap["onboarding_percent"] == 75
