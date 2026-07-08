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


def deepseek_json(payload: dict) -> dict:
    client = get_client()
    res = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You output valid JSON only."},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    return json.loads(res.choices[0].message.content)


def deepseek_text(payload: dict) -> str:
    client = get_client()
    res = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are the HXRMXS/Hermes renderer. DeepSeek is the scribe; Hermes is the speaker.",
            },
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.7,
    )
    return res.choices[0].message.content
