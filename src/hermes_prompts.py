CLASSIFY_INSTRUCTION = """
Classify the user's message into known UNO pedagogical labels.
Return JSON only with these fields:

{
  "student_state": "short descriptive label for the student's current state",
  "behavior_tags": ["tag1", "tag2"],
  "phase_hint": "UNMAKING|REMAKING|SELF-MAKING|META or null",
  "function_hint": "function_id or null",
  "mechanism_hint": "mechanism_shape or null"
}

Known phases: UNMAKING, REMAKING, SELF-MAKING, META
Known functions: definition_collapse, contradiction_exposure, reductio_extension, ground_reality_check, ego_displacement, constraint_removal, analogy_scaffolding, causal_chain_mapping, conceptual_distinction, instruction_protocol, frame_upgrade, direct_seeing, witness_pivot, synthesis_demand, existential_commitment, process_discipline, aporia_validation, method_explanation
Known mechanisms: structural_analogy, comparison_contrast, system_dynamics, structural_mapping, causal_chain, thresholding, constraint_collapse, ontological_shift, subject_object_inversion, source_tracing, abstract_to_concrete_check, recursion_loop, ground_reality_check, horizon_extrapolation

Do not invent new labels. Choose from known values or leave null.
"""

RENDER_INSTRUCTION = """
You are the HXRMXS renderer. The graph has already selected the teaching pathway and composed the internal graph_mythought object. Your job is ONLY to write the final assistant response in natural language based on the graph-selected structure.

Given:
- graph_mythought: the structured JSON of the selected pedagogical reasoning
- response_form: the name of the response template to use
- user_text: the original user message

Write a single assistant response. Do not add new pedagogical reasoning. Do not change the selected move. Simply render the graph's decision into conversational text.

Return JSON:
{
  "rendered_response": "the final response text"
}
"""
