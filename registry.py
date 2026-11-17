"""Registry of official sources: which sources exist, what they may be used for, and how they were verified.
Rule: only entries with evidence_allowed=True may support a legal statement. Secondary sources never can."""
from __future__ import annotations
import json, pathlib
from urllib.parse import urlparse

PATH = pathlib.Path(__file__).resolve().parent.parent / "sources" / "registry.json"
TIERS = {1, 2, 3}
AUTH = {"official_journal", "official_gazette", "consolidated_no_legal_effect", "official_database", "official_guidance", "secondary"}
VSTATUS = {"verified", "partly_verified", "to_verify"}
REQUIRED = ("id", "name", "jurisdiction", "publisher", "tier", "authenticity", "evidence_allowed", "automation", "domains", "access", "verified")


def load(path: pathlib.Path = PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["sources"]


def validate(entries: list[dict]) -> list[str]:
    errs: list[str] = []
    seen: set[str] = set()
    for e in entries:
        i = e.get("id", "?")
        for k in REQUIRED:
            if k not in e:
                errs.append(f"{i}: missing {k}")
        if i in seen:
            errs.append(f"{i}: duplicate id")
        seen.add(i)
        if e.get("tier") not in TIERS:
            errs.append(f"{i}: bad tier")
        if e.get("authenticity") not in AUTH:
            errs.append(f"{i}: bad authenticity")
        if e.get("tier") == 3 and e.get("evidence_allowed"):
            errs.append(f"{i}: a tier 3 (secondary) source cannot be evidence")
        if e.get("authenticity") == "secondary" and e.get("evidence_allowed"):
            errs.append(f"{i}: a secondary source cannot be evidence")
        if not e.get("domains"):
            errs.append(f"{i}: no domains")
        for d in e.get("domains", []):
            if "/" in d or ":" in d or d != d.lower():
                errs.append(f"{i}: domain must be a bare lowercase host: {d}")
        if (e.get("verified") or {}).get("status") not in VSTATUS:
            errs.append(f"{i}: bad verified.status")
        if e.get("automation") not in ("allowed", "manual_only", "to_verify"):
            errs.append(f"{i}: bad automation value")
        if e.get("evidence_allowed") and (e.get("verified") or {}).get("status") == "to_verify":
            errs.append(f"{i}: unverified source cannot be evidence yet")
    return errs


def evidence_allowed_for_url(url: str, entries: list[dict]) -> bool:
    u = urlparse(url or "")
    if u.scheme != "https" or not u.hostname:
        return False
    h = u.hostname.lower()
    return any(e["evidence_allowed"] and any(h == d or h.endswith("." + d) for d in e["domains"]) for e in entries)
