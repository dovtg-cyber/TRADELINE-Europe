import unittest
from app import registry as R

class Registry(unittest.TestCase):
    def setUp(self): self.e = R.load()
    def test_registry_is_valid(self): self.assertEqual(R.validate(self.e), [])
    def test_official_urls_allowed(self):
        for u in ("https://eur-lex.europa.eu/eli/reg/2026/382/oj", "https://api.sejm.gov.pl/eli/acts/DU/2020/1", "https://eli.gov.pl/eli/DU/2020/1/ogl"):
            self.assertTrue(R.evidence_allowed_for_url(u, self.e), u)
    def test_secondary_and_lookalike_urls_rejected(self):
        for u in ("https://mondaq.com/x", "https://eur-lex.europa.eu.evil.example/x", "http://eur-lex.europa.eu/x", "https://notapi.sejm.gov.pl.evil/x", "ftp://eur-lex.europa.eu/x", ""):
            self.assertFalse(R.evidence_allowed_for_url(u, self.e), u)
    def test_manual_only_source_is_not_evidence(self):
        self.assertFalse(R.evidence_allowed_for_url("https://ec.europa.eu/taxation_customs/dds2/taric", self.e))
    def test_validator_catches_bad_entries(self):
        bad = [dict(self.e[0], id="x", tier=3, authenticity="secondary", evidence_allowed=True), dict(self.e[0], id="y", verified={"status": "to_verify"})]
        errs = R.validate(bad); self.assertTrue(any("tier 3" in x for x in errs)); self.assertTrue(any("unverified" in x for x in errs))
    def test_every_entry_records_when_it_was_checked(self):
        for x in self.e: self.assertTrue(x["verified"]["on"])
