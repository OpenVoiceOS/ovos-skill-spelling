"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to
route to the ``spell.intent`` handler. The spoken spelling is ignored, so the
assertion covers only the intent binding and the slot.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"
LANG = "en-US"


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
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang=LANG)

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _messages(self, text: str):
        session = Session(f"test-{hash(text)}")
        session.lang = LANG
        session.pipeline = list(PIPELINE)
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
        return capture.finish()

    def _assert_intent(self, text: str, intent: str):
        types = [m.msg_type for m in self._messages(text)]
        TALLY.assert_routed(text, f"{SKILL_ID}:{intent.removesuffix('.intent')}", types)

    def test_how_do_you_spell(self):
        self._assert_intent("how do you spell cat", "spell.intent")

    def test_spell_the_word(self):
        self._assert_intent("spell the word cat", "spell.intent")

    def test_spelling_of(self):
        self._assert_intent("spelling of cat", "spell.intent")

    def test_can_you_what_is_the_spelling_of(self):
        # golden_utterances.jsonl row 5
        self._assert_intent("can you what is the spelling of word", "spell.intent")

    def _assert_word_slot_unresolved(self, text: str):
        # OVOS-INTENT-2 §4.3: a pronoun bound to {word} must be excluded by
        # word.blacklist, leaving the slot unresolved instead of binding the
        # pronoun literally.
        messages = self._messages(text)
        TALLY.assert_routed(text, f"{SKILL_ID}:spell", [m.msg_type for m in messages])
        matched = [m for m in messages if m.msg_type == f"{SKILL_ID}:spell"]
        self.assertFalse(
            matched[0].data.get("word"),
            f"pronoun bound to unresolved {{word}} slot: {matched[0].data}",
        )

    def test_pronoun_it_is_blacklisted(self):
        self._assert_word_slot_unresolved("how do you spell it")

    def test_pronoun_that_is_blacklisted(self):
        self._assert_word_slot_unresolved("spell that")

    def test_pronoun_this_is_blacklisted(self):
        self._assert_word_slot_unresolved("can you spell this")

    def test_pronoun_them_is_blacklisted(self):
        self._assert_word_slot_unresolved("can you spell them")


if __name__ == "__main__":
    unittest.main()
