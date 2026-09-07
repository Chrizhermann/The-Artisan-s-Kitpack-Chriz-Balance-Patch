"""Inspect real WeiDU output in a synthetic game; these are not engine tests."""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    _raw_tree,
    _write_marker_key_and_bif,
)


ROOT = Path(__file__).resolve().parents[1]
WEIDU = ROOT / "Setup-ArtisansKitpack.exe"
INCLUDE = Path("ArtisansKitpack/lib/assassin_expose_weakness.tpa")
MAIN = Path("ArtisansKitpack/Thief/Assassin/spells/c0ashla1.spl")
FUNCTIONS = Path("ArtisansKitpack/lib/functions.tph")
HELPERS = tuple(f"AKCBEW{amount}" for amount in range(1, 16))
REMOVED_OPCODES = {0, 86, 87, 88, 89}


@dataclass(frozen=True)
class Effect:
    raw: bytes

    @property
    def opcode(self) -> int:
        return struct.unpack_from("<H", self.raw)[0]

    @property
    def target(self) -> int:
        return self.raw[2]

    @property
    def parameter1(self) -> int:
        return struct.unpack_from("<i", self.raw, 4)[0]

    @property
    def parameter2(self) -> int:
        return struct.unpack_from("<i", self.raw, 8)[0]

    @property
    def timing(self) -> int:
        return self.raw[12]

    @property
    def duration(self) -> int:
        return struct.unpack_from("<I", self.raw, 14)[0]

    @property
    def resource(self) -> str:
        return self.raw[20:28].rstrip(b"\0").decode("ascii").upper()


class Spell:
    def __init__(self, raw: bytes) -> None:
        if raw[:8] != b"SPL V1  ":
            raise ValueError("expected SPL V1")
        self.raw = raw
        headers, count, effects, first_global, globals_count = struct.unpack_from(
            "<IHIHH", raw, 0x64
        )
        self.headers = [raw[headers + i * 40 : headers + (i + 1) * 40] for i in range(count)]

        def slice_effects(first: int, length: int) -> list[Effect]:
            result = [Effect(raw[effects + i * 48 : effects + (i + 1) * 48]) for i in range(first, first + length)]
            if any(len(effect.raw) != 48 for effect in result):
                raise ValueError("effect slice exceeds spell length")
            return result

        self.globals = slice_effects(first_global, globals_count)
        self.abilities = [
            slice_effects(*reversed(struct.unpack_from("<HH", header, 0x1E)))
            for header in self.headers
        ]

    @property
    def effects(self) -> list[Effect]:
        return self.globals + [effect for ability in self.abilities for effect in ability]


def read_tlk_string(path: Path, reference: int) -> str:
    raw = path.read_bytes()
    count, strings = struct.unpack_from("<II", raw, 10)
    if not 0 <= reference < count:
        raise ValueError(f"TLK reference {reference} outside {count} entries")
    offset, size = struct.unpack_from("<II", raw, 18 + reference * 26 + 18)
    return raw[strings + offset : strings + offset + size].decode("utf-8")


class SyntheticAssassinGame:
    def __init__(self, root: Path, *, existing_rows: bool = False) -> None:
        self.root = root
        self.root.mkdir()
        self.override = root / "override"
        self.override.mkdir()
        shutil.copy2(WEIDU, root / "weidu.exe")
        for relative in (INCLUDE, MAIN, FUNCTIONS):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, root / relative)
        self.bif = _write_marker_key_and_bif(root)
        self.immutable = {
            path: path.read_bytes()
            for path in (root / "chitin.key", self.bif, root / INCLUDE, root / MAIN, root / FUNCTIONS)
        }
        self.tlk = root / "lang/en_US/dialog.tlk"
        self.tlk.parent.mkdir(parents=True)
        self.tlk.write_bytes(ONE_EMPTY_STRING_TLK)
        (root / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
        rows = [
            "FILLER0 0x10a 0 4",
            "AKCB_EW_GE 23 -1 4" if existing_rows else "FILLER1 40 -1 4",
            "FILLER2 * * *",
            "FILLER3 40 -1 2",
            "FILLER4 1 0 3",
            "AKCB_EW_EQ 23 -1 1" if existing_rows else "FILLER5 41 -1 2",
            "FILLER6 0x10b 4 1",
        ]
        (self.override / "SPLPROT.2DA").write_text(
            "2DA V1.0\n0xffff\nSTAT VALUE RELATION\n" + "\n".join(rows) + "\n",
            encoding="ascii",
        )
        shutil.copy2(ROOT / MAIN, self.override / "C0ASHLA1.SPL")
        (self.override / "UNRELATED.IDS").write_bytes(b"IDS V1.0\n1 LEAVE_ALONE\n")
        # A pre-existing generated resource must also be restored on uninstall.
        (self.override / "AKCBEW7.SPL").write_bytes(b"previous helper contents\n")
        patch = root / "AKCB_EW_TEST/setup-AKCB_EW_TEST.tp2"
        patch.parent.mkdir()
        patch.write_text(
            "BACKUP ~AKCB_EW_TEST/backup~\n"
            "AUTHOR ~synthetic test~\n"
            "BEGIN ~Expose Weakness production include test~\n"
            "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
            f"INCLUDE ~{FUNCTIONS.as_posix()}~\n"
            f"INCLUDE ~{INCLUDE.as_posix()}~\n",
            encoding="ascii",
        )
        self.before = _raw_tree(self.override)

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.root / "weidu.exe"),
                "AKCB_EW_TEST/setup-AKCB_EW_TEST.tp2",
                "--game", str(self.root),
                *[argument for operation in operations for argument in (operation, "0")],
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

    def rows(self) -> list[list[str]]:
        table = _raw_tree(self.override)["SPLPROT.2DA"].decode("ascii")
        return [line.split() for line in table.splitlines() if line.strip()][3:]


class AssassinExposeWeaknessTests(unittest.TestCase):
    def _game(self, **kwargs: bool) -> SyntheticAssassinGame:
        self.assertTrue((ROOT / INCLUDE).is_file(), f"missing production include: {INCLUDE}")
        temporary = tempfile.TemporaryDirectory(prefix="akcb-assassin-")
        self.addCleanup(temporary.cleanup)
        return SyntheticAssassinGame(Path(temporary.name) / "game", **kwargs)

    def _install(self, game: SyntheticAssassinGame, *operations: str) -> None:
        process = game.run(*(operations or ("--force-install-list",)))
        transcript = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        for path, original in game.immutable.items():
            self.assertEqual(original, path.read_bytes(), str(path))

    def _assert_spell_behavior(self, game: SyntheticAssassinGame) -> None:
        original = Spell((ROOT / MAIN).read_bytes())
        installed = game.spell("C0ASHLA1")
        self.assertEqual(1, len(installed.abilities))
        self.assertFalse(REMOVED_OPCODES & {fx.opcode for fx in installed.effects})
        # Casting metadata and ability metadata remain the original HLA's.
        self.assertEqual(original.raw[0x10:0x50], installed.raw[0x10:0x50])
        self.assertEqual(original.raw[0x58:0x64], installed.raw[0x58:0x64])
        self.assertEqual(original.headers[0][:0x1E], installed.headers[0][:0x1E])
        self.assertEqual(original.headers[0][0x22:], installed.headers[0][0x22:])

        def retained_bytes(spell: Spell) -> list[bytes]:
            retained = []
            for effect in spell.effects:
                if effect.opcode in REMOVED_OPCODES or effect.opcode == 326:
                    continue
                if effect.opcode == 321 and effect.resource in HELPERS:
                    continue
                raw = effect.raw
                if effect.opcode == 139:
                    raw = raw[:4] + b"\0" * 4 + raw[8:]
                retained.append(raw)
            return retained

        self.assertEqual(retained_bytes(original), retained_bytes(installed))
        self.assertEqual(
            [effect.raw for effect in original.effects if effect.opcode == 337],
            [effect.raw for effect in installed.effects if effect.opcode == 337],
        )
        cleanup = [fx for fx in installed.globals if fx.opcode == 321]
        self.assertEqual({"C0ASHLA1", *HELPERS}, {fx.resource for fx in cleanup})
        self.assertEqual(16, len(cleanup))
        for effect in cleanup:
            self.assertEqual(4, effect.target)
            self.assertEqual((1, 0, 0), (effect.timing, effect.duration, effect.parameter2))

        rows = game.rows()
        branches = [effect for effect in installed.abilities[0] if effect.opcode == 326]
        self.assertEqual(list(HELPERS), [effect.resource for effect in branches])
        self.assertEqual(list(range(1, 16)), [effect.parameter1 for effect in branches])
        modifiers = {}
        for amount, branch in enumerate(branches, 1):
            helper = game.spell(branch.resource)
            self.assertEqual(1, len(helper.abilities))
            self.assertEqual(0, len(helper.globals))
            self.assertEqual(1, len(helper.effects))
            effect = helper.effects[0]
            self.assertEqual((88, 2, -amount, 0, 0, 18), (
                effect.opcode, effect.target, effect.parameter1,
                effect.parameter2, effect.timing, effect.duration,
            ))
            self.assertEqual(0, effect.raw[3])  # original power level
            self.assertEqual(0, effect.raw[13])  # original dispel/resistance flags
            self.assertEqual(b"\x64\0", effect.raw[18:20])
            self.assertEqual(b"\0" * 8, effect.raw[36:44])  # no saving throw
            self.assertEqual(2, branch.target)
            self.assertEqual((1, 0), (branch.timing, branch.duration))
            self.assertEqual((0, 0), (branch.raw[3], branch.raw[13]))
            self.assertEqual(b"\0" * 8, branch.raw[36:44])
            row = rows[branch.parameter2]
            self.assertEqual(["23", "-1", "4" if amount == 15 else "1"], row[1:])
            modifiers[branch.resource] = effect.parameter1

        # Exhaustive signed-byte boundaries include 0, 1..14, 15, 16, 29, 30,
        # 50, 100 and 127. Models intentionally cover both possible timings of
        # derived-stat refresh without claiming to simulate the game engine.
        for resistance in range(-128, 128):
            for snapshot in (True, False):
                current = resistance
                applied = []
                for branch in branches:
                    observed = resistance if snapshot else current
                    relation = int(rows[branch.parameter2][3])
                    matches = (observed == branch.parameter1) if relation == 1 else (observed >= branch.parameter1)
                    if matches:
                        current += modifiers[branch.resource]
                        applied.append(branch.resource)
                with self.subTest(resistance=resistance, snapshot=snapshot):
                    expected = resistance if resistance < 0 else max(0, resistance - 15)
                    self.assertEqual(expected, current)
                    self.assertEqual(int(resistance > 0), len(applied))

        description = read_tlk_string(game.tlk, struct.unpack_from("<I", installed.raw, 0x50)[0])
        self.assertIn("piercing resistance", description.lower())
        self.assertIn("15", description)
        self.assertIn("minimum of 0", description.lower())
        self.assertIn("three rounds", description.lower())
        self.assertIn("immunity permanently", description.lower())
        self.assertIn("only mark a single target", description.lower())
        self.assertNotIn("Armor Class", description)
        self.assertNotIn("physical resistance", description.lower())
        feedback = [fx for fx in installed.effects if fx.opcode == 139]
        self.assertEqual(["Vulnerable"], [read_tlk_string(game.tlk, fx.parameter1) for fx in feedback])

    def test_production_include_builds_scoped_floor_and_uninstalls_byte_exact(self) -> None:
        game = self._game()
        self._install(game)
        self._assert_spell_behavior(game)
        self.assertEqual(9, len(game.rows()))
        self.assertEqual(game.before["UNRELATED.IDS"], _raw_tree(game.override)["UNRELATED.IDS"])
        process = game.run("--force-uninstall-list")
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_existing_nonadjacent_condition_rows_are_reused_on_reinstall(self) -> None:
        game = self._game(existing_rows=True)
        self._install(game)
        self._assert_spell_behavior(game)
        self.assertEqual(7, len(game.rows()))
        branches = [fx for fx in game.spell("C0ASHLA1").effects if fx.opcode == 326]
        self.assertEqual([5] * 14 + [1], [fx.parameter2 for fx in branches])
        first = _raw_tree(game.override)
        self._install(game, "--force-uninstall-list", "--force-install-list")
        self.assertEqual(first, _raw_tree(game.override))
        self.assertEqual(7, len(game.rows()))
        process = game.run("--force-uninstall-list")
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_assassin_installer_uses_the_tested_include(self) -> None:
        source = (ROOT / "ArtisansKitpack/lib/Assassin.tpa").read_text(encoding="utf-8")
        self.assertEqual(1, source.lower().count("include ~%mod_folder%/lib/assassin_expose_weakness.tpa~"))
        self.assertNotIn("reducing their Armor Class by 10 points", source)


if __name__ == "__main__":
    unittest.main()
