import json
from pathlib import Path
from src.models.pedagogy import TurnRecord, TransitionRecord, EpisodeArc


def write_jsonl(path: str, records: list) -> None:
    with open(path, "w") as f:
        for r in records:
            if hasattr(r, "__dataclass_fields__"):
                f.write(json.dumps(_dataclass_to_dict(r)) + "\n")
            else:
                f.write(json.dumps(r) + "\n")


def _dataclass_to_dict(obj):
    if hasattr(obj, "__dataclass_fields__"):
        d = {}
        for field_name in obj.__dataclass_fields__:
            val = getattr(obj, field_name)
            if hasattr(val, "__dataclass_fields__"):
                d[field_name] = _dataclass_to_dict(val)
            elif isinstance(val, list) and val and hasattr(val[0], "__dataclass_fields__"):
                d[field_name] = [_dataclass_to_dict(v) for v in val]
            elif hasattr(val, "value"):
                d[field_name] = val.value
            elif hasattr(val, "name"):
                d[field_name] = val.name
            else:
                d[field_name] = val
        return d
    return obj


def build_graph_data(records: list[TurnRecord], transitions: list[TransitionRecord],
                     arcs: list[EpisodeArc], output_dir: str):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    write_jsonl(str(out / "turn_records.jsonl"), records)
    write_jsonl(str(out / "transition_records.jsonl"), transitions)
    write_jsonl(str(out / "episode_arcs.jsonl"), arcs)

    nodes = []
    edges = []
    state_nodes = {}
    function_nodes = {}
    mechanism_nodes = {}

    for rec in records:
        p = rec.pedagogy
        turn_id = f"{rec.episode_id}_t{rec.turn_index}"

        nodes.append({"id": turn_id, "type": "turn", "episode_id": rec.episode_id})
        nodes.append({"id": f"user_{turn_id}", "type": "user_utterance", "text": rec.user_text[:200]})
        nodes.append({"id": f"asst_{turn_id}", "type": "assistant_move", "text": rec.assistant_visible_text[:200]})

        if p.student_state not in state_nodes:
            state_nodes[p.student_state] = f"state_{len(state_nodes)}"
            nodes.append({"id": state_nodes[p.student_state], "type": "student_state", "label": p.student_state})

        if p.function_id and p.function_id.name not in function_nodes:
            function_nodes[p.function_id.name] = f"fn_{len(function_nodes)}"
            nodes.append({"id": function_nodes[p.function_id.name], "type": "function", "label": p.function_id.name})

        if p.mechanism_shape.value not in mechanism_nodes:
            mechanism_nodes[p.mechanism_shape.value] = f"mech_{len(mechanism_nodes)}"
            nodes.append({"id": mechanism_nodes[p.mechanism_shape.value], "type": "mechanism", "label": p.mechanism_shape.value})

        edges.append({"from": turn_id, "to": f"user_{turn_id}", "type": "HAS_USER_UTTERANCE"})
        edges.append({"from": turn_id, "to": f"asst_{turn_id}", "type": "HAS_ASSISTANT_MOVE"})
        edges.append({"from": f"user_{turn_id}", "to": state_nodes[p.student_state], "type": "EXPRESSES"})
        if p.function_id:
            edges.append({"from": f"asst_{turn_id}", "to": function_nodes[p.function_id.name], "type": "HAS_FUNCTION"})
        edges.append({"from": f"asst_{turn_id}", "to": mechanism_nodes[p.mechanism_shape.value], "type": "USES_MECHANISM"})

    for i in range(len(records) - 1):
        curr = records[i]
        nxt = records[i + 1]
        if curr.episode_id == nxt.episode_id:
            t1 = f"{curr.episode_id}_t{curr.turn_index}"
            t2 = f"{nxt.episode_id}_t{nxt.turn_index}"
            edges.append({"from": t1, "to": t2, "type": "NEXT_TURN"})

    write_jsonl(str(out / "graph_nodes.jsonl"), nodes)
    write_jsonl(str(out / "graph_edges.jsonl"), edges)

    stats = {
        "total_episodes": len(set(r.episode_id for r in records)),
        "total_turns": len(records),
        "total_transitions": len(transitions),
        "unique_states": len(state_nodes),
        "unique_functions": len(function_nodes),
        "unique_mechanisms": len(mechanism_nodes),
    }
    with open(str(out / "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    return stats
