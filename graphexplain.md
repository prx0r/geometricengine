# Graph Engine: What We Have

## Source Data

**`data/uno.txt`** — 58 episodes of annotated therapy dialogues. Each episode contains 2-5 turns of (user → assistant → user → assistant...).

Each assistant turn has a `[PEDAGOGY]` block with 18+ fields.

## Parser

**`src/parser/uno_parser.py`** — extracts all fields from `[PEDAGOGY]` blocks into `PedagogyBlock` dataclass.

**`src/parser/graph_builder.py`** — builds `TransitionRecord` objects: `(from_state → function/mechanism/register/actions → to_state)` with `prediction_match`.

## Training (src/train.py)

**Input:** 201 parsed turns from UNO, grouped into 143 state→state transitions.

**Output:** 2153 trained weight edges stored in `policy_weights` table.

### The Prediction Loop (per turn)

```
Turn N:                         Turn N+1:
  student_state: X                student_state: Y
  function_id: F                  user_text: "..."
  mechanism_shape: M
  register: R
  teaching_actions: [A1, A2]
  impact_predicted: P
  impact_confidence: C
  my_thoughts: "Hypothesis:..."
    ↓
    → USER says: "..." (next_user_text)
    → STATE SHIFT: X → Y
    → impact_update: "Predicted P. Student said '...'. Shift X→Y."
    → prediction_match: true | partial | false | unknown
```

This is an RL loop:
1. Observe state X
2. Choose action (F, M, R, actions)
3. Predict outcome P
4. See actual outcome Y
5. Reward from prediction_match
6. Update policy weights

### What we train

| Edge type | Count | Example |
|---|---|---|
| state → function | per state | `fearful_disclosure → RM_03` |
| state → mechanism | per state | `fearful_disclosure → system_dynamics` |
| state → register | per state | `fearful_disclosure → register_intensity=PR_02` |
| state → action | per state | `fearful_disclosure → validates_insight` |
| state → next_state | per state | `fearful_disclosure → dawning_awareness` |
| function → next_state | per function | `RM_03 → dawning_awareness` |
| function → mechanism | per function | `RM_03 → system_dynamics` |
| state+function → predicted_impact | per pair | `fearful_disclosure\|RM_03 → ask_deeper_question` |
| behavior → function | per tag | `anxiety_report → RM_03` |
| trap → function | per trap | `identification_with_content → structural_analogy` |

### Example trained weights

```
fearful_disclosure:
  → RM_03 (0.5) → dawning_awareness (1.0)
  → system_dynamics (0.5)
  → register: PR_02 / IN_03 / AT_03 / LS_04 / PD_01 / MM_01
  → predicts: ask_deeper_question (0.5)
  → actions: validates_insight, identifies_mechanism, externalizes_superego

dawning_awareness:
  → RM_01 (0.3) → resonating_agreement (1.0)
  → RM_03 (0.3) → cognitive_resistance (1.0) or agreement (1.0)
  → register: PR_02 / IN_02 / AT_02 / LS_03 / PD_02 / MM_01

defensive_insistence:
  → UM_04 (0.3) → stuck_in_loop (1.0)
```

## Graph Engine (src/graph.py)

**LangGraph pipeline:**

```
pathway_node (select from trained weights + retrieve hyperedges)
  → render_node (template output)
  → save_node (persist)
```

The engine:
1. Retrieves top-6 similar hyperedges from vector search
2. Infers student state from incidence data of retrieved hyperedges
3. Queries `policy_weights` for that state's trained function/mechanism/register
4. Returns the selected pathway

## Tables in engine.sqlite

| Table | Rows | Content |
|---|---|---|
| `mythought_hyperedges` | 201 | Full pedagogy blocks |
| `mythought_incidences` | 3062 | Typed relationships |
| `uno_transitions` | 201 | Full turn data with all fields |
| `policy_weights` | 2153 | Trained graph edges |
| `episodes` | 58 | Episode metadata |
| `turns` | 201 | User/assistant text |
| `transitions` | 143 | State→state transitions |
| `graph_mythoughts` | varied | Runtime traces |

## What's Missing

- **State classifier**: No mapping from free-text user input to the 160 UNO student states (currently returns "unknown")
- **Prediction validation**: The graph doesn't yet use `impact_predicted` vs actual outcome as a learning signal during inference
- **Behavior tags**: Not used in inference, only in training
- **Traps**: Not used in inference
- **Accumulated insight**: Not used — could provide episode-level context
- **LLM rendering**: Available via `deepseek_client.py` but not wired into the pipeline
