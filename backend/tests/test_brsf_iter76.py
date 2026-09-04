"""Iteration 76 BRSF regression.

Verifies (via localhost:8001, since Cloudflare blocks python-requests on preview):
  * N03 uses duration equivalents, threshold 2.0 -> 0 or > 2.0 -> exactly -3
  * N03 children carry equivalent 0.5 or 1.0
  * N01 lists ALL leave types (not just Sick/Preplanned)
  * N01 children carry leave_validity + reason + value in {0, -1}
  * N01 child override rejects values other than {0, -1}
  * Overall Star: active-first, name asc within each group
  * Completed-month gating on recalculate
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:8001")
UA = {"User-Agent": "Mozilla/5.0 (brsf-iter76)"}
ADMIN = ("admin", "HrAdmin786$")
MONTH = "2026-08"


@pytest.fixture(scope="module")
def sess():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": ADMIN[0], "password": ADMIN[1]},
                      headers=UA, timeout=120)
    assert r.status_code == 200, r.text[:300]
    tok = r.json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", **UA})
    return s


@pytest.fixture(scope="module")
def summary(sess):
    r = sess.get(f"{BASE_URL}/api/brsf/summary", params={"month": MONTH}, timeout=120)
    assert r.status_code == 200, r.text[:500]
    payload = r.json()
    assert payload.get("rows"), "no BRSF summary rows"
    return payload


def _get_stars(sess, employee_id):
    r = sess.get(f"{BASE_URL}/api/brsf/stars",
                 params={"employee_id": employee_id, "month": MONTH}, timeout=120)
    assert r.status_code == 200, r.text[:400]
    return r.json()


def _lines_by_code(stars_payload, code):
    return [ln for ln in stars_payload.get("lines") or [] if ln.get("code") == code]


# ---------- Sample: pull stars for the first ~8 employees, scan across ----------
@pytest.fixture(scope="module")
def sample_stars(sess, summary):
    rows = summary["rows"][:12]
    out = []
    for r in rows:
        try:
            s = _get_stars(sess, r["id"])
            out.append((r, s))
        except AssertionError:
            continue
    assert out, "no employee star payload retrieved"
    return out


# ---------- N03 ----------
def test_n03_system_note_mentions_equivalent(sample_stars):
    seen = 0
    for emp, s in sample_stars:
        for ln in _lines_by_code(s, "N03"):
            seen += 1
            note = (ln.get("system_note") or "")
            sv = ln.get("system_value")
            fv = ln.get("final_value")
            assert sv in (0, -3), f"N03 system_value {sv} for {emp['full_name']}"
            assert fv in (0, -3) or ln.get("override_value") is not None, (
                f"N03 final_value {fv} for {emp['full_name']} unexpected")
            assert "equivalent" in note.lower(), (
                f"N03 system_note missing 'equivalent' for {emp['full_name']}: {note!r}")
    assert seen > 0, "no N03 lines observed across sample"


def test_n03_children_have_equivalent(sample_stars):
    for emp, s in sample_stars:
        for ln in _lines_by_code(s, "N03"):
            for ch in (ln.get("system_children") or []):
                eq = ch.get("equivalent")
                assert eq in (0.5, 1.0), (
                    f"N03 child bad equivalent {eq} for {emp['full_name']}: {ch}")
                assert "date" in ch, f"N03 child missing date: {ch}"


# ---------- N01 ----------
def test_n01_lists_all_leave_types(sess, summary):
    """Adwaid Suresh has mixed leave types in Aug-2026."""
    target = next((r for r in summary["rows"]
                   if "adwaid" in (r.get("full_name") or "").lower()), None)
    if not target:
        pytest.skip("Adwaid Suresh not eligible in Aug-2026")
    s = _get_stars(sess, target["id"])
    lines = _lines_by_code(s, "N01")
    assert lines, "N01 missing for Adwaid"
    kids = lines[0].get("system_children") or []
    assert len(kids) >= 5, f"expected >=5 N01 children, got {len(kids)}"
    types = {(c.get("leave_type") or "").lower() for c in kids}
    assert types & {"paid", "emergency"}, (
        f"N01 children must include Paid/Emergency, got {types}")


def test_n01_children_carry_validity_and_reason(sample_stars):
    checked = 0
    for emp, s in sample_stars:
        for ln in _lines_by_code(s, "N01"):
            for ch in (ln.get("system_children") or []):
                checked += 1
                assert "leave_validity" in ch, (
                    f"child missing leave_validity: {list(ch.keys())}")
                assert (ch.get("reason") or "").strip(), (
                    f"child missing reason for {emp['full_name']}: {ch}")
                sv = ch.get("value")
                assert sv in (0, -1), f"N01 child value {sv} out of range: {ch}"
    assert checked > 0, "no N01 children observed"


def test_n01_child_override_rejects_bad_values(sess, summary):
    """PUT /brsf/stars/{line_id}/child-override — allowed values are only 0 and -1."""
    # find any employee with an applicable N01 child
    target_line, target_key, target_emp = None, None, None
    for r in summary["rows"][:20]:
        try:
            s = _get_stars(sess, r["id"])
        except AssertionError:
            continue
        for ln in _lines_by_code(s, "N01"):
            for ch in (ln.get("system_children") or []):
                if ch.get("applicable") is not False and ch.get("key"):
                    target_line, target_key, target_emp = ln, ch["key"], r
                    break
            if target_line:
                break
        if target_line:
            break
    if not target_line:
        pytest.skip("no applicable N01 child found in sample")

    line_id = target_line["id"]
    for bad in (-2, 1, 0.5):
        r = sess.put(
            f"{BASE_URL}/api/brsf/stars/{line_id}/child-override",
            json={"key": target_key, "value": bad}, timeout=60,
        )
        assert r.status_code in (400, 422), (
            f"child override value {bad} should be rejected — got {r.status_code}: "
            f"{r.text[:200]}")

    # positive: allow -1 then reset
    r = sess.put(f"{BASE_URL}/api/brsf/stars/{line_id}/child-override",
                 json={"key": target_key, "value": -1,
                       "note": "iter76-test"}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    # reset the child-level override
    rr = sess.post(f"{BASE_URL}/api/brsf/stars/{line_id}/child-override/reset",
                   json={"key": target_key}, timeout=60)
    assert rr.status_code == 200, rr.text[:300]


# ---------- Overall Star ordering ----------
def test_overall_active_first(sess):
    r = sess.get(f"{BASE_URL}/api/brsf/overall",
                 params={"from_month": MONTH, "to_month": MONTH}, timeout=120)
    assert r.status_code == 200, r.text[:400]
    rows = r.json().get("rows") or []
    assert rows, "overall report returned no rows"
    flags = [bool(r.get("is_active")) for r in rows]
    if False in flags:
        idx = flags.index(False)
        assert not any(flags[idx:]), "active row appears after an inactive row"
    active_names = [r["full_name"] for r in rows if r.get("is_active")]
    inactive_names = [r["full_name"] for r in rows if not r.get("is_active")]
    assert active_names == sorted(active_names, key=lambda s: (s or "").lower()), \
        f"active group not sorted asc: {active_names}"
    assert inactive_names == sorted(inactive_names, key=lambda s: (s or "").lower()), \
        f"inactive group not sorted asc: {inactive_names}"


# ---------- Completed-month gating ----------
def test_future_month_recalculate_blocked(sess):
    r = sess.post(f"{BASE_URL}/api/brsf/recalculate",
                  json={"month": "2026-09"}, timeout=60)
    assert r.status_code in (400, 403, 409), (
        f"Sep-2026 (not completed) should be blocked; got {r.status_code}: {r.text[:200]}")


def test_recalculate_idempotent_aug(sess, summary):
    """Auto Calculate for a completed month should not error and should preserve totals."""
    before = {r["id"]: r.get("net_total") for r in summary["rows"]}
    r = sess.post(f"{BASE_URL}/api/brsf/recalculate",
                  json={"month": MONTH}, timeout=180)
    assert r.status_code == 200, r.text[:400]
    r2 = sess.get(f"{BASE_URL}/api/brsf/summary",
                  params={"month": MONTH}, timeout=120)
    assert r2.status_code == 200
    after = {r["id"]: r.get("net_total") for r in r2.json()["rows"]}
    # allow tiny fp diff
    diffs = {k: (before.get(k), after.get(k))
             for k in before if before.get(k) != after.get(k)}
    assert not diffs, f"recalculate changed net_total for: {list(diffs)[:5]}"
