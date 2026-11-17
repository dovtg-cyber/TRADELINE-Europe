"""EU: EUR-Lex through the public CELLAR service of the Publications Office (no API key).
Texts: https://publications.europa.eu/resource/celex/{CELEX} with Accept: application/xhtml+xml.
Metadata and relations: SPARQL endpoint http://publications.europa.eu/webapi/rdf/sparql.
NOT executed here (no network). CELLAR uses content negotiation and may answer with redirects or a choice list:
test with a real request and adjust. Consolidated texts have no legal effect; the Official Journal text is authentic."""
from __future__ import annotations
import urllib.request
from datetime import date
from html.parser import HTMLParser
from app.verification import SourceVersion, sha256_text


def celex_query(celex: str) -> str:
    """SPARQL to resolve a CELEX number to its work and document date. Properties cdm:resource_legal_id_celex and
    cdm:work_date_document were seen in public CELLAR query examples (checked 2026-11-16). Properties for entry into force
    and end of validity are NOT yet verified: confirm them in the CDM ontology before relying on them."""
    if not celex.isalnum():
        raise ValueError("bad CELEX")
    return ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
            "SELECT DISTINCT ?work ?date WHERE { ?work cdm:resource_legal_id_celex ?c . "
            f"FILTER(STR(?c) = \"{celex}\") OPTIONAL {{ ?work cdm:work_date_document ?date }} }}")


class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.out: list[str] = []
    def handle_data(self, d): self.out.append(d)


def fetch_celex(celex: str, version_from: date, version_to: date | None = None, lang: str = "eng") -> SourceVersion:
    req = urllib.request.Request(f"https://publications.europa.eu/resource/celex/{celex}",
                                 headers={"Accept": "application/xhtml+xml", "Accept-Language": lang})
    with urllib.request.urlopen(req, timeout=90) as r:
        html = r.read().decode("utf-8", "replace")
    p = _Text(); p.feed(html); text = " ".join(p.out)
    return SourceVersion(
        source_id=f"eurlex:{celex}:{version_from.isoformat()}", doc_id=f"eurlex:{celex}", title=f"CELEX {celex}",
        jurisdiction="EU", publisher="EUR-Lex", url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
        version_from=version_from, version_to=version_to, text=text, sha256=sha256_text(text), retrieved=date.today())
