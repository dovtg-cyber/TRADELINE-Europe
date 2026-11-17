"""One research request, end to end. Order matters: missing data is checked BEFORE any model call."""
from __future__ import annotations
import re
from datetime import date
from typing import Protocol
from .verification import KnowledgeBase, verify_report


def missing_data(p: dict) -> list[dict]:
    """Mirror of missingData() in the website (public/js/legal.js). Keep both in sync."""
    m: list[dict] = []
    add = lambda f, w: m.append({"field": f, "why": w})
    if len((p.get("question") or "").strip()) < 10: add("Your question", "Describe what you need to establish.")
    if not p.get("jurisdictions"): add("Jurisdictions", "Choose the jurisdictions to analyse.")
    if not p.get("goods"): add("Goods description", "Composition, material, purpose and technical features decide the classification.")
    cn = re.sub(r"[\s.]", "", p.get("cn") or "")
    if not cn: add("CN / TARIC code", "The code decides duties, measures and restrictions.")
    elif not re.fullmatch(r"\d{6}|\d{8}|\d{10}", cn): add("CN / TARIC code", "A code has 6, 8 or 10 digits.")
    elif len(cn) < 8: add("CN / TARIC code", "Duties and measures need at least the 8-digit CN code.")
    if not p.get("origin"): add("Country of origin", "Origin is not the country of dispatch and decides preferences and duties.")
    if not p.get("from") or not p.get("to"): add("Route", "Country of dispatch and of destination.")
    if not p.get("as_of"): add("Operation date", "The law is checked as it stood on this date.")
    if not p.get("role"): add("Your role", "Obligations differ for an importer, an exporter and a forwarder.")
    return m


class Retriever(Protocol):
    def search(self, params: dict, as_of: date) -> list[dict]:
        """Return passages: {source_id, text}. Only versions in force on as_of."""


class LLM(Protocol):
    def analyse(self, params: dict, passages: list[dict]) -> dict:
        """Return a draft: {summary, claims:[{kind,text,article,source_id,quote}], limits:[...]}"""


def run_research(params: dict, kb: KnowledgeBase, retriever: Retriever, llm: LLM) -> dict:
    as_of = date.fromisoformat(params["as_of"]) if params.get("as_of") else date.today()
    missing = missing_data(params)
    if missing:  # evidence first: no model call, no conclusion
        return verify_report({"claims": []}, kb, as_of, missing)
    passages = retriever.search(params, as_of)
    if not passages:
        return verify_report({"claims": [], "limits": ["No applicable source was found in the knowledge base."]}, kb, as_of)
    return verify_report(llm.analyse(params, passages), kb, as_of)
