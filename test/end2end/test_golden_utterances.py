"""Golden-utterance end-to-end coverage for ovos-skill-spelling (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-spelling.openvoiceos"``. One shared ``MiniCroft``
(module-scoped fixture) is booted for the whole suite; every row is its own
parametrized test item.

Runtime note: the corpus keys rows by the PyPI/repo-derived skill_id
(``ovos-skill-spelling.openvoiceos``), but the skill's actual OPM entry point
-- and therefore the routed message prefix -- is
``skill-ovos-spelling.openvoiceos`` (see ``pyproject.toml``'s
``[project.entry-points."opm.skill"]`` and ``test_intents_en_us.py``). This
suite asserts against the runtime id, not the corpus label.
"""
import json
import re
from pathlib import Path

import pytest
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

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# utterances lifted verbatim from OTHER skills' golden-utterance slices in
# the shared ovoscope corpus, picked for lexical overlap with spelling's
# "word"/"tell me"/"ask ... about" vocabulary.
NEGATIVE_UTTERANCES = [
    ("can you tell me the weather", "ovos-skill-weather.openvoiceos"),
    ("can you tell jokes", "ovos-skill-icanhazdadjokes.openvoiceos"),
    ("can you find something on wikipedia", "ovos-skill-wikipedia.openvoiceos"),
    ("ask wordnet about word", "ovos-skill-wordnet.openvoiceos"),
    ("tell me the word of the day", "ovos-skill-word-of-the-day.openvoiceos"),
    ("search wikihow for something", "ovos-skill-wikihow.openvoiceos"),
    ("set an alarm", "ovos-skill-alerts.openvoiceos"),
]

# Real, CI-reproduced collision: en-US/Spell.intent's padatious training data
# uses the literal word "word" as fixed vocabulary in several lines (eg.
# "spell word {word}", "spelling of the word {word}"), not only as the slot
# name. That gives padatious's fuzzy matcher enough token overlap to loosely
# claim "tell me the word of the day" (it shares "tell", "me", "the", "word",
# "of" with several Spell.intent training lines). This reproduces on the
# CI-pinned padatious build (see PR CI run) but NOT in this dev environment,
# where ovos-padatious can't be built (missing libfann-dev, no sudo) and the
# medium-priority padacioso pipeline -- a stricter, non-fuzzy matcher --
# handles the utterance instead and correctly rejects it. Rather than pick a
# different negative and hide a real cross-skill leak, or blind-edit
# Spell.intent's templates without a way to locally verify the fix against
# padatious, this is tracked as a strict xfail: a row that stops reproducing
# (env gets padatious, and it no longer collides) must fail the build.
_NEGATIVE_XFAIL_REASONS = {
    "tell me the word of the day": (
        "padatious fuzzy-matches this to Spell.intent via token overlap on "
        "the literal 'word' vocabulary shared by several training lines "
        "(see ovos-skill-word-of-the-day.openvoiceos golden-utterance "
        "corpus row); reproduces under CI-pinned padatious, not under the "
        "padacioso fallback used in this dev venv (no libfann-dev locally)."
    ),
}


try:
    import ovos_padatious  # noqa: F401
    _PADATIOUS_INSTALLED = True
except ImportError:
    _PADATIOUS_INSTALLED = False


def _as_negative_param(negative):
    text, _source_skill = negative
    reason = _NEGATIVE_XFAIL_REASONS.get(text)
    # the collision only reproduces when ovos-padatious's fuzzy matcher is
    # actually in the pipeline (see _NEGATIVE_XFAIL_REASONS docstring above);
    # without it, padacioso handles the utterance and correctly rejects it,
    # so the xfail must not be applied or this would XPASS-fail locally.
    if reason is None or not _PADATIOUS_INSTALLED:
        return pytest.param(negative, id=text)
    return pytest.param(negative, id=text, marks=pytest.mark.xfail(reason=reason, strict=True))


NEGATIVE_PARAMS = [_as_negative_param(n) for n in NEGATIVE_UTTERANCES]


def _matches_intent(msg_type: str, skill_id: str, intent_file: str) -> bool:
    """Same tolerant matcher as ``test_intents_en_us.py``: compare the
    ``:``-suffix basename, extension-stripped and case/punct-insensitive, so
    the assertion doesn't pin the wire format of any one pipeline plugin."""
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed.rsplit(".", 1)[0] if observed.endswith(".intent") else observed
    expected_base = intent_file.rsplit(".", 1)[0] if intent_file.endswith(".intent") else intent_file
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return norm(observed_base) == norm(expected_base)


# Rows that do not currently route correctly, with the root-caused reason.
# Every reason below must be confirmed by isolated investigation before being
# accepted as a real, out-of-scope defect rather than a corpus mistake. All
# xfails are ``strict=True``: a row that starts passing must fail the build.
_XFAIL_REASONS = {}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


def _as_param(row):
    reason = _XFAIL_REASONS.get(row["utterance"])
    if reason is None:
        return pytest.param(row, id=row["utterance"])
    return pytest.param(
        row,
        id=row["utterance"],
        marks=pytest.mark.xfail(reason=reason, strict=True),
    )


GOLDEN_ROWS = [_as_param(r) for r in _load_golden_rows()]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()


def _types(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(_PIPELINE)
    # blacklisted_intents defaults to None on a fresh Session, which crashes
    # the padacioso pipeline (NoneType membership test) - force an empty list.
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    # End capture when the handler starts: handle_spell speaks with wait=True,
    # which never resolves on a bare MiniCroft. The intent binding under test
    # is emitted first, so this bounds each case while capturing the
    # assertion (same mechanism as test_intents_en_us.py).
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


def _golden_id(row):
    return row["utterance"]


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    types = _types(minicroft, row["utterance"], f"golden-{_golden_id(row)}")
    assert any(_matches_intent(t, SKILL_ID, row["intent_label"]) for t in types), (
        f"{row['utterance']!r}: expected {SKILL_ID}:{row['intent_label']}, got {types!r}"
    )


@pytest.mark.timeout(60)
@pytest.mark.parametrize("negative", NEGATIVE_PARAMS)
def test_negative_confusable_not_claimed(minicroft, negative):
    text, source_skill = negative
    types = _types(minicroft, text, f"negative-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"
