import unittest
from datetime import date
from app.verification import SourceVersion, sha256_text
from app.timemachine import act_status, entry_into_force_default, APPLICABLE, IN_FORCE_NOT_APPLICABLE, PUBLISHED_NOT_IN_FORCE, CEASED, BOUNDARY_CHECK, NOT_YET_PUBLISHED, UNKNOWN

T = "Article 2. From 1 July 2026 until 1 July 2028 a customs duty of EUR 3 per item shall apply."
def reg_2026_382():
    # Real act: Council Regulation (EU) 2026/382 of 11 Feb 2026, OJ L 18.2.2026 (EUR-Lex page read on 2026-11-16).
    # Entry into force: 'twentieth day following publication' = computed value; applies from 1 July 2026; 'until 1 July 2028'.
    pub = date(2026, 2, 18)
    return SourceVersion(source_id="eurlex:32026R0382", doc_id="eurlex:32026R0382", title="Council Regulation (EU) 2026/382", jurisdiction="EU",
        publisher="EUR-Lex", url="https://eur-lex.europa.eu/eli/reg/2026/382/oj", version_from=pub, version_to=None, text=T, sha256=sha256_text(T),
        retrieved=date(2026, 11, 16), adopted_on=date(2026, 2, 11), published_on=pub, entered_into_force=entry_into_force_default(pub),
        applies_from=date(2026, 7, 1), ceases_on=date(2028, 7, 1))

class TimeMachine(unittest.TestCase):
    def test_default_entry_into_force_is_computed(self):
        self.assertEqual(entry_into_force_default(date(2026, 2, 18)), date(2026, 3, 10))
    def test_five_dates_kept_apart(self):
        v = [reg_2026_382()]
        self.assertEqual(act_status(v, date(2026, 1, 1)).state, NOT_YET_PUBLISHED)
        self.assertEqual(act_status(v, date(2026, 2, 20)).state, PUBLISHED_NOT_IN_FORCE)
        self.assertEqual(act_status(v, date(2026, 3, 15)).state, IN_FORCE_NOT_APPLICABLE)   # in force but not yet applicable
        self.assertEqual(act_status(v, date(2026, 7, 1)).state, APPLICABLE)
        self.assertEqual(act_status(v, date(2027, 6, 30)).state, APPLICABLE)
    def test_before_publication(self):
        self.assertEqual(act_status([reg_2026_382()], date(2026, 2, 1)).state, NOT_YET_PUBLISHED)
    def test_sunset_boundary_needs_human(self):
        s = act_status([reg_2026_382()], date(2028, 7, 1))
        self.assertEqual(s.state, BOUNDARY_CHECK); self.assertFalse(s.relied_on); self.assertTrue(any("sunset_date_boundary" in w for w in s.warnings))
    def test_after_sunset(self):
        self.assertEqual(act_status([reg_2026_382()], date(2028, 7, 2)).state, CEASED)
    def test_not_applicable_blocks_verified_claim(self):
        from app.verification import KnowledgeBase, verify_claim
        kb = KnowledgeBase(); kb.add(reg_2026_382())
        c = {"kind": "mandatory", "text": "EUR 3 per item.", "source_id": "eurlex:32026R0382", "quote": "a customs duty of EUR 3 per item shall apply"}
        self.assertTrue(verify_claim(c, kb, date(2026, 8, 1))["verified"])
        r = verify_claim(c, kb, date(2026, 5, 1)); self.assertFalse(r["verified"]); self.assertIn("not_applicable_on_date", r["reasons"])
        r2 = verify_claim(c, kb, date(2028, 8, 1)); self.assertFalse(r2["verified"])
    def test_unknown_dates_give_warnings_not_guesses(self):
        v = reg_2026_382(); v.entered_into_force = None; v.published_on = None
        s = act_status([v], date(2026, 8, 1)); self.assertIn("entry_into_force_unknown", s.warnings)
    def test_no_versions(self):
        self.assertEqual(act_status([], date(2026, 1, 1)).state, UNKNOWN)
    def test_consolidated_gets_warning(self):
        from app.verification import KnowledgeBase, verify_report
        v = reg_2026_382(); v.authenticity = "consolidated"; kb = KnowledgeBase(); kb.add(v)
        rep = verify_report({"claims": [{"kind": "mandatory", "text": "x", "source_id": v.source_id, "quote": "a customs duty of EUR 3 per item shall apply"}]}, kb, date(2026, 8, 1))
        self.assertEqual(rep["status"], "verified"); self.assertTrue(any("consolidated" in l for l in rep["limits"]))
