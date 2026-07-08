from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.pathway import select_pathway, make_graph_mythought, render_pathway
from src.weights import save_pathway_run


class EngineState(TypedDict, total=False):
    thread_id: str
    user_text: str
    pathway: dict[str, Any]
    graph_mythought: dict[str, Any]
    final_response: str
    pathway_run_id: str


def pathway_node(state: EngineState) -> dict:
    return {"pathway": select_pathway(state["user_text"])}


def mythought_node(state: EngineState) -> dict:
    from src.retrieve import retrieve_mythoughts
    retrieved = retrieve_mythoughts(state["user_text"], k=6)
    return {"graph_mythought": make_graph_mythought(state["user_text"], state["pathway"], retrieved)}


def render_node(state: EngineState) -> dict:
    return {"final_response": render_pathway(state["pathway"])}


def save_node(state: EngineState) -> dict:
    run_id = save_pathway_run("data/engine.sqlite", dict(state))
    return {"pathway_run_id": run_id}


builder = StateGraph(EngineState)

builder.add_node("pathway", pathway_node)
builder.add_node("mythought", mythought_node)
builder.add_node("render", render_node)
builder.add_node("save", save_node)

builder.set_entry_point("pathway")
builder.add_edge("pathway", "mythought")
builder.add_edge("mythought", "render")
builder.add_edge("render", "save")
builder.add_edge("save", END)

graph = builder.compile(checkpointer=MemorySaver())
