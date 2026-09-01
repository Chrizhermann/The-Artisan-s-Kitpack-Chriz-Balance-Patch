from __future__ import annotations

import hashlib
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEIDU = ROOT / "Setup-ArtisansKitpack.exe"
PATCH_DIR = ROOT / "live-patch/AKCB_SHAPESHIFTER"
PATCH_TP2 = PATCH_DIR / "setup-AKCB_SHAPESHIFTER.tp2"

GREATER_FOLDERS = (
    "werewolf_greater",
    "werewolf_greater_white",
    "werewolf_greater_grey",
    "werewolf_greater_black",
)
REGULAR_FOLDERS = (
    "werewolf",
    "werewolf_white",
    "werewolf_grey",
    "werewolf_black",
)
TEMPLATE_ROOT = ROOT / "ArtisansKitpack/Druid/Shapeshifter/animations"

SLOTS = {
    "C0_WEREWOLF": 0xE055,
    "C0_WEREWOLF_GREATER": 0xE101,
    "C0_WEREWOLF_GREATER_WHITE": 0xE2A0,
    "C0_WEREWOLF_GREATER_GREY": 0xE00F,
    "C0_WEREWOLF_GREATER_BLACK": 0xEABC,
}
TARGET_SYMBOLS = tuple(symbol for symbol in SLOTS if "GREATER" in symbol)
TARGET_FILES = tuple(f"{SLOTS[symbol]:04x}.ini" for symbol in TARGET_SYMBOLS)
ONE_EMPTY_STRING_TLK = (
    struct.pack("<8sHII", b"TLK V1  ", 0, 1, 0x2C)
    + struct.pack("<H8siiII", 0, b"\0" * 8, 0, 0, 0, 0)
)


def _raw_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix().upper(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_marker_key_and_bif(game_root: Path) -> Path:
    """Create the smallest KEY/BIFF pair that WeiDU recognizes as BG2EE."""

    payload = b"synthetic BG2EE marker"
    bif_relative = Path("data/akcbtest.bif")
    bif_path = game_root / bif_relative
    bif_path.parent.mkdir(parents=True)
    table_offset = 0x14
    payload_offset = table_offset + 0x10
    bif_path.write_bytes(
        struct.pack("<4s4sIII", b"BIFF", b"V1  ", 1, 0, table_offset)
        + struct.pack("<IIIHH", 0, payload_offset, len(payload), 1010, 0)
        + payload
    )

    encoded_bif_name = (str(bif_relative).replace("/", "\\") + "\0").encode(
        "ascii"
    )
    bif_table_offset = 0x18
    resource_table_offset = bif_table_offset + 0x0C
    names_offset = resource_table_offset + 0x0E
    key = bytearray(
        struct.pack(
            "<4s4sIIII",
            b"KEY ",
            b"V1  ",
            1,
            1,
            bif_table_offset,
            resource_table_offset,
        )
    )
    key.extend(
        struct.pack(
            "<IIHH",
            bif_path.stat().st_size,
            names_offset,
            len(encoded_bif_name),
            0,
        )
    )
    key.extend(struct.pack("<8sHI", b"OH6000\0", 1010, 0))
    key.extend(encoded_bif_name)
    (game_root / "chitin.key").write_bytes(key)
    return bif_path


def _ini_payload(symbol: str, personal_space: int) -> bytes:
    newline = b"\r\n" if SLOTS[symbol] % 2 else b"\n"
    return newline.join(
        (
            f"// fixture {symbol}".encode("ascii"),
            b"[general]",
            b"ellipse=16",
            b"color_blood=47",
            b"sound_freq=5",
            f"personal_space={personal_space}".encode("ascii"),
            b"cast_frame=4",
            b"move_scale=9",
            b"",
        )
    )


class SyntheticShapeshifterGame:
    def __init__(
        self,
        temporary: tempfile.TemporaryDirectory[str],
        *,
        installed_component: int | None = 5110,
        initial_personal_space: int = 5,
        missing_target: str | None = None,
        malformed_target: str | None = None,
    ) -> None:
        self.temporary = temporary
        self.root = Path(temporary.name) / "game"
        self.root.mkdir()
        self.override = self.root / "override"
        self.override.mkdir()

        shutil.copy2(WEIDU, self.root / "weidu.exe")
        shutil.copytree(PATCH_DIR, self.root / PATCH_DIR.name)
        self.bif_path = _write_marker_key_and_bif(self.root)

        animate_lines = ["IDS V1.0"]
        animate_lines.extend(
            f"0x{slot:04x} {symbol}" for symbol, slot in SLOTS.items()
        )
        (self.override / "ANIMATE.IDS").write_text(
            "\n".join(animate_lines) + "\n", encoding="ascii", newline="\n"
        )

        for symbol, slot in SLOTS.items():
            if symbol == missing_target:
                continue
            path = self.override / f"{slot:04x}.ini"
            if symbol == malformed_target:
                path.write_bytes(
                    b"// personal_space=3 appears only in this comment\n"
                    b"[general]\nellipse=16\nmove_scale=9\n"
                )
            else:
                space = 3 if symbol == "C0_WEREWOLF" else initial_personal_space
                path.write_bytes(_ini_payload(symbol, space))

        (self.override / "e999.ini").write_bytes(
            b"[general]\npersonal_space=5\nmarker=unrelated\n"
        )
        self.lang_tlk = self.root / "lang/en_US/dialog.tlk"
        self.lang_tlk.parent.mkdir(parents=True)
        self.lang_tlk.write_bytes(ONE_EMPTY_STRING_TLK)
        self.root_tlk = self.root / "dialog.tlk"
        self.root_tlk.write_bytes(ONE_EMPTY_STRING_TLK)

        if installed_component is not None:
            (self.root / "WeiDU.log").write_text(
                "~ARTISANSKITPACK/ARTISANSKITPACK.TP2~ "
                f"#0 #{installed_component} // synthetic prerequisite\n",
                encoding="utf-8",
                newline="\n",
            )

        self.before = _raw_tree(self.override)
        self.stable_hashes = {
            "key": _sha256(self.root / "chitin.key"),
            "bif": _sha256(self.bif_path),
            "lang_tlk": _sha256(self.lang_tlk),
            "root_tlk": _sha256(self.root_tlk),
        }

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        operation_arguments = [
            argument
            for operation in operations
            for argument in (operation, "0")
        ]
        return subprocess.run(
            [
                str(self.root / "weidu.exe"),
                "AKCB_SHAPESHIFTER/setup-AKCB_SHAPESHIFTER.tp2",
                "--game",
                str(self.root),
                *operation_arguments,
                "--language",
                "0",
                "--use-lang",
                "en_US",
                "--no-exit-pause",
                "--quick-log",
            ],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )

    @staticmethod
    def transcript(process: subprocess.CompletedProcess[str]) -> str:
        return f"{process.stdout}\n{process.stderr}".strip()

    def active_weidu_log(self) -> str:
        path = self.root / "WeiDU.log"
        if not path.exists():
            return ""
        return "\n".join(
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not line.lstrip().startswith("//")
        )

    def assert_stable_inputs(self, testcase: unittest.TestCase) -> None:
        testcase.assertEqual(self.stable_hashes["key"], _sha256(self.root / "chitin.key"))
        testcase.assertEqual(self.stable_hashes["bif"], _sha256(self.bif_path))
        testcase.assertEqual(self.stable_hashes["lang_tlk"], _sha256(self.lang_tlk))
        testcase.assertEqual(self.stable_hashes["root_tlk"], _sha256(self.root_tlk))


class ShapeshifterSourceTemplateTests(unittest.TestCase):
    def test_all_player_werewolf_templates_use_humanoid_personal_space(self) -> None:
        for folder in GREATER_FOLDERS + REGULAR_FOLDERS:
            with self.subTest(folder=folder):
                path = TEMPLATE_ROOT / folder / "exxx.ini"
                personal_space_lines = [
                    line.strip().lower()
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip().lower().startswith("personal_space=")
                ]
                self.assertEqual(["personal_space=3"], personal_space_lines)


class ShapeshifterTailPatchTests(unittest.TestCase):
    def _require_patch(self) -> None:
        self.assertTrue(PATCH_TP2.is_file(), f"missing tail patch: {PATCH_TP2}")

    def _game(self, **kwargs: object) -> SyntheticShapeshifterGame:
        self._require_patch()
        temporary = tempfile.TemporaryDirectory(prefix="akcb-shapeshifter-")
        self.addCleanup(temporary.cleanup)
        return SyntheticShapeshifterGame(temporary, **kwargs)

    def _assert_installed(
        self,
        game: SyntheticShapeshifterGame,
        process: subprocess.CompletedProcess[str],
    ) -> None:
        transcript = game.transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertRegex(game.active_weidu_log(), r"(?m)#0\s+#0\b")
        game.assert_stable_inputs(self)

    def _assert_not_installed(
        self,
        game: SyntheticShapeshifterGame,
        process: subprocess.CompletedProcess[str],
    ) -> None:
        transcript = game.transcript(process)
        self.assertNotIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertNotRegex(game.active_weidu_log(), r"(?m)#0\s+#0\b")
        game.assert_stable_inputs(self)

    def test_remapped_slots_patch_only_four_targets_and_uninstall_byte_exact(self) -> None:
        game = self._game(installed_component=5110)
        process = game.run("--force-install-list")
        self._assert_installed(game, process)

        after = _raw_tree(game.override)
        self.assertEqual(set(game.before), set(after))
        for relative, original in game.before.items():
            if relative.lower() in TARGET_FILES:
                expected = re.sub(
                    rb"(?m)^personal_space=[0-9]+",
                    b"personal_space=3",
                    original,
                )
                self.assertEqual(expected, after[relative], relative)
            else:
                self.assertEqual(original, after[relative], relative)

        process = game.run("--force-uninstall-list")
        transcript = game.transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertNotIn("NOT UNINSTALLED", transcript, transcript)
        self.assertEqual(game.before, _raw_tree(game.override))
        game.assert_stable_inputs(self)

    def test_component_5111_and_already_fixed_inputs_are_idempotent(self) -> None:
        game = self._game(installed_component=5111, initial_personal_space=3)
        process = game.run("--force-install-list")
        self._assert_installed(game, process)
        self.assertEqual(game.before, _raw_tree(game.override))

        process = game.run("--force-uninstall-list")
        transcript = game.transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_paired_reinstall_matches_first_installed_tree(self) -> None:
        game = self._game(installed_component=5110)
        process = game.run("--force-install-list")
        self._assert_installed(game, process)
        first_installed = _raw_tree(game.override)

        process = game.run("--force-uninstall-list", "--force-install-list")
        self._assert_installed(game, process)
        self.assertEqual(first_installed, _raw_tree(game.override))

    def test_missing_artisan_component_skips_without_mutation(self) -> None:
        game = self._game(installed_component=None)
        process = game.run("--force-install-list")
        self._assert_not_installed(game, process)
        self.assertIn("SKIPPING", game.transcript(process))
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_missing_target_ini_fails_before_mutation(self) -> None:
        game = self._game(missing_target="C0_WEREWOLF_GREATER_BLACK")
        process = game.run("--force-install-list")
        self._assert_not_installed(game, process)
        self.assertIn("NOT INSTALLED DUE TO ERRORS", game.transcript(process))
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_comment_cannot_substitute_for_real_personal_space_key(self) -> None:
        game = self._game(malformed_target="C0_WEREWOLF_GREATER_BLACK")
        process = game.run("--force-install-list")
        self._assert_not_installed(game, process)
        self.assertIn("NOT INSTALLED DUE TO ERRORS", game.transcript(process))
        self.assertEqual(game.before, _raw_tree(game.override))


if __name__ == "__main__":
    unittest.main()
