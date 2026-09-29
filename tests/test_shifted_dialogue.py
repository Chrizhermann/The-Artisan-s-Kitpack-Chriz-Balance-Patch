"""Real WeiDU checks on disposable synthetic games; no live-engine assertion."""
from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK, ROOT, WEIDU, _raw_tree, _write_marker_key_and_bif,
)

COMPONENT = 51010
TP2 = Path("ArtisansKitpack_tweak/ArtisansKitpack_tweak.TP2")
SHIFTER = {name: ROOT / f"ArtisansKitpack/Druid/Shapeshifter/spells/{name}"
           for name in ("C0SS-W.ITM", "C0SS-F.ITM")}
HIVE = {f"C0PHIVE{i}.ITM": ROOT / f"ArtisansKitpack/Druid/Hivemaster/spells/c0phive{i}.itm"
        for i in range(1, 5)}


def slices(raw: bytes) -> tuple[list[bytes], list[list[bytes]]]:
    ability_offset, ability_count, effect_offset, first, count = struct.unpack_from("<IHIHH", raw, 0x64)
    def effects(start: int, length: int) -> list[bytes]:
        return [raw[effect_offset + n * 48:effect_offset + (n + 1) * 48]
                for n in range(start, start + length)]
    abilities = []
    for index in range(ability_count):
        length, start = struct.unpack_from("<HH", raw, ability_offset + index * 56 + 0x1E)
        abilities.append(effects(start, length))
    return effects(first, count), abilities


def is_form_talk(effect: bytes) -> bool:
    return (struct.unpack_from("<H", effect)[0] == 144 and effect[2] == 1
            and struct.unpack_from("<I", effect, 8)[0] == 7 and effect[12] == 2)


def with_other_restrictions(raw: bytes) -> bytes:
    # Add distinct equipped restrictions; the optional patch must not erase them.
    data = bytearray(raw)
    offset = struct.unpack_from("<I", data, 0x6A)[0]
    first, count = struct.unpack_from("<HH", data, 0x6E)
    at = offset + (first + count) * 48
    added = bytearray()
    for opcode, button, timing, target in ((144, 2, 2, 1), (144, 8, 2, 1),
                                           (38, 0, 2, 1), (144, 7, 0, 1),
                                           (144, 7, 2, 2)):
        record = bytearray(48)
        struct.pack_into("<HBBiiBBI", record, 0, opcode, target, 0, 0, button, timing, 2, 6)
        record[18] = 100
        added.extend(record)
    data[at:at] = added
    struct.pack_into("<H", data, 0x70, count + 5)
    abilities, n = struct.unpack_from("<IH", data, 0x64)
    for i in range(n):
        field = abilities + i * 56 + 0x20
        index = struct.unpack_from("<H", data, field)[0]
        if index >= first + count:
            struct.pack_into("<H", data, field, index + 5)
    return bytes(data)


class ShiftedDialogueTests(unittest.TestCase):
    def game(self, installed: tuple[int, ...] = (5100, 5002), *, missing: str | None = None,
             extras: bool = False) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-shifted-dialogue-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "override").mkdir()
        shutil.copy2(WEIDU, root / "weidu.exe")
        shutil.copytree(ROOT / "ArtisansKitpack/lib", root / "ArtisansKitpack/lib")
        (root / TP2).parent.mkdir()
        shutil.copy2(ROOT / TP2, root / TP2)
        _write_marker_key_and_bif(root)
        for name in ("dialog.tlk", "lang/en_us/dialog.tlk"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ONE_EMPTY_STRING_TLK)
        for name, source in (SHIFTER | HIVE).items():
            if name != missing:
                raw = source.read_bytes()
                (root / "override" / name).write_bytes(with_other_restrictions(raw) if extras else raw)
        (root / "override/OTHER.ITM").write_bytes(SHIFTER["C0SS-W.ITM"].read_bytes())
        (root / "WeiDU.log").write_text("".join(
            f"~ARTISANSKITPACK/ARTISANSKITPACK.TP2~ #0 #{number} // fixture\n"
            for number in installed), encoding="ascii")
        return root

    def run_weidu(self, root: Path, *operations: str, expected_exit: int = 0) -> str:
        result = subprocess.run(
            [str(root / "weidu.exe"), TP2.as_posix(), "--game", str(root),
             *[arg for operation in (operations or ("--force-install-list",))
               for arg in (operation, str(COMPONENT))],
             "--language", "0", "--use-lang", "en_us", "--no-exit-pause", "--quick-log"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = result.stdout + result.stderr
        self.assertEqual(expected_exit, result.returncode, output)
        self.assertNotIn("NOT INSTALLED DUE TO ERRORS", output)
        return output

    def assert_changes(self, before: dict[str, bytes], after: dict[str, bytes], selected: set[str]) -> None:
        self.assertEqual(before.keys(), after.keys())
        for name, original in before.items():
            if name not in selected:
                self.assertEqual(original, after[name], name)
                continue
            equipped, abilities = slices(original)
            self.assertEqual(([e for e in equipped if not is_form_talk(e)], abilities), slices(after[name]), name)
            # Text, usability, combat fields and other header metadata stay exact.
            self.assertEqual(original[:0x64], after[name][:0x64], name)
            old_offset, old_count = struct.unpack_from("<IH", original, 0x64)
            new_offset, new_count = struct.unpack_from("<IH", after[name], 0x64)
            self.assertEqual(old_count, new_count, name)
            for index in range(old_count):
                old_header = original[old_offset + index * 56:old_offset + (index + 1) * 56]
                new_header = after[name][new_offset + index * 56:new_offset + (index + 1) * 56]
                # Removing equipped effects may relocate an ability's effect index,
                # but its count, damage, range and every other ability field stay exact.
                self.assertEqual(old_header[:0x20] + old_header[0x22:],
                                 new_header[:0x20] + new_header[0x22:], name)
            if not any(map(is_form_talk, equipped)):
                self.assertEqual(original, after[name], name)

    def test_both_kits_preserve_other_restrictions_and_restore_exactly(self) -> None:
        root = self.game(extras=True)
        before = _raw_tree(root / "override")
        stable = {name: (root / name).read_bytes()
                  for name in ("dialog.tlk", "lang/en_us/dialog.tlk", "chitin.key", "data/akcbtest.bif")}
        self.assertIn("SUCCESSFULLY INSTALLED", self.run_weidu(root))
        once = _raw_tree(root / "override")
        self.assert_changes(before, once, set(SHIFTER | HIVE))
        self.run_weidu(root, "--force-uninstall-list", "--force-install-list")
        self.assertEqual(once, _raw_tree(root / "override"))
        self.run_weidu(root, "--force-uninstall-list")
        self.assertEqual(before, _raw_tree(root / "override"))
        for name, original in stable.items():
            self.assertEqual(original, (root / name).read_bytes(), name)

    def test_each_kit_only_patches_its_own_items(self) -> None:
        for component, selected in ((5100, set(SHIFTER)), (5002, set(HIVE))):
            with self.subTest(component=component):
                root = self.game((component,))
                before = _raw_tree(root / "override")
                self.run_weidu(root)
                self.assert_changes(before, _raw_tree(root / "override"), selected)

    def test_without_either_kit_skips_unchanged(self) -> None:
        root = self.game(())
        before = _raw_tree(root / "override")
        self.assertIn("SKIPPING", self.run_weidu(root))
        self.assertEqual(before, _raw_tree(root / "override"))

    def test_missing_item_warns_and_other_forms_still_patch(self) -> None:
        root = self.game(missing="C0PHIVE2.ITM")
        before = _raw_tree(root / "override")
        output = self.run_weidu(root, expected_exit=3)
        self.assertIn("C0PHIVE2.ITM is missing", output)
        self.assertIn("INSTALLED WITH WARNINGS", output)
        self.assert_changes(before, _raw_tree(root / "override"), set(SHIFTER | HIVE))

    def test_already_unrestricted_items_are_idempotent(self) -> None:
        root = self.game()
        self.run_weidu(root)
        patched = _raw_tree(root / "override")
        self.run_weidu(root, "--force-uninstall-list")
        for name, data in patched.items():
            (root / "override" / name).write_bytes(data)
        self.run_weidu(root)
        self.assertEqual(patched, _raw_tree(root / "override"))


if __name__ == "__main__":
    unittest.main()
