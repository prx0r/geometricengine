from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.retrieve import (
    retrieve_mythoughts,
    aggregate_candidate_nodes,
    score_pathway_candidates,
    select_pathway,
)
from src.weights import save_graph_run


class EngineState(TypedDict, total=False):
    thread_id: str
    user_text: str
    classification: dict[str, Any]
    retrieved_hyperedges: list[dict[str, Any]]
    aggregated_incidences: dict[str, Any]
    candidate_nodes: dict[str, Any]
    pathway_candidates: list[dict[str, Any]]
    selected_pathway: dict[str, Any]
    graph_mythought: dict[str, Any]
    response_form: str
    rendered_response: str
    final_response: str
    pathway_run_id: str
    feedback: dict[str, Any]
    validation_ok: bool
    validation_note: str


KNOWN_STATES = [
    "fearful_disclosure", "dawning_awareness", "resonating_agreement",
    "cognitive_fog", "architecture_correction", "spiralling",
    "resistance", "confusion", "avoidance", "integration",
    "breakthrough", "skepticism", "withdrawal", "engagement",
]

KNOWN_BEHAVIORS = [
    "adding_modules", "losing_focus", "rejects_wrong_abstraction",
    "protects_graph_sovereignty", "detects_llm_sovereignty_leak",
    "seeks_clarity", "resists_frame", "accepts_correction",
]


def _simple_classify(text: str) -> dict:
    text_lower = text.lower()
    state = "unknown"
    for s in KNOWN_STATES:
        if s.replace("_", " ") in text_lower or s.replace("_", "") in text_lower:
            state = s
            break
    if state == "unknown":
        words = text_lower.split()
        negative_words = {"afraid", "fear", "anxious", "spiral", "overwhelm", "stuck", "lost", "confused", "resist"}
        positive_words = {"understand", "see", "aware", "realize", "integration", "breakthrough", "agree"}
        if any(w in words for w in negative_words):
            state = "fearful_disclosure"
        elif any(w in words for w in positive_words):
            state = "dawning_awareness"

    behavior_tags = []
    for b in KNOWN_BEHAVIORS:
        if b.replace("_", " ") in text_lower or b.replace("_", "") in text_lower:
            behavior_tags.append(b)
    if not behavior_tags:
        if "module" in text_lower or "add" in text_lower:
            behavior_tags.append("adding_modules")
        if "focus" in text_lower:
            behavior_tags.append("losing_focus")
        if "wrong" in text_lower or "architect" in text_lower:
            behavior_tags.append("rejects_wrong_abstraction")

    return {
        "student_state": state,
        "behavior_tags": behavior_tags,
        "phase_hint": None,
        "function_hint": None,
        "mechanism_hint": None,
    }


def classify_node(state: EngineState) -> dict:
    labels = _simple_classify(state["user_text"])
    return {"classification": labels}


def retrieve_node(state: EngineState) -> dict:
    results = retrieve_mythoughts(state["user_text"], k=6)
    return {"retrieved_hyperedges": results}


def aggregate_node(state: EngineState) -> dict:
    candidates = aggregate_candidate_nodes(state["retrieved_hyperedges"])
    return {"candidate_nodes": candidates}


def score_pathways_node(state: EngineState) -> dict:
    candidates = score_pathway_candidates(
        state["retrieved_hyperedges"],
        state["candidate_nodes"],
        state.get("classification", {}),
        db_path="data/engine.sqlite",
    )
    return {"pathway_candidates": candidates}


def select_pathway_node(state: EngineState) -> dict:
    pathway = select_pathway(state["pathway_candidates"])
    return {"selected_pathway": pathway}


def compose_mythought_node(state: EngineState) -> dict:
    cls = state.get("classification", {})
    pathway = state.get("selected_pathway", {})
    retrieved = state.get("retrieved_hyperedges", [])

    top_pattern = ""
    if retrieved:
        top_pattern = retrieved[0].get("mythought_text", "")[:300]

    graph_mythought = {
        "derived_by": "graph",
        "input_state": cls.get("student_state", "unknown"),
        "behavior_tags": cls.get("behavior_tags", []),
        "retrieved_pattern": top_pattern,
        "selected_phase": pathway.get("phase", cls.get("phase_hint")),
        "selected_function_id": pathway.get("function_id", cls.get("function_hint")),
        "selected_mechanism_shape": pathway.get("mechanism_shape"),
        "selected_teaching_actions": pathway.get("teaching_actions", []),
        "selected_register": {
            "intensity": pathway.get("register_intensity"),
            "attunement": pathway.get("register_attunement"),
        },
        "traps_avoided": pathway.get("traps_avoided", []),
        "predicted_effect": pathway.get("predicted_impact", ""),
        "source_hyperedges": [he.get("id") for he in retrieved[:3]],
    }

    return {"graph_mythought": graph_mythought}


def select_response_form_node(state: EngineState) -> dict:
    function_id = state["graph_mythought"].get("selected_function_id", "")

    form_map = {
        "definition_collapse": "socratic_contradiction",
        "contradiction_exposure": "socratic_contradiction",
        "reductio_extension": "logical_chain",
        "ground_reality_check": "direct_question",
        "ego_displacement": "direct_question",
        "constraint_removal": "permission_grant",
        "analogy_scaffolding": "analogy_narrative",
        "causal_chain_mapping": "logical_chain",
        "conceptual_distinction": "direct_distinction",
        "instruction_protocol": "step_by_step",
        "frame_upgrade": "reframe",
        "direct_seeing": "pointing",
        "witness_pivot": "reframe",
        "synthesis_demand": "integration_question",
        "existential_commitment": "direct_question",
        "process_discipline": "step_by_step",
        "aporia_validation": "validation",
        "method_explanation": "exposition",
    }

    response_form = form_map.get(function_id, "direct_response")
    return {"response_form": response_form}


def _template_render(graph_mythought: dict, response_form: str) -> str:
    fn = graph_mythought.get("selected_function_id", "")
    phase = graph_mythought.get("selected_phase", "")
    state = graph_mythought.get("input_state", "unknown")
    actions = graph_mythought.get("selected_teaching_actions", [])
    effect = graph_mythought.get("predicted_effect", "")
    traps = graph_mythought.get("traps_avoided", [])
    register = graph_mythought.get("selected_register", {})

    trap_note = ""
    if traps:
        trap_note = f" Avoiding trap: {traps[0]}."

    action_note = ""
    if actions:
        action_note = f" {actions[0].replace('_', ' ').capitalize()}."

    templates = {
        "socratic_contradiction": [
            f"I notice something in what you're saying.{action_note} Could it be that the opposite is also true? Consider what you might be avoiding.{trap_note}",
            f"Let me reflect this back: you seem to be in a {state.replace('_', ' ')} state.{action_note} What if the frame itself is the problem?{trap_note}",
        ],
        "direct_question": [
            f"I see you're in a {state.replace('_', ' ')} space.{action_note} What evidence do you have that this is true?{trap_note}",
            f"Let me ask directly: given what you are describing as {state.replace('_', ' ')}, what would change if you saw this differently?{trap_note}",
        ],
        "direct_distinction": [
            f"There is a distinction to make here.{action_note} What you are describing as {state.replace('_', ' ')} may not be what it appears.{trap_note}",
            f"Let me separate two things that may have collapsed together.{action_note} The {state.replace('_', ' ')} you describe is not necessarily the whole picture.{trap_note}",
        ],
        "logical_chain": [
            f"Let me trace this through.{action_note} If {state.replace('_', ' ')}, then what follows?{trap_note}",
            f"Following the logic of what you've said:{action_note} This leads to a conclusion you may not have considered.{trap_note}",
        ],
        "analogy_narrative": [
            f"Consider this analogy:{action_note} What you describe as {state.replace('_', ' ')} is like something else I have seen.{trap_note}",
            f"Let me offer a parallel.{action_note} The pattern of {state.replace('_', ' ')} reminds me of...{trap_note}",
        ],
        "reframe": [
            f"Let me offer a different frame.{action_note} Rather than {state.replace('_', ' ')}, what if this is actually about something else?{trap_note}",
            f"Consider shifting perspective.{action_note} What you call {state.replace('_', ' ')} might be seen as...{trap_note}",
        ],
        "pointing": [
            f"Look at this directly.{action_note} Right now, in this moment of {state.replace('_', ' ')}, what is actually present?{trap_note}",
            f"Just notice.{action_note} The {state.replace('_', ' ')} you describe - can you see it as a passing state rather than a fixed truth?{trap_note}",
        ],
        "step_by_step": [
            f"Let me break this down.{action_note} First, acknowledge the {state.replace('_', ' ')}. Then:{trap_note}",
            f"Here is a structured approach.{action_note} Starting from {state.replace('_', ' ')}, the next step is...{trap_note}",
        ],
        "integration_question": [
            f"Can you integrate what you are seeing?{action_note} The {state.replace('_', ' ')} you describe contains a synthesis waiting to happen.{trap_note}",
            f"What would it mean to hold all of this together?{action_note} The pieces you describe as {state.replace('_', ' ')} may form a larger whole.{trap_note}",
        ],
        "validation": [
            f"I see what you mean.{action_note} The {state.replace('_', ' ')} you describe is a real and valid experience.{trap_note}",
            f"That is a valid observation.{action_note} Sitting with {state.replace('_', ' ')} is part of the process.{trap_note}",
        ],
        "permission_grant": [
            f"You have permission to let go of this.{action_note} The {state.replace('_', ' ')} you are holding is a constraint you can release.{trap_note}",
            f"It is okay to stop here.{action_note} The {state.replace('_', ' ')} does not need to be resolved right now.{trap_note}",
        ],
        "exposition": [
            f"Here is what is happening.{action_note} The {state.replace('_', ' ')} state operates through a mechanism you may not see directly.{trap_note}",
            f"Let me explain the process.{action_note} What appears as {state.replace('_', ' ')} is actually...{trap_note}",
        ],
    }

    import random
    candidates = templates.get(response_form, templates["direct_question"])
    return random.choice(candidates)


def render_node(state: EngineState) -> dict:
    graph_mythought = state.get("graph_mythought", {})
    response_form = state.get("response_form", "direct_response")
    rendered = _template_render(graph_mythought, response_form)
    return {"rendered_response": rendered, "final_response": rendered}


def validate_node(state: EngineState) -> dict:
    graph_mythought = state.get("graph_mythought", {})
    rendered = state.get("rendered_response", "")

    issues = []
    if not graph_mythought.get("selected_function_id"):
        issues.append("no function selected")
    if not graph_mythought.get("selected_phase"):
        issues.append("no phase selected")
    if not rendered:
        issues.append("empty response")

    return {
        "validation_ok": len(issues) == 0,
        "validation_note": "; ".join(issues) if issues else "ok",
    }


def save_node(state: EngineState) -> dict:
    run_id = save_graph_run("data/engine.sqlite", dict(state))
    return {"pathway_run_id": run_id}


builder = StateGraph(EngineState)

builder.add_node("classify", classify_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("aggregate", aggregate_node)
builder.add_node("score_pathways", score_pathways_node)
builder.add_node("select_pathway", select_pathway_node)
builder.add_node("compose_mythought", compose_mythought_node)
builder.add_node("select_response_form", select_response_form_node)
builder.add_node("render", render_node)
builder.add_node("validate", validate_node)
builder.add_node("save", save_node)

builder.set_entry_point("classify")
builder.add_edge("classify", "retrieve")
builder.add_edge("retrieve", "aggregate")
builder.add_edge("aggregate", "score_pathways")
builder.add_edge("score_pathways", "select_pathway")
builder.add_edge("select_pathway", "compose_mythought")
builder.add_edge("compose_mythought", "select_response_form")
builder.add_edge("select_response_form", "render")
builder.add_edge("render", "validate")
builder.add_edge("validate", "save")
builder.add_edge("save", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
