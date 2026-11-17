"""Reference retriever (keyword scoring over article chunks). Production adds PostgreSQL full-text and pgvector,
but the contract is the same: return ONLY passages from versions applicable on the operation date."""
from __future__ import annotations
import re
from collections import Counter
from datetime import date
from .verification import KnowledgeBase, norm

_ART = re.compile(r"(?:^|(?<=[.\n]))\s*(Article|Art\.)\s+(\d+[a-z]?)\.?\s")
_STOP = set("the and for with from that this which what shall into under have been their other about how are any can does need".split())
JMAP = {"European Union": "EU", "Poland": "PL", "China": "CN", "Germany": "DE", "Other": None}


def chunk_articles(text: str) -> list[tuple[str, str]]:
    ms = list(_ART.finditer(text))
    if not ms:
        return [("", text)] if text.strip() else []
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.append((f"Art. {m.group(2)}", text[m.start():end].strip()))
    return out


def _tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"\w+", norm(s)) if len(t) >= 4 and t not in _STOP]


class KeywordRetriever:
    def __init__(self, kb: KnowledgeBase, top_k: int = 8) -> None:
        self.kb, self.top_k = kb, top_k

    def search(self, params: dict, as_of: date) -> list[dict]:
        q = Counter(_tokens(" ".join(str(params.get(k) or "") for k in ("question", "goods", "note"))))
        if not q:
            return []
        wanted = {JMAP.get(j) for j in params.get("jurisdictions") or []} - {None}
        scored = []
        for sv in self.kb.all():
            if not sv.applicable_on(as_of):          # the Time Machine rule: never retrieve a version that did not apply
                continue
            if wanted and sv.jurisdiction not in wanted:
                continue
            for art, body in chunk_articles(sv.text):
                toks = Counter(_tokens(body))
                score = sum(min(toks[t], 3) * w for t, w in q.items() if t in toks)
                if score:
                    scored.append((score, sv.source_id, art, body))
        scored.sort(key=lambda x: (-x[0], x[1], x[2]))
        return [{"source_id": s, "article": a, "text": b, "score": sc} for sc, s, a, b in scored[: self.top_k]]
