import unittest

from ovos_bus_client.message import Message
from ovos_plugin_manager.skills import find_skill_plugins
from ovos_utils.fakebus import FakeBus

from skill_ovos_spelling import SpellingSkill

SKILL_ID = "skill-ovos-spelling.openvoiceos"


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
        names = {data["name"] for _, data in skill.intent_service.registered_intents}
        self.assertIn(f"{SKILL_ID}:Spell.intent", names)

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
