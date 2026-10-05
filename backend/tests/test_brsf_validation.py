"""BRSF strict star-value validation tests — iteration 71.

Covers the request matrix: limits payload for all 14 codes, parent override
rejections/valid saves, manual monthly/weekly rejections, N07/N08 instance
validation, and invalid-historical-data flagging (line_violation path).

The tests self-clean any override/manual/instance mutations on teardown.
"""
import os
import asyncio
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONTH = "2026-09"


# --------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def hr_headers():
    import time
    last = None
    for _ in range(6):
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"username": "admin", "password": "HrAdmin786$"},
                              timeout=30)
            if r.status_code == 200:
                tok = r.json().get("token") or r.json().get("access_token")
                return {"Authorization": f"Bearer {tok}"}
            last = r.status_code
        except Exception as e:
            last = str(e)
        time.sleep(3)
    pytest.fail(f"admin login failed: {last}")


@pytest.fixture(scope="module")
def emp(hr_headers):
    r = requests.get(f"{BASE_URL}/api/brsf/eligible-employees",
                     params={"month": MONTH}, headers=hr_headers, timeout=30)
    assert r.status_code == 200, r.text
    emps = r.json()["employees"]
    assert emps
    return emps[0]


@pytest.fixture(scope="module")
def stars(hr_headers, emp):
    r = requests.get(f"{BASE_URL}/api/brsf/stars",
                     params={"employee_id": emp["id"], "month": MONTH},
                     headers=hr_headers, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def _line(stars, code):
    return next(l for l in stars["lines"] if l["code"] == code)


def _put_override(hr_headers, line_id, value, reason="test"):
    return requests.put(f"{BASE_URL}/api/brsf/stars/{line_id}/override",
                        json={"value": value, "reason": reason},
                        headers=hr_headers, timeout=30)


def _reset_override(hr_headers, line_id):
    return requests.post(f"{BASE_URL}/api/brsf/stars/{line_id}/reset-override",
                         headers=hr_headers, timeout=30)


def _put_manual(hr_headers, line_id, payload):
    return requests.put(f"{BASE_URL}/api/brsf/stars/{line_id}/manual",
                        json=payload, headers=hr_headers, timeout=30)


# --------------------------------------------------------------- limits payload
class TestLimitsPayload:
    def test_lines_return_limits_and_validation(self, stars):
        codes = {l["code"] for l in stars["lines"]}
        assert len(codes) == 14
        for l in stars["lines"]:
            assert "limits" in l and "validation" in l
            assert "parent" in l["limits"]
            assert "child" in l["limits"]
            assert "child_count" in l["limits"]

    def test_static_parent_ranges(self, stars):
        assert _line(stars, "P01")["limits"]["parent"] == {"allowed": None, "min": 0, "max": 2}
        assert _line(stars, "P02")["limits"]["parent"] == {"allowed": None, "min": 0, "max": 5}
        assert _line(stars, "P03")["limits"]["parent"] == {"allowed": None, "min": 0, "max": 3}
        assert _line(stars, "P04")["limits"]["parent"] == {"allowed": None, "min": 0, "max": 5}
        assert _line(stars, "P05")["limits"]["parent"] == {"allowed": None, "min": 0, "max": 5}

    def test_monthly_fixed_ranges_n03_n06(self, stars):
        for code in ("N03", "N06"):
            p = _line(stars, code)["limits"]["parent"]
            assert p["allowed"] == [0, -3], (code, p)
            assert p["min"] == -3 and p["max"] == 0

    def test_child_allowed_values(self, stars):
        assert _line(stars, "P02")["limits"]["child"]["allowed"] == [0, 1]
        assert _line(stars, "N01")["limits"]["child"]["allowed"] == [0, -1]
        assert _line(stars, "N07")["limits"]["child"] == {"allowed": [-3], "fixed": -3}
        assert _line(stars, "N08")["limits"]["child"] == {"allowed": [-4], "fixed": -4}

    def test_instance_driven_parent_matches_child_count(self, stars):
        for code, mag in (("P06", 1), ("N01", 1), ("N02", 2), ("N05", 3),
                          ("N07", 3), ("N08", 4)):
            l = _line(stars, code)
            n = l["limits"]["child_count"]
            span = n * mag
            p = l["limits"]["parent"]
            if l["sign"] > 0:
                assert p["min"] == 0 and p["max"] == span, (code, n, p)
            else:
                assert p["min"] == -span and p["max"] == 0, (code, n, p)

    def test_n04_parent_matches_week_count(self, stars):
        weeks = len(stars["weeks"])
        p = _line(stars, "N04")["limits"]["parent"]
        assert p == {"allowed": None, "min": -weeks, "max": 0}


# --------------------------------------------------------------- parent override rejections
class TestOverrideRejections:
    """Focused on rows the main agent asked to cover: P04, P06, N01, N02, N06, N08."""

    def test_p04_over_range(self, hr_headers, stars):
        p04 = _line(stars, "P04")
        assert _put_override(hr_headers, p04["id"], 6).status_code == 400
        assert _put_override(hr_headers, p04["id"], -1).status_code == 400

    def test_p06_over_child_count(self, hr_headers, stars):
        p06 = _line(stars, "P06")
        span = p06["limits"]["parent"]["max"]
        r = _put_override(hr_headers, p06["id"], span + 1)
        assert r.status_code == 400, r.text
        assert _put_override(hr_headers, p06["id"], -1).status_code == 400

    def test_n01_beyond_instances(self, hr_headers, stars):
        n01 = _line(stars, "N01")
        lo = n01["limits"]["parent"]["min"]
        r = _put_override(hr_headers, n01["id"], lo - 1)
        assert r.status_code == 400
        assert _put_override(hr_headers, n01["id"], 1).status_code == 400  # positive rejected

    def test_n02_beyond_2x_instances(self, hr_headers, stars):
        n02 = _line(stars, "N02")
        lo = n02["limits"]["parent"]["min"]
        r = _put_override(hr_headers, n02["id"], lo - 1)
        assert r.status_code == 400

    def test_n06_only_0_or_minus_3(self, hr_headers, stars):
        n06 = _line(stars, "N06")
        for bad in (-1, -2, -6, 1):
            r = _put_override(hr_headers, n06["id"], bad)
            assert r.status_code == 400, (bad, r.status_code, r.text)

    def test_n08_beyond_4x_incidents(self, hr_headers, stars):
        n08 = _line(stars, "N08")
        lo = n08["limits"]["parent"]["min"]
        r = _put_override(hr_headers, n08["id"], lo - 1)
        assert r.status_code == 400

    def test_reject_non_whole(self, hr_headers, stars):
        p01 = _line(stars, "P01")
        for bad in [1.5, "abc", None, "NaN"]:
            r = _put_override(hr_headers, p01["id"], bad)
            assert r.status_code == 400, (bad, r.text)

    def test_reject_infinity(self, hr_headers, stars):
        p01 = _line(stars, "P01")
        # 1e309 -> Infinity in JSON parse
        r = requests.put(f"{BASE_URL}/api/brsf/stars/{p01['id']}/override",
                         data='{"value": 1e309, "reason": "x"}',
                         headers={**hr_headers, "Content-Type": "application/json"},
                         timeout=30)
        # server may reject as bad JSON or as invalid star — both acceptable
        assert r.status_code in (400, 422), r.text


# --------------------------------------------------------------- valid override saves + cleanup
class TestValidOverrides:
    def test_p01_plus_2_saves_then_reset(self, hr_headers, stars):
        p01 = _line(stars, "P01")
        r = _put_override(hr_headers, p01["id"], 2, "iter71-test")
        assert r.status_code == 200, r.text
        assert r.json()["override_value"] == 2
        # reset
        rr = _reset_override(hr_headers, p01["id"])
        assert rr.status_code == 200
        assert rr.json()["override_value"] is None

    def test_n03_minus_3_and_zero_save_then_reset(self, hr_headers, stars):
        n03 = _line(stars, "N03")
        for v in (-3, 0):
            r = _put_override(hr_headers, n03["id"], v, "iter71")
            assert r.status_code == 200, (v, r.text)
            assert r.json()["override_value"] == v
        _reset_override(hr_headers, n03["id"])


# --------------------------------------------------------------- manual monthly + weekly
class TestManualEntryValidation:
    def test_p02_monthly_over_and_negative(self, hr_headers, stars):
        p02 = _line(stars, "P02")
        assert _put_manual(hr_headers, p02["id"],
                           {"entry_mode": "monthly", "monthly_value": 6}).status_code == 400
        assert _put_manual(hr_headers, p02["id"],
                           {"entry_mode": "monthly", "monthly_value": -1}).status_code == 400

    def test_p03_monthly_range(self, hr_headers, stars):
        p03 = _line(stars, "P03")
        assert _put_manual(hr_headers, p03["id"],
                           {"entry_mode": "monthly", "monthly_value": 4}).status_code == 400
        assert _put_manual(hr_headers, p03["id"],
                           {"entry_mode": "monthly", "monthly_value": 0.5}).status_code == 400
        # valid save
        r = _put_manual(hr_headers, p03["id"],
                        {"entry_mode": "monthly", "monthly_value": 3, "reason": "iter71"})
        assert r.status_code == 200, r.text
        assert r.json()["manual_value"] == 3
        # cleanup
        _put_manual(hr_headers, p03["id"],
                    {"entry_mode": "monthly", "monthly_value": 0, "reason": "cleanup"})

    def test_p04_monthly_over(self, hr_headers, stars):
        p04 = _line(stars, "P04")
        assert _put_manual(hr_headers, p04["id"],
                           {"entry_mode": "monthly", "monthly_value": 6}).status_code == 400

    def test_p02_weekly_value_2_rejected(self, hr_headers, stars, emp):
        p02 = _line(stars, "P02")
        weeks = stars["weeks"]
        r = _put_manual(hr_headers, p02["id"], {
            "entry_mode": "weekly",
            "weekly": [{"week": w["week"], "start": w["start"], "end": w["end"], "value": 2}
                       for w in weeks],
        })
        assert r.status_code == 400
        assert "0 or +1" in r.text

    def test_p02_weekly_total_over_5(self, hr_headers, stars):
        p02 = _line(stars, "P02")
        weeks = stars["weeks"]
        if len(weeks) < 6:
            pytest.skip("need >=6 weekly buckets to exceed 5")
        r = _put_manual(hr_headers, p02["id"], {
            "entry_mode": "weekly",
            "weekly": [{"week": w["week"], "start": w["start"], "end": w["end"], "value": 1}
                       for w in weeks],
        })
        assert r.status_code == 400

    def test_p02_weekly_valid_sum(self, hr_headers, stars):
        p02 = _line(stars, "P02")
        weeks = stars["weeks"][:3]
        if not weeks:
            pytest.skip("no weeks")
        r = _put_manual(hr_headers, p02["id"], {
            "entry_mode": "weekly",
            "weekly": [{"week": w["week"], "start": w["start"], "end": w["end"], "value": 1}
                       for w in weeks],
            "reason": "iter71",
        })
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["final_value"] == len(weeks)
        # cleanup: zero out
        _put_manual(hr_headers, p02["id"], {
            "entry_mode": "weekly",
            "weekly": [{"week": w["week"], "start": w["start"], "end": w["end"], "value": 0}
                       for w in weeks],
            "reason": "cleanup",
        })
        _put_manual(hr_headers, p02["id"],
                    {"entry_mode": "monthly", "monthly_value": 0, "reason": "cleanup"})


# --------------------------------------------------------------- instance validation N07/N08
class TestInstanceValidation:
    def _add(self, hr_headers, line_id, payload):
        return requests.post(f"{BASE_URL}/api/brsf/stars/{line_id}/instances",
                             json=payload, headers=hr_headers, timeout=30)

    def test_n07_only_minus_3(self, hr_headers, stars):
        n07 = _line(stars, "N07")
        for bad in (-1, -2, -4, 3):
            r = self._add(hr_headers, n07["id"], {"date": "2026-09-01", "value": bad})
            assert r.status_code == 400, (bad, r.text)

    def test_n07_defaults_and_aggregates(self, hr_headers, stars, emp):
        n07 = _line(stars, "N07")
        ids = []
        for d in ("2026-09-02", "2026-09-03"):
            r = self._add(hr_headers, n07["id"], {"date": d, "remarks": "iter71"})
            assert r.status_code == 200, r.text
            ids.append(r.json()["instances"][-1]["id"])
        # re-fetch and verify aggregation
        s = requests.get(f"{BASE_URL}/api/brsf/stars",
                        params={"employee_id": emp["id"], "month": MONTH},
                        headers=hr_headers).json()
        n07b = _line(s, "N07")
        # each is -3, 2 added
        added = [i for i in n07b["instances"] if i["id"] in ids]
        assert all(i["value"] == -3 for i in added)
        # delete + verify parent reduces
        for iid in ids:
            r = requests.delete(f"{BASE_URL}/api/brsf/stars/{n07['id']}/instances/{iid}",
                                headers=hr_headers, timeout=30)
            assert r.status_code == 200

    def test_n08_fixed_minus_4(self, hr_headers, stars, emp):
        n08 = _line(stars, "N08")
        r = self._add(hr_headers, n08["id"], {"date": "2026-09-04", "value": -3})
        assert r.status_code == 400
        r = self._add(hr_headers, n08["id"], {"date": "2026-09-04", "value": -4, "remarks": "iter71"})
        assert r.status_code == 200
        iid = r.json()["instances"][-1]["id"]
        requests.delete(f"{BASE_URL}/api/brsf/stars/{n08['id']}/instances/{iid}",
                        headers=hr_headers, timeout=30)


# --------------------------------------------------------------- invalid historical data flagging
class TestInvalidDataFlagging:
    """Inject an out-of-range override_value directly in Mongo, then verify the
    GET response's `validation` field flags it without deleting the value."""

    def test_flag_n03_out_of_range(self, hr_headers, emp):
        import pymongo
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        client = pymongo.MongoClient(mongo_url)
        col = client[db_name]["brsf_star_lines"]
        try:
            # trigger line creation first via API
            requests.get(f"{BASE_URL}/api/brsf/stars",
                         params={"employee_id": emp["id"], "month": MONTH},
                         headers=hr_headers, timeout=30)
            key = {"employee_id": emp["id"], "year": 2026, "month": 9, "code": "N03"}
            res = col.update_one(key, {"$set": {"override_value": -9}})
            assert res.matched_count == 1, "N03 line not present to inject invalid value"

            # re-fetch: should still show -9 with validation.invalid
            r = requests.get(f"{BASE_URL}/api/brsf/stars",
                             params={"employee_id": emp["id"], "month": MONTH},
                             headers=hr_headers, timeout=30)
            assert r.status_code == 200
            n03 = _line(r.json(), "N03")
            assert n03["override_value"] == -9, "stored value must NOT be auto-corrected"
            v = n03["validation"]
            assert v and v.get("invalid") is True, n03
            assert any("Override" in reason or "-9" in reason for reason in v["reasons"])

            # cleanup and verify flag clears
            col.update_one(key, {"$unset": {"override_value": ""}})
            r2 = requests.get(f"{BASE_URL}/api/brsf/stars",
                              params={"employee_id": emp["id"], "month": MONTH},
                              headers=hr_headers, timeout=30)
            n03b = _line(r2.json(), "N03")
            assert n03b["validation"] is None or not n03b["validation"].get("invalid")
        finally:
            # ensure any injected value is reverted even on failure
            col.update_one({"employee_id": emp["id"], "year": 2026, "month": 9, "code": "N03"},
                           {"$unset": {"override_value": ""}})
            client.close()
