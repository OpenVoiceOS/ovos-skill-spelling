"""Multilingual golden-utterance end-to-end coverage for ovos-skill-spelling.

The skill has exactly one intent (spell.intent). Every locale that ships a
spell.intent file gets its own golden_utterances_<lang>.jsonl, one row per
locale expanded directly from that locale's own .intent template lines
(optionals/alternations resolved), with the {word} slot filled by an
obvious loanword. kab ships only a word.entity (no .intent file) and has no
rows -- see the gap note in the PR body.

One MiniCroft is booted per locale in turn (lang=<locale>, no
secondary_langs -- see ovos-skill-date-time/test/end2end/test_intents_it_it.py
on dev), mirroring test_golden_utterances.py's padacioso-only pipeline (this
skill's intent is a plain .intent file, no Adapt fallback). Each locale's
MiniCroft is created on first use and stopped at module teardown.
"""
import json
import re
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"

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

END2END_DIR = Path(__file__).parent

LANGS = [
    "ca-ES", "da-DK", "de-DE", "es-ES", "eu-ES", "fr-FR", "gl-ES",
    "it-IT", "nl-NL", "oc-FR", "pt-BR", "pt-PT", "sv-SE",
]


def _matches_intent(msg_type: str, skill_id: str, intent_file: str) -> bool:
    """Exact match on the base name the skill registers.

    The runtime emits ``<skill_id>:<basename>`` with the basename spelled as
    the file is; a comparison that folded case let 50 rows read
    ``Spell.intent`` against a shipped ``spell.intent`` and pass. A row
    must name the file exactly, or the census that trains a corpus from
    these rows trains a label no skill registers.
    """
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed[:-len(".intent")] if observed.endswith(".intent") else observed
    expected_base = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
    return observed_base == expected_base


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


ALL_ROWS = []
for _lang in LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)


def _as_param(row):
    tag = "tier2" if row.get("machine_generated") else "tier1"
    return pytest.param(row, id=f"{row['lang']}-{tag}-{row['intent_label']}-{row['utterance']}")


GOLDEN_ROWS = [_as_param(r) for r in ALL_ROWS]


_BOOTED = {}


@pytest.fixture(scope="module")
def mc_factory(request):
    def _get(lang):
        if lang not in _BOOTED:
            mc = get_minicroft([SKILL_ID], max_wait=150, lang=lang)
            _BOOTED[lang] = mc
            request.addfinalizer(mc.stop)
        return _BOOTED[lang]
    return _get


def _types(mc, text, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(_PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


def _golden_id(row):
    return f"{row['lang']}-{row['intent_label']}-{row['utterance']}"


KNOWN_BUGS = {}


@pytest.mark.timeout(120)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance_multilang(mc_factory, row):
    mc = mc_factory(row["lang"])
    types = _types(mc, row["utterance"], row["lang"], f"golden-{_golden_id(row)}")
    assert row["skill_id"] == SKILL_ID, (
        f"{row['utterance']!r}: skill_id {row['skill_id']!r} is not the entry point {SKILL_ID!r}")
    matched = any(_matches_intent(t, SKILL_ID, row["intent_label"]) for t in types)
    bug_key = (row["lang"], row["utterance"])
    if bug_key in KNOWN_BUGS and not matched:
        pytest.xfail(reason=f"known-bug: {KNOWN_BUGS[bug_key]}")
    assert matched, (
        f"[{row['lang']}] {row['utterance']!r}: expected {SKILL_ID}:{row['intent_label']}, got {types!r}"
    )
