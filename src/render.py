from typing import Any


def select_response_form(graph_mythought: dict) -> dict:
    pathway = graph_mythought.get("selected_pathway", {})
    function_id = pathway.get("function_id", "")

    if function_id.startswith("UM"):
        form = "direct_structural_correction"
    elif function_id.startswith("RM"):
        form = "reframe_and_rebuild"
    elif function_id.startswith("SM"):
        form = "self_making_protocol"
    else:
        form = "meta_method_correction"

    return {
        "derived_by": "graph",
        "response_form": form,
        "required_slots": ["name_state", "name_move", "state_reason", "give_next_action"],
        "forbidden_slots": ["free_llm_strategy", "new_module_expansion", "system_prompt_roleplay"],
    }


def render_response_from_plan(graph_mythought: dict, response_form: dict) -> str:
    pathway = graph_mythought.get("selected_pathway", {})
    state = graph_mythought.get("input_state", "unknown")
    pattern = graph_mythought.get("retrieved_pattern", {}).get("summary", "")

    return (
        f"State: {state}.\n\n"
        f"Move: {pathway.get('phase', '?')} / {pathway.get('function_id', '?')} "
        f"through {pathway.get('mechanism_shape', '?')}.\n\n"
        f"Reason: {pattern}\n\n"
        f"Next action: follow this selected pathway. The graph chose the move, not the LLM."
    )


def validate_response(response: str, graph_mythought: dict, response_form: dict) -> list[str]:
    failures = []

    if "DeepSeek should decide" in response.lower():
        failures.append("llm_sovereignty_leak")

    source_hids = graph_mythought.get("retrieved_pattern", {}).get("source_hyperedges", [])
    if not source_hids:
        failures.append("missing_source_hyperedges")

    if graph_mythought.get("derived_by") != "graph":
        failures.append("mythought_not_graph_derived")

    pathway = graph_mythought.get("selected_pathway", {})
    if not pathway.get("function_id"):
        failures.append("no_function_selected")

    return failures
