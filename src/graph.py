from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.retrieve import retrieve_mythoughts
from src.pathway import aggregate_incidences, select_weighted_pathway
from src.graph_mythought import compose_graph_mythought
from src.render import select_response_form, render_response_from_plan, validate_response
from src.weights import save_pathway_run


class EngineState(TypedDict, total=False):
    thread_id: str
    user_text: str
    classified_labels: dict[str, Any]
    retrieved_hyperedges: list[dict[str, Any]]
    incidence_aggregate: dict[str, Any]
    selected_pathway: dict[str, Any]
    graph_mythought: dict[str, Any]
    response_form: dict[str, Any]
    final_response: str
    validation_failures: list[str]
    pathway_run_id: str


def classify_node(state: EngineState) -> dict:
    return {
        "classified_labels": {
            "student_state": "unknown",
            "behavior_tags": [],
            "derived_by": "stub",
        }
    }


def retrieve_node(state: EngineState) -> dict:
    return {"retrieved_hyperedges": retrieve_mythoughts(state["user_text"], k=6)}


def aggregate_node(state: EngineState) -> dict:
    return {"incidence_aggregate": aggregate_incidences(state["retrieved_hyperedges"])}


def select_pathway_node(state: EngineState) -> dict:
    selected = select_weighted_pathway(
        classified_labels=state.get("classified_labels"),
        retrieved_hyperedges=state.get("retrieved_hyperedges"),
        incidence_aggregate=state.get("incidence_aggregate"),
    )
    return {"selected_pathway": selected}


def graph_mythought_node(state: EngineState) -> dict:
    mythought = compose_graph_mythought(
        user_text=state["user_text"],
        classified_labels=state.get("classified_labels", {}),
        selected_pathway=state["selected_pathway"],
        retrieved_hyperedges=state["retrieved_hyperedges"],
    )
    return {"graph_mythought": mythought}


def response_form_node(state: EngineState) -> dict:
    return {"response_form": select_response_form(state["graph_mythought"])}


def render_node(state: EngineState) -> dict:
    response = render_response_from_plan(state["graph_mythought"], state["response_form"])
    return {"final_response": response}


def validate_node(state: EngineState) -> dict:
    failures = validate_response(
        state["final_response"],
        state["graph_mythought"],
        state["response_form"],
    )
    return {"validation_failures": failures}


def save_node(state: EngineState) -> dict:
    run_id = save_pathway_run("data/engine.sqlite", dict(state))
    return {"pathway_run_id": run_id}


builder = StateGraph(EngineState)

builder.add_node("classify", classify_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("aggregate", aggregate_node)
builder.add_node("select_pathway", select_pathway_node)
builder.add_node("graph_mythought", graph_mythought_node)
builder.add_node("response_form", response_form_node)
builder.add_node("render", render_node)
builder.add_node("validate", validate_node)
builder.add_node("save", save_node)

builder.set_entry_point("classify")
builder.add_edge("classify", "retrieve")
builder.add_edge("retrieve", "aggregate")
builder.add_edge("aggregate", "select_pathway")
builder.add_edge("select_pathway", "graph_mythought")
builder.add_edge("graph_mythought", "response_form")
builder.add_edge("response_form", "render")
builder.add_edge("render", "validate")
builder.add_edge("validate", "save")
builder.add_edge("save", END)

graph = builder.compile(checkpointer=MemorySaver())
