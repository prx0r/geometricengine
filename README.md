# HXRMXS UNO Engine

A **graph-native pedagogical policy engine** trained from UNO therapy transitions. Like a LoRA for graphs — the edge weights are learned from real therapy data, and inference queries those weights to select a teaching pathway.

## How it works

**Training (src/train.py):**
```
UNO transitions → for each from_state→(function, mechanism, register)→to_state:
                   increment W[state][function]
                   increment W[state][mechanism]
                   increment W[function][next_state]
                   → stored in policy_weights table
```

**Inference (src/pathway.py):**
```
user_text → retrieve similar hyperedges → infer state from incidences
→ query trained W[state] for top function/mechanism/register
→ if state unknown, use marginal weights across all transitions
→ compose graph_mythought → render
```

No LLM in the cognition path. The graph selects the move from UNO-trained weights.

## Pipeline

```
pathway (graph-owned, from trained weights)
  → mythought (composed from pathway + source hyperedges)
  → render (template)
  → save
  → feedback fine-tunes policy_weights
```

## Key files

| File | Purpose |
|---|---|
| `src/train.py` | Train graph weights from UNO transitions |
| `src/pathway.py` | Inference: select pathway from trained weights |
| `src/retrieve.py` | Vector search over mythought hyperedges |
| `src/graph.py` | LangGraph pipeline |
| `src/weights.py` | Save runs + apply feedback |
| `src/ingest_uno.py` | Parse UNO transcripts into SQLite |
| `src/embed.py` | Generate embeddings for vector retrieval |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m src.ingest_uno   # Parse UNO into SQLite
python3 -m src.embed        # Generate embeddings
python3 -m src.train        # Train graph weights from transitions
```

## Run

```bash
python3 server.py  # HTTP on :2222
# or
streamlit run src/app.py --server.port 8501
```

## Project structure

```
src/
  train.py          UNO → graph weights (like LoRA training)
  pathway.py        Inference from trained weights
  retrieve.py       Vector search
  graph.py          LangGraph pipeline
  weights.py        Persistence + feedback
  ingest_uno.py     UNO parser
  embed.py          Embedding generation
  deepseek_client.py  Optional LLM renderer (env-only)
  hermes_prompts.py   Quarantined
```
