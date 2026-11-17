import unittest
from datetime import date
from app.verification import KnowledgeBase, SourceVersion, sha256_text, verify_claim, verify_report, norm
from app.pipeline import run_research, missing_data

TEXT = "Article 5. Goods brought into the customs territory of the Union shall be declared by the person concerned. Article 6. Other rules."
TODAY = date(2026, 11, 16)

def sv(**kw):
    base = dict(source_id="eurlex:X:2025-01-01", doc_id="eurlex:X", title="Regulation X", jurisdiction="EU", publisher="EUR-Lex",
                url="https://eur-lex.europa.eu/x", version_from=date(2025, 1, 1), version_to=None, text=TEXT,
                sha256=sha256_text(TEXT), retrieved=date(2026, 11, 16))
    base.update(kw); return SourceVersion(**base)

def kb_with(*vs):
    kb = KnowledgeBase()
    for v in vs: kb.add(v)
    return kb

GOOD = {"kind": "mandatory", "text": "Goods must be declared.", "article": "Art. 5", "source_id": "eurlex:X:2025-01-01",
        "quote": "Goods brought into the customs territory of the Union shall be declared"}

class Verify(unittest.TestCase):
    def test_good_claim_verified_and_source_from_kb(self):
        c = verify_claim(dict(GOOD, url="https://evil.example"), kb_with(sv()), TODAY)
        self.assertTrue(c["verified"]); self.assertEqual(c["source"]["url"], "https://eur-lex.europa.eu/x")
    def test_fabricated_source(self):
        c = verify_claim(dict(GOOD, source_id="eurlex:NOPE"), kb_with(sv()), TODAY)
        self.assertFalse(c["verified"]); self.assertIn("source_not_found", c["reasons"]); self.assertIsNone(c["source"])
    def test_quote_not_in_source(self):
        c = verify_claim(dict(GOOD, quote="Goods may never be declared by anyone at all"), kb_with(sv()), TODAY)
        self.assertIn("quote_not_in_source", c["reasons"])
    def test_short_quote_rejected(self):
        self.assertIn("quote_missing_or_too_short", verify_claim(dict(GOOD, quote="Goods"), kb_with(sv()), TODAY)["reasons"])
    def test_date_outside_version(self):
        self.assertIn("not_in_force_on_date", verify_claim(GOOD, kb_with(sv()), date(2024, 12, 31))["reasons"])
        k = kb_with(sv(version_to=date(2025, 12, 31)))
        self.assertIn("not_in_force_on_date", verify_claim(GOOD, k, date(2026, 1, 1))["reasons"])
    def test_tampered_text_detected(self):
        self.assertIn("source_integrity_failed", verify_claim(GOOD, kb_with(sv(text=TEXT + " extra")), TODAY)["reasons"])
    def test_norm_handles_dashes_quotes_space(self):
        self.assertEqual(norm("A \u2013  B \u201cC\u201d"), norm('a - b "c"'))

class Report(unittest.TestCase):
    def test_needs_data_wins(self):
        self.assertEqual(verify_report({"claims": [GOOD]}, kb_with(sv()), TODAY, [{"field": "CN"}])["status"], "needs_data")
    def test_verified(self):
        self.assertEqual(verify_report({"claims": [GOOD]}, kb_with(sv()), TODAY)["status"], "verified")
    def test_unverified_mandatory_blocks_conclusion(self):
        r = verify_report({"claims": [GOOD, dict(GOOD, source_id="nope")]}, kb_with(sv()), TODAY)
        self.assertEqual(r["status"], "insufficient_basis"); self.assertTrue(r["limits"])
    def test_no_claims_is_insufficient(self):
        self.assertEqual(verify_report({"claims": []}, kb_with(sv()), TODAY)["status"], "insufficient_basis")
    def test_time_machine(self):
        k = kb_with(sv(source_id="a", version_to=date(2025, 6, 30)), sv(source_id="b", version_from=date(2025, 7, 1)))
        self.assertEqual(k.version_on("eurlex:X", date(2025, 3, 1)).source_id, "a")
        self.assertEqual(k.version_on("eurlex:X", date(2026, 1, 1)).source_id, "b")
        self.assertIsNone(k.version_on("eurlex:X", date(2024, 1, 1)))

class Pipeline(unittest.TestCase):
    P = dict(question="Which documents apply to importing lamps?", jurisdictions=["EU"], goods="LED lamps", cn="94054200",
             origin="China", as_of="2026-11-16", role="Importer", **{"from": "China", "to": "Poland"})
    class Ret:
        def search(self, p, d): return [{"source_id": "eurlex:X:2025-01-01", "text": TEXT}]
    class Fake:
        called = 0
        def analyse(self, p, passages):
            Pipeline.Fake.called += 1
            return {"summary": "x", "claims": [GOOD, {"kind": "mandatory", "text": "Invented rule", "source_id": "eurlex:X:2025-01-01",
                    "quote": "A certificate of the Ministry is always required for lamps"}]}
    def test_missing_data_means_no_model_call(self):
        Pipeline.Fake.called = 0
        r = run_research(dict(self.P, cn=""), kb_with(sv()), self.Ret(), self.Fake())
        self.assertEqual(r["status"], "needs_data"); self.assertEqual(Pipeline.Fake.called, 0)
    def test_invented_claim_is_flagged(self):
        r = run_research(self.P, kb_with(sv()), self.Ret(), self.Fake())
        self.assertEqual(r["status"], "insufficient_basis")
        self.assertEqual([c["verified"] for c in r["claims"]], [True, False])
    def test_missing_rules(self):
        self.assertTrue(any(m["field"] == "CN / TARIC code" for m in missing_data(dict(self.P, cn="9405"))))

if __name__ == "__main__":
    unittest.main()
