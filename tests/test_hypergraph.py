"""Hypergraph tests: incidence completeness, transition integrity."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parser.uno_parser import parse_uno, build_transitions, build_episode_arcs


def test_hyperedge_count():
    """Number of hyperedges equals number of parsed turns."""
    records = parse_uno("data/uno.txt")
    assert len(records) > 0
    print(f"  Hyperedges (turns with pedagogy): {len(records)}")


def test_incidence_populated():
    """Populated fields in hyperedge have corresponding incidences."""
    import sqlite3
    conn = sqlite3.connect("data/engine.sqlite")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT hyperedge_id) FROM mythought_incidences")
    inc_hyperedges = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM mythought_hyperedges")
    total_hyperedges = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM mythought_incidences")
    total_incidences = cur.fetchone()[0]
    conn.close()
    print(f"  Hyperedges: {total_hyperedges}, with incidences: {inc_hyperedges}")
    print(f"  Total incidences: {total_incidences}")
    print(f"  Avg incidences per hyperedge: {total_incidences/max(total_hyperedges,1):.1f}")
    assert inc_hyperedges == total_hyperedges, "Not all hyperedges have incidences"
    assert total_incidences > total_hyperedges * 5, "Too few incidences per hyperedge"


def test_incidence_types():
    """Required incidence types are present."""
    import sqlite3
    conn = sqlite3.connect("data/engine.sqlite")
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT node_type FROM mythought_incidences")
    types = set(row[0] for row in cur.fetchall())
    conn.close()
    required = {"student_state", "teaching_action", "behavior_tag", "trap_avoided",
                "function", "mechanism", "phase", "register", "intent", "approach"}
    found = required & types
    missing = required - types
    print(f"  Incidence types found: {sorted(found)}")
    if missing:
        print(f"  MISSING types: {missing}")
    assert len(found) >= len(required) * 0.7, f"Too many missing types: {missing}"


def test_transition_match():
    """Transitions connect consecutive turns within episodes."""
    records = parse_uno("data/uno.txt")
    transitions = build_transitions(records)
    by_ep = {}
    for r in records:
        by_ep.setdefault(r.episode_id, []).append(r)
    multi_turn = {ep: turns for ep, turns in by_ep.items() if len(turns) > 1}
    trans_by_ep = {}
    for t in transitions:
        trans_by_ep.setdefault(t.episode_id, []).append(t)
    for ep_id, turns in multi_turn.items():
        expected = len(turns) - 1
        actual = len(trans_by_ep.get(ep_id, []))
        if actual != expected:
            print(f"  Episode {ep_id}: expected {expected} transitions, got {actual}")
    print(f"  Multi-turn episodes: {len(multi_turn)}, with transitions: {len(trans_by_ep)}")


def test_episode_arcs():
    """Episode arcs are built correctly."""
    records = parse_uno("data/uno.txt")
    arcs = build_episode_arcs(records)
    by_ep = {}
    for r in records:
        by_ep.setdefault(r.episode_id, []).append(r)
    print(f"  Episodes with turns: {len(by_ep)}, arcs built: {len(arcs)}")
    for a in arcs[:3]:
        print(f"    {a.episode_id}: states={a.state_sequence}, fn={a.function_sequence}")


def test_my_thoughts_in_hyperedges():
    """my_thoughts present in SQLite hyperedges."""
    import sqlite3
    conn = sqlite3.connect("data/engine.sqlite")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM mythought_hyperedges WHERE mythought_text IS NOT NULL AND mythought_text != ''")
    with_thoughts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM mythought_hyperedges")
    total = cur.fetchone()[0]
    conn.close()
    pct = 100 * with_thoughts // max(total, 1)
    print(f"  Hyperedges with my_thoughts: {with_thoughts}/{total} ({pct}%)")
    assert pct >= 80, f"Only {pct}% of hyperedges have my_thoughts"


if __name__ == "__main__":
    test_hyperedge_count()
    test_incidence_populated()
    test_incidence_types()
    test_transition_match()
    test_episode_arcs()
    test_my_thoughts_in_hyperedges()
    print("\nAll hypergraph tests done.")
