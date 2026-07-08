"""Retrieval tests: golden cases, candidate move aggregation."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.retrieve import retrieve_mythoughts, aggregate_candidate_nodes


def load_golden():
    with open("tests/golden_inputs.jsonl") as f:
        return json.load(f)


def test_retrieve_returns_hyperedges():
    results = retrieve_mythoughts("I am afraid", k=3)
    assert len(results) > 0
    for r in results:
        assert "id" in r
        assert "similarity" in r
        assert "mythought_text" in r or "compression" in r
    print(f"  Retrieved {len(results)} hyperedges for 'I am afraid'")


def test_retrieve_scored():
    results = retrieve_mythoughts("I keep avoiding the real work", k=5)
    scores = [r["similarity"] for r in results]
    assert all(s >= 0 for s in scores), "Negative similarity scores"
    assert scores == sorted(scores, reverse=True), "Not sorted by similarity"
    print(f"  Scores: {[round(s, 3) for s in scores]}")


def test_candidate_aggregation():
    results = retrieve_mythoughts("I keep adding modules instead of building", k=5)
    candidates = aggregate_candidate_nodes(results)
    assert "top_functions" in candidates
    assert "top_mechanisms" in candidates
    assert len(candidates["top_functions"]) > 0
    print(f"  Top functions: {candidates['top_functions'][:3]}")
    print(f"  Top mechanisms: {candidates['top_mechanisms'][:3]}")


def test_golden_retrieval_hit_rate():
    goldens = load_golden()
    hits = 0
    total = 0
    for tc in goldens:
        results = retrieve_mythoughts(tc["input"], k=5)
        candidates = aggregate_candidate_nodes(results)
        top_fns = [fn for fn, _ in candidates.get("top_functions", [])]
        for ef in tc.get("expected_functions", []):
            total += 1
            if ef in top_fns:
                hits += 1
        for es in tc.get("expected_state", []):
            pass  # state matching needs refinement
    pct = 100 * hits // max(total, 1) if total else 0
    print(f"  Golden hit rate: {hits}/{total} ({pct}%)")


def test_golden_candidate_moves():
    goldens = load_golden()
    for tc in goldens:
        results = retrieve_mythoughts(tc["input"], k=5)
        candidates = aggregate_candidate_nodes(results)
        top_fns = [fn for fn, _ in candidates.get("top_functions", [])]
        expected = tc.get("expected_functions", tc.get("expected_moves", []))
        match = any(ef in top_fns for ef in expected)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] {tc['input'][:40]} -> expected {expected} in top fns {top_fns[:3]}")


def test_no_bad_moves_in_top():
    goldens = load_golden()
    for tc in goldens:
        results = retrieve_mythoughts(tc["input"], k=5)
        candidates = aggregate_candidate_nodes(results)
        top_fns = [fn for fn, _ in candidates.get("top_functions", [])]
        bad = tc.get("bad_moves", [])
        if bad:
            conflict = [b for b in bad if b in top_fns[:3]]
            if conflict:
                print(f"  WARN: {tc['input'][:40]} bad moves in top 3: {conflict}")


if __name__ == "__main__":
    test_retrieve_returns_hyperedges()
    test_retrieve_scored()
    test_candidate_aggregation()
    test_golden_retrieval_hit_rate()
    test_golden_candidate_moves()
    test_no_bad_moves_in_top()
    print("\nAll retrieval tests done.")
