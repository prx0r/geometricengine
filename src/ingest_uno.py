import json
import sqlite3
from datetime import datetime

from src.parser.uno_parser import parse_uno, build_transitions, build_episode_arcs


def ingest(uno_path: str, db_path: str):
    records = parse_uno(uno_path)
    transitions = build_transitions(records)
    arcs = build_episode_arcs(records)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    with open("src/schema.sql") as f:
        cur.executescript(f.read())

    hyperedge_count = 0
    incidence_count = 0

    for rec in records:
        p = rec.pedagogy
        he_id = f"he_{rec.episode_id}_{rec.turn_index}"
        compression = p.my_thoughts[:200] if p.my_thoughts else ""

        prev_user = ""
        next_user = ""
        for other in records:
            if other.episode_id == rec.episode_id:
                if other.turn_index == rec.turn_index - 1:
                    prev_user = other.user_text or ""
                if other.turn_index == rec.turn_index + 1:
                    next_user = other.user_text or ""

        cur.execute("""
            INSERT OR IGNORE INTO mythought_hyperedges
            (id, source, episode_id, turn_id, turn_index,
             mythought_text, assistant_visible_text, previous_user_text, next_user_text,
             lineage, phase, function_id, mechanism_shape, intent,
             impact_predicted, impact_confidence, impact_update, accumulated_insight,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', ?)
        """, (
            he_id,
            "uno",
            rec.episode_id,
            f"{rec.episode_id}_t{rec.turn_index}",
            rec.turn_index,
            p.my_thoughts,
            rec.assistant_visible_text,
            prev_user,
            next_user,
            p.lineage,
            p.phase.value if p.phase else None,
            p.function_id.name if p.function_id else None,
            p.mechanism_shape.value,
            p.intent,
            p.impact_predicted,
            0.5,
            p.impact_update,
            p.accumulated_insight,
            datetime.utcnow().isoformat(),
        ))
        hyperedge_count += 1

        reg = p.register
        incidences = [
            (f"inc_{he_id}_state", he_id, "student_state", p.student_state, "expresses", 1.0),
        ]
        if p.phase:
            incidences.append((f"inc_{he_id}_phase", he_id, "phase", p.phase.value, "in_phase", 1.0))
        if p.function_id:
            incidences.append((f"inc_{he_id}_fn", he_id, "function", p.function_id.name, "fires", 1.0))
        if p.mechanism_shape.value != "none":
            incidences.append((f"inc_{he_id}_mech", he_id, "mechanism", p.mechanism_shape.value, "uses", 1.0))
        if p.intent:
            incidences.append((f"inc_{he_id}_intent", he_id, "intent", p.intent[:200], "intends", 0.8))
        if p.approach:
            incidences.append((f"inc_{he_id}_approach", he_id, "approach", p.approach, "approaches", 0.8))
        if p.impact_predicted:
            incidences.append((f"inc_{he_id}_impact", he_id, "predicted_impact", p.impact_predicted, "predicts", 0.7))
        if reg:
            for dim, val in [("intensity", reg.intensity.name), ("intimacy", reg.intimacy.name),
                             ("attunement", reg.attunement.name), ("style", reg.style.name),
                             ("depth", reg.depth.name), ("meta_mode", reg.meta_mode.name)]:
                incidences.append((f"inc_{he_id}_{dim}", he_id, "register", f"{dim}={val}", "modulates", 0.6))
        for tag in p.behavior_tags:
            incidences.append((f"inc_{he_id}_tag_{tag}", he_id, "behavior_tag", tag, "cites", 1.0))
        for action in p.teaching_actions:
            incidences.append((f"inc_{he_id}_act_{action}", he_id, "teaching_action", action, "performs", 1.0))
        for trap in p.traps_avoided:
            incidences.append((f"inc_{he_id}_trap_{trap}", he_id, "trap_avoided", trap, "avoids", 1.0))

        for inc_id, hyperedge_id, node_type, node_value, role, weight in incidences:
            cur.execute("""
                INSERT OR IGNORE INTO mythought_incidences
                (id, hyperedge_id, node_type, node_value, role, weight)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (inc_id, hyperedge_id, node_type, node_value, role, weight))
            incidence_count += 1

    for arc in arcs:
        cur.execute("""
            INSERT OR IGNORE INTO episodes
            (id, lineage, arc_length, final_state, arc_summary)
            VALUES (?, ?, ?, ?, ?)
        """, (arc.episode_id, arc.lineage, arc.arc_length,
              arc.final_state, arc.arc_summary[:500] if arc.arc_summary else ""))

    for rec in records:
        ped_json = json.dumps({
            "student_state": rec.pedagogy.student_state,
            "function_id": rec.pedagogy.function_id.name if rec.pedagogy.function_id else None,
            "mechanism_shape": rec.pedagogy.mechanism_shape.value,
            "teaching_actions": rec.pedagogy.teaching_actions,
            "impact_predicted": rec.pedagogy.impact_predicted,
            "impact_update": rec.pedagogy.impact_update,
        })
        cur.execute("""
            INSERT OR IGNORE INTO turns
            (id, episode_id, turn_index, lineage, user_text,
             assistant_visible_text, pedagogy_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{rec.episode_id}_t{rec.turn_index}",
            rec.episode_id, rec.turn_index, rec.lineage,
            rec.user_text[:500], rec.assistant_visible_text[:500], ped_json,
        ))

    for t in transitions:
        cur.execute("""
            INSERT OR IGNORE INTO transitions
            (id, episode_id, from_turn, to_turn, from_state, to_state,
             move_function, mechanism_shape, teaching_actions_json,
             register_json, predicted_impact, impact_update, prediction_match)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"trans_{t.episode_id}_{t.from_turn}_{t.to_turn}",
            t.episode_id, t.from_turn, t.to_turn,
            t.from_state, t.to_state, t.move_function,
            t.mechanism_shape,
            json.dumps(t.teaching_actions),
            json.dumps(list(t.register)) if t.register else None,
            t.predicted_impact, t.impact_update, t.prediction_match,
        ))

    conn.commit()
    conn.close()

    print(f"Hyperedges: {hyperedge_count}, Incidences: {incidence_count}")
    print(f"Unique states: {len(set(r.pedagogy.student_state for r in records))}")
    print(f"Episodes: {len(set(r.episode_id for r in records))}")
    print(f"Turns: {len(records)}, Transitions: {len(transitions)}")

    return records, transitions, arcs


if __name__ == "__main__":
    ingest("data/uno.txt", "data/engine.sqlite")
