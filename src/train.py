"""Train graph weights from ALL UNO fields.

Loads directly from the parser (which extracts all fields) — not from the truncated DB.
Trains on the prediction loop: state → action → predicted impact → actual next state.
"""
import sqlite3
import json
import re
import uuid
from collections import defaultdict, Counter
from typing import Any
from src.models.function import HXRMXSFunction
from src.parser.uno_parser import parse_uno, build_transitions


def load_from_parser(uno_path: str = "data/uno.txt") -> tuple[list, list]:
    records = parse_uno(uno_path)
    transitions = build_transitions(records)
    return records, transitions


def extract_full_turn(record, next_record=None):
    """Extract every field from a parsed turn record."""
    p = record.pedagogy
    reg = p.register

    result = {
        "episode_id": record.episode_id,
        "turn_index": record.turn_index,
        "lineage": p.lineage,
        "user_text": record.user_text or "",
        "assistant_text": record.assistant_visible_text or "",
        "student_state": p.student_state or "",
        "behavior_tags": p.behavior_tags or [],
        "phase": p.phase.name if p.phase else "",
        "function_id": p.function_id.name if p.function_id else "",
        "mechanism_shape": p.mechanism_shape.value if p.mechanism_shape else "",
        "teaching_actions": p.teaching_actions or [],
        "register_intensity": reg.intensity.name if reg else "",
        "register_intimacy": reg.intimacy.name if reg else "",
        "register_attunement": reg.attunement.name if reg else "",
        "register_style": reg.style.name if reg else "",
        "register_depth": reg.depth.name if reg else "",
        "register_meta_mode": reg.meta_mode.name if reg else "",
        "traps_avoided": p.traps_avoided or [],
        "intent": p.intent or "",
        "approach": p.approach or "",
        "impact_predicted": p.impact_predicted or "",
        "impact_confidence": p.impact_confidence or "",
        "impact_update": p.impact_update or "",
        "accumulated_insight": p.accumulated_insight or "",
        "my_thoughts": p.my_thoughts or "",
    }

    if next_record:
        np = next_record.pedagogy
        result["to_state"] = np.student_state or ""
        result["next_user_text"] = next_record.user_text or ""
        result["next_behavior_tags"] = np.behavior_tags or []
    else:
        result["to_state"] = ""
        result["next_user_text"] = ""
        result["next_behavior_tags"] = []

    return result


def train_all(db_path: str = "data/engine.sqlite"):
    records, transitions = load_from_parser()

    # Group by episode and sort by turn_index
    episodes = defaultdict(list)
    for r in records:
        episodes[r.episode_id].append(r)
    for ep_id in episodes:
        episodes[ep_id].sort(key=lambda r: r.turn_index)

    # Build transition lookup: (from_state, to_state) → prediction_match
    match_lookup = {}
    for t in transitions:
        match_lookup[(t.from_state, t.to_state)] = t.prediction_match

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create full transitions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uno_transitions (
            id TEXT PRIMARY KEY,
            episode_id TEXT, turn_index INTEGER,
            lineage TEXT, user_text TEXT, assistant_text TEXT,
            student_state TEXT, behavior_tags TEXT,
            phase TEXT, function_id TEXT, mechanism_shape TEXT,
            teaching_actions TEXT,
            register_intensity TEXT, register_intimacy TEXT, register_attunement TEXT,
            register_style TEXT, register_depth TEXT, register_meta_mode TEXT,
            traps_avoided TEXT,
            intent TEXT, approach TEXT,
            impact_predicted TEXT, impact_confidence TEXT, impact_update TEXT,
            accumulated_insight TEXT, my_thoughts TEXT,
            to_state TEXT, next_user_text TEXT,
            prediction_match TEXT
        )
    """)
    cur.execute("DELETE FROM uno_transitions")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS policy_weights (
            id TEXT PRIMARY KEY,
            from_type TEXT, from_value TEXT,
            to_type TEXT, to_value TEXT,
            weight REAL DEFAULT 0.0,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0
        )
    """)
    cur.execute("DELETE FROM policy_weights")

    weight_data = defaultdict(lambda: {"total": 0.0, "count": 0, "success": 0, "failure": 0})
    inserted = 0

    for ep_id, ep_records in episodes.items():
        for i, rec in enumerate(ep_records):
            next_rec = ep_records[i + 1] if i + 1 < len(ep_records) else None
            t = extract_full_turn(rec, next_rec)

            if not t["student_state"]:
                continue

            # Look up prediction match
            match = match_lookup.get((t["student_state"], t["to_state"]), "unknown")
            t["prediction_match"] = match

            # Store full transition
            trans_id = f"uno_{t['episode_id']}_{t['turn_index']}"
            trans_id = re.sub(r'[^a-zA-Z0-9_]', '_', trans_id)[:100]

            cur.execute("""
                INSERT OR REPLACE INTO uno_transitions
                (id, episode_id, turn_index, lineage, user_text, assistant_text,
                 student_state, behavior_tags,
                 phase, function_id, mechanism_shape, teaching_actions,
                 register_intensity, register_intimacy, register_attunement,
                 register_style, register_depth, register_meta_mode,
                 traps_avoided, intent, approach,
                 impact_predicted, impact_confidence, impact_update,
                 accumulated_insight, my_thoughts,
                 to_state, next_user_text, prediction_match)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trans_id,
                t["episode_id"], t["turn_index"], t["lineage"],
                t["user_text"], t["assistant_text"],
                t["student_state"], json.dumps(t["behavior_tags"]),
                t["phase"], t["function_id"], t["mechanism_shape"],
                json.dumps(t["teaching_actions"]),
                t["register_intensity"], t["register_intimacy"],
                t["register_attunement"], t["register_style"],
                t["register_depth"], t["register_meta_mode"],
                json.dumps(t["traps_avoided"]),
                t["intent"], t["approach"],
                t["impact_predicted"], t["impact_confidence"], t["impact_update"],
                t["accumulated_insight"], t["my_thoughts"],
                t["to_state"], t["next_user_text"], match,
            ))
            inserted += 1

            # Calculate reward for weight updates
            if match == "true":
                reward = 1.0
            elif match == "partial":
                reward = 0.5
            else:
                reward = 0.3

            from_state = t["student_state"]
            fn = t["function_id"]
            mech = t["mechanism_shape"]
            actions = t["teaching_actions"]
            to_state = t["to_state"]
            predicted = t["impact_predicted"]
            behaviors = t["behavior_tags"]

            # state → function
            if from_state and fn:
                k = ("state", from_state, "function", fn)
                weight_data[k]["total"] += reward
                weight_data[k]["count"] += 1
                if reward >= 0.5:
                    weight_data[k]["success"] += 1

            # state → mechanism
            if from_state and mech and mech != "none":
                k = ("state", from_state, "mechanism", mech)
                weight_data[k]["total"] += reward
                weight_data[k]["count"] += 1

            # state → next_state
            if from_state and to_state:
                k = ("state", from_state, "next_state", to_state)
                weight_data[k]["total"] += 1.0
                weight_data[k]["count"] += 1

            # function → next_state
            if fn and to_state:
                k = ("function", fn, "next_state", to_state)
                weight_data[k]["total"] += 1.0
                weight_data[k]["count"] += 1

            # function → mechanism (co-occurrence)
            if fn and mech and mech != "none":
                k = ("function", fn, "mechanism", mech)
                weight_data[k]["total"] += reward
                weight_data[k]["count"] += 1

            # state+function → predicted_impact
            if from_state and fn and predicted:
                k = ("state_function", f"{from_state}||{fn}", "predicted", predicted)
                weight_data[k]["total"] += reward
                weight_data[k]["count"] += 1

            # behavior_tags → function
            for tag in behaviors:
                if tag and fn:
                    k = ("behavior", tag, "function", fn)
                    weight_data[k]["total"] += reward
                    weight_data[k]["count"] += 1

            # state → register
            for dim in ["intensity", "intimacy", "attunement", "style", "depth", "meta_mode"]:
                val = t.get(f"register_{dim}")
                if from_state and val:
                    k = ("state", from_state, f"register_{dim}", str(val))
                    weight_data[k]["total"] += reward
                    weight_data[k]["count"] += 1

            # state → action
            for action in actions:
                if from_state and action:
                    k = ("state", from_state, "action", action)
                    weight_data[k]["total"] += reward
                    weight_data[k]["count"] += 1

            # traps_avoided → function
            for trap in t["traps_avoided"]:
                if trap and fn:
                    k = ("trap", trap, "function", fn)
                    weight_data[k]["total"] += reward
                    weight_data[k]["count"] += 1

    # Write all weights
    for key, data in weight_data.items():
        from_type, from_val, to_type, to_val = key
        avg = data["total"] / data["count"] if data["count"] > 0 else 0.0
        eid = f"w_{from_type}_{from_val}_{to_type}_{to_val}"
        eid = re.sub(r'[^a-zA-Z0-9_]', '_', eid)[:100]

        cur.execute("""
            INSERT INTO policy_weights
            (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                weight = weight + ?,
                success_count = success_count + ?,
                failure_count = failure_count + ?
        """, (eid, from_type, from_val, to_type, to_val,
              avg, data["success"], data["failure"],
              avg * 0.1, data["success"], data["failure"]))

    conn.commit()
    conn.close()

    print(f"Transitions: {inserted}")
    print(f"Weight edges: {len(weight_data)}")
    state_count = len(set(k[1] for k in weight_data if k[0] == "state"))
    fn_count = len(set(k[3] for k in weight_data if k[2] == "function"))
    mech_count = len(set(k[3] for k in weight_data if k[2] == "mechanism"))
    print(f"States: {state_count}, Functions: {fn_count}, Mechanisms: {mech_count}")


def _build_state_similarity(db_path: str = "data/engine.sqlite"):
    """Build in-memory state similarity lookup for sparse states."""
    import json
    from collections import Counter, defaultdict

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        SELECT student_state, behavior_tags,
               register_intensity, register_intimacy, register_attunement,
               register_style, register_depth, register_meta_mode,
               mechanism_shape, function_id
        FROM uno_transitions WHERE student_state != ''
    ''')
    rows = cur.fetchall()
    conn.close()

    profiles = defaultdict(lambda: {
        'register': defaultdict(Counter),
        'behaviors': Counter(), 'mechanisms': Counter(), 'functions': Counter(),
        'count': 0,
    })

    for r in rows:
        state = r[0]
        behaviors = json.loads(r[1]) if r[1] else []
        reg = dict(zip(
            ['intensity','intimacy','attunement','style','depth','meta_mode'],
            [r[2],r[3],r[4],r[5],r[6],r[7]]
        ))
        mech, fn = r[8], r[9]
        p = profiles[state]
        p['count'] += 1
        for dim, val in reg.items():
            if val: p['register'][dim][val] += 1
        for b in behaviors: p['behaviors'][b] += 1
        if mech: p['mechanisms'][mech] += 1
        if fn: p['functions'][fn] += 1

    def similarity(a, b):
        pa, pb = profiles.get(a), profiles.get(b)
        if not pa or not pb: return 0.0
        sim = 0.0
        for dim in ['intensity','intimacy','attunement','style','depth','meta_mode']:
            ca, cb = pa['register'][dim], pb['register'][dim]
            common = set(ca.keys()) & set(cb.keys())
            denom = len(ca) + len(cb) - len(common)
            sim += len(common) / denom if denom > 0 else 0
        sim /= 6
        b_common = set(pa['behaviors'].keys()) & set(pb['behaviors'].keys())
        b_denom = len(pa['behaviors']) + len(pb['behaviors']) - b_common
        b_sim = len(b_common) / b_denom if b_denom > 0 else 0
        return sim * 0.5 + b_sim * 0.5

    return profiles, similarity


def _query_state(state: str, cur) -> dict:
    """Query policy_weights for a single state. Returns dict of lists or None."""
    result = {}

    cur.execute("""
        SELECT to_value, weight FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'function'
        ORDER BY weight DESC LIMIT 5
    """, (state,))
    result["functions"] = [{"id": r[0], "weight": r[1]} for r in cur.fetchall()]

    cur.execute("""
        SELECT to_value, weight FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'mechanism'
        ORDER BY weight DESC LIMIT 3
    """, (state,))
    result["mechanisms"] = [{"id": r[0], "weight": r[1]} for r in cur.fetchall()]

    cur.execute("""
        SELECT to_value, weight FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'next_state'
        ORDER BY weight DESC LIMIT 3
    """, (state,))
    result["next_states"] = [{"state": r[0], "weight": r[1]} for r in cur.fetchall()]

    cur.execute("""
        SELECT to_value, weight FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'action'
        ORDER BY weight DESC LIMIT 3
    """, (state,))
    result["actions"] = [{"action": r[0], "weight": r[1]} for r in cur.fetchall()]

    reg = {}
    for dim in ["intensity","intimacy","attunement","style","depth","meta_mode"]:
        cur.execute("""
            SELECT to_value, weight FROM policy_weights
            WHERE from_type = 'state' AND from_value = ? AND to_type = ?
            ORDER BY weight DESC LIMIT 1
        """, (state, f"register_{dim}"))
        row = cur.fetchone()
        if row: reg[dim] = {"value": row[0], "weight": row[1]}
    result["register"] = reg

    return result


def query(state: str, function_id: str = None,
          db_path: str = "data/engine.sqlite") -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = _query_state(state, cur)
    result["state"] = state
    result["similarity_fallback"] = None

    # If state has no functions, fall back to nearest neighbor by feature similarity
    if not result["functions"]:
        profiles, sim_fn = _build_state_similarity(db_path)
        best_sim, best_state = 0.0, None
        for other in profiles:
            if other == state: continue
            s = sim_fn(state, other)
            if s > best_sim:
                best_sim, best_state = s, other

        if best_state and best_sim > 0:
            neighbor = _query_state(best_state, cur)
            # Borrow neighbor's weights, scaled by similarity
            result["functions"] = [{"id": f["id"], "weight": f["weight"] * best_sim,
                                    "source": best_state} for f in neighbor["functions"]]
            result["mechanisms"] = [{"id": m["id"], "weight": m["weight"] * best_sim,
                                     "source": best_state} for m in neighbor["mechanisms"]]
            result["next_states"] = [{"state": n["state"], "weight": n["weight"] * best_sim,
                                      "source": best_state} for n in neighbor["next_states"]]
            result["actions"] = [{"action": a["action"], "weight": a["weight"] * best_sim,
                                  "source": best_state} for a in neighbor["actions"]]
            result["register"] = neighbor["register"]
            result["similarity_fallback"] = {"source": best_state, "similarity": round(best_sim, 3)}

    if function_id:
        cur.execute("""
            SELECT to_value, weight FROM policy_weights
            WHERE from_type = 'state_function' AND from_value = ? AND to_type = 'predicted'
            ORDER BY weight DESC LIMIT 3
        """, (f"{state}||{function_id}",))
        result["predicted_impacts"] = [{"impact": r[0], "weight": r[1]} for r in cur.fetchall()]

    conn.close()
    return result


if __name__ == "__main__":
    train_all()

    print("\n=== fearful_disclosure ===")
    w = query("fearful_disclosure", "RM_03")
    print(f"Functions: {[(f['id'], f['weight']) for f in w['functions'][:5]]}")
    print(f"Mechanisms: {[(m['id'], m['weight']) for m in w['mechanisms'][:3]]}")
    print(f"Next states: {[(s['state'], s['weight']) for s in w['next_states'][:5]]}")
    print(f"Actions: {[(a['action'], a['weight']) for a in w['actions'][:3]]}")
    print(f"Register: {w['register']}")
    print(f"Predicted impact for RM_03: {w['predicted_impacts']}")

    print("\n=== dawning_awareness ===")
    w = query("dawning_awareness")
    print(f"Functions: {[(f['id'], f['weight']) for f in w['functions'][:5]]}")
    print(f"Next states: {[(s['state'], s['weight']) for s in w['next_states'][:5]]}")
    print(f"Register: {w['register']}")

    print("\n=== defensive_insistence ===")
    w = query("defensive_insistence")
    print(f"Functions: {[(f['id'], f['weight']) for f in w['functions'][:3]]}")
    print(f"Next states: {[(s['state'], s['weight']) for s in w['next_states'][:3]]}")
