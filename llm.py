"""Model adapter. NOT executed in the environment where this was written (no network or API key).
The prompt contract is the important part: the model may only use the supplied passages."""
from __future__ import annotations
import json, os, urllib.request

SYSTEM = """You are the analysis step of a legal research system for international trade.
Rules, without exceptions:
1. Use ONLY the passages provided. They are the only source of law you may rely on.
2. Every claim must carry source_id (copied from a passage) and quote (copied word for word from that passage).
3. Never cite an act, article or number that is not in the passages. Never invent a link.
4. Mark each claim as kind=mandatory (a binding requirement) or kind=recommended.
5. If the passages do not support an answer, say so in limits. Do not guess.
Return JSON only: {"summary": str, "claims": [{"kind": str, "text": str, "article": str, "source_id": str, "quote": str}], "limits": [str]}"""


class AnthropicLLM:
    def __init__(self) -> None:
        self.key = os.environ["ANTHROPIC_API_KEY"]
        self.model = os.environ.get("LLM_MODEL", "claude-sonnet-5-5")

    def analyse(self, params: dict, passages: list[dict]) -> dict:
        body = {"model": self.model, "max_tokens": 3000, "system": SYSTEM, "messages": [{"role": "user", "content": json.dumps(
            {"brief": params, "passages": passages}, ensure_ascii=False)}]}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
                                     headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.load(r)
        text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
        a, b = text.find("{"), text.rfind("}")
        return json.loads(text[a:b + 1]) if a >= 0 and b > a else {"claims": [], "limits": ["The model returned no usable draft."]}
