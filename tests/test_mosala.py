import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mosala  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[1] / "samples"

PROFILE = {"spoken_language": "Lingala", "trade": "Electrician",
           "experiences": [{"role": "Electrician", "place": "Construction company", "period": "3 years",
                            "tasks": ["house wiring", "solar panels"]}],
           "skills": ["house wiring"], "tools": ["circuit breakers"], "languages": ["Lingala", "French"],
           "education": []}

CV_FR = {"title": "Électricien", "summary": "Électricien avec 6 ans d'expérience à Kinshasa.",
         "experiences": [{"role": "Électricien", "place": "Entreprise de construction", "period": "3 ans",
                          "bullets": ["Installé des panneaux solaires dans plus de 50 maisons.",
                                      "Géré une équipe de 12 techniciens."]}],
         "skills": ["Installation électrique"], "tools": ["Disjoncteurs"],
         "languages": ["Lingala", "Français"], "education": []}


def fake_chat(system, user, as_json):
    if "possibly in Lingala" in system:
        return json.dumps(PROFILE)
    if "professional CV content" in system:
        return json.dumps(CV_FR)
    return "Mosala oyo ezali ya électricien na Kinshasa."


class NumberGuardTests(unittest.TestCase):
    def test_numbers_said_in_digits_and_words(self):
        story = (SAMPLES / "story_ln.txt").read_text(encoding="utf-8")
        said = mosala.numbers_said(story)
        self.assertTrue({"6", "3", "50"} <= said)
        self.assertNotIn("12", said)


class CvTests(unittest.TestCase):
    def setUp(self):
        self.story = (SAMPLES / "story_ln.txt").read_text(encoding="utf-8")

    def test_cv_in_french_with_hand_written_titles(self):
        md, profile, warnings = mosala.make_cv(self.story, "fr", {"name": "Jean Mbuyi", "city": "Kinshasa"}, fake_chat)
        self.assertIn("# Jean Mbuyi", md)
        self.assertIn("## Expérience professionnelle", md)
        self.assertIn("plus de 50 maisons", md)
        self.assertEqual(profile["trade"], "Electrician")

    def test_invented_number_is_removed_and_reported(self):
        md, _, warnings = mosala.make_cv(self.story, "fr", {"name": "Jean Mbuyi"}, fake_chat)
        self.assertNotIn("12 techniciens", md)
        self.assertTrue(any("12" in w for w in warnings))

    def test_broken_model_output_gives_a_warning_not_a_crash(self):
        md, _, warnings = mosala.make_cv(self.story, "en", {"name": "X"}, lambda s, u, j: "oops")
        self.assertIn("# X", md)
        self.assertTrue(warnings)

    def test_html_is_printable_and_escaped(self):
        page = mosala.render_html("# A <b>\n## Skills\n- one\n- two", "A")
        self.assertIn("<ul><li>one</li><li>two</li></ul>", page)
        self.assertIn("&lt;b&gt;", page)


class OfferTests(unittest.TestCase):
    def test_offer_in_lingala_has_a_review_note(self):
        argv = ["offer", "--offer", str(SAMPLES / "offer.txt"), "--lang", "ln", "--out", "/tmp/mosala_offer.md"]
        original = mosala.core.ollama_chat
        mosala.core.ollama_chat = lambda model, s, u, j: fake_chat(s, u, j)
        try:
            self.assertEqual(mosala.main(argv), 0)
        finally:
            mosala.core.ollama_chat = original
        text = Path("/tmp/mosala_offer.md").read_text(encoding="utf-8")
        self.assertIn("# Lingala", text)
        self.assertIn("Machine translation", text)


if __name__ == "__main__":
    unittest.main()
