"""
Test RAG retriever — uses MockRAG so no OpenAI key needed.

  python app/rag/test_rag.py
"""
import sys, json
sys.path.insert(0, ".")

from pathlib import Path
from app.rag.retriever import MockRulesRAG

# Load rules docs with chunks (matches what ingestion creates)
BUCKET = Path("data/bucket")

def load_rules_docs():
    docs = []
    for filename, doc_id in [("weather_minima.md", "doc_weather"), 
                              ("dispatch_rules.md", "doc_dispatch")]:
        content = (BUCKET / filename).read_text()
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks = [{"chunk_id": f"{doc_id}#chunk{i+1}", "text": p}
                  for i, p in enumerate(paragraphs)]
        docs.append({"id": doc_id, "chunks": chunks})
    return docs

rules_docs = load_rules_docs()
rag = MockRulesRAG()
rag.index_documents(rules_docs)

print("\n── Query tests ──\n")

queries = [
    "What is the ceiling minima for PPL-2 students?",
    "Wind limits for solo flights",
    "Visibility requirements for advanced training",
    "Can SIM training proceed in bad weather?",
]

for q in queries:
    print(f"Q: {q}")
    results = rag.query(q, top_k=2)
    for chunk_id, text, score in results:
        snippet = text[:80].replace("\n", " ")
        print(f"  → {chunk_id} (score={score:.1f}): {snippet}...")
    print()