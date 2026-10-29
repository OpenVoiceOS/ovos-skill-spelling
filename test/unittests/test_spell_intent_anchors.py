"""Every spell.intent form asks for spelling.

A line whose only content is a verb and the open ``{word}`` slot, or a line
that starts with ``{word}``, lets the intent engines give spell any request
that shares a few words with it ("{word} how do you spell that" took general
questions under padatious). Each line is expanded into every form it can
produce, and every form must contain one of its locale's spelling words and
must not start with the slot.
"""
import unittest
from pathlib import Path

from ovos_spec_tools.expansion import expand
from ovos_spec_tools.resources import read_resource_file

LOCALE_DIR = Path(__file__).resolve().parents[2] / "locale"

# Lowercase stems that name spelling in each locale: spell, letters, letter by
# letter, spelling, or "how is it written".
SPELLING_WORDS = {
    "ca-ES": ("lletr", "s'escriu", "escrius", "ortograf"),
    "da-DK": ("stav",),
    "de-DE": ("buchstab", "schreib"),
    "en-US": ("spell",),
    "es-CO": ("deletre", "letra", "se escribe", "escribes"),
    "es-ES": ("deletre", "letra", "se escribe", "escribes"),
    "eu-ES": ("letr", "idazten da", "idazten duzu", "idazketa", "ortografia"),
    "fa-IR": ("هجی", "املا", "حروف"),
    "fr-FR": ("épel", "orthographe", "s'écrit"),
    "gl-ES": ("soletr", "letra", "ortograf", "se escribe", "escribes"),
    "it-IT": ("scand", "ortografia", "lettera", "si scrive", "scrivi"),
    "kab": ("isekkilen", "tira"),
    "nl-NL": ("spel", "schrijf", "letter"),
    "oc-FR": ("espèl", "letra", "s'escriu", "escrives"),
    "pl-PL": ("liter", "pisz", "pisown"),
    "pt-BR": ("soletr",),
    "pt-PT": ("soletr", "escreve"),
    "ru-RU": ("букв", "пишется", "написание", "орфограф"),
    "sv-SE": ("stav", "skriver"),
}


def _forms(path):
    for line in read_resource_file(path):
        for form in expand(line):
            yield line, " ".join(form.split())


class TestSpellIntentAnchors(unittest.TestCase):
    def test_every_locale_has_a_spelling_word_set(self):
        shipped = {p.parent.name for p in LOCALE_DIR.glob("*/spell.intent")}
        self.assertEqual(shipped, set(SPELLING_WORDS))

    def test_no_form_starts_with_the_slot(self):
        leading = [f"{path.parent.name}: {form!r} <- {line!r}"
                   for path in sorted(LOCALE_DIR.glob("*/spell.intent"))
                   for line, form in _forms(path) if form.startswith("{word}")]
        self.assertEqual(leading, [], "forms that start with {word}:\n" + "\n".join(leading))

    def test_every_form_names_spelling(self):
        missing = []
        for path in sorted(LOCALE_DIR.glob("*/spell.intent")):
            words = SPELLING_WORDS.get(path.parent.name, ())
            missing += [f"{path.parent.name}: {form!r} <- {line!r}"
                        for line, form in _forms(path)
                        if not any(w in form.lower() for w in words)]
        self.assertEqual(missing, [], "forms with no spelling word:\n" + "\n".join(missing))
