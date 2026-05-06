from __future__ import annotations

import os
import re
from typing import Optional

import httpx


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _clean_text(t: str) -> str:
    t = (t or "").strip()
    t = t.replace("**", "").replace("__", "")
    t = t.replace("—", ",").replace("–", ",")
    t = t.replace("\n", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _is_bad_tone(t: str) -> bool:
    low = (t or "").lower()
    banned = [
        "your confusion may stem",
        "it seems you are",
        "it appears you are",
        "typically doesn't apply",
        "hierarchical structure",
        "in this context",
        "stems from",
        "perceived in the interaction",
        "you are asking",
        "you feel that",
    ]
    return any(b in low for b in banned)


def _postprocess_explain(text: str) -> str:
    """
    World class constraints:
    - 1 short WhatsApp sentence (max ~16 words)
    - calm, polite, supportive
    - NO questions
    - NO academic/superior tone
    """
    t = _clean_text(text)
    if not t:
        return ""

    # hard reject bad tone
    if _is_bad_tone(t):
        return ""

    # remove questions entirely
    if "?" in t:
        t = t.split("?", 1)[0].strip()
    t = t.replace("?", "").strip()

    # keep short
    words = t.split()
    if len(words) > 16:
        t = " ".join(words[:16]).rstrip(" ,.;:") + "."

    # end neatly
    if t and t[-1] not in ".!":
        t += "."

    return t


def ask_openai_fallback(*, state: str, user_text: str) -> str:
    """
    OpenAI is used ONLY for short explanations / calming responses.
    """
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    timeout_s = float(_env("OPENAI_TIMEOUT_SECONDS", "20") or "20")

    # Trust-first Nigerian WhatsApp tone lock
    system_msg = (
        "You are a calm, friendly Nigerian real-estate assistant on WhatsApp.\n"
        "Goal: reply in ONE short sentence (max 16 words).\n"
        "Style: polite, warm, human, supportive.\n"
        "If user is upset: apologize gently and reassure.\n"
        "Never sound academic, superior, or defensive.\n"
        "Never say: 'your confusion may stem', 'it seems you are', 'you are asking'.\n"
        "No questions. No follow up prompts. No greetings.\n"
        "No mention of system/flow/state."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "developer", "content": system_msg},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 60,
    }

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/chat/completions"

    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    content = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
    final = _postprocess_explain(content)

    if not final:
        raise RuntimeError("OpenAI output rejected by tone/format filters")

    return final
