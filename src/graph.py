from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.retrieve import retrieve_mythoughts, aggregate_candidate_nodes
from src.deepseek_client import deepseek_json
from src.hermes_prompts import SEED_INSTRUCTION
from src.weights import save_pathway_run


class EngineState(TypedDict, total=False):
    thread_id: str
    user_text: str
    retrieved_hyperedges: list[dict[str, Any]]
    candidate_nodes: dict[str, Any]
    hermes_seed: dict[str, Any]
    final_response: str
    pathway_run_id: str
    feedback: dict[str, Any]
    failure_tags: list[str]
    rejected_seed: dict[str, Any]
    rejected_response: str


def retrieve_node(state: EngineState) -> dict:
    results = retrieve_mythoughts(state["user_text"], k=6)
    return {"retrieved_hyperedges": results}


def candidate_node(state: EngineState) -> dict:
    candidates = aggregate_candidate_nodes(state["retrieved_hyperedges"])
    return {"candidate_nodes": candidates}


def hermes_seed_node(state: EngineState) -> dict:
    prompt = {
        "user_text": state["user_text"],
        "retrieved_hyperedges": [
            {
                "mythought_text": he["mythought_text"],
                "function_id": he.get("function_id"),
                "mechanism_shape": he.get("mechanism_shape"),
                "intent": he.get("intent"),
                "predicted_impact": he.get("predicted_impact"),
            }
            for he in state["retrieved_hyperedges"]
        ],
        "candidate_nodes": state["candidate_nodes"],
        "instruction": SEED_INSTRUCTION,
    }

    failure_tags = state.get("failure_tags", [])
    if failure_tags:
        prompt["failure_tags"] = failure_tags
        prompt["rejected_seed"] = state.get("rejected_seed", {})
        prompt["rejected_response"] = state.get("rejected_response", "")
        prompt["instruction"] += "\n\nAVOID these failures: " + ", ".join(failure_tags)

    seed = deepseek_json(prompt)
    return {"hermes_seed": seed}


def finalize_node(state: EngineState) -> dict:
    seed = state.get("hermes_seed", {})
    my_thought = seed.get("my_thought", "")
    return {"final_response": my_thought}


def save_node(state: EngineState) -> dict:
    run_id = save_pathway_run("data/engine.sqlite", dict(state))
    return {"pathway_run_id": run_id}


builder = StateGraph(EngineState)

builder.add_node("retrieve", retrieve_node)
builder.add_node("candidate", candidate_node)
builder.add_node("hermes_seed", hermes_seed_node)
builder.add_node("finalize", finalize_node)
builder.add_node("save", save_node)

builder.set_entry_point("retrieve")
builder.add_edge("retrieve", "candidate")
builder.add_edge("candidate", "hermes_seed")
builder.add_edge("hermes_seed", "finalize")
builder.add_edge("finalize", "save")
builder.add_edge("save", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
