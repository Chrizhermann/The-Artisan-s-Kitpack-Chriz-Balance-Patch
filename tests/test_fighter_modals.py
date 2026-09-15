from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_shapeshifter_personal_space import _write_marker_key_and_bif


ROOT = Path(__file__).resolve().parents[1]
TAIL = ROOT / "live-patch/AKCB_FIGHTER_MODALS"
TP2 = "AKCB_FIGHTER_MODALS/setup-AKCB_FIGHTER_MODALS.tp2"
PAYLOADS = ("c0fig01a", "c0fig01b", "c0fig02a", "c0fig02b")
POWER_OLD = "sacrificing 3 points of melee THAC0 to increase their melee damage by 3."
POWER_NEW = "sacrificing 2 points of melee THAC0 to increase their melee damage by 2."
EXPERT_OLD = "sacrificing 3 points of THAC0 to increase their Armor Class by 3."
EXPERT_NEW = "sacrificing 2 points of THAC0 to increase their Armor Class by 2."
IMPROVED_OLD = "which provide 6 points to the original abilities' bonuses and penalties."
IMPROVED_NEW = "which provide 4 points to the original abilities' bonuses and penalties."
SINGLE_OLD = "which provide 6 points to the original ability's bonuses and penalties."
SINGLE_NEW = "which provides 4 points to the original ability's bonuses and penalties."
CHANGES = ((POWER_OLD, POWER_NEW), (EXPERT_OLD, EXPERT_NEW),
           (IMPROVED_OLD, IMPROVED_NEW), (SINGLE_OLD, SINGLE_NEW))


def _new_text(text: str) -> str:
    for old, new in CHANGES:
        text = text.replace(old, new)
    return text


def _write_tlk(path: Path, strings: list[str]) -> None:
    payload = bytearray()
    rows = bytearray()
    for text in strings:
        encoded = text.encode("utf-8")
        rows += struct.pack("<H8siiII", 7, b"\0" * 8, 0, 0, len(payload), len(encoded))
        payload += encoded
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<8sHII", b"TLK V1  ", 0, len(strings),
                                 18 + 26 * len(strings)) + rows + payload)


def _tlk_entries(data: bytes) -> list[tuple[bytes, bytes]]:
    count, start = struct.unpack_from("<II", data, 10)
    entries = []
    for index in range(count):
        row = data[18 + index * 26:18 + (index + 1) * 26]
        offset, size = struct.unpack_from("<II", row, 18)
        entries.append((row[:18], data[start + offset:start + offset + size]))
    return entries


def _state(game: Path) -> dict[str, bytes]:
    paths = [*game.joinpath("override").iterdir(), game / "lang/en_us/dialog.tlk",
             game / "chitin.key", game / "data/akcbtest.bif"]
    return {p.relative_to(game).as_posix().upper(): p.read_bytes() for p in paths}


def _active_log(game: Path) -> list[str]:
    return [line.split("//")[0].strip().upper()
            for line in (game / "WeiDU.log").read_text().splitlines()
            if line.startswith("~")]


def _payload_value(data: bytes, name: str, *, old: bool) -> bytes:
    """Only reverse the committed source stat values to create a pre-update fixture."""
    output = bytearray(data)
    value = (3 if old else 2) if name.endswith("a") else (6 if old else 4)
    wanted = {(284, 0): -value, (73, 0): value, (286, 0): -value}
    if name.startswith("c0fig02"):
        wanted = {(54, 0): -value, **{(0, mode): value for mode in (1, 2, 4, 8)}}
    effects = struct.unpack_from("<I", data, 0x6a)[0]
    for pos in range(effects, len(data), 48):
        key = (struct.unpack_from("<H", data, pos)[0],
               struct.unpack_from("<I", data, pos + 8)[0])
        if key in wanted:
            struct.pack_into("<i", output, pos + 4, wanted[key])
    return bytes(output)


class FighterModalTests(unittest.TestCase):
    def _fixture(self, *, optional: bool = False, old: bool = True,
                 prerequisite: bool = True) -> tuple[Path, set[int]]:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-fighter-modals-")
        self.addCleanup(temporary.cleanup)
        game = Path(temporary.name)
        (game / "override").mkdir()
        _write_marker_key_and_bif(game)
        shutil.copy2(ROOT / "Setup-ArtisansKitpack.exe", game / "weidu.exe")
        shutil.copytree(TAIL, game / TAIL.name)
        # Include percent tokens and unrelated prose to detect accidental evaluation
        # or a replacement of the whole installed description by source text.
        suffix = "\nInstalled note: %SOURCE_FILE% <CHARNAME>; unrelated damage by 3."
        strings = ["Unrelated spell: " + POWER_OLD,
                   "Power Attack: " + POWER_OLD + suffix,
                   "Expertise: " + EXPERT_OLD + suffix,
                   "Fighter: " + POWER_OLD + "\n" + EXPERT_OLD + "\n" + IMPROVED_OLD + suffix,
                   "Barbarian: " + POWER_OLD + "\n" + SINGLE_OLD + suffix,
                   "Divine Champion: " + POWER_OLD + "\n" + EXPERT_OLD + "\n" + IMPROVED_OLD,
                   "Rashemi Berserker: " + POWER_OLD + "\n" + SINGLE_OLD,
                   "DD Power Attack: " + POWER_OLD,
                   "DD Expertise: " + EXPERT_OLD,
                   "Campaign Barbarian: " + POWER_OLD + "\n" + SINGLE_OLD,
                   "Plain unrelated description."]
        selected = {1, 2, 3} | (set(range(4, 10)) if optional else set())
        if not old:
            strings = [_new_text(text) if i in selected else text
                       for i, text in enumerate(strings)]
        _write_tlk(game / "lang/en_us/dialog.tlk", strings)
        source = ROOT / "ArtisansKitpack/Fighter/spells"
        for name in PAYLOADS:
            data = (source / (name + ".SPL")).read_bytes()
            (game / "override" / (name + ".spl")).write_bytes(_payload_value(data, name, old=old))
        entries = [("c0fig01", "c0fig01", 1), ("c0fig02", "c0fig02", 2)]
        if optional:
            entries += [("c0dwd01", "c0fig01", 7), ("c0dwd02", "c0fig02", 8)]
        for name, donor, ref in entries:
            data = bytearray((source / (donor + ".SPL")).read_bytes())
            struct.pack_into("<i", data, 0x50, ref)
            (game / "override" / (name + ".spl")).write_bytes(data)
        kit_rows = ["0 OTHER 10 10 10 CLABFI01 29 0 2 0"]
        if optional:
            kit_rows += ["1 BARBARIAN 10 10 4 CLABFI05 29 0 2 1",
                         "2 C0DC 10 10 5 C0DC 29 0 6 2",
                         "3 C0TBM 10 10 6 C0TBM 29 0 12 3"]
        else:
            kit_rows += ["1 BARBARIAN 10 10 10 CLABFI05 29 0 2 1"]
        (game / "override/KITLIST.2DA").write_text(
            "2DA V1.0\n*\nROWNAME LOWER MIXED HELP ABILITIES PROFICIENCY UNUSABLE CLASS KITIDS\n"
            + "\n".join(kit_rows) + "\n")
        class_rows = ["FIGHTER 2 16384 10 3 10 -1 0 10 -1", "THIEF 4 16384 10 10 10 -1 0 10 -1"]
        if optional:
            class_rows += ["BARBARIAN 2 1 10 9 10 -1 0 10 -1",
                           "C0DC 6 2 10 5 10 -1 0 10 -1",
                           "C0TBM 12 3 10 6 10 -1 0 10 -1"]
        else:
            class_rows += ["BARBARIAN 2 1 10 10 10 -1 0 10 -1"]
        for table in (("CLASTEXT", "BGCLATXT", "SODCLTXT") if optional else ("CLASTEXT",)):
            (game / "override" / (table + ".2da")).write_text(
                "2DA V1.0\n-1\nCLASSID KITID LOWER DESCSTR MIXED BIOGRAPHY FALLEN BRIEFDESC FALLEN_NOTICE\n"
                + "\n".join(class_rows) + "\n")
        (game / "WeiDU.log").write_text(
            "~ARTISANSKITPACK/ARTISANSKITPACK.TP2~ #0 #1100 // prerequisite\n"
            if prerequisite else "")
        return game, selected

    def _invoke(self, game: Path, *, uninstall: bool = False, success: bool = True) -> str:
        run = subprocess.run(
            [str(game / "weidu.exe"), TP2, "--game", str(game),
             "--force-uninstall-list" if uninstall else "--force-install-list", "0",
             "--language", "0", "--use-lang", "en_US", "--no-exit-pause", "--quick-log"],
            cwd=game, capture_output=True, text=True, errors="replace", timeout=90,
        )
        transcript = run.stdout + run.stderr
        if success:
            self.assertEqual(0, run.returncode, transcript)
            self.assertIn("SUCCESSFULLY REMOVED" if uninstall else "SUCCESSFULLY INSTALLED", transcript)
            self.assertNotIn("ERROR", transcript)
        else:
            self.assertIn("NOT INSTALLED DUE TO ERRORS", transcript)
        return transcript

    def _check_changes(self, before: dict[str, bytes], after: dict[str, bytes], refs: set[int]) -> None:
        self.assertEqual(before.keys(), after.keys())
        expected = dict(before)
        for name in PAYLOADS:
            key = "OVERRIDE/" + name.upper() + ".SPL"
            expected[key] = _payload_value(before[key], name, old=False)
        for key in before:
            if key != "LANG/EN_US/DIALOG.TLK":
                self.assertEqual(expected[key], after[key], key)
        old = _tlk_entries(before["LANG/EN_US/DIALOG.TLK"])
        new = _tlk_entries(after["LANG/EN_US/DIALOG.TLK"])
        self.assertEqual(len(old), len(new))
        for index, ((metadata, text), actual) in enumerate(zip(old, new)):
            replacement = _new_text(text.decode("utf-8")).encode("utf-8") if index in refs else text
            self.assertEqual((metadata, replacement), actual, index)

    def _roundtrip(self, game: Path, refs: set[int]) -> None:
        before, log = _state(game), _active_log(game)
        self._invoke(game)
        self._check_changes(before, _state(game), refs)
        self.assertEqual(log, _active_log(game)[:-1])
        self._invoke(game, uninstall=True)
        self.assertEqual(before, _state(game))
        self.assertEqual(log, _active_log(game))

    def test_old_tradeoffs_without_optional_kits_roundtrip(self) -> None:
        self._roundtrip(*self._fixture())

    def test_optional_kits_and_distinct_campaign_descriptions_roundtrip(self) -> None:
        self._roundtrip(*self._fixture(optional=True))

    def test_current_source_tradeoffs_are_idempotent(self) -> None:
        game, refs = self._fixture(optional=True, old=False)
        before = _state(game)
        self._invoke(game)
        self.assertEqual(before, _state(game))
        self._invoke(game, uninstall=True)
        self.assertEqual(before, _state(game))

    def test_unrelated_installed_effect_and_text_are_preserved(self) -> None:
        game, refs = self._fixture(optional=True)
        path = game / "override/c0fig01a.spl"
        data = bytearray(path.read_bytes())
        header = struct.unpack_from("<I", data, 0x64)[0]
        count = struct.unpack_from("<H", data, header + 0x1e)[0]
        struct.pack_into("<H", data, header + 0x1e, count + 1)
        extra = bytearray(48)
        struct.pack_into("<HBBiiBBIBB", extra, 0, 142, 2, 0, 77, 88, 0, 2, 15, 100, 0)
        extra[20:28] = b"DW#GUARD"
        path.write_bytes(data + extra)
        self._roundtrip(game, refs)

    def test_unexpected_stat_or_effect_shape_rolls_back(self) -> None:
        for field, replacement in ((4, struct.pack("<i", -9)), (2, b"\1"), (12, b"\0")):
            with self.subTest(field=field):
                game, _ = self._fixture()
                path = game / "override/c0fig02b.spl"
                data = bytearray(path.read_bytes())
                start = struct.unpack_from("<I", data, 0x6a)[0]
                pos = next(p for p in range(start, len(data), 48)
                           if struct.unpack_from("<H", data, p)[0] == 54)
                data[pos + field:pos + field + len(replacement)] = replacement
                path.write_bytes(data)
                before = _state(game)
                self._invoke(game, success=False)
                self.assertEqual(before, _state(game))

    def test_duplicate_stat_effect_rolls_back(self) -> None:
        game, _ = self._fixture()
        path = game / "override/c0fig02b.spl"
        data = bytearray(path.read_bytes())
        header = struct.unpack_from("<I", data, 0x64)[0]
        count = struct.unpack_from("<H", data, header + 0x1e)[0]
        struct.pack_into("<H", data, header + 0x1e, count + 1)
        path.write_bytes(data + data[-48:])
        before = _state(game)
        self._invoke(game, success=False)
        self.assertEqual(before, _state(game))

    def test_unsupported_english_wording_rolls_back_prior_changes(self) -> None:
        for malformed in ("sacrificing 3 points of THAC0 for a different bonus.",
                          POWER_NEW.replace("damage by 2", "damage by 9"),
                          "Untranslated modal description."):
            with self.subTest(malformed=malformed):
                game, _ = self._fixture()
                path = game / "lang/en_us/dialog.tlk"
                strings = [entry[1].decode("utf-8") for entry in _tlk_entries(path.read_bytes())]
                strings[3] = malformed
                _write_tlk(path, strings)
                before = _state(game)
                self._invoke(game, success=False)
                self.assertEqual(before, _state(game))

    def test_modified_description_flags_use_weidu_normalization_and_restore(self) -> None:
        game, refs = self._fixture()
        path = game / "lang/en_us/dialog.tlk"
        data = bytearray(path.read_bytes())
        struct.pack_into("<H", data, 18 + 26, 1)
        path.write_bytes(data)
        before = _state(game)
        self._invoke(game)
        after = _state(game)
        expected_before = dict(before)
        normalized = bytearray(before["LANG/EN_US/DIALOG.TLK"])
        struct.pack_into("<H", normalized, 18 + 26, 7)
        expected_before["LANG/EN_US/DIALOG.TLK"] = bytes(normalized)
        self._check_changes(expected_before, after, refs)
        self._invoke(game, uninstall=True)
        self.assertEqual(before, _state(game))

    def test_missing_fighter_prerequisite_skips_without_changes(self) -> None:
        game, _ = self._fixture(prerequisite=False)
        before = _state(game)
        run = subprocess.run(
            [str(game / "weidu.exe"), TP2, "--force-install-list", "0", "--language", "0",
             "--use-lang", "en_US", "--no-exit-pause", "--quick-log"],
            cwd=game, capture_output=True, text=True, errors="replace", timeout=90,
        )
        self.assertIn("SKIPPING", run.stdout + run.stderr)
        self.assertEqual(before, _state(game))


if __name__ == "__main__":
    unittest.main()
