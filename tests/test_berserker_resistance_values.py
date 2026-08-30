import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BERSERKER_INSTALLERS = (
    Path("ArtisansKitpack/lib/Berserker.tpa"),
    Path("live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2"),
)
EXPECTED_RESISTANCE_VALUES = [("1", "3"), ("2", "6"), ("3", "10")]
RESISTANCE_ASSIGNMENT = re.compile(
    r"^[ \t]*OUTER_SET[ \t]+ie_r([123])[ \t]*=[ \t]*(.*?)[ \t]*\r?$",
    re.MULTILINE | re.IGNORECASE,
)


def read_weidu_source(relative_path):
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


class BerserkerResistanceValuesTest(unittest.TestCase):
    def test_both_installers_use_one_normalized_resistance_set(self):
        for relative_path in BERSERKER_INSTALLERS:
            with self.subTest(path=str(relative_path)):
                source = read_weidu_source(relative_path)
                assignments = RESISTANCE_ASSIGNMENT.findall(source)
                self.assertEqual(assignments, EXPECTED_RESISTANCE_VALUES)

    def test_both_installers_do_not_mention_spell_revisions(self):
        for relative_path in BERSERKER_INSTALLERS:
            with self.subTest(path=str(relative_path)):
                source = read_weidu_source(relative_path)
                self.assertFalse(
                    "spell_rev" in source.lower(),
                    f"{relative_path} still contains Spell Revisions-specific logic",
                )


if __name__ == "__main__":
    unittest.main()
