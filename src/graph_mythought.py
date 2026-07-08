from typing import Any


def summarize_retrieved_pattern(retrieved_hyperedges: list[dict[str, Any]]) -> str:
    functions = [h.get("function_id") for h in retrieved_hyperedges if h.get("function_id")]
    mechanisms = [h.get("mechanism_shape") for h in retrieved_hyperedges if h.get("mechanism_shape")]
    states_from_hyperedges = [h.get("mythought_text", "")[:60] for h in retrieved_hyperedges[:3] if h.get("mythought_text")]

    return (
        f"Retrieved hyperedges cluster around functions={functions[:3]}, "
        f"mechanisms={mechanisms[:3]}. "
        f"Sample patterns: {' | '.join(states_from_hyperedges)}."
    )


def compose_graph_mythought(
    user_text: str,
    classified_labels: dict[str, Any],
    selected_pathway: dict[str, Any],
    retrieved_hyperedges: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "derived_by": "graph",
        "user_text": user_text,
        "input_state": classified_labels.get("student_state", "unknown"),
        "behavior_tags": classified_labels.get("behavior_tags", []),
        "retrieved_pattern": {
            "summary": summarize_retrieved_pattern(retrieved_hyperedges),
            "source_hyperedges": selected_pathway.get("source_hyperedges", []),
        },
        "selected_pathway": selected_pathway,
        "traps_avoided": [],
        "predicted_effect": "graph_selected_pathway_followed",
    }
