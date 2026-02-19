"""
Run this to verify schemas + chunking logic without a real DB.
Uses stdlib only — no pydantic/sqlalchemy needed.
  python app/ingestion/test_dry_run.py
"""
import sys, json, hashlib
from pathlib import Path

BUCKET = Path("data/bucket")

def _chunk_text(text: str, doc_id: str) -> list:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [{"chunk_id": f"{doc_id}#chunk{i+1}", "text": p}
            for i, p in enumerate(paragraphs)]

def _bucket_hash() -> str:
    combined = "".join(
        hashlib.md5(f.read_bytes()).hexdigest()
        for f in sorted(BUCKET.iterdir()) if f.is_file()
    )
    return hashlib.md5(combined.encode()).hexdigest()

BUCKET = Path("data/bucket")

REQUIRED_FIELDS = {
    "students.json":    ["id", "name", "stage", "availability"],
    "instructors.json": ["id", "name", "ratings", "currency", "availability"],
    "aircraft.json":    ["id", "type", "status", "availability_windows"],
    "simulators.json":  ["id", "type", "max_sessions_per_day", "availability"],
    "time_slots.json":  ["id", "start_time", "end_time"],
}

def test_schemas():
    for filename, required in REQUIRED_FIELDS.items():
        raw = json.loads((BUCKET / filename).read_text())
        for record in raw:
            missing = [f for f in required if f not in record]
            assert not missing, f"{filename}: missing fields {missing} in {record.get('id')}"
        print(f"✅ {filename}: {len(raw)} records valid")

def test_chunking():
    for doc_file, doc_id in [("weather_minima.md", "doc_weather"), ("dispatch_rules.md", "doc_dispatch")]:
        content = (BUCKET / doc_file).read_text()
        chunks = _chunk_text(content, doc_id)
        print(f"✅ {doc_file}: {len(chunks)} chunks → {[c['chunk_id'] for c in chunks[:3]]}")

def test_hash():
    h = _bucket_hash()
    print(f"✅ Bucket hash: {h}")

if __name__ == "__main__":
    test_schemas()
    test_chunking()
    test_hash()
    print("\nAll dry-run checks passed.")