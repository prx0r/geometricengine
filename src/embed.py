import json
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


def embed_all(db_path: str, output_path: str):
    model = SentenceTransformer(MODEL_NAME)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, mythought_text, compression FROM mythought_hyperedges")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No hyperedges to embed")
        return

    texts = []
    ids = []
    for he_id, mythought, compression in rows:
        text = compression or mythought[:256] or ""
        texts.append(text)
        ids.append(he_id)

    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings_list = embeddings.tolist()

    with open(output_path, "w") as f:
        for he_id, emb in zip(ids, embeddings_list):
            f.write(json.dumps({"id": he_id, "embedding": emb}) + "\n")

    print(f"Embedded {len(ids)} hyperedges -> {output_path}")


def load_embeddings(path: str) -> tuple[list[str], np.ndarray, dict]:
    ids = []
    embeddings = []
    meta = {}
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            ids.append(row["id"])
            embeddings.append(row["embedding"])
    return ids, np.array(embeddings), {}


if __name__ == "__main__":
    embed_all("data/engine.sqlite", "data/embeddings.jsonl")
