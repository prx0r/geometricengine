# HXRMXS UNO Engine

A pedagogical pathway engine that learns therapeutic teaching moves from annotated therapy transcripts (UNO dataset). Uses heterogeneous graph retrieval, LangGraph orchestration, and DeepSeek V4 Flash for response generation.

## How it works

```
UNO transcripts → PEDAGOGY parser → my_thought hyperedges → embeddings → vector retrieval
→ LangGraph pipeline (retrieve → candidate → hermes_seed → response → save)
→ Streamlit UI with rating + regeneration
→ policy weight updates from feedback
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Build data

```bash
# Parse UNO transcripts into SQLite hyperedge store
python3 -m src.ingest_uno

# Embed my_thought text for vector retrieval
python3 -m src.embed
```

## Run

```bash
export DEEPSEEK_API_KEY="sk-..."
streamlit run src/app.py --server.port 8501
```

## Test

```bash
pytest tests/
```

## Project structure

```
data/
  uno.txt              Raw UNO transcription dataset
  engine.sqlite        SQLite hypergraph + feedback store (generated)
  embeddings.jsonl     Vector embeddings for retrieval (generated)
src/
  parser/              UNO → structured records + graph builder
  models/              PedagogyBlock, Register, Mechanism, Function
  engine/              State classifier (WIP)
  ingest_uno.py        Parse UNO into hyperedge store
  embed.py             Generate embeddings
  retrieve.py          Vector search + candidate aggregation
  deepseek_client.py   DeepSeek V4 Flash API client
  hermes_prompts.py    Prompt templates for seed + response
  graph.py             LangGraph pipeline
  weights.py           Feedback + policy weight updates
  app.py               Streamlit UI
  schema.sql           SQLite table definitions
uno/
  uno.txt              Raw dataset
  unoguide.md          Graph parsing guide
  metaunoguide.md      my_thought metacognitive guide
```

## Key concepts

- **UNO**: Dataset of annotated therapy dialogues. Each assistant turn has a `[PEDAGOGY]` block with teaching metadata.
- **my_thought**: The teacher's internal monologue — the most valuable field for policy learning.
- **HXRMXS**: The function taxonomy (UM/RM/SM/ME) + mechanism shapes + register system.
- **Hyperedge**: A my_thought bound to its student_state, behavior_tags, mechanism, move, register, and traps.
