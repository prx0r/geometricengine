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


def score_pathway_candidates(hyperedges: list[dict],
                             candidate_nodes: dict[str, Any],
                             classification: dict[str, Any] | None = None,
                             db_path: str = "data/engine.sqlite") -> list[dict[str, Any]]:
    cand_functions = dict(candidate_nodes.get("top_functions", []))
    cand_mechanisms = dict(candidate_nodes.get("top_mechanisms", []))
    cand_impacts = dict(candidate_nodes.get("top_impacts", []))
    cand_states = dict(candidate_nodes.get("top_states", []))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    candidates = []
    for fn, fn_score in cand_functions.items():
        mech = None
        impact = None
        for m, m_score in cand_mechanisms.items():
            if m_score > 0:
                mech = m
                break

        for imp, imp_score in cand_impacts.items():
            if imp_score > 0:
                impact = imp
                break

        cur.execute("""
            SELECT from_value, to_value, weight, success_count, failure_count
            FROM policy_weights
            WHERE from_type = 'retrieved_function' AND from_value = ?
        """, (fn,))
        pw_rows = cur.fetchall()

        policy_bonus = 0.0
        for _, to_val, weight, succ, fail in pw_rows:
            total = succ + fail
            if total > 0:
                policy_bonus += weight * (succ / total)

        combined_score = fn_score + policy_bonus

        cls_fn_hint = (classification or {}).get("function_hint")
        cls_phase_hint = (classification or {}).get("phase_hint")
        cls_mech_hint = (classification or {}).get("mechanism_hint")

        if cls_fn_hint and cls_fn_hint == fn:
            combined_score += 0.5
        if cls_mech_hint and cls_mech_hint == (mech or ""):
            combined_score += 0.3

        from src.models.function import HXRMXSFunction
        fn_enum = HXRMXSFunction.from_str(fn.replace(" ", "_"))
        phase = fn_enum.phase.value if fn_enum else (cls_phase_hint or "UNMAKING")

        if cls_phase_hint and cls_phase_hint == phase:
            combined_score += 0.2

        actions = []
        traps = []
        for he in hyperedges:
            if he.get("function_id") == fn:
                incs = _get_incidences_for_hyperedge(he["id"], cur)
                for inc in incs:
                    if inc["node_type"] == "teaching_action":
                        actions.append(inc["node_value"])
                    elif inc["node_type"] == "trap_avoided":
                        traps.append(inc["node_value"])

        unique_actions = list(dict.fromkeys(actions))
        unique_traps = list(dict.fromkeys(traps))

        register_intensity = None
        register_attunement = None
        for he in hyperedges:
            if he.get("function_id") == fn:
                incs = _get_incidences_for_hyperedge(he["id"], cur)
                for inc in incs:
                    if inc["node_type"] == "register" and inc["node_value"].startswith("intensity="):
                        register_intensity = inc["node_value"].split("=")[1]
                    if inc["node_type"] == "register" and inc["node_value"].startswith("attunement="):
                        register_attunement = inc["node_value"].split("=")[1]

        candidates.append({
            "function_id": fn,
            "mechanism_shape": mech,
            "phase": phase,
            "predicted_impact": impact or "unknown",
            "teaching_actions": unique_actions[:5],
            "traps_avoided": unique_traps[:3],
            "register_intensity": register_intensity,
            "register_attunement": register_attunement,
            "score": round(combined_score, 4),
            "retrieval_score": round(fn_score, 4),
            "policy_bonus": round(policy_bonus, 4),
        })

    conn.close()
    candidates.sort(key=lambda c: -c["score"])
    return candidates


def _get_incidences_for_hyperedge(he_id: str, cur) -> list[dict]:
    cur.execute("""
        SELECT node_type, node_value, role, weight
        FROM mythought_incidences WHERE hyperedge_id = ?
    """, (he_id,))
    rows = cur.fetchall()
    return [
        {"node_type": r[0], "node_value": r[1], "role": r[2], "weight": r[3]}
        for r in rows
    ]


def select_pathway(pathway_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not pathway_candidates:
        return {
            "function_id": None,
            "mechanism_shape": None,
            "phase": None,
            "predicted_impact": "",
            "teaching_actions": [],
            "traps_avoided": [],
            "register_intensity": None,
            "register_attunement": None,
            "score": 0.0,
        }
    return pathway_candidates[0]


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "I am spiralling and adding too many modules"
    results = retrieve_mythoughts(query)
    print(f"Top {len(results)} similar my_thoughts:")
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['function_id']} | {r.get('compression', '')[:100]}")
    candidates = aggregate_candidate_nodes(results)
    print(f"\nCandidate functions: {candidates['top_functions']}")
    print(f"Candidate mechanisms: {candidates['top_mechanisms']}")
    scored = score_pathway_candidates(results, candidates)
    print(f"\nScored pathways ({len(scored)}):")
    for s in scored[:3]:
        print(f"  {s['function_id']:30s} score={s['score']:.3f}  phase={s['phase']}")
    best = select_pathway(scored)
    print(f"\nSelected: {best['function_id']}")
