import sqlite3
from collections import Counter, defaultdict
from typing import Any


def aggregate_incidences(retrieved_hyperedges: list[dict[str, Any]]) -> dict[str, Counter]:
    buckets = defaultdict(Counter)

    for he in retrieved_hyperedges:
        sim = float(he.get("similarity", 1.0))

        for key in ["lineage", "phase", "function_id", "mechanism_shape", "intent", "predicted_impact"]:
            value = he.get(key)
            if value:
                buckets[key][value] += sim

        buckets["source_ids"][he.get("id", "")] += sim

    return dict(buckets)


def load_policy_weights(db_path: str = "data/engine.sqlite") -> dict[tuple, float]:
    weights: dict[tuple, float] = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT from_type, from_value, to_type, to_value, weight, success_count, failure_count FROM policy_weights")
        for row in cur.fetchall():
            from_type, from_val, to_type, to_val, weight, succ, fail = row
            total = succ + fail
            if total > 0:
                effective = weight * (succ / total)
            else:
                effective = weight
            weights[(from_type, from_val, to_type, to_val)] = effective
        conn.close()
    except Exception:
        pass
    return weights


def select_weighted_pathway(
    classified_labels: dict[str, Any] | None = None,
    retrieved_hyperedges: list[dict[str, Any]] | None = None,
    incidence_aggregate: dict[str, Counter] | None = None,
    policy_weights: dict[tuple, float] | None = None,
) -> dict[str, Any]:
    classified_labels = classified_labels or {}
    retrieved_hyperedges = retrieved_hyperedges or []
    incidence_aggregate = incidence_aggregate or aggregate_incidences(retrieved_hyperedges)
    policy_weights = policy_weights or load_policy_weights()

    def top(counter: Counter, default=None):
        return counter.most_common(1)[0][0] if counter else default

    phase = top(incidence_aggregate.get("phase", Counter()), "UNMAKING")
    function_id = top(incidence_aggregate.get("function_id", Counter()))
    mechanism_shape = top(incidence_aggregate.get("mechanism_shape", Counter()))

    base_score = sum(retrieved_hyperedges[0].get("similarity", 1.0) for _ in [0]) if retrieved_hyperedges else 0.0

    if function_id and (phase, function_id) in policy_weights:
        base_score += policy_weights[(phase, function_id)]

    if function_id and mechanism_shape and ("selected_function", function_id, "selected_mechanism", mechanism_shape) in policy_weights:
        base_score += policy_weights[("selected_function", function_id, "selected_mechanism", mechanism_shape)]

    source_ids = [hid for hid, _ in incidence_aggregate.get("source_ids", Counter()).most_common(5)]

    selected = {
        "derived_by": "graph",
        "phase": phase,
        "function_id": function_id,
        "mechanism_shape": mechanism_shape,
        "teaching_actions": [],
        "register": {
            "intensity": top(incidence_aggregate.get("register_intensity", Counter())),
            "intimacy": top(incidence_aggregate.get("register_intimacy", Counter())),
            "attunement": top(incidence_aggregate.get("register_attunement", Counter())),
            "style": top(incidence_aggregate.get("register_style", Counter())),
            "depth": top(incidence_aggregate.get("register_depth", Counter())),
            "meta_mode": top(incidence_aggregate.get("register_meta_mode", Counter())),
        },
        "source_hyperedges": source_ids,
        "score": round(base_score, 4),
    }

    return selected
