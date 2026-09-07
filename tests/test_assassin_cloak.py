"""Inspect real WeiDU output for activated Cloak; no live-engine simulation."""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_assassin_balance import INSTALLER, SPELLS
from test_assassin_expose_weakness import FUNCTIONS, ROOT, WEIDU, Spell, read_tlk_string
from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    _raw_tree,
    _write_marker_key_and_bif,
)


INCLUDE = Path("ArtisansKitpack/lib/assassin_cloak.tpa")
STATIC_CLAB = ROOT / "ArtisansKitpack/Thief/Assassin/2da/clabth02.2da"


def table_rows(raw: bytes) -> list[list[str]]:
    return [line.split() for line in raw.decode("ascii").splitlines() if line.strip()][3:]


def cloak_grant_levels(raw: bytes) -> list[int]:
    return sorted(
        level
        for row in table_rows(raw)
        for level, entry in enumerate(row[1:], 1)
        if entry.upper() == "GA_C0AS#I5"
    )


class SyntheticCloakGame:
    def __init__(self, root: Path, *, existing_rows: bool = False) -> None:
        self.root = root
        self.root.mkdir()
        self.override = root / "override"
        self.override.mkdir()
        shutil.copy2(WEIDU, root / "weidu.exe")
        shutil.copytree(ROOT / SPELLS, root / SPELLS)
        (root / FUNCTIONS).parent.mkdir(parents=True)
        shutil.copy2(ROOT / FUNCTIONS, root / FUNCTIONS)
        shutil.copy2(ROOT / INCLUDE, root / INCLUDE)
        bif = _write_marker_key_and_bif(root)
        self.immutable = {
            path: path.read_bytes()
            for path in (root / "chitin.key", bif, root / FUNCTIONS, root / INCLUDE)
        }
        self.source_spells = _raw_tree(root / SPELLS)
        self.tlk = root / "lang/en_US/dialog.tlk"
        self.tlk.parent.mkdir(parents=True)
        self.tlk.write_bytes(ONE_EMPTY_STRING_TLK)
        (root / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
        self.condition_rows = [
            "FILLER0 0x10a 0 4",
            "FILLER1 40 -1 4",
            "FILLER2 * * *",
            "FILLER3 40 -1 2",
            "FILLER4 1 0 3",
            "AKCB_CS_INVISIBLE 0x111 16 8" if existing_rows else "FILLER5 41 -1 2",
            "FILLER6 0x10b 4 1",
        ]
        (self.override / "SPLPROT.2DA").write_text(
            "2DA V1.0\n0xffff\nSTAT VALUE RELATION\n"
            + "\n".join(self.condition_rows) + "\n",
            encoding="ascii",
        )
        (self.override / "CLABTH01.2DA").write_text(
            "2DA V1.0\n****\n" + " ".join(map(str, range(1, 51)))
            + "\nEXISTING AP_SENTINEL " + " ".join(["****"] * 49) + "\n",
            encoding="ascii",
        )
        (self.override / "UNRELATED.IDS").write_bytes(b"IDS V1.0\n1 LEAVE_ALONE\n")
        # A source resource already in override must be restored on uninstall.
        shutil.copy2(ROOT / SPELLS / "c0as#i5.spl", self.override / "C0AS#I5.SPL")
        source = INSTALLER.read_text(encoding="utf-8")
        start = source.index("COPY_EXISTING ~CLABTH01.2DA~")
        stop = source.index("// ICONS", start)
        patch = root / "AKCB_CLOAK_TEST/setup-AKCB_CLOAK_TEST.tp2"
        patch.parent.mkdir()
        patch.write_text(
            "BACKUP ~AKCB_CLOAK_TEST/backup~\n"
            "AUTHOR ~synthetic test~\n"
            "BEGIN ~Cloak of Shadows production include test~\n"
            "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
            f"INCLUDE ~{FUNCTIONS.as_posix()}~\n"
            "COPY ~%MOD_FOLDER%/Thief/Assassin/spells~ ~override~\n"
            + source[start:stop]
            + f"\nINCLUDE ~{INCLUDE.as_posix()}~\n",
            encoding="utf-8",
        )
        self.before = _raw_tree(self.override)

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.root / "weidu.exe"),
                "AKCB_CLOAK_TEST/setup-AKCB_CLOAK_TEST.tp2",
                "--game", str(self.root),
                *[argument for operation in (operations or ("--force-install-list",))
                  for argument in (operation, "0")],
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


class AssassinCloakTests(unittest.TestCase):
    def _game(self, **kwargs: bool) -> SyntheticCloakGame:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-assassin-cloak-")
        self.addCleanup(temporary.cleanup)
        return SyntheticCloakGame(Path(temporary.name) / "game", **kwargs)

    def _install(self, game: SyntheticCloakGame, *operations: str) -> None:
        process = game.run(*operations)
        transcript = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        for path, before in game.immutable.items():
            self.assertEqual(before, path.read_bytes(), str(path))
        self.assertEqual(game.source_spells, _raw_tree(game.root / SPELLS))

    def test_static_and_dynamic_clabs_grant_one_use_at_10_15_20_25(self) -> None:
        game = self._game()
        self._install(game)
        output = _raw_tree(game.override)
        for raw in (STATIC_CLAB.read_bytes(), output["CLABTH02.2DA"]):
            self.assertEqual([10, 15, 20, 25], cloak_grant_levels(raw))
            self.assertNotIn(b"AP_C0AS#I5", raw.upper())
            for level in range(1, 51):
                expected = min(4, max(0, (level - 5) // 5))
                self.assertEqual(expected, sum(grant <= level for grant in cloak_grant_levels(raw)))
        self.assertIn(b"AP_SENTINEL", output["CLABTH02.2DA"])
        self.assertEqual(game.before["CLABTH01.2DA"], output["CLABTH01.2DA"])

    def test_installer_uses_the_production_include_once(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertEqual(1, source.lower().count("include ~%mod_folder%/lib/assassin_cloak.tpa~"))
        self.assertNotIn("Gained Passive Ability: Cloak of Shadows", source)
        self.assertNotIn("AP_C0AS#I5", source)

    def _assert_cloak_window(self, game: SyntheticCloakGame, condition_row: int) -> None:
        output = _raw_tree(game.override)
        main = game.spell("C0AS#I5")
        self.assertEqual(4, struct.unpack_from("<H", main.raw, 0x1C)[0])  # innate spell
        self.assertEqual(1, struct.unpack_from("<I", main.raw, 0x34)[0])
        self.assertEqual(0, struct.unpack_from("<I", main.raw, 0x18)[0] & 0x600)
        self.assertEqual(0, struct.unpack_from("<H", main.raw, 0x22)[0])
        self.assertEqual(1, len(main.headers))
        header = main.headers[0]
        self.assertEqual(4, struct.unpack_from("<H", header, 2)[0])  # innate button
        self.assertEqual(5, header[0x0C])  # self-targeted ability
        self.assertEqual(0, struct.unpack_from("<H", header, 0x12)[0])  # instant cast

        # Recast cleanup precedes replacement state, including the old deadline.
        self.assertEqual(
            [(321, "C0AS#I5"), (321, "C0AS#02"), (326, "C0AS#02"),
             (272, "AKCBCSCK"), (146, "AKCBCSEN")],
            [(effect.opcode, effect.resource) for effect in main.effects],
        )
        reset, clear_payload, immediate, poller, deadline = main.effects
        for effect in (reset, clear_payload, immediate):
            self.assertEqual((1, 0), (effect.timing, effect.duration))
        self.assertEqual((16, condition_row), (immediate.parameter1, immediate.parameter2))
        self.assertEqual((1, 3, 0, 18), (
            poller.parameter1, poller.parameter2, poller.timing, poller.duration,
        ))
        self.assertEqual((1, 4, 18), (deadline.parameter2, deadline.timing, deadline.duration))
        self.assertEqual(poller.duration, deadline.duration)  # full three-round window
        for effect in main.effects:
            self.assertEqual(1, effect.target)
            self.assertEqual(0, effect.raw[13])  # no dispel/MR interference
            self.assertEqual(b"\x64\0", effect.raw[18:20])
            self.assertEqual(b"\0" * 8, effect.raw[36:44])

        # The expiry child cancels the polling parent before removing protection.
        expiry = game.spell(deadline.resource)
        self.assertEqual(
            [(321, "C0AS#I5", 1, 0), (321, "C0AS#02", 1, 0)],
            [(effect.opcode, effect.resource, effect.timing, effect.duration) for effect in expiry.effects],
        )
        self.assertTrue(all(effect.target == 1 for effect in expiry.effects))

        rows = table_rows(output["SPLPROT.2DA"])
        self.assertEqual(["AKCB_CS_INVISIBLE", "0x111", "16", "8"], rows[condition_row])
        self.assertEqual(1, sum(row[0] == "AKCB_CS_INVISIBLE" for row in rows))
        # Both initial application and subsequent polls use the state-bit row,
        # with no restriction on the spell/potion/stealth that grants invisibility.
        checker = output["AKCBCSCK.EFF"]
        self.assertEqual(326, struct.unpack_from("<I", checker, 0x10)[0])
        self.assertEqual((16, condition_row), struct.unpack_from("<II", checker, 0x1C))
        self.assertEqual(b"C0AS#02\0", checker[0x30:0x38].upper())
        original_checker = game.source_spells["C0AS#03.EFF"]
        self.assertEqual(original_checker[:0x20], checker[:0x20])
        self.assertEqual(original_checker[0x24:], checker[0x24:])

        # Retain every original protection, but make all of them expire/remove
        # normally instead of writing permanent base Non-Detection (opcode 69).
        original_payload = Spell(game.source_spells["C0AS#02.SPL"])
        payload = game.spell(immediate.resource)
        self.assertTrue(all(struct.unpack_from("<H", header, 0x26)[0] == 0 for header in payload.headers))
        self.assertEqual(len(original_payload.effects), len(payload.effects))
        self.assertTrue(any(effect.opcode == 69 for effect in payload.effects))
        for before, after in zip(original_payload.effects, payload.effects):
            self.assertEqual((0, 18), (after.timing, after.duration))
            expected = before.raw[:12] + b"\0" + before.raw[13:14] + struct.pack("<I", 18) + before.raw[18:]
            self.assertEqual(expected, after.raw)
        self.assertNotIn(20, [effect.opcode for spell in (main, expiry, payload) for effect in spell.effects])

        # An obsolete saved passive checker now invokes the same self-removal,
        # rather than applying protection outside an activated window.
        obsolete = output["C0AS#03.EFF"]
        self.assertEqual(146, struct.unpack_from("<I", obsolete, 0x10)[0])
        self.assertEqual((0, 1), struct.unpack_from("<II", obsolete, 0x1C))
        self.assertEqual(b"AKCBCSEN", obsolete[0x30:0x38])
        expected_obsolete = bytearray(original_checker)
        struct.pack_into("<I", expected_obsolete, 0x10, 146)
        struct.pack_into("<II", expected_obsolete, 0x1C, 0, 1)
        expected_obsolete[0x30:0x38] = b"AKCBCSEN"
        self.assertEqual(bytes(expected_obsolete), obsolete)
        # Existing visibility and on-hit cleanup remain available.
        for resource in ("C0AS#00.EFF", "C0AS#02.EFF", "C0AS#I1.SPL"):
            self.assertEqual(game.source_spells[resource], output[resource])

        description = read_tlk_string(game.tlk, struct.unpack_from("<I", main.raw, 0x50)[0])
        for phrase in ("three rounds", "while hiding or Invisible", "does not grant or break invisibility",
                       "Casting Time: 0", "10th level", "four uses per day at 25th level"):
            self.assertIn(phrase, description)
        self.assertEqual("Cloak of Shadows", read_tlk_string(game.tlk, struct.unpack_from("<I", main.raw, 8)[0]))

    def test_activation_has_bounded_checker_and_deadline_and_uninstalls_exactly(self) -> None:
        game = self._game()
        self._install(game)
        self._assert_cloak_window(game, condition_row=7)
        output = _raw_tree(game.override)
        self.assertEqual(8, len(table_rows(output["SPLPROT.2DA"])))
        self.assertEqual(game.before["UNRELATED.IDS"], output["UNRELATED.IDS"])
        process = game.run("--force-uninstall-list")
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_existing_condition_row_is_reused_and_reinstall_is_identical(self) -> None:
        game = self._game(existing_rows=True)
        self._install(game)
        self._assert_cloak_window(game, condition_row=5)
        first = _raw_tree(game.override)
        self.assertEqual(7, len(table_rows(first["SPLPROT.2DA"])))
        self._install(game, "--force-uninstall-list", "--force-install-list")
        self.assertEqual(first, _raw_tree(game.override))
        self._assert_cloak_window(game, condition_row=5)


if __name__ == "__main__":
    unittest.main()
