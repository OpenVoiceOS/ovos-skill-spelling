"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to route
to the padatious ``Spell.intent`` handler. The spoken spelling is a side effect
that varies by backend and is ignored, so the assertion covers only the intent
binding.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"
LANG = "en-US"

_PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-medium",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "mycroft.audio.play_sound",
    "enclosure.mouth.text",
    "enclosure.mouth.reset",
    "enclosure.mouth.events.deactivate",
    "enclosure.mouth.events.activate",
]


class TestSpellingIntentsEnUS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _types(self, text: str) -> list[str]:
        session = Session(f"test-{hash(text)}")
        session.lang = LANG
        session.pipeline = list(_PIPELINE)
        # blacklisted_intents defaults to None, which crashes the padacioso
        # pipeline (NoneType membership test) - force an empty list.
        session.blacklisted_intents = []
        utterance = Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        # End capture when the handler starts: handle_spell speaks with wait=True,
        # which never resolves in a bare MiniCroft. The intent binding under test
        # is emitted first, so this bounds each case while capturing the assertion.
        capture = CaptureSession(
            self.minicroft,
            eof_msgs=["mycroft.skill.handler.start"],
            ignore_messages=_IGNORE,
        )
        capture.capture(utterance, timeout=30)
        return [m.msg_type for m in capture.finish()]

    def _assert_intent(self, text: str, intent: str):
        self.assertIn(f"{SKILL_ID}:{intent}", self._types(text))

    def test_how_do_you_spell(self):
        self._assert_intent("how do you spell cat", "Spell.intent")

    def test_spell_the_word(self):
        self._assert_intent("spell the word cat", "Spell.intent")

    def test_spelling_of(self):
        self._assert_intent("spelling of cat", "Spell.intent")


if __name__ == "__main__":
    unittest.main()
