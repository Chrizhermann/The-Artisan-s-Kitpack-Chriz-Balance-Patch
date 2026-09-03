import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DWARVEN_DEFENDER_INSTALLER = (
    REPOSITORY_ROOT / "ArtisansKitpack/lib/dwarvendefender.tpa"
)
SHIELD_BASH_GRANT = re.compile(
    r"^[ \t]*LPF[ \t]+set_clab_2da_entries\b"
    r"(?=[^\r\n]*\bf_MinLevel[ \t]*=[ \t]*1\b)"
    r"(?=[^\r\n]*\bf_Entry[ \t]*=[ \t]*GA_C0DWD03\b)"
    r"[^\r\n]*\bEND[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE,
)


class DwarvenDefenderShieldBashTest(unittest.TestCase):
    def test_rebuilt_clab_grants_shield_bash_at_level_one(self):
        source = DWARVEN_DEFENDER_INSTALLER.read_text(encoding="utf-8")

        self.assertEqual(
            1,
            len(SHIELD_BASH_GRANT.findall(source)),
            "the shared Dwarven Defender/Vanguard CLAB must grant GA_C0DWD03 once",
        )


if __name__ == "__main__":
    unittest.main()
