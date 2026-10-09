"""Requests that belong to other skills never route to the spelling skill.

Each ``cross_skill_<lang>.jsonl`` in this directory holds golden rows of other
OpenVoiceOS skills in that language, copied verbatim from their
``test/end2end/golden_utterances_<lang>.jsonl`` at the commit named in each
row's ``source_sha``. They are pinned here so the test does not depend on the
network or on another repository's later edits.

For each locale, one MiniCroft loads this skill alone on the m2v prototype
pipeline, the engine built at boot from the skill's own ``.intent``,
``.entity`` and ``.blacklist`` files. Each row goes through the high, medium
and low tiers in order, and the row fails when the first tier that matches
names a spelling intent. With no other skill loaded nothing competes for the
row, so this is stricter than a full install: a row passes only when no
spelling template is close to it.

A claim that m2v makes in every measured run is listed by name in
``CROSS_SKILL_KNOWN_CLAIMS`` and tolerated; any other claim fails the locale.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "skill-ovos-spelling.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
END2END_DIR = Path(__file__).parent
MIN_ROWS_PER_LOCALE = 30
MIN_SKILLS_PER_LOCALE = 8

# Rows of other skills that m2v gave to spell in both of two measured runs,
# with the skill each row belongs to. A listed claim is allowed, not required:
# the row may also match nothing. Two kinds are listed. A word-of-the-day
# follow-up such as "spell it" is a spelling request by meaning; that skill
# answers it only while its own context is active. The fa-IR, kab, pl-PL and
# ru-RU rows are requests that the published m2v model places near the
# spelling templates when no other skill is loaded; with every OpenVoiceOS
# skill loaded, none of them routes to spell.
CROSS_SKILL_KNOWN_CLAIMS = {
    'de-DE': {
        'buchstabiere das',  # ovos-skill-word-of-the-day
    },
    'en-US': {
        'spell it out for me',  # ovos-skill-word-of-the-day
    },
    'fa-IR': {
        'آخر آی پی من چه عددی هست',  # ovos-skill-ip
        'آخر هفته\u200cی پیش چه روزهایی بود؟',  # ovos-skill-date-time
        'آفوریسم کنفسیوس',  # ovos-skill-confucius-quotes
        'از وردنت درباره مترادف بپرس',  # ovos-skill-wordnet
        'الان به کدوم وای فای وصلی',  # ovos-skill-ip
        'امروز چه روز خاصی است',  # ovos-skill-number-facts
        'ایستگاه فضایی امشب چه ساعتی از بالای ما عبور می\u200cکند',  # ovos-skill-iss-location
        'باد آنقدر شدید است که باید وسایل حیاط را محکم ببندم؟',  # ovos-skill-weather
        'به من بگویید درباره یوگا در ویکیپدیا',  # ovos-skill-wikipedia
        'به نظرت هوا بیرون خیلی داغ است؟',  # ovos-skill-weather
        'به ولفرام بگو ارتفاع اورست',  # ovos-skill-wolfie
        'تایپ صوتی را متوقف کن',  # ovos-skill-dictation
        'حالت طوطی رو فعال کن',  # ovos-skill-parrot
        'در وردنت متضاد را جستجو کن',  # ovos-skill-wordnet
        'درباره کنفسیوس بگویید',  # ovos-skill-confucius-quotes
        'دیکته را تمام کن',  # ovos-skill-dictation
        'رنگ کد هگز ff5733 را بگو',  # ovos-skill-color-picker
        'روشنایی را به ۵۰',  # ovos-skill-mark1-ctrl
        'زبان اصلی شما چیست',  # ovos-skill-diagnostics
        'زنگ ساعتم را از دست دادم؟',  # ovos-skill-alerts
        'سال نو چه روزی از هفته میفته؟',  # ovos-skill-date-time
        'صدا را روی 50 بگذار',  # ovos-skill-volume
        'صدا رو ضبط کن و به اسم مصاحبه ذخیره کن',  # ovos-skill-audio-recording
        'عدد 7 چه ویژگی جالبی دارد',  # ovos-skill-number-facts
        'عکس\u200cهایی که می\u200cگیری کجا میرن',  # ovos-skill-camera
        'فهرست فیلم هایی که در کمدی',  # ovos-skill-moviemaster
        'لطفاً یک ذره بلندترش کن',  # ovos-skill-volume
        'می\u200cخوام یه صدا ضبط کنم',  # ovos-skill-audio-recording
        'می\u200cخواهم بدانم هوای فردا قرار است چطور باشد',  # ovos-skill-weather
        'می\u200cخواهم یک یادداشت دیکته کنم',  # ovos-skill-dictation
        'نقل قول کنفسیوس',  # ovos-skill-confucius-quotes
        'وردنت درباره متضادها چه می گوید',  # ovos-skill-wordnet
        'ولفرام آلفا درباره تاریخچه پیتزا چه می گوید',  # ovos-skill-wolfie
        'ویکی درباره چه می گوید پیتزا',  # ovos-skill-wikihow
        'ویکیپدیا را بررسی کنید پیتزا',  # ovos-skill-wikipedia
        'چه زبان هایی را می توان فهمید',  # ovos-skill-diagnostics
        'چی می شه',  # ovos-skill-fallback-unknown
        'یادآوری بعدی\u200cام را هفته\u200cای یک بار تکرار کن',  # ovos-skill-alerts
        'یک جوک بگو',  # ovos-skill-icanhazdadjokes
        'یک جوک در مورد بابایی بگو',  # ovos-skill-icanhazdadjokes
        'یک دانستنی درباره سال 1984 بگو',  # ovos-skill-number-facts
    },
    'it-IT': {
        'scandiscila',  # ovos-skill-word-of-the-day
    },
    'kab': {
        'tzemreḍ ad iyi-d-tiniḍ ccetla n baba',  # ovos-skill-icanhazdadjokes
        'tzemreḍ ad tiniḍ azul ay amaḍal',  # ovos-skill-hello-world
    },
    'pl-PL': {
        'które języki można zrozumieć',  # ovos-skill-diagnostics
        'przełącz wyciszenie',  # ovos-skill-volume
    },
    'pt-BR': {
        'soletra',  # ovos-skill-word-of-the-day
    },
    'ru-RU': {
        'Какие языки ты можешь понять',  # ovos-skill-diagnostics
        'Скажи мне язык, на котором мы разговариваем',  # ovos-skill-diagnostics
        'включи диктовку',  # ovos-skill-dictation
        'всё, хватит диктовать',  # ovos-skill-dictation
        'измени цвет своих глаз на умолчание',  # ovos-skill-mark1-ctrl
        'мне больше не нужен этот список, убери его насовсем',  # ovos-skill-alerts
        'объясни мне, что такое индиго',  # ovos-skill-color-picker
        'посмотри налево и направо анимация корпус',  # ovos-skill-mark1-ctrl
        'приготовить звук',  # ovos-skill-boot-finished
        'расскажи интересный факт о завтрашнем дне',  # ovos-skill-number-facts
        'расскажи мне анекдот про Папа',  # ovos-skill-icanhazdadjokes
        'расскажи мне шутку про программист',  # ovos-skill-icanhazdadjokes
        'сбрось громкость',  # ovos-skill-volume
        'то, за что прославился конфуций',  # ovos-skill-confucius-quotes
        'ты знаешь какие-нибудь анекдоты',  # ovos-skill-icanhazdadjokes
        'что ворднет говорит о определение',  # ovos-skill-wordnet
    },
    'sv-SE': {
        'stava det ordet',  # ovos-skill-word-of-the-day
    },
}


def _rows_by_lang():
    rows = {}
    for path in sorted(END2END_DIR.glob("cross_skill_*.jsonl")):
        lang = path.stem.removeprefix("cross_skill_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang()


def _first_match(engine, utterance, lang):
    """Return ``(tier, intent)`` for the first tier that matches, or ``(None, None)``."""
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    for tier in TIERS:
        match = getattr(engine, f"match_{tier}")([utterance], lang, message)
        if match:
            return tier, match.match_type
    return None, None


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_other_skills_rows_do_not_route_to_spell(lang):
    rows = ROWS[lang]
    known = CROSS_SKILL_KNOWN_CLAIMS.get(lang, set())
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        results = [_first_match(engine, row["utterance"], lang) for row in rows]
    finally:
        minicroft.stop()
    claims, unknown = [], []
    for row, (tier, got) in zip(rows, results):
        if got and got.startswith(f"{SKILL_ID}:"):
            claim = f"{row['utterance']!r} ({row['source_repo']}): matched {got} at {tier}"
            claims.append(claim)
            if row["utterance"] not in known:
                unknown.append(claim)
    print(f"[{lang}] {len(rows) - len(claims)} of {len(rows)} rows of other skills stay out of"
          f" spelling, {len(unknown)} unknown claims", *claims, sep="\n  ")
    assert not unknown, (
        f"[{lang}] rows of other skills claimed by spelling, not in CROSS_SKILL_KNOWN_CLAIMS:\n  "
        + "\n  ".join(unknown))


def test_every_shipping_locale_has_a_cross_skill_file():
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert set(ROWS) == shipping, f"cross_skill files {sorted(set(ROWS) ^ shipping)} differ from shipping locales"
    for lang, rows in ROWS.items():
        skills = {row["source_repo"] for row in rows}
        assert len(rows) >= MIN_ROWS_PER_LOCALE, f"[{lang}] {len(rows)} rows"
        assert len(skills) >= MIN_SKILLS_PER_LOCALE, f"[{lang}] rows from {len(skills)} skills"
        assert "ovos-skill-spelling" not in skills
        assert all(len(row["source_sha"]) == 40 for row in rows), f"[{lang}] row without a source sha"
