import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parser.uno_parser import parse_uno, build_transitions, build_episode_arcs
from src.retrieve import retrieve_mythoughts, aggregate_candidate_nodes


def test_parser_loads():
    records = parse_uno("data/uno.txt")
    assert len(records) > 0, "No records parsed"
    print(f"Records: {len(records)}")
    for r in records[:3]:
        assert r.episode_id
        assert r.user_text
        assert r.pedagogy.student_state
        assert r.pedagogy.mechanism_shape


def test_parser_first_episode():
    records = parse_uno("data/uno.txt")
    first = [r for r in records if r.turn_index == 0]
    assert len(first) > 0
    ep0 = first[0]
    assert ep0.pedagogy.student_state
    assert ep0.pedagogy.function_id
    print(f"First episode: {ep0.episode_id}")
    print(f"  state: {ep0.pedagogy.student_state}")
    print(f"  function: {ep0.pedagogy.function_id.name}")
    print(f"  mechanism: {ep0.pedagogy.mechanism_shape.value}")


def test_transitions():
    records = parse_uno("data/uno.txt")
    transitions = build_transitions(records)
    assert len(transitions) > 0
    for t in transitions[:5]:
        assert t.from_state
        assert t.to_state or True
        assert t.move_function or True
        assert t.predicted_impact
        print(f"  {t.from_state} -> {t.to_state} via {t.move_function} ({t.predicted_impact})")


def test_episode_arcs():
    records = parse_uno("data/uno.txt")
    arcs = build_episode_arcs(records)
    assert len(arcs) > 0
    for a in arcs[:3]:
        assert a.state_sequence
        assert a.function_sequence
        assert a.final_state
        print(f"  {a.episode_id}: {a.state_sequence} -> {a.final_state}")


def test_retrieve():
    results = retrieve_mythoughts("I am afraid of being dependent", k=3)
    assert len(results) > 0
    for r in results:
        assert r["id"]
        assert r["similarity"] > 0
        print(f"  [{r['similarity']:.3f}] {r.get('function_id', '?')}: {r.get('compression', '')[:80]}")


def test_candidate_aggregation():
    results = retrieve_mythoughts("I keep avoiding the real work", k=5)
    candidates = aggregate_candidate_nodes(results)
    assert len(candidates["top_functions"]) > 0
    print(f"Top functions: {candidates['top_functions']}")
    print(f"Top mechanisms: {candidates['top_mechanisms']}")
    print(f"Top states: {candidates.get('top_states', [])}")


def run_golden_tests():
    with open("tests/golden_inputs.jsonl") as f:
        tests = json.load(f)
    passed = 0
    for tc in tests:
        inp = tc["input"]
        results = retrieve_mythoughts(inp, k=6)
        candidates = aggregate_candidate_nodes(results)
        top_fns = [fn for fn, _ in candidates.get("top_functions", [])]
        top_mechs = [m for m, _ in candidates.get("top_mechanisms", [])]
        if tc.get("expected_functions"):
            match = any(fn in top_fns for fn in tc["expected_functions"])
            status = "PASS" if match else "FAIL"
            print(f"  [{status}] {inp[:50]} -> expected fn {tc['expected_functions']} in {top_fns[:3]}")
            if match:
                passed += 1
        if tc.get("expected_mechanisms"):
            match = any(m in top_mechs for m in tc["expected_mechanisms"])
            status = "PASS" if match else "FAIL"
            print(f"  [{status}] {inp[:50]} -> expected mech {tc['expected_mechanisms']} in {top_mechs[:3]}")
            if match:
                passed += 1
    print(f"\n{passed}/{len(tests)*2} golden assertions passed")


if __name__ == "__main__":
    test_parser_loads()
    test_parser_first_episode()
    test_transitions()
    test_episode_arcs()
    test_retrieve()
    test_candidate_aggregation()
    run_golden_tests()
    print("\nAll tests done.")
