"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to route
to the padacioso ``spell.intent`` handler. The spoken spelling is a side effect
that varies by backend and is ignored, so the assertion covers only the intent
binding.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"
LANG = "en-US"


def _matches_intent(msg_type: str, skill_id: str, intent_file: str) -> bool:
    """Exact match on the base name the skill registers.

    The runtime emits ``<skill_id>:<basename>`` with the basename spelled as
    the file is; a comparison that folded case let ``Spell.intent`` or
    ``sPeLl`` pass against a shipped ``spell.intent``. A caller must name the
    file exactly, or a routing bug to the wrong case ships undetected.
    """
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed[:-len(".intent")] if observed.endswith(".intent") else observed
    expected_base = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
    return observed_base == expected_base

_PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
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


class TestMatchesIntentExact(unittest.TestCase):
    def test_pascal_case_does_not_match_lower_case(self):
        self.assertFalse(
            _matches_intent("skill-ovos-spelling.openvoiceos:Spell.intent",
                             SKILL_ID, "spell.intent")
        )

    def test_mixed_case_basename_does_not_match(self):
        self.assertFalse(
            _matches_intent("skill-ovos-spelling.openvoiceos:sPeLl",
                             SKILL_ID, "spell.intent")
        )

    def test_exact_match_still_matches(self):
        self.assertTrue(
            _matches_intent("skill-ovos-spelling.openvoiceos:spell.intent",
                             SKILL_ID, "spell.intent")
        )


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
        types = self._types(text)
        self.assertTrue(
            any(_matches_intent(t, SKILL_ID, intent) for t in types),
            f"no message routed to {SKILL_ID}:{intent} ({types})",
        )

    def test_how_do_you_spell(self):
        self._assert_intent("how do you spell cat", "spell.intent")

    def test_spell_the_word(self):
        self._assert_intent("spell the word cat", "spell.intent")

    def test_spelling_of(self):
        self._assert_intent("spelling of cat", "spell.intent")

    def test_can_you_what_is_the_spelling_of(self):
        # golden_utterances.jsonl row 5; padacioso rejected this phrasing
        # once "can you" stopped alternating in front of "what is the
        # spelling of {word}" (regression fix).
        self._assert_intent("can you what is the spelling of word", "spell.intent")

    def _assert_word_slot_unresolved(self, text: str):
        # OVOS-INTENT-2 §4.3: a pronoun bound to {word} must be excluded by
        # word.blacklist, leaving the slot unresolved instead of binding the
        # pronoun literally.
        session = Session(f"test-{hash(text)}")
        session.lang = LANG
        session.pipeline = list(_PIPELINE)
        session.blacklisted_intents = []
        utterance = Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(
            self.minicroft,
            eof_msgs=["mycroft.skill.handler.start"],
            ignore_messages=_IGNORE,
        )
        capture.capture(utterance, timeout=30)
        messages = capture.finish()
        matched = [
            m for m in messages
            if _matches_intent(m.msg_type, SKILL_ID, "spell.intent")
        ]
        self.assertTrue(matched, f"no message routed to {SKILL_ID}:spell.intent")
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
