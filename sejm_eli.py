"""Poland: Dziennik Ustaw / Monitor Polski through the public Sejm ELI API (https://api.sejm.gov.pl/eli).
Fields below were checked on 2026-11-16 against the official API description (api.sejm.gov.pl/API_pl.html, eli_pl.html):
ELI, announcementDate, entryIntoForce, inForce ("IN_FORCE"), status, texts[{fileName,type}], references{"Akty zmieniajace"...}.
parse_act_meta() is pure and tested. The network functions are NOT run in the build environment (no network).
"""
from __future__ import annotations
import json, urllib.request
from datetime import date
from html.parser import HTMLParser
from app.verification import SourceVersion, sha256_text

BASE = "https://api.sejm.gov.pl/eli"
REL = {"Akty zmieniające": "amended_by", "Akty zmienione": "amends", "Akty uznane za uchylone": "repeals", "Odesłania": "refers_to"}


class NoTextLayer(Exception):
    """The act has no HTML text (only scanned PDF). It must not be indexed as if it had text."""


def _d(v):
    return date.fromisoformat(v[:10]) if v else None


def parse_act_meta(meta: dict) -> dict:
    texts = meta.get("texts") or []
    rels = []
    for key, kind in REL.items():
        for r in (meta.get("references") or {}).get(key, []) or []:
            rels.append({"kind": kind, "doc": "sejm:" + r.get("id", ""), "date": r.get("date")})
    return {
        "eli": meta.get("ELI"), "title": meta.get("title"), "published_on": _d(meta.get("announcementDate")),
        "entered_into_force": _d(meta.get("entryIntoForce")), "in_force_flag": meta.get("inForce"), "status": meta.get("status"),
        "has_html_text": any(t.get("type") == "H" for t in texts), "relations": rels, "changed_at": meta.get("changeDate"),
    }


def _get(url: str, accept: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": accept}), timeout=60) as r:
        return r.read()


class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.out: list[str] = []
    def handle_data(self, d): self.out.append(d)


def fetch_act(publisher: str, year: int, position: int) -> SourceVersion:
    meta = parse_act_meta(json.loads(_get(f"{BASE}/acts/{publisher}/{year}/{position}", "application/json")))
    if not meta["has_html_text"]:
        raise NoTextLayer(f"{publisher}/{year}/{position}")
    html = _get(f"{BASE}/acts/{publisher}/{year}/{position}/text.html", "text/html").decode("utf-8", "replace")
    p = _Text(); p.feed(html); text = " ".join(p.out)
    eli = meta["eli"] or f"{publisher}/{year}/{position}"
    start = meta["entered_into_force"] or meta["published_on"]
    return SourceVersion(
        source_id=f"sejm:{eli}:{start}", doc_id=f"sejm:{eli}", title=meta["title"] or eli, jurisdiction="PL", publisher="Sejm ELI",
        url=f"https://eli.gov.pl/eli/{eli}/ogl", version_from=start, version_to=None, text=text, sha256=sha256_text(text),
        retrieved=date.today(), published_on=meta["published_on"], entered_into_force=meta["entered_into_force"], authenticity="official")
