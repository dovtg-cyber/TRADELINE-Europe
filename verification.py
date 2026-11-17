"""Verification Engine: the part of TRADELINE Legal Intelligence that decides what may be shown as fact.

Principle: the language model is never a source of law. It may only propose claims that point to a
source version stored in the knowledge base, with a verbatim quotation. This module checks every claim
and builds the displayed source data (name, URL, version date) from the knowledge base, never from the model.
Standard library only.
"""
from __future__ import annotations
import hashlib, re, unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Optional

_DASH = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
_QUOTE = dict.fromkeys(map(ord, "\u2018\u2019\u201a\u201b\u2032"), "'")
_DQUOTE = dict.fromkeys(map(ord, "\u201c\u201d\u201e\u201f\u00ab\u00bb"), '"')
MIN_QUOTE_CHARS = 20


def norm(text: str) -> str:
    """Normalise text for quotation matching: Unicode form, case, dashes, quotes, whitespace."""
    t = unicodedata.normalize("NFKC", text or "").translate(_DASH).translate(_QUOTE).translate(_DQUOTE)
    return re.sub(r"\s+", " ", t).strip().casefold()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass
class SourceVersion:
    source_id: str            # unique id of this exact version, e.g. "eurlex:32013R0952:2025-01-01"
    doc_id: str               # id of the act itself, e.g. "eurlex:32013R0952"
    title: str                # e.g. "Regulation (EU) No 952/2013 (Union Customs Code)"
    jurisdiction: str         # "EU", "PL", ...
    publisher: str            # "EUR-Lex", "Sejm ELI", ...
    url: str                  # official page of this version
    version_from: date        # first day this version applies
    version_to: Optional[date]  # last day it applies, None = still in force
    text: str                 # stored original text
    sha256: str               # checksum of `text` taken at ingestion
    retrieved: date
    # --- the five legal dates (all optional; see docs/03-SOURCES-AND-TIME-MACHINE.md) ---
    adopted_on: Optional[date] = None          # date of adoption / signature
    published_on: Optional[date] = None        # date of official publication
    entered_into_force: Optional[date] = None  # entry into force
    applies_from: Optional[date] = None        # date of application, if later than entry into force
    ceases_on: Optional[date] = None           # last day of application (repeal / sunset), if known
    authenticity: str = "official"             # "official" (Official Journal / official gazette) or "consolidated" (no legal effect)

    def intact(self) -> bool:
        return sha256_text(self.text) == self.sha256

    def in_force_on(self, d: date) -> bool:
        return self.version_from <= d and (self.version_to is None or d <= self.version_to)

    def applicable_on(self, d: date) -> bool:
        """True only if the version interval AND the application / sunset dates (when known) contain d."""
        if not self.in_force_on(d):
            return False
        if self.applies_from is not None and d < self.applies_from:
            return False
        if self.ceases_on is not None and d > self.ceases_on:
            return False
        return True


class KnowledgeBase:
    """In-memory reference implementation. Production uses the PostgreSQL schema in db/schema.sql."""

    def __init__(self) -> None:
        self._by_id: dict[str, SourceVersion] = {}

    def add(self, sv: SourceVersion) -> None:
        self._by_id[sv.source_id] = sv

    def get(self, source_id: str) -> Optional[SourceVersion]:
        return self._by_id.get(source_id)

    def all(self) -> list[SourceVersion]:
        return list(self._by_id.values())

    def versions(self, doc_id: str) -> list[SourceVersion]:
        return sorted((v for v in self._by_id.values() if v.doc_id == doc_id), key=lambda v: v.version_from)

    def version_on(self, doc_id: str, d: date) -> Optional[SourceVersion]:
        """Legal Time Machine: the version of an act that applied on date d."""
        for v in self.versions(doc_id):
            if v.in_force_on(d):
                return v
        return None


def verify_claim(claim: dict, kb: KnowledgeBase, as_of: date) -> dict:
    reasons: list[str] = []
    sv = kb.get(str(claim.get("source_id") or ""))
    quote = str(claim.get("quote") or "")
    if sv is None:
        reasons.append("source_not_found")
    else:
        if not sv.intact():
            reasons.append("source_integrity_failed")
        if len(norm(quote)) < MIN_QUOTE_CHARS:
            reasons.append("quote_missing_or_too_short")
        elif norm(quote) not in norm(sv.text):
            reasons.append("quote_not_in_source")
        if not sv.in_force_on(as_of):
            reasons.append("not_in_force_on_date")
        elif not sv.applicable_on(as_of):
            reasons.append("not_applicable_on_date")
    out = {
        "kind": "mandatory" if claim.get("kind") == "mandatory" else "recommended",
        "text": str(claim.get("text") or ""),
        "jurisdiction": sv.jurisdiction if sv else str(claim.get("jurisdiction") or ""),
        "act": sv.title if sv else "",
        "article": str(claim.get("article") or ""),
        "quote": quote,
        "authenticity": sv.authenticity if sv else "",
        "verified": not reasons,
        "reasons": reasons,
        "source": None,
    }
    if sv is not None:  # source data comes from the knowledge base, never from the model
        out["source"] = {
            "name": sv.publisher, "url": sv.url, "version_date": sv.version_from.isoformat(),
            "retrieved": sv.retrieved.isoformat(), "checksum": sv.sha256,
        }
    return out


def verify_report(draft: dict, kb: KnowledgeBase, as_of: date, missing: Optional[list] = None) -> dict:
    """Turn a model draft into the report returned to the client. Status rules:
    needs_data          required input is missing, no conclusion is given
    insufficient_basis  no verified claim, or a mandatory claim could not be verified
    verified            every mandatory claim is verified and at least one claim exists
    """
    claims = [verify_claim(c, kb, as_of) for c in (draft.get("claims") or [])]
    limits = list(draft.get("limits") or [])
    for c in claims:
        if not c["verified"]:
            limits.append(f"A statement could not be verified and is not relied on ({', '.join(c['reasons'])}): {c['text'][:120]}")
    for c in claims:
        if c["verified"] and c.get("authenticity") == "consolidated":
            limits.append("A statement relies on a consolidated text, which has no legal effect. Check it against the authentic Official Journal text before acting: " + c["text"][:100])
    if missing:
        status = "needs_data"
    elif not any(c["verified"] for c in claims) or any(c["kind"] == "mandatory" and not c["verified"] for c in claims):
        status = "insufficient_basis"
    else:
        status = "verified"
    summary = {
        "needs_data": "Required information is missing. No conclusion is given until it is provided.",
        "insufficient_basis": "The verified sources are not sufficient for a conclusion. See the open points.",
        "verified": str(draft.get("summary") or "Every mandatory statement below is tied to a verified source."),
    }[status]
    return {"status": status, "as_of": as_of.isoformat(), "summary": summary, "missing_data": missing or [],
            "claims": claims, "limits": limits}
