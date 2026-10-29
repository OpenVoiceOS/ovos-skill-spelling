"""End-to-end coverage for the re-prompt when {word} is unresolved.

"how do you spell it" routes to Spell.intent with the pronoun excluded from
the {word} slot (word.blacklist, OVOS-INTENT-2 §4.3). The skill must then ask
which word it should spell instead of spelling the pronoun or going silent.
"""
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"
LANG = "en-US"


def _dialog_lines(name):
    path = Path(__file__).parents[2] / "locale" / LANG / "dialog" / f"{name}.dialog"
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


PROMPTS = _dialog_lines("what_word")
GAVE_UP = _dialog_lines("no_word")


@pytest.fixture(scope="module")
def minicroft():
    mc = get_prototype_minicroft([SKILL_ID], lang=LANG)
    yield mc
    mc.stop()


def _spoken(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, eof_msgs=["ovos.utterance.handled"])
    capture.capture(utterance, timeout=60)
    messages = capture.finish()
    TALLY.assert_routed(text, f"{SKILL_ID}:spell", [m.msg_type for m in messages])
    return [m.data["utterance"] for m in messages
            if m.msg_type == "ovos.utterance.speak"]


@pytest.mark.timeout(120)
@pytest.mark.parametrize("utterance", ["how do you spell it",
                                       "spell that",
                                       "can you spell this"])
def test_unresolved_word_asks_which_word(minicroft, utterance):
    spoken = _spoken(minicroft, utterance, f"ask-{utterance}")
    assert spoken, f"{utterance!r}: the skill said nothing"
    assert spoken[0] in PROMPTS, (
        f"{utterance!r}: expected a prompt from what_word.dialog, got {spoken[0]!r}"
    )
    # unanswered here (nothing replies on a bare MiniCroft): one more ask,
    # then a short apology rather than silence or a spelled-out pronoun
    assert spoken[-1] in GAVE_UP, spoken
    assert sum(s in PROMPTS for s in spoken) == 2, spoken
