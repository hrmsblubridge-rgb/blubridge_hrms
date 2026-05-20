"""Pytest regression for the onboarding completion engine.

After 2026-05-20: 3 mandatory documents only — Aadhaar, PAN, Education.
The passport-size photograph requirement was retired (avatar covers it).
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
    assert snap["overall_percent"] == 0
    assert len(snap["missing_sections"]) == 3  # aadhaar + pan + education


def test_completion_partial_uploaded():
    docs = [
        _doc("aadhaar_card", "uploaded"),
        _doc("pan_card", "verified"),
    ]
    snap = compute_completion({"avatar": None}, docs)
    assert snap["onboarding_status"] == "partial"
    # 1 verified (1.0) + 1 uploaded (0.5) of 3 → 50%
    assert snap["onboarding_percent"] == 50


def test_completion_all_verified_no_avatar():
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "verified"),
        _doc("education", "verified"),
    ]
    snap = compute_completion({"avatar": None}, docs)
    assert snap["onboarding_status"] == "complete"
    assert snap["onboarding_percent"] == 100
    # Avatar is irrelevant to onboarding completion now
    assert snap["overall_percent"] == 100


def test_completion_fully_complete_with_avatar():
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "verified"),
        _doc("education", "verified"),
    ]
    snap = compute_completion(
        {"avatar": "https://res.cloudinary.com/x/y.jpg"}, docs,
    )
    assert snap["onboarding_status"] == "complete"
    assert snap["onboarding_percent"] == 100
    assert snap["overall_percent"] == 100
    assert snap["missing_sections"] == []


def test_completion_pending_review_caps_at_99():
    docs = [
        _doc("aadhaar_card", "uploaded"),
        _doc("pan_card", "uploaded"),
        _doc("education", "uploaded"),
    ]
    snap = compute_completion({"avatar": None}, docs)
    # All uploaded but none verified — strictly NOT complete.
    assert snap["onboarding_status"] == "partial"
    assert snap["onboarding_percent"] < 100


def test_completion_rejected_counts_as_missing():
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "rejected"),
        _doc("education", "verified"),
    ]
    snap = compute_completion({"avatar": "x"}, docs)
    assert snap["onboarding_status"] == "partial"
    assert any(m["type"] == "pan_card" for m in snap["missing_sections"])
    # 2 of 3 verified → 67% rounded
    assert snap["onboarding_percent"] == 67


def test_completion_ignores_legacy_photo_doc():
    """A `photo` document still present in the DB (pre-prune) must NOT
    count toward or against onboarding completion."""
    docs = [
        _doc("aadhaar_card", "verified"),
        _doc("pan_card", "verified"),
        _doc("education", "verified"),
        _doc("photo", "verified"),       # legacy
        _doc("photo", "not_uploaded"),   # legacy
    ]
    snap = compute_completion({"avatar": None}, docs)
    assert snap["onboarding_status"] == "complete"
    assert snap["onboarding_percent"] == 100
    assert all(m["type"] != "photo" for m in snap["missing_sections"])
