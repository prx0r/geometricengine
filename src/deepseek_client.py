import os
import json
from openai import OpenAI

BASE_URL = "https://opencode.ai/zen/go/v1"
API_KEY = "sk-7dtUVBKJrJcglO9WzdLQZJXwNuz1MucUrDQCZxJjJaH29Q8CqT357DSeFyHV4B75"
MODEL = "deepseek-v4-flash"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY", API_KEY),
            base_url=BASE_URL,
        )
    return _client


def classify_input(user_text: str, instruction: str) -> dict:
    client = get_client()
    res = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You output valid JSON only. Classify the input into known labels. Never invent new label values."},
            {"role": "user", "content": json.dumps({"instruction": instruction, "user_text": user_text})},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(res.choices[0].message.content)


def render_response(payload: dict) -> str:
    client = get_client()
    res = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are the HXRMXS renderer. The graph has already made all pedagogical decisions. You only write the natural language response based on the graph's selected structure. Do not add reasoning.",
            },
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.7,
    )
    return res.choices[0].message.content
