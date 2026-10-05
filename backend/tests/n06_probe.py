import os, sys, json, requests

API = "http://localhost:8001"
S = requests.Session()
TOKEN = S.post(API + "/api/auth/login",
               json={"username": "admin", "password": "HrAdmin786$"}).json()["token"]
S.headers["Authorization"] = f"Bearer {TOKEN}"


def get(path):
    r = S.get(API + path, timeout=120)
    r.raise_for_status()
    return r.json()


months = sys.argv[1:] or ["2026-04", "2026-05", "2026-06"]
hits = []
for m in months:
    emps = get(f"/api/brsf/eligible-employees?month={m}")["employees"]
    for e in emps:
        try:
            d = get(f"/api/brsf/stars?employee_id={e['id']}&month={m}")
        except Exception as ex:
            print("ERR", e["full_name"], m, ex)
            continue
        line = next((l for l in d["lines"] if l["code"] == "N06"), None)
        if not line:
            print("NO N06 LINE", e["full_name"], m)
            continue
        ch = line.get("system_children") or []
        if ch:
            eq = round(sum(c["equivalent"] for c in ch), 2)
            dates = [c["date"] for c in ch]
            dup = len(dates) != len(set(dates))
            expected = -3 if eq > 4.0 else 0
            ok = line["system_value"] == expected
            hits.append((m, e["full_name"], eq, line["system_value"], expected, ok, dup, len(ch)))

hits.sort(key=lambda x: -x[2])
print(f"{'month':8} {'name':28} {'equiv':>6} {'sys':>4} {'exp':>4} {'ok':>5} {'dup':>4} {'n':>3}")
for h in hits[:40]:
    print(f"{h[0]:8} {h[1][:28]:28} {h[2]:>6} {h[3]:>4} {h[4]:>4} {str(h[5]):>5} {str(h[6]):>4} {h[7]:>3}")
print("total with children:", len(hits))
print("FAILURES:", [h for h in hits if not h[5] or h[6]])
