# Copyright 2018 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from pathlib import Path

from kw_template_matcher import TemplateMatcher, expand_template
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill


class SpellingSkill(OVOSSkill):
    SEC_PER_LETTER = 0.9  # based on the Mark 1 scrolling speed
    LETTERS_PER_SCREEN = 7.0  # based on the Mark 1 screen size

    def ask_for_word(self) -> str:
        """Ask which word to spell, giving up after a second unusable answer."""
        blacklist = self.resources.load_blacklist_file("word")
        for _ in range(2):
            reply = self.get_response("what_word")
            word = self.word_from_reply(reply) if reply else ""
            if word and word.lower() not in blacklist:
                return word
        self.speak_dialog("no_word")
        return ""

    def word_from_reply(self, reply: str) -> str:
        """Strip the carrier phrase off a reply: people answer "which word?"
        with "the word banana" or "spell banana" as often as with "banana"."""
        samples = []
        # a locale can ship no spell.intent at all (kab): find_resource then
        # returns None, and the carrier template below is the only sample
        intent_file = self.find_resource("spell.intent", "locale")
        if intent_file:
            lines = Path(intent_file).read_text()
            samples = [l for l in lines.splitlines()
                       if l and not l.startswith("#")]
        matcher = TemplateMatcher()
        # expand_template leaves a double space where an optional group was
        # dropped; simplematch would never match those against real speech
        matcher.add_templates([" ".join(t.split())
                               for s in samples + ["[the] word {word}"]
                               for t in expand_template(s)])
        return matcher.match(reply).get("word", reply)

    @intent_handler("spell.intent")
    def handle_spell(self, message):
        # OVOS-INTENT-2 §4.3: an anaphoric pronoun ("it", "that", ...) is
        # blacklisted out of the {word} slot (word.blacklist), leaving it
        # unresolved rather than binding the pronoun literally.
        word = message.data.get("word") or self.ask_for_word()
        if not word:
            return
        spelled_word = '; '.join(word).upper()

        # Pause mouth shapes appearing on screen for at least enough time
        # for the word to scroll by on the Mark 1 screen.  Pad with blanks
        # to prevent re-starting the scroll action if the timing is slightly
        # off.
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(word + "          ")

        self.speak(spelled_word, wait=True)

        # allow mouth movements again
        self.enclosure.activate_mouth_events()
        self.enclosure.mouth_reset()
