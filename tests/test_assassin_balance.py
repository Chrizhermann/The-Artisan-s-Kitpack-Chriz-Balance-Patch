"""Exercise production Assassin patches with WeiDU; no live-engine claims."""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_assassin_expose_weakness import FUNCTIONS, ROOT, WEIDU, Spell, read_tlk_string
from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    _raw_tree,
    _write_marker_key_and_bif,
)


INSTALLER = ROOT / "ArtisansKitpack/lib/Assassin.tpa"
SPELLS = Path("ArtisansKitpack/Thief/Assassin/spells")
PREPARATION_HELPERS = ("C0AS#01", "C0AS#1A", "C0AS#1B")


def production_actions() -> str:
    """Extract complete production actions, never reimplement their patches."""
    source = INSTALLER.read_text(encoding="utf-8")
    preparation = source.index("// CHRIZ BALANCE: Remove Preparation")
    preparation_end = source.index("COPY_EXISTING ~CLABTH01.2DA~", preparation)

    def copy_action(resource: str) -> str:
        pattern = re.compile(
            r"^[ \t]*COPY(?:_EXISTING)? ~" + re.escape(resource) + r"~",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(source)
        if match is None:
            raise AssertionError(f"missing production COPY for {resource}")
        next_copy = re.search(r"^[ \t]*COPY(?:_EXISTING)? ", source[match.end():], re.MULTILINE)
        if next_copy is None:
            raise AssertionError(f"missing action boundary after {resource}")
        return source[match.start():match.end() + next_copy.start()]

    description = re.search(r"STRING_SET_EVALUATE kit_strref ~.*?~", source, re.DOTALL)
    if description is None:
        raise AssertionError("missing production kit description")
    return "\n".join((
        "COPY ~%MOD_FOLDER%/Thief/Assassin/spells~ ~override~",
        source[preparation:preparation_end],
        copy_action("abclsmod.2da"),
        copy_action("%MOD_FOLDER%/Thief/Assassin/spells/c0ashla3.spl"),
        "OUTER_SET kit_strref = 0",
        description.group(0),
    ))


class SyntheticAssassinBalanceGame:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir()
        self.override = root / "override"
        self.override.mkdir()
        shutil.copy2(WEIDU, root / "weidu.exe")
        shutil.copytree(ROOT / SPELLS, root / SPELLS)
        (root / FUNCTIONS).parent.mkdir(parents=True)
        shutil.copy2(ROOT / FUNCTIONS, root / FUNCTIONS)
        bif = _write_marker_key_and_bif(root)
        self.immutable = {
            path: path.read_bytes()
            for path in (root / "chitin.key", bif, root / FUNCTIONS)
        }
        self.source_spells = _raw_tree(root / SPELLS)
        self.tlk = root / "lang/en_US/dialog.tlk"
        self.tlk.parent.mkdir(parents=True)
        self.tlk.write_bytes(ONE_EMPTY_STRING_TLK)
        (root / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
        (self.override / "ABCLSMOD.2DA").write_text(
            "2DA V1.0\n0\nSTR DEX CON INT WIS CHR\n"
            "DEFAULT 0 0 0 0 0 0\n"
            "ASSASIN 1 2 3 4 5 -2\n"
            "OTHER 6 7 8 9 10 -2\n",
            encoding="ascii",
        )
        # Existing override state must be restored, including patched resources.
        shutil.copy2(ROOT / SPELLS / "c0as#01.spl", self.override / "C0AS#01.SPL")
        (self.override / "UNRELATED.IDS").write_bytes(b"IDS V1.0\n1 LEAVE_ALONE\n")
        patch = root / "AKCB_ASSASSIN_TEST/setup-AKCB_ASSASSIN_TEST.tp2"
        patch.parent.mkdir()
        patch.write_text(
            "BACKUP ~AKCB_ASSASSIN_TEST/backup~\n"
            "AUTHOR ~synthetic test~\n"
            "BEGIN ~Assassin production balance actions test~\n"
            "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
            f"INCLUDE ~{FUNCTIONS.as_posix()}~\n"
            + production_actions() + "\n",
            encoding="utf-8",
        )
        self.before = _raw_tree(self.override)

    def run(self, operation: str = "--force-install-list") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.root / "weidu.exe"),
                "AKCB_ASSASSIN_TEST/setup-AKCB_ASSASSIN_TEST.tp2",
                "--game", str(self.root), operation, "0",
                "--language", "0", "--use-lang", "en_US",
                "--no-exit-pause", "--quick-log",
            ],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )

    def spell(self, resource: str) -> Spell:
        return Spell(_raw_tree(self.override)[f"{resource.upper()}.SPL"])


class AssassinBalanceTests(unittest.TestCase):
    def _installed_game(self) -> SyntheticAssassinBalanceGame:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-assassin-balance-")
        self.addCleanup(temporary.cleanup)
        game = SyntheticAssassinBalanceGame(Path(temporary.name) / "game")
        process = game.run()
        transcript = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        for path, original in game.immutable.items():
            self.assertEqual(original, path.read_bytes(), str(path))
        self.assertEqual(game.source_spells, _raw_tree(game.root / SPELLS))
        return game

    def test_preparation_removed_at_every_level_without_removing_shared_hooks(self) -> None:
        game = self._installed_game()
        original = Spell((ROOT / SPELLS / "c0as#i1.spl").read_bytes())
        installed = game.spell("C0AS#I1")
        expected = [
            effect.raw for effect in original.effects
            if not (effect.opcode == 272 and effect.resource == "C0AS#01")
        ]
        self.assertEqual(expected, [effect.raw for effect in installed.effects])
        self.assertEqual(
            [(303, "C0AS#01"), (248, "C0AS#00"), (249, "C0AS#00"), (272, "C0AS#02"), (177, "C0AS#NM")],
            [(effect.opcode, effect.resource) for effect in installed.effects],
        )
        self.assertEqual([4], [effect.parameter2 for effect in installed.effects if effect.opcode == 303])
        for resource in PREPARATION_HELPERS:
            with self.subTest(resource=resource):
                original = Spell(game.source_spells[resource + ".SPL"])
                installed = game.spell(resource)
                self.assertTrue(original.effects)
                self.assertEqual([], installed.effects)
                self.assertEqual(len(original.headers), len(installed.headers))
                self.assertEqual(original.raw[:0x64], installed.raw[:0x64])
                for before, after in zip(original.headers, installed.headers):
                    self.assertEqual(before[:0x1E], after[:0x1E])
                    self.assertEqual(before[0x22:], after[0x22:])

        # These extracted removal actions leave other resources untouched;
        # later installer actions (including Cloak's own patch) run separately.
        changed = {resource + ".SPL" for resource in (*PREPARATION_HELPERS, "C0AS#I1", "C0ASHLA3")}
        output = _raw_tree(game.override)
        for resource, before in game.source_spells.items():
            if resource not in changed:
                self.assertEqual(before, output[resource], resource)

    def test_death_attack_keeps_delivery_and_saving_throw_without_automatic_crit(self) -> None:
        game = self._installed_game()
        original = Spell(game.source_spells["C0ASHLA3.SPL"])
        installed = game.spell("C0ASHLA3")
        expected = []
        for effect in original.effects:
            if effect.opcode == 301:
                continue
            raw = effect.raw
            if effect.opcode == 142 and effect.parameter2 == 152:
                raw = raw[:8] + struct.pack("<i", 154) + raw[12:]
            expected.append(raw)
        self.assertEqual(expected, [effect.raw for effect in installed.effects])
        self.assertNotIn(301, [effect.opcode for effect in installed.effects])
        self.assertEqual(original.raw[0x10:0x50], installed.raw[0x10:0x50])
        self.assertEqual(original.raw[0x58:0x64], installed.raw[0x58:0x64])
        self.assertEqual(len(original.headers), len(installed.headers))
        for before, after in zip(original.headers, installed.headers):
            self.assertEqual(before[:0x1E], after[:0x1E])
            self.assertEqual(before[0x22:], after[0x22:])
        death = _raw_tree(game.override)["C0ASHLA3.EFF"]
        self.assertEqual(game.source_spells["C0ASHLA3.EFF"], death)
        self.assertEqual(55, struct.unpack_from("<I", death, 0x10)[0])
        self.assertEqual((4, -4), struct.unpack_from("<Ii", death, 0x40))
        description = read_tlk_string(game.tlk, struct.unpack_from("<I", installed.raw, 0x50)[0])
        self.assertIn("next successful attack within five rounds", description)
        self.assertIn("kills the target instantly on a failed save vs. death at -4", description)
        self.assertIn("once per day", description)
        self.assertIn("Requires: Assassin's Blade", description)
        self.assertNotIn("critical", description.lower())

    def test_charisma_description_and_uninstall_preserve_unrelated_state(self) -> None:
        game = self._installed_game()
        output = _raw_tree(game.override)
        lines = output["ABCLSMOD.2DA"].decode("ascii").splitlines()
        rows = [line.split() for line in lines if line.strip()][3:]
        self.assertEqual([
            ["DEFAULT", "0", "0", "0", "0", "0", "0"],
            ["ASSASIN", "1", "2", "3", "4", "5", "0"],
            ["OTHER", "6", "7", "8", "9", "10", "-2"],
        ], rows)
        description = read_tlk_string(game.tlk, 0)
        self.assertNotIn("PREPARATION", description.upper())
        self.assertNotIn("penalty to Charisma", description)
        self.assertNotIn("penalty to starting Reputation", description)
        for retained in ("ENHANCED BACKSTAB:", "CLOAK OF SHADOWS:", "May not Set Traps.", "10 skill points"):
            self.assertIn(retained, description)
        self.assertEqual(game.before["UNRELATED.IDS"], output["UNRELATED.IDS"])
        process = game.run("--force-uninstall-list")
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_installer_does_not_restore_preparation_or_add_reputation_penalty(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("reputation.baf", source.lower())
        self.assertNotIn("Analysis: Critical Bonus", source)
        self.assertNotIn("Gains the Preparation", source)
        self.assertNotIn("PREPARATION:", source)
        self.assertNotIn("guaranteed critical hit", source)
        # The former feedback COPY restored the original Preparation controller.
        self.assertNotRegex(source, r"(?im)^\s*COPY\s+~%MOD_FOLDER%/Thief/Assassin/spells/c0as#01\.spl~")
        self.assertIn("AP_C0AS#I1", source)
        self.assertIn("GA_C0AS#I5", source)
        self.assertNotIn("AP_C0AS#I5", source)


if __name__ == "__main__":
    unittest.main()
