"""HTTP API (FastAPI). Not run in the environment where this was written (FastAPI was not installable there)."""
import os
from datetime import date
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from .verification import KnowledgeBase
from .pipeline import run_research

app = FastAPI(title="TRADELINE Legal Intelligence API", version="0.1")
KB = KnowledgeBase()  # replace with the PostgreSQL-backed implementation (db/schema.sql)


class Research(BaseModel):
    question: str
    jurisdictions: list[str] = []
    goods: str = ""
    cn: str = ""
    origin: str = ""
    to: str = ""
    as_of: str = ""
    role: str = ""
    note: str = ""
    from_: str = ""  # the website sends "from"; map it with an alias when wiring the real client


def auth(token: str | None):
    # Wire this to the platform's real accounts. Until then the API refuses everything except local development.
    if os.environ.get("TL_DEV_NOAUTH") == "1":
        return
    if not token or token != "Bearer " + os.environ.get("TL_API_TOKEN", "\0"):
        raise HTTPException(401, "Unauthorized")


@app.get("/health")
def health():
    return {"ok": True, "knowledge_base_versions": len(KB._by_id)}


@app.post("/v1/research")
def research(r: Research, authorization: str | None = Header(default=None)):
    auth(authorization)
    p = r.model_dump()
    p["question"] = r.question
    p["from"] = p.pop("from_")
    p["as_of"] = r.as_of or date.today().isoformat()
    from .retrieval import KeywordRetriever  # TO BUILD: full-text + semantic search over the KB, versions in force on as_of only
    from .llm import AnthropicLLM
    return run_research(p, KB, KeywordRetriever(KB), AnthropicLLM())
