"""End-to-end coverage for the en-US phrasings people actually use.

Each row asserts the spoken effect -- the letters -- rather than the intent
name, so a phrasing that routes but swallows part of the sentence into
{word} ("can you spell banana for me" spelling "banana for me") fails here.
"""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"
LANG = "en-US"

BANANA = "B; A; N; A; N; A"

PHRASINGS = [
    "spell banana",
    "spell out banana",
    "spell the word banana",
    "how do you spell banana",
    "how would i spell banana",
    "how is banana spelled",
    "what is the spelling of banana",
    "what's the spelling of banana",
    "give me the spelling of banana",
    "spelling of banana",
    "can you spell banana",
    "can you spell banana for me",
    "spell banana letter by letter",
    "how do you spell banana letter by letter",
]

# proofreading, definitions and witchcraft: they share the word "spell" with
# every training sample and mean something else entirely
NOT_SPELLING = [
    "spell check my essay",
    "spellcheck my document",
    "run a spell checker on this",
    "what does spell mean",
    "cast a spell",
]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_prototype_minicroft([SKILL_ID], lang=LANG)
    yield mc
    mc.stop()


def _run(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, eof_msgs=["ovos.utterance.handled",
                                           "complete_intent_failure"])
    capture.capture(utterance, timeout=30)
    return capture.finish()


@pytest.mark.timeout(90)
@pytest.mark.parametrize("utterance", PHRASINGS)
def test_phrasing_spells_the_word(minicroft, utterance):
    messages = _run(minicroft, utterance, f"say-{utterance}")
    TALLY.assert_routed(utterance, f"{SKILL_ID}:spell", [m.msg_type for m in messages])
    spoken = [m.data["utterance"] for m in messages
              if m.msg_type == "ovos.utterance.speak"]
    assert spoken == [BANANA], f"{utterance!r} spelled {spoken!r}"


@pytest.mark.timeout(90)
@pytest.mark.parametrize("utterance", NOT_SPELLING)
def test_confusable_is_not_claimed(minicroft, utterance):
    types = [m.msg_type for m in _run(minicroft, utterance, f"no-{utterance}")]
    TALLY.assert_not_routed(utterance, [f"{SKILL_ID}:spell"], types)
