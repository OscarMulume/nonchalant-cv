import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app  # noqa: E402
from test_mosala import fake_chat  # noqa: E402


class AppTests(unittest.TestCase):
    def test_cv_endpoint_returns_markdown_html_and_warnings(self):
        out = app.handle_cv({"story": "Nazali électricien mibu motoba", "name": "Jean", "to": "fr"}, fake_chat)
        self.assertIn("# Jean", out["markdown"])
        self.assertIn("<h1>Jean</h1>", out["html"])
        self.assertIsInstance(out["warnings"], list)

    def test_empty_inputs_are_rejected(self):
        self.assertEqual(app.handle_cv({"story": "  "}, fake_chat)["error"], "empty_story")
        self.assertEqual(app.handle_offer({}, fake_chat)["error"], "empty_offer")
        self.assertEqual(app.handle_match({"cv": "x"}, fake_chat)["error"], "empty_match")

    def test_unknown_languages_fall_back_safely(self):
        out = app.handle_offer({"offer": "Network Engineer, Cisco, VLAN", "lang": "xx"}, fake_chat)
        self.assertTrue(out["local"])  # falls back to Lingala
        self.assertIn("cisco", out["keywords"])


if __name__ == "__main__":
    unittest.main()
