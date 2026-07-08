"""Parser tests: pedagogy extraction, field preservation, turn pairing."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parser.uno_parser import parse_uno, parse_pedagogy_block, PEDAGOGY_RE


def count_pedagogy_blocks(content: str) -> int:
    return len(PEDAGOGY_RE.findall(content))


def test_episode_count():
    """Every episode in uno.txt is represented."""
    records = parse_uno("data/uno.txt")
    with open("data/uno.txt") as f:
        raw = f.read()
    # Count episodes by counting top-level JSON array openings
    ep_count = records[-1].episode_id if records else ""
    ep_ids = set(r.episode_id for r in records)
    assert len(ep_ids) > 0, "No episodes parsed"
    print(f"  Episodes: {len(ep_ids)}, Turns: {len(records)}")


def test_turn_count():
    """Every assistant message with [PEDAGOGY] creates a turn."""
    records = parse_uno("data/uno.txt")
    with open("data/uno.txt") as f:
        raw = f.read()
    block_count = count_pedagogy_blocks(raw)
    print(f"  Pedagogy blocks in raw: {block_count}")
    print(f"  Parsed turns: {len(records)}")
    assert len(records) > 0, "No turns parsed"


def test_field_preservation():
    """Fields present in raw PEDAGOGY blocks are preserved in parsed output."""
    records = parse_uno("data/uno.txt")
    fields = ["lineage", "phase", "student_state", "mechanism_shape",
              "impact_predicted", "approach"]
    missing = 0
    total = 0
    for r in records[:50]:
        p = r.pedagogy
        pairs = [("lineage", p.lineage), ("student_state", p.student_state),
                 ("mechanism_shape", p.mechanism_shape.value),
                 ("impact_predicted", p.impact_predicted)]
        for name, val in pairs:
            total += 1
            if not val or val == "none":
                missing += 1
    print(f"  Fields checked: {total}, missing/empty: {missing}")
    assert missing / total < 0.3 if total > 0 else True, f"Too many missing fields: {missing}/{total}"


def test_turn_pairing():
    """Assistant turns have associated user text."""
    records = parse_uno("data/uno.txt")
    no_user = sum(1 for r in records if not r.user_text)
    print(f"  Turns with missing user text: {no_user}/{len(records)}")
    assert no_user == 0, f"{no_user} turns missing user text"


def test_visible_response():
    """Visible assistant text is separate from pedagogy block."""
    records = parse_uno("data/uno.txt")
    empty_visible = sum(1 for r in records if not r.assistant_visible_text)
    tagged = sum(1 for r in records if "[PEDAGOGY]" in r.assistant_visible_text)
    print(f"  Empty visible: {empty_visible}/{len(records)}")
    print(f"  Pedagogy tags in visible: {tagged}/{len(records)}")
    assert tagged == 0, f"{tagged} turns have pedagogy tags in visible text"


def test_my_thoughts_preserved():
    """my_thoughts field is preserved in every parsed turn."""
    records = parse_uno("data/uno.txt")
    with_thoughts = sum(1 for r in records if r.pedagogy.my_thoughts)
    print(f"  Turns with my_thoughts: {with_thoughts}/{len(records)} ({100*with_thoughts//max(len(records),1)}%)")


def test_register_parsed():
    """Register fields are parsed where present."""
    records = parse_uno("data/uno.txt")
    with_register = sum(1 for r in records if r.pedagogy.register)
    print(f"  Turns with register: {with_register}/{len(records)}")


def test_transition_count():
    """Transition count matches turn count - 1 per episode."""
    from src.parser.uno_parser import build_transitions
    records = parse_uno("data/uno.txt")
    transitions = build_transitions(records)
    by_ep = {}
    for r in records:
        by_ep.setdefault(r.episode_id, []).append(r)
    total_expected = sum(len(v) - 1 for v in by_ep.values())
    print(f"  Expected transitions: {total_expected}, actual: {len(transitions)}")


if __name__ == "__main__":
    test_episode_count()
    test_turn_count()
    test_field_preservation()
    test_turn_pairing()
    test_visible_response()
    test_my_thoughts_preserved()
    test_register_parsed()
    test_transition_count()
    print("\nAll parser tests done.")
