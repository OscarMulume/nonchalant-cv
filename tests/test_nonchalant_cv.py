import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nonchalant_cv as nc  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


class KeywordTests(unittest.TestCase):
    def test_accents_and_case_are_ignored(self):
        self.assertTrue(nc.contains_term(nc.normalize("Gestion des Réseaux"), "reseaux"))

    def test_whole_words_only(self):
        norm = nc.normalize("I like javascript")
        self.assertFalse(nc.contains_term(norm, "java"))
        self.assertTrue(nc.contains_term(norm, "javascript"))

    def test_symbols_in_terms(self):
        norm = nc.normalize("Strong TCP/IP and Node.js, CI/CD")
        for t in ("tcp/ip", "node.js", "ci/cd"):
            self.assertTrue(nc.contains_term(norm, t), t)

    def test_plural_matches_singular(self):
        self.assertTrue(nc.contains_term(nc.normalize("VLANs and VPNs"), "vlan"))
        self.assertTrue(nc.contains_term(nc.normalize("VLANs and VPNs"), "VPN"))

    def test_compare_dedupes_and_scores(self):
        m = nc.compare(["VLAN", "vlan", "Fortinet", "DNS"], "VLAN and DNS")
        self.assertEqual(m.matched, ["VLAN", "DNS"])
        self.assertEqual(m.missing, ["Fortinet"])
        self.assertEqual(m.score, 67)


class FakeChat:
    """Stands in for Ollama so the tests run without a model."""

    def __init__(self, bullet="Administered the network of three hotels with Cisco switches and VLANs.",
                 letter="Dear Hiring Manager,\nI run networks.\nBest regards,\nAmani Kabila"):
        self.calls, self.bullet, self.letter = [], bullet, letter

    def __call__(self, system, user, as_json):
        self.calls.append(as_json)
        if as_json:
            return json.dumps({
                "job_title": "Network Engineer",
                "skills": ["TCP/IP", "VLANs", "Fortinet", "ITIL", "DHCP", "tests de santé réseau"],
                "certifications": ["CCNA"], "years_experience": "3+ years",
            })
        return self.letter if "cover letter" in system else self.bullet


class HelperTests(unittest.TestCase):
    def test_language_detection(self):
        self.assertEqual(nc.detect_language("Nous recherchons un ingénieur avec 3 ans d'expérience pour le poste"), "fr")
        self.assertEqual(nc.detect_language("We are looking for an engineer with 3 years of experience"), "en")

    def test_candidate_name_and_bullets(self):
        cv = (SAMPLES / "cv.txt").read_text(encoding="utf-8")
        self.assertEqual(nc.candidate_name(cv), "Amani Kabila")
        self.assertEqual(len(nc.cv_bullets(cv)), 5)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.cv = (SAMPLES / "cv.txt").read_text(encoding="utf-8")
        self.offer = (SAMPLES / "offer.txt").read_text(encoding="utf-8")

    def missing_section(self, report):
        return report.split("## Keywords missing from your CV")[1].split("##")[0]

    def test_no_ai_report(self):
        report = nc.run(self.cv, self.offer, chat=None)
        self.assertIn("ATS keyword match", report)
        self.assertIn("fortinet", report)
        self.assertNotIn("Cover letter draft", report)

    def test_full_run_with_fake_model(self):
        chat = FakeChat()
        report = nc.run(self.cv, self.offer, chat=chat)
        self.assertEqual(chat.calls, [True, False, False, False, False])  # extract, 3 bullets, letter
        self.assertIn("**Offer:** Network Engineer", report)
        self.assertIn("Cover letter draft", report)
        missing = self.missing_section(report)
        self.assertIn("Fortinet", missing)
        self.assertNotIn("DHCP", missing)
        self.assertNotIn("Check before sending", report)

    def test_keywords_not_in_offer_are_dropped(self):
        report = nc.run(self.cv, self.offer, chat=FakeChat())
        self.assertNotIn("tests de santé réseau", report)

    def test_invented_tool_in_bullet_falls_back_to_original(self):
        chat = FakeChat(bullet="Managed Fortinet firewalls for three hotels.")
        report = nc.run(self.cv, self.offer, chat=chat)
        self.assertNotIn("Managed Fortinet firewalls", report)
        self.assertIn("kept as is", report)

    def test_letter_claiming_missing_skill_is_flagged(self):
        chat = FakeChat(letter="Dear Hiring Manager,\nI know Fortinet and [Your Name].\nAmani Kabila")
        report = nc.run(self.cv, self.offer, chat=chat)
        self.assertIn("The letter mentions Fortinet", report)
        self.assertIn("[placeholder]", report)

    def test_bad_json_from_model_does_not_crash(self):
        report = nc.run(self.cv, self.offer, chat=lambda s, u, j: "not json" if j else "")
        self.assertIn("ATS keyword match", report)


if __name__ == "__main__":
    unittest.main()
