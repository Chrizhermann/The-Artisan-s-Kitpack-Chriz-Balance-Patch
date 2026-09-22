"""Check actual WeiDU output and delivery semantics; no live-engine claim."""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_assassin_expose_weakness import FUNCTIONS, ROOT, WEIDU, Effect, Spell, read_tlk_string
from test_shapeshifter_personal_space import ONE_EMPTY_STRING_TLK, _raw_tree, _write_marker_key_and_bif


INCLUDE = Path("ArtisansKitpack/lib/archer_called_shot.tpa")
SPELLS = Path("ArtisansKitpack/Ranger/Archer/spells")
RESOURCES = ("SPCL121.SPL", "C0ARCCS1.SPL", "C0ARCCS1.EFF")
REMOVED = {1, 12, 15, 89, 176}


def _save(effect: Effect) -> tuple[int, int]:
    return struct.unpack_from("<Ii", effect.raw, 36)


def _with_global(raw: bytes, *, first: bool) -> bytes:
    """Add a valid casting slice on either side of the original ability slice."""
    result = bytearray(raw)
    abilities, count, effects = struct.unpack_from("<IHI", result, 0x64)
    sentinel = bytearray(48)
    struct.pack_into("<HBBiiBBI", sentinel, 0, 174, 1, 0, 0, 0, 1, 2, 0)
    sentinel[18] = 100
    sentinel[20:28] = b"AKCBTEST"
    if first:
        result[effects:effects] = sentinel
        struct.pack_into("<HH", result, 0x6E, 0, 1)
        for index in range(count):
            offset = abilities + index * 40 + 0x20
            struct.pack_into("<H", result, offset, struct.unpack_from("<H", result, offset)[0] + 1)
    else:
        first_global = (len(result) - effects) // 48
        result.extend(sentinel)
        struct.pack_into("<HH", result, 0x6E, first_global, 1)
    return bytes(result)


class SyntheticCalledShotGame:
    def __init__(self, root: Path, *, globals_first: bool | None = None) -> None:
        self.root = root
        root.mkdir()
        self.override = root / "override"
        self.override.mkdir()
        shutil.copy2(WEIDU, root / "weidu.exe")
        for relative in (INCLUDE, FUNCTIONS, *(SPELLS / name for name in RESOURCES)):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, root / relative)
        if globals_first is not None:
            for name in ("SPCL121.SPL", "C0ARCCS1.SPL"):
                path = root / SPELLS / name
                path.write_bytes(_with_global(path.read_bytes(), first=globals_first))
        self.source = _raw_tree(root / SPELLS)
        bif = _write_marker_key_and_bif(root)
        self.tlk = root / "lang/en_us/dialog.tlk"
        self.tlk.parent.mkdir(parents=True)
        self.tlk.write_bytes(ONE_EMPTY_STRING_TLK)
        (root / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
        self.immutable = {
            path: path.read_bytes()
            for path in (root / "chitin.key", bif, root / "dialog.tlk", root / INCLUDE, root / FUNCTIONS)
        }
        # Existing resources and an unrelated file must survive uninstall exactly.
        (self.override / "SPCL121.SPL").write_bytes(b"previous spell override\n")
        (self.override / "C0ARCCS1.EFF").write_bytes(b"previous effect override\n")
        (self.override / "UNRELATED.IDS").write_bytes(b"IDS V1.0\n1 SENTINEL\n")
        patch = root / "AKCB_ARCHER_CS_TEST/setup-AKCB_ARCHER_CS_TEST.tp2"
        patch.parent.mkdir()
        patch.write_text(
            "BACKUP ~AKCB_ARCHER_CS_TEST/backup~\n"
            "AUTHOR ~synthetic test~\n"
            "BEGIN ~Called Shot production include test~\n"
            "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
            f"INCLUDE ~{FUNCTIONS.as_posix()}~\n"
            f"COPY ~{SPELLS.as_posix()}~ ~override~\n"
            f"INCLUDE ~{INCLUDE.as_posix()}~\n",
            encoding="utf-8",
        )
        self.before = _raw_tree(self.override)

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.root / "weidu.exe"),
                "AKCB_ARCHER_CS_TEST/setup-AKCB_ARCHER_CS_TEST.tp2",
                "--game", str(self.root),
                *[arg for op in (operations or ("--force-install-list",)) for arg in (op, "0")],
                "--language", "0", "--use-lang", "en_us", "--no-exit-pause", "--quick-log",
            ],
            cwd=self.root, capture_output=True, encoding="utf-8", errors="replace",
            timeout=90, check=False,
        )

    def spell(self, resource: str) -> Spell:
        return Spell(_raw_tree(self.override)[f"{resource.upper()}.SPL"])


class ArcherCalledShotTests(unittest.TestCase):
    def _game(self, **kwargs: object) -> SyntheticCalledShotGame:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-archer-cs-")
        self.addCleanup(temporary.cleanup)
        return SyntheticCalledShotGame(Path(temporary.name) / "game", **kwargs)

    def _install(self, game: SyntheticCalledShotGame, *operations: str) -> None:
        process = game.run(*operations)
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("SUCCESSFULLY INSTALLED", process.stdout + process.stderr)
        for path, original in game.immutable.items():
            self.assertEqual(original, path.read_bytes(), str(path))
        self.assertEqual(game.source, _raw_tree(game.root / SPELLS))

    def test_activation_preserves_delivery_and_adds_damage_only_at_level_16(self) -> None:
        game = self._game()
        self._install(game)
        original = Spell(game.source["SPCL121.SPL"])
        installed = game.spell("SPCL121")
        self.assertEqual([1, 16], [struct.unpack_from("<H", h, 16)[0] for h in installed.headers])
        self.assertEqual(original.raw[0x10:0x50], installed.raw[0x10:0x50])
        self.assertEqual(original.raw[0x58:0x64], installed.raw[0x58:0x64])
        self.assertEqual(original.globals, installed.globals)
        for index, (header, effects) in enumerate(zip(installed.headers, installed.abilities)):
            self.assertEqual(original.headers[0][:16], header[:16])
            self.assertEqual(original.headers[0][18:30], header[18:30])
            self.assertEqual(original.headers[0][34:], header[34:])
            reset = effects[0]
            self.assertEqual((321, 1, 1, "SPCL121"), (reset.opcode, reset.target, reset.timing, reset.resource))
            self.assertEqual((0, 0), _save(reset))
            retained = [effect.raw for effect in effects if effect.opcode not in (321, 286)]
            self.assertEqual([effect.raw for effect in original.abilities[0]], retained)
            ranged = [effect for effect in effects if effect.opcode == 249]
            self.assertEqual(1, len(ranged))
            self.assertEqual(("C0ARCCS1", 0, 10), (ranged[0].resource, ranged[0].timing, ranged[0].duration))
            damage = [effect for effect in effects if effect.opcode == 286]
            self.assertEqual(index, len(damage))
            if damage:
                self.assertEqual((1, 2, 0, 0, 10), (damage[0].target, damage[0].parameter1, damage[0].parameter2, damage[0].timing, damage[0].duration))
                self.assertEqual((0, 0), _save(damage[0]))
        for level in (4, 7, 8, 12, 15, 16, 20, 40):
            selected = max(index for index, header in enumerate(installed.headers) if struct.unpack_from("<H", header, 16)[0] <= level)
            self.assertEqual(2 if level >= 16 else 0, sum(effect.parameter1 for effect in installed.abilities[selected] if effect.opcode == 286))

    def test_save_gates_cleanup_and_all_payload_tiers_are_movement_only(self) -> None:
        game = self._game()
        self._install(game)
        output = _raw_tree(game.override)
        original_eff = game.source["C0ARCCS1.EFF"]
        gated = output["C0ARCCS1.EFF"]
        self.assertEqual((4, 0), struct.unpack_from("<Ii", gated, 0x40))
        self.assertEqual(original_eff[:0x40], gated[:0x40])
        self.assertEqual(original_eff[0x48:], gated[0x48:])
        self.assertEqual((146, 2), struct.unpack_from("<II", gated, 0x10))
        self.assertEqual("C0ARCCS1", gated[0x30:0x38].decode("ascii").upper())
        self.assertEqual(1, struct.unpack_from("<I", gated, 0x20)[0])
        original = Spell(game.source["C0ARCCS1.SPL"])
        installed = game.spell("C0ARCCS1")
        self.assertEqual(original.raw[:0x64], installed.raw[:0x64])
        self.assertEqual([1, 8, 12, 16], [struct.unpack_from("<H", h, 16)[0] for h in installed.headers])
        for old_header, header, old_fx, effects in zip(original.headers, installed.headers, original.abilities, installed.abilities):
            self.assertEqual(old_header[:30], header[:30])
            self.assertEqual(old_header[34:], header[34:])
            self.assertEqual([321, 126, 142], [effect.opcode for effect in effects])
            self.assertEqual(old_fx[0].raw, effects[0].raw)
            reset, slow, icon = effects
            self.assertEqual((2, "C0ARCCS1", 1), (reset.target, reset.resource, reset.timing))
            self.assertEqual((75, 5), (slow.parameter1, slow.parameter2))
            self.assertEqual(41, icon.parameter2)
            for effect in (slow, icon):
                self.assertEqual((2, 0, 12), (effect.target, effect.timing, effect.duration))
                self.assertEqual((0, 0), _save(effect))
            self.assertTrue(all(_save(effect) == (0, 0) for effect in effects))
            self.assertFalse(REMOVED & {effect.opcode for effect in effects})

    def test_failed_save_refreshes_once_and_successful_save_preserves_old_slow(self) -> None:
        game = self._game()
        self._install(game)
        delivery = _raw_tree(game.override)["C0ARCCS1.EFF"]
        payload = game.spell("C0ARCCS1")
        active: list[tuple[str, int, float]] = []

        def impact(time: float, *, saved: bool) -> None:
            active[:] = [entry for entry in active if entry[2] > time]
            # Interpret the installed delivery graph, not another copy of its values.
            if saved and struct.unpack_from("<I", delivery, 0x40)[0] & 4:
                return
            for effect in payload.abilities[0]:
                if effect.opcode == 321:
                    active[:] = [entry for entry in active if entry[0] != effect.resource]
                elif effect.opcode == 126:
                    active.append(("C0ARCCS1", effect.parameter1, time + effect.duration))

        impact(0, saved=False)
        self.assertEqual([("C0ARCCS1", 75, 12)], active)
        impact(6, saved=True)
        self.assertEqual([("C0ARCCS1", 75, 12)], active)
        impact(8, saved=False)
        self.assertEqual([("C0ARCCS1", 75, 20)], active)
        impact(9, saved=False)
        self.assertEqual([("C0ARCCS1", 75, 21)], active)
        impact(21, saved=True)
        self.assertEqual([], active)

    def test_casting_features_survive_both_valid_storage_orders(self) -> None:
        for first in (True, False):
            with self.subTest(globals_first=first):
                game = self._game(globals_first=first)
                self._install(game)
                for resource in ("SPCL121", "C0ARCCS1"):
                    source = Spell(game.source[f"{resource}.SPL"])
                    actual = game.spell(resource)
                    self.assertEqual(source.globals, actual.globals)
                    self.assertEqual(1, len(actual.globals))
                    self.assertEqual("AKCBTEST", actual.globals[0].resource)
                activation = game.spell("SPCL121")
                self.assertEqual([6, 7], list(map(len, activation.abilities)))
                self.assertEqual([1, 16], [struct.unpack_from("<H", h, 16)[0] for h in activation.headers])

    def test_description_matches_installed_rules(self) -> None:
        game = self._game()
        self._install(game)
        reference = struct.unpack_from("<I", game.spell("SPCL121").raw, 0x50)[0]
        description = read_tlk_string(game.tlk, reference)
        for phrase in ("10 seconds", "25%", "two rounds", "save vs. Death", "does not stack", "failed save refreshes", "16th level", "+2 bonus to missile weapon damage", "does not depend"):
            self.assertIn(phrase, description)
        for phrase in ("dexterity", "attack per round", "unmitigated", "1 turn"):
            self.assertNotIn(phrase, description.lower())

    def test_reinstall_is_identical_and_uninstall_restores_override(self) -> None:
        game = self._game()
        self._install(game)
        installed = _raw_tree(game.override)
        self.assertEqual(set(game.before) | set(RESOURCES), set(installed))
        self.assertEqual(game.before["UNRELATED.IDS"], installed["UNRELATED.IDS"])
        self._install(game, "--force-uninstall-list", "--force-install-list")
        self.assertEqual(installed, _raw_tree(game.override))
        process = game.run("--force-uninstall-list")
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("SUCCESSFULLY REMOVED", process.stdout + process.stderr)
        self.assertEqual(game.before, _raw_tree(game.override))
        for path, original in game.immutable.items():
            self.assertEqual(original, path.read_bytes(), str(path))
        self.assertFalse(list(game.root.rglob("*.IDS.INSTALLED")))


if __name__ == "__main__":
    unittest.main()
