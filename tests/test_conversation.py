import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import africa  # noqa: E402
import app  # noqa: E402
import mosala  # noqa: E402


def echo_chat(prefix):
    """A fake model that tags its output, so tests can see which prompt produced it."""
    calls = []

    def chat(system, user, as_json):
        calls.append(system)
        return f"{prefix}:{user}"
    chat.calls = calls
    return chat


class CatalogueTests(unittest.TestCase):
    def test_every_african_country_is_listed_once(self):
        codes = [c for c, _, _, _ in africa.COUNTRIES]
        self.assertEqual(len(codes), 54)
        self.assertEqual(len(set(codes)), 54)

    def test_at_least_three_languages_per_country(self):
        for code, fr, _, langs in africa.COUNTRIES:
            if code not in africa.FEWER_THAN_THREE:
                self.assertGreaterEqual(len(langs), 3, fr)

    def test_every_language_is_known_to_mosala(self):
        for _, fr, _, langs in africa.COUNTRIES:
            for lang in langs:
                self.assertIn(lang, mosala.LANG_INFO, f"{lang} ({fr})")

    def test_new_languages_say_where_they_are_spoken(self):
        self.assertIn("Senegal", mosala.LANG_INFO["srr"]["where"])
        self.assertEqual(mosala.LANG_INFO["pcm"]["group"], "africa_more")


class InterpretTests(unittest.TestCase):
    def test_translation_names_both_languages(self):
        chat = echo_chat("T")
        out = mosala.interpret("Mbote, ozali malamu?", "ln", "sw", chat)
        self.assertEqual(out["text"], "T:Mbote, ozali malamu?")
        self.assertIn("Lingala", chat.calls[0])
        self.assertIn("Swahili", chat.calls[0])
        self.assertIsNone(out["back"])

    def test_back_translation_on_request(self):
        chat = echo_chat("T")
        out = mosala.interpret("Bonjour", "fr", "wo", chat, check=True)
        self.assertEqual(out["back"], "T:T:Bonjour")
        self.assertEqual(len(chat.calls), 2)

    def test_same_language_is_not_sent_to_the_model(self):
        out = mosala.interpret(" Habari ", "sw", "sw", None)
        self.assertEqual(out["text"], "Habari")

    def test_lost_numbers_are_flagged(self):
        out = mosala.interpret("Rendez-vous à 14 h, salle 3", "fr", "ln", lambda s, u, j: "Tokokutana na salle 3")
        self.assertEqual(out["missing_numbers"], ["14"])

    def test_talk_endpoint_reports_the_weaker_tier(self):
        out = app.handle_talk({"text": "Hello", "from": "en", "to": "kbp"}, echo_chat("T"))
        self.assertEqual(out["tier"], "experimental")
        self.assertEqual(app.handle_talk({"text": "", "from": "en", "to": "fr"}, None)["error"], "empty_talk")
        self.assertEqual(app.handle_talk({"text": "x", "from": "en", "to": "zz"}, None)["error"], "empty_talk")


class RoomTests(unittest.TestCase):
    def setUp(self):
        app.ROOMS.clear()

    def test_two_people_each_read_in_their_own_language(self):
        chat = echo_chat("T")
        a = app.handle_room_join({"name": "Oscar", "lang": "fr"}, chat)
        b = app.handle_room_join({"name": "Amina", "lang": "sw", "room": a["room"]}, chat)
        self.assertRegex(a["room"], r"^\d{4}$")
        app.handle_room_send({"room": a["room"], "pid": a["pid"], "text": "Bonjour Amina"}, chat)

        for_b = app.handle_room_poll({"room": a["room"], "pid": b["pid"], "since": 0}, chat)
        self.assertEqual(for_b["messages"][0]["text"], "T:Bonjour Amina")
        self.assertEqual(for_b["messages"][0]["original"], "Bonjour Amina")
        self.assertFalse(for_b["messages"][0]["mine"])
        self.assertEqual(len(for_b["people"]), 2)

        for_a = app.handle_room_poll({"room": a["room"], "pid": a["pid"], "since": 0}, chat)
        self.assertEqual(for_a["messages"][0]["text"], "Bonjour Amina")  # no translation for the sender
        self.assertTrue(for_a["messages"][0]["mine"])

        # A second poll from B gets nothing new, and the translation is not redone.
        calls = len(chat.calls)
        self.assertEqual(app.handle_room_poll({"room": a["room"], "pid": b["pid"], "since": 1}, chat)["messages"], [])
        app.handle_room_poll({"room": a["room"], "pid": b["pid"], "since": 0}, chat)
        self.assertEqual(len(chat.calls), calls)

    def test_wrong_code_or_person_is_refused(self):
        self.assertEqual(app.handle_room_join({"name": "X", "lang": "fr", "room": "0000"}, None)["error"], "no_room")
        a = app.handle_room_join({"name": "X", "lang": "fr"}, None)
        self.assertEqual(app.handle_room_send({"room": a["room"], "pid": "intruder", "text": "hi"}, None)["error"], "no_room")
        self.assertEqual(app.handle_room_join({"name": "X", "lang": "zz"}, None)["error"], "empty_room")

    def test_idle_rooms_expire(self):
        a = app.handle_room_join({"name": "X", "lang": "fr"}, None)
        app.ROOMS[a["room"]]["active"] -= app.ROOM_IDLE + 1
        app.handle_room_join({"name": "Y", "lang": "fr"}, None)  # any join cleans up
        self.assertNotIn(a["room"], app.ROOMS)


if __name__ == "__main__":
    unittest.main()
