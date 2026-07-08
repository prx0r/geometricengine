import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from src.parser.uno_parser import parse_uno, build_transitions, build_episode_arcs


def ingest(uno_path: str, db_path: str):
    records = parse_uno(uno_path)
    transitions = build_transitions(records)
    arcs = build_episode_arcs(records)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    hyperedge_count = 0
    incidence_count = 0

    for rec in records:
        p = rec.pedagogy
        he_id = f"he_{rec.episode_id}_{rec.turn_index}"

        compression = p.my_thoughts[:200] if p.my_thoughts else ""

        cur.execute("""
            INSERT OR IGNORE INTO mythought_hyperedges
            (id, source, turn_index, mythought_text, compression, lineage,
             phase, function_id, mechanism_shape, intent,
             predicted_impact, impact_confidence, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', ?)
        """, (
            he_id, "uno", rec.turn_index, p.my_thoughts, compression,
            p.lineage, p.phase.value if p.phase else None,
            p.function_id.name if p.function_id else None,
            p.mechanism_shape.value,
            p.intent, p.impact_predicted, 0.5,
            datetime.utcnow().isoformat(),
        ))
        hyperedge_count += 1

        incidences = [
            (f"inc_{he_id}_state", he_id, "student_state", p.student_state, "expresses", 1.0),
        ]
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

    conn.commit()
    conn.close()

    print(f"Ingested {hyperedge_count} hyperedges, {incidence_count} incidences")
    print(f"Unique states: {len(set(r.pedagogy.student_state for r in records))}")
    print(f"Episodes: {len(set(r.episode_id for r in records))}")
    print(f"Turns: {len(records)}")

    return records, transitions, arcs


if __name__ == "__main__":
    ingest("data/uno.txt", "data/engine.sqlite")
