from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.retrieve import (
    retrieve_mythoughts,
    aggregate_candidate_nodes,
    score_pathway_candidates,
    select_pathway,
)
from src.deepseek_client import classify_input, render_response
from src.hermes_prompts import CLASSIFY_INSTRUCTION, RENDER_INSTRUCTION
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


def classify_node(state: EngineState) -> dict:
    labels = classify_input(state["user_text"], CLASSIFY_INSTRUCTION)
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
    }

    return {"graph_mythought": graph_mythought}


def select_response_form_node(state: EngineState) -> dict:
    function_id = state["graph_mythought"].get("selected_function_id", "")
    phase = state["graph_mythought"].get("selected_phase", "")

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


def render_node(state: EngineState) -> dict:
    graph_mythought = state.get("graph_mythought", {})
    response_form = state.get("response_form", "direct_response")
    user_text = state.get("user_text", "")

    payload = {
        "instruction": RENDER_INSTRUCTION,
        "graph_mythought": graph_mythought,
        "response_form": response_form,
        "user_text": user_text,
    }

    try:
        result = render_response(payload)
        import json
        parsed = json.loads(result)
        rendered = parsed.get("rendered_response", result)
    except Exception:
        rendered = result

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
