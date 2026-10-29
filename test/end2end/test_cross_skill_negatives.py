"""Requests that belong to other skills reach no intent of the spelling skill.

Each ``cross_skill_<lang>.jsonl`` holds golden rows of other OpenVoiceOS
skills in that language, copied verbatim from their repository at the commit
named in each row's ``source_sha``.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope.routing import TALLY, get_prototype_minicroft

SKILL_ID = "skill-ovos-spelling.openvoiceos"
END2END_DIR = Path(__file__).parent
MIN_ROWS_PER_LOCALE = 30
MIN_SKILLS_PER_LOCALE = 8

ROWS = []
for _path in sorted(END2END_DIR.glob("cross_skill_*.jsonl")):
    ROWS += [json.loads(line) for line in _path.read_text(encoding="utf-8").splitlines()
             if line.strip()]
_booted = {}


@pytest.fixture(scope="module")
def engine_for():
    def engine(lang):
        if lang not in _booted:
            for minicroft in _booted.values():
                minicroft.stop()
            _booted.clear()
            _booted[lang] = get_prototype_minicroft([SKILL_ID], lang=lang)
        return _booted[lang].intents.pipeline_plugins["ovos-m2v-prototype-pipeline"]
    yield engine
    for minicroft in _booted.values():
        minicroft.stop()


@pytest.mark.parametrize("row", ROWS, ids=lambda row: f"{row['lang']}:{row['utterance']}")
def test_other_skills_row_reaches_no_spelling_intent(engine_for, row):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [row["utterance"]], "lang": row["lang"]}, {"lang": row["lang"]})
    match = engine_for(row["lang"]).match_low([row["utterance"]], row["lang"], message)
    fired = [match.match_type] if match else []
    TALLY.assert_not_routed(row["utterance"],
                            [t for t in fired if t.startswith(f"{SKILL_ID}:")], fired)


def test_every_shipping_locale_has_a_cross_skill_file():
    rows_by_lang = {}
    for path in sorted(END2END_DIR.glob("cross_skill_*.jsonl")):
        lang = path.stem.removeprefix("cross_skill_")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert all(row["lang"] == lang for row in rows), f"{path.name} holds a row of another lang"
        rows_by_lang[lang] = rows
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert set(rows_by_lang) == shipping, \
        f"cross_skill files {sorted(set(rows_by_lang) ^ shipping)} differ from shipping locales"
    for lang, rows in rows_by_lang.items():
        skills = {row["source_repo"] for row in rows}
        assert len(rows) >= MIN_ROWS_PER_LOCALE, f"[{lang}] {len(rows)} rows"
        assert len(skills) >= MIN_SKILLS_PER_LOCALE, f"[{lang}] rows from {len(skills)} skills"
        assert "ovos-skill-spelling" not in skills
        assert all(len(row["source_sha"]) == 40 for row in rows), f"[{lang}] row without a source sha"
