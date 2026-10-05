"""Replace-Offer-Letter regression test.

Scenarios:
  1. Fresh upload creates one row.
  2. Second upload replaces the row (same DB id, new file_url/public_id).
  3. Race-condition duplicate rows are pruned to exactly one on next upload.
"""
import os, sys, asyncio, uuid, json, requests

BASE = "http://localhost:8001"

def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]

def get_first_employee(tok):
    r = requests.get(f"{BASE}/api/employees", headers={"Authorization": f"Bearer {tok}"}, params={"limit": 1}, timeout=15)
    r.raise_for_status()
    data = r.json()
    emps = data if isinstance(data, list) else data.get("employees") or data.get("items") or []
    assert emps, "no employees"
    return emps[0]["id"]

def upload(tok, emp_id, url, name, ftype, pid):
    r = requests.post(
        f"{BASE}/api/employees/{emp_id}/documents",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "file_url": url,
            "file_name": name,
            "file_type": ftype,
            "file_public_id": pid,
            "document_type": "offer_letter",
        },
        timeout=20,
    )
    print("upload", r.status_code, r.text[:250])
    r.raise_for_status()
    return r.json()

def list_docs(tok, emp_id):
    r = requests.get(f"{BASE}/api/employees/{emp_id}/documents", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    r.raise_for_status()
    return r.json()["documents"]

async def inject_dupe(emp_id):
    """Directly insert a rogue second offer_letter row (simulates a race)."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    rogue_id = str(uuid.uuid4())
    await db.employee_documents.insert_one({
        "id": rogue_id,
        "employee_id": emp_id,
        "document_type": "offer_letter",
        "file_url": "https://res.cloudinary.com/dummy/upload/rogue.pdf",
        "file_name": "rogue.pdf",
        "file_type": "application/pdf",
        "file_public_id": "blubridge/documents/rogue-race",
        "uploaded_by": "test",
        "uploaded_by_name": "race",
        "uploaded_at": "2020-01-01T00:00:00",
        "updated_at": "2020-01-01T00:00:00",
    })
    client.close()
    return rogue_id

def main():
    tok = login("admin", "HrAdmin786$")
    emp_id = get_first_employee(tok)
    print("Testing with employee:", emp_id)

    # Snapshot existing offer_letter (test isolation)
    pre = [d for d in list_docs(tok, emp_id) if d["document_type"] == "offer_letter"]
    print("Pre-existing offer_letter rows:", len(pre))

    # 1) First upload
    r1 = upload(tok, emp_id, "https://res.cloudinary.com/dummy/upload/v1/first.pdf", "first.pdf", "application/pdf", "blubridge/documents/first_seed")
    docs = [d for d in list_docs(tok, emp_id) if d["document_type"] == "offer_letter"]
    assert len(docs) == 1, f"expected 1, got {len(docs)}"
    id1 = docs[0]["id"]
    assert docs[0]["file_public_id"] == "blubridge/documents/first_seed", docs[0]
    print("STEP1 OK: id=", id1, "url=", docs[0]["file_url"])

    # 2) Replace upload
    r2 = upload(tok, emp_id, "https://res.cloudinary.com/dummy/upload/v1/second.pdf", "second.pdf", "application/pdf", "blubridge/documents/second_seed")
    docs = [d for d in list_docs(tok, emp_id) if d["document_type"] == "offer_letter"]
    assert len(docs) == 1, f"expected exactly 1 offer_letter after replace, got {len(docs)}: {docs}"
    assert docs[0]["id"] == id1, "primary row id must be preserved across replacement"
    assert docs[0]["file_public_id"] == "blubridge/documents/second_seed", f"public_id not updated: {docs[0]}"
    assert docs[0]["file_name"] == "second.pdf"
    assert docs[0]["file_url"].endswith("second.pdf")
    print("STEP2 OK: replacement kept id, updated public_id/url/name to new.")

    # 3) Inject a duplicate row and re-upload → duplicates must be pruned.
    rogue_id = asyncio.run(inject_dupe(emp_id))
    docs = [d for d in list_docs(tok, emp_id) if d["document_type"] == "offer_letter"]
    assert len(docs) == 2, f"expected 2 after inject, got {len(docs)}"
    print("Injected rogue dupe id:", rogue_id, "→ rows now:", len(docs))

    r3 = upload(tok, emp_id, "https://res.cloudinary.com/dummy/upload/v1/third.pdf", "third.pdf", "application/pdf", "blubridge/documents/third_seed")
    docs = [d for d in list_docs(tok, emp_id) if d["document_type"] == "offer_letter"]
    assert len(docs) == 1, f"expected exactly 1 after dupe prune, got {len(docs)}: {docs}"
    assert docs[0]["file_public_id"] == "blubridge/documents/third_seed"
    print("STEP3 OK: race duplicate pruned, exactly one row remains.")

    print("\nALL OFFER-LETTER REPLACE TESTS PASSED")

if __name__ == "__main__":
    main()
