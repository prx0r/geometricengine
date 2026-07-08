import json
import re
from pathlib import Path
from typing import Optional

from src.models.pedagogy import PedagogyBlock, TurnRecord, TransitionRecord, EpisodeArc
from src.models.register import RegisterProfile
from src.models.mechanism import MechanismShape
from src.models.function import HXRMXSFunction, Phase


PEDAGOGY_RE = re.compile(
    r"\[PEDAGOGY\](.*?)\[/PEDAGOGY\]",
    re.DOTALL,
)


def _parse_register_field(raw: str, style_raw="", depth_raw="", meta_raw="") -> Optional[RegisterProfile]:
    if not raw or raw.strip() == "none":
        return None
    parts = raw.replace(" ", "").split(",")
    kwargs = {}
    mapping = {"intensity": "pr", "intimacy": "inn", "attunement": "at"}
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip().lower()
        v = v.strip().upper()
        target = mapping.get(k)
        if target:
            kwargs[target] = v
    # style, depth, meta are separate fields
    for raw_val, key in [(style_raw, "ls"), (depth_raw, "pd"), (meta_raw, "mm")]:
        if raw_val and raw_val.strip().upper() != "NONE":
            kwargs[key] = raw_val.strip().upper()
    try:
        return RegisterProfile.from_strings(**kwargs)
    except (KeyError, ValueError):
        return None


def _parse_field(text: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _parse_list_field(text: str, key: str) -> list[str]:
    raw = _parse_field(text, key)
    if raw.lower() == "none" or not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def parse_pedagogy_block(raw: str) -> Optional[PedagogyBlock]:
    if not raw.strip():
        return None

    lineage = _parse_field(raw, "lineage")
    phase_raw = _parse_field(raw, "phase")
    phase = None
    for p in Phase:
        if p.value.replace("-", "_") == phase_raw.upper().replace("-", "_"):
            phase = p
            break

    fn_raw = _parse_field(raw, "function_id")
    function_id = HXRMXSFunction.from_str(fn_raw) if fn_raw else None

    student_state = _parse_field(raw, "student_state")
    behavior_tags = _parse_list_field(raw, "behavior_tags")
    mechanism_raw = _parse_field(raw, "mechanism_shape")
    mechanism = MechanismShape.from_str(mechanism_raw)

    teaching_actions = _parse_list_field(raw, "teaching_actions")
    register_raw = _parse_field(raw, "register")
    style_raw = _parse_field(raw, "style")
    depth_raw = _parse_field(raw, "depth")
    meta_raw = _parse_field(raw, "meta_mode")
    register = _parse_register_field(register_raw, style_raw, depth_raw, meta_raw)
    traps = _parse_list_field(raw, "traps_avoided")
    intent = _parse_field(raw, "intent")
    approach = _parse_field(raw, "approach")
    impact_predicted = _parse_field(raw, "impact_predicted")
    impact_confidence = _parse_field(raw, "impact_confidence")
    impact_update = _parse_field(raw, "impact_update")
    accumulated_insight = _parse_field(raw, "accumulated_insight")
    my_thoughts = _parse_field(raw, "my_thoughts")

    return PedagogyBlock(
        lineage=lineage, phase=phase, function_id=function_id,
        student_state=student_state, behavior_tags=behavior_tags,
        mechanism_shape=mechanism, teaching_actions=teaching_actions,
        register=register, traps_avoided=traps, intent=intent,
        approach=approach, impact_predicted=impact_predicted,
        impact_confidence=impact_confidence, impact_update=impact_update,
        accumulated_insight=accumulated_insight, my_thoughts=my_thoughts,
    )


def _load_json_arrays(path: str) -> list:
    """Load all JSON arrays from a file that may contain multiple concatenated arrays."""
    with open(path) as f:
        text = f.read()
    arrays = []
    idx = 0
    while True:
        start = text.find("[", idx)
        if start == -1:
            break
        depth = 0
        in_str = False
        i = start
        while i < len(text):
            ch = text[i]
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            arrays.extend(json.loads(text[start:i+1]))
                        except json.JSONDecodeError:
                            pass
                        idx = i + 1
                        break
            i += 1
        else:
            break
    return arrays


def parse_uno(uno_path: str) -> list[TurnRecord]:
    episodes = _load_json_arrays(uno_path)

    records = []
    for episode in episodes:
        ep_id = episode.get("episode_id", "unknown")
        lineage = episode.get("lineage", "unknown")
        messages = episode.get("messages", [])

        turn_idx = 0
        for i in range(len(messages) - 1):
            if messages[i]["role"] != "user":
                continue
            user_msg = messages[i]
            assistant_msg = messages[i + 1]
            if assistant_msg["role"] != "assistant":
                continue

            content = assistant_msg["content"]
            m = PEDAGOGY_RE.search(content)
            if not m:
                continue

            pedagogy = parse_pedagogy_block(m.group(1))
            if pedagogy is None:
                continue

            visible_text = PEDAGOGY_RE.sub("", content).strip()

            rec = TurnRecord(
                episode_id=ep_id,
                turn_index=turn_idx,
                lineage=lineage,
                user_text=user_msg["content"],
                assistant_visible_text=visible_text,
                pedagogy=pedagogy,
            )
            records.append(rec)
            turn_idx += 1

    return records


def build_transitions(records: list[TurnRecord]) -> list[TransitionRecord]:
    by_episode: dict[str, list[TurnRecord]] = {}
    for r in records:
        by_episode.setdefault(r.episode_id, []).append(r)

    transitions = []
    for ep_id, ep_records in by_episode.items():
        ep_records.sort(key=lambda x: x.turn_index)
        for i in range(len(ep_records) - 1):
            curr = ep_records[i]
            nxt = ep_records[i + 1]
            p = curr.pedagogy

            trans = TransitionRecord(
                episode_id=ep_id,
                from_turn=curr.turn_index,
                to_turn=nxt.turn_index,
                from_state=p.student_state,
                move_function=p.function_id.name if p.function_id else None,
                mechanism_shape=p.mechanism_shape.value,
                teaching_actions=p.teaching_actions,
                register=p.register.to_tuple() if p.register else None,
                predicted_impact=p.impact_predicted,
                observed_user_text=nxt.user_text,
                to_state=nxt.pedagogy.student_state,
                impact_update=p.impact_update,
                lineage=p.lineage,
                prediction_match="unknown",
            )
            transitions.append(trans)

    return transitions


def build_episode_arcs(records: list[TurnRecord]) -> list[EpisodeArc]:
    by_episode: dict[str, list[TurnRecord]] = {}
    for r in records:
        by_episode.setdefault(r.episode_id, []).append(r)

    arcs = []
    for ep_id, ep_records in by_episode.items():
        ep_records.sort(key=lambda x: x.turn_index)
        state_seq = [r.pedagogy.student_state for r in ep_records]
        fn_seq = [r.pedagogy.function_id.name if r.pedagogy.function_id else "" for r in ep_records]
        mech_seq = [r.pedagogy.mechanism_shape.value for r in ep_records]
        act_seq = [r.pedagogy.teaching_actions for r in ep_records]
        reg_seq = [r.pedagogy.register.to_tuple() if r.pedagogy.register else None for r in ep_records]
        imp_seq = [r.pedagogy.impact_predicted for r in ep_records]
        summary = ep_records[-1].pedagogy.accumulated_insight if ep_records else ""

        arcs.append(EpisodeArc(
            episode_id=ep_id,
            lineage=ep_records[0].lineage,
            state_sequence=state_seq,
            function_sequence=fn_seq,
            mechanism_sequence=mech_seq,
            action_sequence=act_seq,
            register_sequence=reg_seq,
            predicted_impact_sequence=imp_seq,
            final_state=state_seq[-1] if state_seq else "",
            arc_length=len(state_seq),
            arc_summary=summary,
        ))

    return arcs
