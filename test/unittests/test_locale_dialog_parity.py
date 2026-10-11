"""Every dialog the skill speaks must exist in every locale that can reach it.

``ask_for_word`` prompts with ``what_word`` and gives up with ``no_word``. A
locale that ships only the prompt makes the skill speak the literal string
``no_word`` to the user, because ``speak_dialog`` falls back to the resource
name. The first test below pins the pair together.

The second test covers a locale that ships no ``spell.intent``. Every locale
this skill ships carries one today, but ``find_resource`` returns ``None`` for
a name it cannot find, and ``word_from_reply`` passed that ``None`` straight to
``Path``, which raises ``TypeError``. A new locale directory, or a locale whose
intent file is renamed, reaches that line.
"""
import unittest
from pathlib import Path

from ovos_utils.fakebus import FakeBus

from skill_ovos_spelling import SpellingSkill

SKILL_ID = "skill-ovos-spelling.openvoiceos"
LOCALE_DIR = Path(__file__).resolve().parents[2] / "locale"


class TestLocaleDialogParity(unittest.TestCase):
    def test_no_word_ships_wherever_what_word_ships(self):
        prompts = sorted(p.parents[1].name
                         for p in LOCALE_DIR.glob("*/dialog/what_word.dialog"))
        self.assertTrue(prompts, "expected at least one what_word.dialog")
        for lang in prompts:
            give_up = LOCALE_DIR / lang / "dialog" / "no_word.dialog"
            self.assertTrue(give_up.is_file(),
                            f"{lang} prompts with what_word.dialog but ships "
                            "no no_word.dialog")
            lines = [l for l in give_up.read_text(encoding="utf-8").splitlines()
                     if l.strip()]
            self.assertTrue(lines, f"{lang}/dialog/no_word.dialog is empty")


class TestWordFromReplyWithoutIntentFile(unittest.TestCase):
    def test_find_resource_returns_none_for_a_name_it_cannot_find(self):
        """The condition under test is find_resource's own contract, not a
        fact about which locales ship which files today."""
        skill = SpellingSkill()
        skill._startup(FakeBus(), SKILL_ID)
        self.assertIsNone(skill.find_resource("no_such.intent", "locale"))

    def test_reply_survives_a_missing_spell_intent(self):
        skill = SpellingSkill()
        skill._startup(FakeBus(), SKILL_ID)
        skill.find_resource = lambda *a, **k: None
        self.assertEqual(skill.word_from_reply("banana"), "banana")
        self.assertEqual(skill.word_from_reply("the word banana"), "banana")
