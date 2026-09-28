import re
import unittest
from pathlib import Path

BASENAME_RE = re.compile(r"^[a-z0-9_]+$")
DIALOG_DIR = Path(__file__).resolve().parents[2] / "locale" / "en-US" / "dialog"


class TestLocaleBasenameCompliance(unittest.TestCase):
    def test_no_word_dialog_basename_is_compliant(self):
        """OVOS-INTENT-2 SS2: a resource base name MUST consist only of
        lowercase ASCII letters, digits, and underscores, and MUST NOT
        contain whitespace; file extensions are likewise lowercase.

        This skill added a dialog resource for the "gave up asking which
        word to spell" case; its basename must be compliant, since en-US
        introduces it and there is no existing en-US name to mirror.
        """
        matches = [
            path.name
            for path in DIALOG_DIR.glob("*.dialog")
            if re.sub(r"[^a-z]", "", path.stem.lower()) == "noword"
        ]
        self.assertTrue(matches, "expected a 'gave up' dialog file")
        for name in matches:
            base = name[: -len(".dialog")]
            self.assertRegex(
                base,
                BASENAME_RE,
                f"'{name}' does not match ^[a-z0-9_]+$ + lowercase extension "
                "(OVOS-INTENT-2 SS2)",
            )
