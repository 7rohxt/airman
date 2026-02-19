"""
RAG over rules documents.

Uses OpenAI embeddings + FAISS for vector search.
Once initialized, you can query for relevant rule chunks and get citations.

Usage:
    rag = RulesRAG()
    rag.index_documents(rules_docs)  # list of RulesDoc from DB
    results = rag.query("ceiling minima for PPL-2 students", top_k=3)
    # returns [(chunk_id, text, score), ...]
"""
import os
from typing import Optional
import numpy as np

try:
    import openai
    import faiss
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class RulesRAG:
    def __init__(self, openai_api_key: Optional[str] = None):
        if not HAS_DEPS:
            raise ImportError("Install: pip install openai faiss-cpu")
        
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        openai.api_key = self.api_key
        
        self.index = None
        self.chunks = []  # [(chunk_id, text), ...]
        self.dimension = 1536  # text-embedding-3-small dimension

    def index_documents(self, rules_docs: list):
        """
        Embed and index all rule doc chunks.
        rules_docs: list of dicts with {'id', 'chunks': [{'chunk_id', 'text'}]}
        """
        all_chunks = []
        for doc in rules_docs:
            for chunk in doc.get("chunks", []):
                all_chunks.append((chunk["chunk_id"], chunk["text"]))
        
        if not all_chunks:
            raise ValueError("No chunks to index")
        
        self.chunks = all_chunks
        texts = [text for _, text in all_chunks]
        
        # Batch embed
        embeddings = self._embed_batch(texts)
        embeddings_np = np.array(embeddings).astype('float32')
        
        # Build FAISS index
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings_np)
        
        print(f"[RAG] Indexed {len(all_chunks)} chunks")

    def query(self, query_text: str, top_k: int = 3) -> list[tuple]:
        """
        Query for relevant chunks.
        Returns: [(chunk_id, text, distance), ...]
        """
        if self.index is None:
            raise RuntimeError("Index not built — call index_documents() first")
        
        query_embedding = self._embed_batch([query_text])[0]
        query_np = np.array([query_embedding]).astype('float32')
        
        distances, indices = self.index.search(query_np, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                chunk_id, text = self.chunks[idx]
                results.append((chunk_id, text, float(distances[0][i])))
        
        return results

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using OpenAI API."""
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [item.embedding for item in response.data]


# ── Mock RAG for testing (no OpenAI key needed) ───────────────────────────────

class MockRulesRAG:
    """
    Deterministic mock — returns hardcoded chunks for known queries.
    Use this for testing without API calls.
    """
    def __init__(self):
        self.chunks = []
    
    def index_documents(self, rules_docs: list):
        for doc in rules_docs:
            for chunk in doc.get("chunks", []):
                self.chunks.append((chunk["chunk_id"], chunk["text"]))
        print(f"[MockRAG] Indexed {len(self.chunks)} chunks")
    
    def query(self, query_text: str, top_k: int = 3) -> list[tuple]:
        # Simple keyword match
        query_lower = query_text.lower()
        scored = []
        
        for chunk_id, text in self.chunks:
            text_lower = text.lower()
            score = 0
            if "ceiling" in query_lower and "ceiling" in text_lower:
                score += 10
            if "visibility" in query_lower and "visibility" in text_lower:
                score += 10
            if "wind" in query_lower and "wind" in text_lower:
                score += 10
            if "solo" in query_lower and "solo" in text_lower:
                score += 10
            if "ppl" in query_lower and "ppl" in text_lower:
                score += 5
            if score > 0:
                scored.append((chunk_id, text, 100 - score))  # lower = better
        
        scored.sort(key=lambda x: x[2])
        return scored[:top_k]