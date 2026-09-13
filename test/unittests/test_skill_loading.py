import re
import unittest

from ovos_bus_client.message import Message
from ovos_plugin_manager.skills import find_skill_plugins
from ovos_utils.fakebus import FakeBus

from skill_ovos_spelling import SpellingSkill

SKILL_ID = "skill-ovos-spelling.openvoiceos"


def _registers_intent(skill: SpellingSkill, skill_id: str, intent_file: str) -> bool:
    """True if ``skill`` has registered ``intent_file`` (eg. "Spell.intent"),
    tolerant of which ".intent" basename normalization the registering
    pipeline uses (ovos-padatious >=2.0 registers the suffixless canonical
    name, eg. "Spell", where older/other pipelines keep "Spell.intent";
    see test/end2end/test_intents_en_us.py's ``_matches_intent`` for the
    same tolerance on the wire).
    """
    prefix = f"{skill_id}:"
    expected_base = intent_file.rsplit(".", 1)[0] if intent_file.endswith(".intent") else intent_file
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for _, data in skill.intent_service.registered_intents:
        name = data["name"]
        if not name.startswith(prefix):
            continue
        observed = name[len(prefix):]
        observed_base = observed.rsplit(".", 1)[0] if observed.endswith(".intent") else observed
        if norm(observed_base) == norm(expected_base):
            return True
    return False


class TestSkillLoading(unittest.TestCase):
    def _make_skill(self) -> SpellingSkill:
        bus = FakeBus()
        skill = SpellingSkill()
        skill._startup(bus, SKILL_ID)
        return skill

    def test_from_class(self):
        bus = FakeBus()
        skill = SpellingSkill()
        skill._startup(bus, SKILL_ID)
        self.assertEqual(skill.bus, bus)
        self.assertEqual(skill.skill_id, SKILL_ID)

    def test_registers_spell_intent(self):
        skill = self._make_skill()
        self.assertTrue(_registers_intent(skill, SKILL_ID, "Spell.intent"))

    def test_spells_word(self):
        skill = self._make_skill()
        spoken: list[str] = []
        skill.speak = lambda utt, *a, **k: spoken.append(utt)
        skill.handle_spell(Message("", {"word": "cat"}))
        self.assertEqual(spoken, ["C; A; T"])

    def test_empty_utterance_does_not_crash(self):
        skill = self._make_skill()
        spoken: list[str] = []
        skill.speak = lambda utt, *a, **k: spoken.append(utt)
        # adversarial: a garbage/empty capture must not take the skill down
        skill.handle_spell(Message("", {"word": ""}))
        self.assertEqual(spoken, [""])

    def test_unresolved_word_reprompts_instead_of_crashing(self):
        # OVOS-INTENT-3 §7.1: a blacklisted slot (word.blacklist) leaves
        # {word} unresolved, i.e. message.data["word"] is None (the key is
        # absent). '; '.join(None) raises TypeError; the handler must
        # re-prompt instead.
        skill = self._make_skill()
        spoken: list[str] = []
        skill.speak = lambda utt, *a, **k: spoken.append(utt)
        skill.get_response = lambda *a, **k: "cat"
        skill.handle_spell(Message("", {}))
        self.assertEqual(spoken, ["C; A; T"])

    def test_unresolved_word_no_answer_does_not_crash(self):
        skill = self._make_skill()
        spoken: list[str] = []
        skill.speak = lambda utt, *a, **k: spoken.append(utt)
        skill.get_response = lambda *a, **k: None
        skill.handle_spell(Message("", {}))
        self.assertEqual(spoken, [])


class TestPluginDiscovery(unittest.TestCase):
    def test_registered_as_opm_plugin(self):
        # only meaningful when installed (entry points present); editable/source
        # runs expose no metadata, so treat an empty registry as not-installed.
        plugins = find_skill_plugins()
        if not plugins:
            self.skipTest("no installed skill plugins in this environment")
        self.assertIn(SKILL_ID, plugins)


if __name__ == "__main__":
    unittest.main()
