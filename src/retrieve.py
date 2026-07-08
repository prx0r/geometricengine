import json
import sqlite3
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
            SELECT id, mythought_text, compression, lineage, phase,
                   function_id, mechanism_shape, intent, predicted_impact
            FROM mythought_hyperedges WHERE id = ?
        """, (he_id,))
        row = cur.fetchone()
        if row:
            results.append({
                "id": row[0],
                "mythought_text": row[1],
                "compression": row[2],
                "lineage": row[3],
                "phase": row[4],
                "function_id": row[5],
                "mechanism_shape": row[6],
                "intent": row[7],
                "predicted_impact": row[8],
                "similarity": float(sims[idx]),
            })

    conn.close()
    return results


def aggregate_candidate_nodes(hyperedges: list[dict],
                               policy_weights_path: str = "data/engine.sqlite") -> dict:
    functions = {}
    mechanisms = {}
    impacts = {}
    states = {}
    actions = {}
    registers = {}
    traps = {}

    for he in hyperedges:
        sim = he.get("similarity", 0.5)
        fname = he.get("function_id")
        mshape = he.get("mechanism_shape")
        impact = he.get("predicted_impact")
        state = he.get("student_state_from_incidence")

        if fname:
            functions[fname] = functions.get(fname, 0) + sim
        if mshape:
            mechanisms[mshape] = mechanisms.get(mshape, 0) + sim
        if impact:
            impacts[impact] = impacts.get(impact, 0) + sim
        if state:
            states[state] = states.get(state, 0) + sim

    # Load policy weights and blend
    try:
        import sqlite3
        conn = sqlite3.connect(policy_weights_path)
        cur = conn.cursor()
        cur.execute("SELECT from_value, to_value, weight FROM policy_weights WHERE from_type = 'retrieved_function'")
        pw_rows = cur.fetchall()
        conn.close()
        for from_val, to_val, weight in pw_rows:
            if from_val in functions and weight > 0:
                functions[to_val] = functions.get(to_val, 0) + weight * 0.5
    except Exception:
        pass

    return {
        "top_functions": sorted(functions.items(), key=lambda x: -x[1])[:5],
        "top_mechanisms": sorted(mechanisms.items(), key=lambda x: -x[1])[:5],
        "top_impacts": sorted(impacts.items(), key=lambda x: -x[1])[:5],
        "top_states": sorted(states.items(), key=lambda x: -x[1])[:5],
        "hyperedges_used": len(hyperedges),
    }


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "I am spiralling and adding too many modules"
    results = retrieve_mythoughts(query)
    print(f"Top {len(results)} similar my_thoughts:")
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['function_id']} | {r['compression'][:100]}")
    candidates = aggregate_candidate_nodes(results)
    print(f"\nCandidate functions: {candidates['top_functions']}")
    print(f"Candidate mechanisms: {candidates['top_mechanisms']}")
