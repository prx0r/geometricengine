import json
import sqlite3
from typing import Any
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
_model = None
_embeddings = None
_embed_ids = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _load_index(embeddings_path: str):
    global _embeddings, _embed_ids
    if _embeddings is not None:
        return
    ids = []
    embs = []
    with open(embeddings_path) as f:
        for line in f:
            row = json.loads(line)
            ids.append(row["id"])
            embs.append(row["embedding"])
    _embed_ids = ids
    _embeddings = np.array(embs)


def retrieve_mythoughts(query: str, k: int = 6, embeddings_path: str = "data/embeddings.jsonl",
                        db_path: str = "data/engine.sqlite") -> list[dict]:
    _load_index(embeddings_path)
    model = _get_model()
    q_emb = model.encode([query])[0]
    sims = np.dot(_embeddings, q_emb) / (
        np.linalg.norm(_embeddings, axis=1) * np.linalg.norm(q_emb) + 1e-10
    )
    top_k = np.argsort(sims)[-k:][::-1]

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    results = []
    for idx in top_k:
        he_id = _embed_ids[idx]
        cur.execute("""
            SELECT id, mythought_text, lineage, phase,
                   function_id, mechanism_shape, intent, impact_predicted
            FROM mythought_hyperedges WHERE id = ?
        """, (he_id,))
        row = cur.fetchone()
        if row:
            results.append({
                "id": row[0],
                "mythought_text": row[1],
                "compression": (row[1] or "")[:200],
                "lineage": row[2],
                "phase": row[3],
                "function_id": row[4],
                "mechanism_shape": row[5],
                "intent": row[6],
                "predicted_impact": row[7],
                "similarity": float(sims[idx]),
            })

    conn.close()
    return results


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "I am spiralling and adding too many modules"
    results = retrieve_mythoughts(query)
    print(f"Top {len(results)} similar my_thoughts:")
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['function_id']} | {r.get('compression', '')[:100]}")
