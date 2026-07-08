# HXRMXS UNO Engine — Test & Diagnostics Spec

## Purpose

This document defines the tests required to prove that the UNO engine is working as a real HXRMXS base layer.

The goal is not merely to check whether files run.

The goal is to verify that:

1. UNO data is parsed without losing structure.
2. Each `[PEDAGOGY]` block becomes a usable hyperedge.
3. `my_thoughts` are preserved as the central rationale layer.
4. Relationships between states, moves, mechanisms, registers, and outcomes are encoded.
5. The graph can retrieve relevant prior cognition events.
6. The AI model can use the retrieved hyperedges to produce useful diagnostics.
7. Feedback can update pathway weights.

A passing test suite means the system is no longer just a database. It is becoming an active weighted pedagogical engine.

---

# 1. Required Data Objects

The engine should produce and preserve these objects.

## 1.1 Episodes

Each source episode from `uno.txt` should become an `Episode`.

Required fields:
```json
{
  "episode_id": "string",
  "lineage": "string | null",
  "message_count": "number",
  "assistant_turn_count": "number",
  "user_turn_count": "number"
}
```

Pass condition:
- Every episode in `uno.txt` is represented.
- No episode is silently discarded.
- Episode ordering is preserved.

---

## 1.2 Turns

Each user/assistant exchange should become a `TurnRecord`.

Required fields:
```json
{
  "turn_id": "string",
  "episode_id": "string",
  "turn_index": "number",
  "user_text": "string | null",
  "assistant_visible_text": "string | null",
  "pedagogy": "object | null"
}
```

Pass condition:
- Every assistant message with a `[PEDAGOGY]` block creates one parsed turn.
- The visible assistant response is stored separately from the pedagogy block.
- The previous user message is correctly paired with the assistant response.

---

## 1.3 MyThought Hyperedges

Each assistant pedagogy block should become one `MyThoughtHyperedge`.

Required fields:
```json
{
  "hyperedge_id": "string",
  "turn_id": "string",
  "mythought_text": "string | null",
  "lineage": "string | null",
  "phase": "string | null",
  "function_id": "string | null",
  "student_state": "string | null",
  "behavior_tags": ["string"],
  "mechanism_shape": "string | null",
  "teaching_actions": ["string"],
  "register": "object | null",
  "style": "string | null",
  "depth": "string | null",
  "meta_mode": "string | null",
  "traps_avoided": ["string"],
  "intent": "string | null",
  "approach": "string | null",
  "impact_predicted": "string | null",
  "impact_confidence": "number | null",
  "impact_update": "string | null",
  "accumulated_insight": "string | null",
  "assistant_visible_text": "string"
}
```

Pass condition:
- Every parsed `[PEDAGOGY]` block creates exactly one hyperedge.
- `my_thoughts` is never discarded.
- Empty fields are allowed, but missing populated fields are failures.
- Assistant response text is attached to the hyperedge.

---

## 1.4 Incidences

Each hyperedge should connect to typed nodes.

Required incidence types:
```
lineage, phase, function_id, student_state, behavior_tag,
mechanism_shape, teaching_action, register_intensity,
register_intimacy, register_attunement, style, depth,
meta_mode, trap_avoided, intent, approach, impact_predicted,
accumulated_insight, response_form
```

Pass condition:
- Every populated field in the hyperedge creates at least one incidence.
- Multi-value fields create multiple incidences.
- Register subfields are broken out into searchable nodes.

---

## 1.5 Transitions

Consecutive assistant turns should create temporal transitions.

Required fields:
```json
{
  "transition_id": "string",
  "from_hyperedge_id": "string",
  "to_hyperedge_id": "string",
  "from_student_state": "string | null",
  "to_student_state": "string | null",
  "move_function": "string | null",
  "mechanism_shape": "string | null",
  "predicted_impact": "string | null",
  "next_impact_update": "string | null",
  "prediction_match": "confirmed | partial | contradicted | unknown"
}
```

Pass condition:
- Consecutive assistant turns in the same episode are connected.
- `impact_predicted` from turn `t` can be compared with `impact_update` from turn `t+1`.
- The system can reconstruct the pedagogical arc of an episode.

---

# 2. Parser Tests

File: `tests/test_parser.py`

## 2.1 Pedagogy Block Extraction

Test: Given a raw assistant message containing `[PEDAGOGY]...[PEDAGOGY]`, the parser separates pedagogy text from visible assistant text.

Pass: `has_pedagogy=true`, `has_visible_response=true`, visible response does not contain pedagogy tags.

## 2.2 Field Preservation Test

For each parsed block, assert known fields are preserved: lineage, phase, function_id, student_state, behavior_tags, mechanism_shape, teaching_actions, register, style, depth, meta_mode, traps_avoided, intent, approach, impact_predicted, impact_confidence, impact_update, accumulated_insight, my_thoughts.

Pass: If a field exists in raw text, it exists in parsed JSON.

## 2.3 Turn Pairing Test

Test that assistant turns are paired with the previous user message.

Pass: `assistant_turn.previous_user_text` is not null for all assistant turns except valid system-only cases.

---

# 3. Hypergraph Tests

File: `tests/test_hypergraph.py`

## 3.1 Hyperedge Count Test

Expected: `number_of_hyperedges == number_of_assistant_messages_with_pedagogy`

## 3.2 Incidence Completeness Test

95%+ populated fields have corresponding incidences.

## 3.3 MyThought Centrality Test

Every hyperedge should preserve `my_thoughts`. Print coverage percentage.

## 3.4 Transition Test

For each episode: `transitions_count == assistant_hyperedge_count - 1` within each episode.

---

# 4. Retrieval Tests

File: `tests/test_retrieval.py`

## 4.1 Golden Retrieval Cases

Seed golden inputs and verify expected concepts appear in top 5 retrieved hyperedges.

## 4.2 Candidate Move Test

At least one expected move appears in top 3 candidate moves. No bad move appears as top candidate.

---

# 5. AI Diagnostic Tests

File: `tests/test_ai_diagnostics.py`

The AI model receives retrieved hyperedges and candidate nodes, returns valid diagnostic JSON. Required keys present, no markdown wrapper. Selected phase/function/mechanism exists in retrieved/candidate data.

---

# 6. Response Generation Tests

File: `tests/test_generation.py`

Given a selected diagnostic, the model generates a response matching the selected pathway - follows selected function and mechanism, avoids forbidden traps, not generic.

---

# 7. Feedback Learning Tests

File: `tests/test_feedback.py`

## 7.1 Weight Update Test
Positive feedback increases weight. Negative feedback decreases weight.

## 7.2 Regeneration Test
Regenerated response selects a different move than rejected response.

## 7.3 Preference Pair Test
Regeneration stores rejected/preferred relation.

---

# 8. Minimum Passing Criteria

```
Parser:
- 95%+ pedagogy blocks parsed
- 95%+ populated fields preserved
- 95%+ hyperedges have incidences

Retrieval:
- 60%+ golden retrieval hit rate
- expected move appears top 3 in 50%+ cases

Diagnostics:
- model returns valid diagnostic JSON 90%+ of the time
- diagnostics average manual score >= 0.5

Feedback:
- positive feedback increases selected pathway weights
- negative feedback decreases selected pathway weights
- regeneration stores preference pairs
```

---

# 9. Critical Failure Conditions

The system is not working if:
- `my_thoughts` are not preserved
- retrieved items are just text chunks, not hyperedges
- model invents functions not found in candidates
- final response ignores selected pathway
- feedback does not update weights
- regeneration merely rewrites style
- trace panel cannot explain why the response happened
- graph-augmented output is not better than raw model

---

# 10. Core Principle

```
UNO is not a prompt library.
UNO is a latent pedagogical transition system.
```

The engine works only if it can transform:
```
new user input → inferred state → relevant UNO hyperedges →
selected pedagogical pathway → HXRMXS-style response →
feedback-updated graph
```
