SEED_INSTRUCTION = """
Generate the Hermes/HXRMXS internal teacher monologue.
Study the retrieved my_thought hyperedges: they show how the HXRMXS teacher has handled similar situations.
Use them as geometric precedent, not copy-paste.

The my_thought field is the actual output. Make it vivid, precise, diagnostic.
It should read like a teacher watching themselves teach in real time.

Return JSON only:
{
  "compression": "one-sentence reframe of the user's situation",
  "my_thought": "internal teacher monologue: state inference, move rationale, trap to avoid, what to watch for",
  "selected_move": "the HXRMXS function to fire (UM_01-06, RM_01-05, SM_01-04, ME_01-03)",
  "mechanism": "the geometric pattern (structural_analogy, constraint_collapse, causal_chain, etc.)",
  "register": {"intensity": "PR_01-04", "intimacy": "IN_01-04", "attunement": "AT_01-03", "style": "LS_01-06", "depth": "PD_01-04", "meta_mode": "MM_01-02"},
  "response_plan": ["step 1", "step 2", "step 3"],
  "forbidden_tone": ["list of tones to avoid"]
}
"""
