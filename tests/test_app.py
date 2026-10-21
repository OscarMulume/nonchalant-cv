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


class AlertAndNetworkTests(unittest.TestCase):
    def test_alert_endpoint(self):
        out = app.handle_alert({"message": "Réunion le 3 mai.", "langs": ["ln", "sw"]}, lambda s, u, j: "Likita mokolo 3 sanza ya mitano.")
        self.assertEqual(len(out["translations"]), 2)
        self.assertEqual(app.handle_alert({"message": "x", "langs": []}, None)["error"], "empty_alert")

    def test_cv_endpoint_returns_titles(self):
        out = app.handle_cv({"story": "Nazali électricien mibu motoba", "to": "fr"}, fake_chat)
        self.assertTrue(any(t["fr"] == "Électricien du bâtiment" for t in out["titles"]))

    def test_lan_address_is_an_ip(self):
        self.assertRegex(app.lan_address(), r"^\d+\.\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
