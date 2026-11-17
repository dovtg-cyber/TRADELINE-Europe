import unittest
from datetime import date
from app.verification import KnowledgeBase, SourceVersion, sha256_text
from app.retrieval import KeywordRetriever, chunk_articles
from app.workspace import WorkspaceStore, ClientDoc, AccessDenied
from ingest.sejm_eli import parse_act_meta
from ingest.eurlex_cellar import celex_query

TXT = "Article 1. Subject matter of furniture imports. Article 2. Customs declaration for furniture goods shall be lodged. Article 3. Unrelated chemical rules."
def sv(sid, vf, vt, jur="EU", text=TXT, **kw):
    return SourceVersion(source_id=sid, doc_id="d:" + sid.split(":")[0], title="T", jurisdiction=jur, publisher="P", url="https://eur-lex.europa.eu/x", version_from=vf, version_to=vt, text=text, sha256=sha256_text(text), retrieved=date(2026, 11, 16), **kw)

class Retrieval(unittest.TestCase):
    def test_chunks_by_article(self):
        c = chunk_articles(TXT); self.assertEqual([a for a, _ in c], ["Art. 1", "Art. 2", "Art. 3"])
    def test_only_versions_applicable_on_date(self):
        kb = KnowledgeBase(); kb.add(sv("old:1", date(2020, 1, 1), date(2024, 12, 31))); kb.add(sv("new:1", date(2025, 1, 1), None))
        r = KeywordRetriever(kb).search({"question": "furniture customs declaration"}, date(2026, 11, 16))
        self.assertTrue(r); self.assertTrue(all(p["source_id"] == "new:1" for p in r))
    def test_application_date_respected(self):
        kb = KnowledgeBase(); kb.add(sv("a:1", date(2026, 1, 1), None, applies_from=date(2026, 7, 1)))
        self.assertEqual(KeywordRetriever(kb).search({"question": "furniture declaration"}, date(2026, 3, 1)), [])
    def test_best_article_first_and_jurisdiction_filter(self):
        kb = KnowledgeBase(); kb.add(sv("eu:1", date(2025, 1, 1), None)); kb.add(sv("pl:1", date(2025, 1, 1), None, jur="PL"))
        r = KeywordRetriever(kb).search({"question": "customs declaration furniture", "jurisdictions": ["Poland"]}, date(2026, 11, 16))
        self.assertTrue(all(p["source_id"] == "pl:1" for p in r)); self.assertEqual(r[0]["article"], "Art. 2")
    def test_empty_query_returns_nothing(self):
        self.assertEqual(KeywordRetriever(KnowledgeBase()).search({"question": "a b"}, date(2026, 1, 1)), [])

class Workspace(unittest.TestCase):
    def setUp(self):
        self.w = WorkspaceStore(); self.w.put("anna", ClientDoc("d1", "anna", "invoice", "secret A")); self.w.put("boris", ClientDoc("d2", "boris", "contract", "secret B"))
    def test_cross_client_blocked_and_audited(self):
        with self.assertRaises(AccessDenied): self.w.get("anna", "d2")
        self.assertFalse(self.w.audit[-1]["allowed"])
    def test_missing_and_foreign_look_the_same(self):
        for d in ("d2", "nope"):
            with self.assertRaises(AccessDenied) as c: self.w.get("anna", d)
            self.assertEqual(str(c.exception), "no access")
    def test_context_contains_only_own_documents(self):
        self.assertEqual([d.doc_id for d in self.w.context_for("anna")], ["d1"])
    def test_cannot_store_under_someone_else(self):
        with self.assertRaises(AccessDenied): self.w.put("anna", ClientDoc("d3", "boris", "x", "y"))
    def test_reviewer_needs_explicit_grant(self):
        with self.assertRaises(AccessDenied): self.w.get("lawyer", "d1")
        self.w.grant("anna", "lawyer", "d1"); self.assertEqual(self.w.get("lawyer", "d1").text, "secret A")
        with self.assertRaises(AccessDenied): self.w.get("lawyer", "d2")
    def test_only_owner_can_grant(self):
        with self.assertRaises(AccessDenied): self.w.grant("anna", "lawyer", "d2")

class Ingest(unittest.TestCase):
    META = {"ELI": "DU/2020/1", "announcementDate": "2019-12-23", "entryIntoForce": "2020-01-17", "inForce": "IN_FORCE", "status": "obowiązujący", "title": "Ustawa X",
            "texts": [{"fileName": "text.html", "type": "H"}, {"fileName": "D20200001.pdf", "type": "O"}],
            "references": {"Akty zmieniające": [{"id": "DU/2024/1222", "date": "2024-11-10"}], "Akty uznane za uchylone": [{"id": "DU/2019/1087", "date": "2021-01-19"}]}}
    def test_parse_sejm_meta(self):
        m = parse_act_meta(self.META)
        self.assertEqual(m["entered_into_force"].isoformat(), "2020-01-17"); self.assertEqual(m["published_on"].isoformat(), "2019-12-23"); self.assertTrue(m["has_html_text"])
        self.assertIn({"kind": "amended_by", "doc": "sejm:DU/2024/1222", "date": "2024-11-10"}, m["relations"])
        self.assertTrue(any(r["kind"] == "repeals" for r in m["relations"]))
    def test_pdf_only_act_is_flagged(self):
        self.assertFalse(parse_act_meta({"ELI": "DU/1/1", "texts": [{"fileName": "a.pdf", "type": "O"}]})["has_html_text"])
    def test_missing_dates_stay_none(self):
        m = parse_act_meta({"ELI": "DU/1/1"}); self.assertIsNone(m["entered_into_force"]); self.assertIsNone(m["published_on"])
    def test_celex_query_rejects_injection(self):
        self.assertIn("32016R0679", celex_query("32016R0679"))
        with self.assertRaises(ValueError): celex_query('1" ) } DROP')
