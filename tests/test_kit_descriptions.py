from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_shapeshifter_personal_space import _write_marker_key_and_bif


ROOT = Path(__file__).resolve().parents[1]
WEIDU = ROOT / "Setup-ArtisansKitpack.exe"
LIBRARIES = (
    ROOT / "ArtisansKitpack/lib/kit_strref.tpa",
    ROOT / "live-patch/AKCB_BERSERKER/lib/kit_strref.tpa",
    ROOT / "live-patch/AKCB_KIT_DESCRIPTIONS/lib/kit_strref.tpa",
)
TAIL_DIR = ROOT / "live-patch/AKCB_KIT_DESCRIPTIONS"
TAIL_TP2 = "AKCB_KIT_DESCRIPTIONS/setup-AKCB_KIT_DESCRIPTIONS.tp2"
CLASS_TABLES = ("BGCLATXT", "CLASTEXT", "SODCLTXT")
# Native table layouts and class/kit identities; small TLK references are fixture data.
KIT_ROWS = (
    ("1", "BERSERKER", "1", "6", "15", "CLABFI02", "29", "0x00000001", "2", "0x00004001"),
    ("10", "ASSASIN", "2", "7", "11", "CLABTH02", "38", "0x00040000", "4", "0x0000400A"),
    ("7", "FERALAN", "3", "8", "12", "CLABRN02", "35", "0x00008000", "12", "0x00004007"),
    ("9", "BEASTMASTER", "4", "9", "13", "CLABRN04", "37", "0x00020000", "12", "0x00004009"),
    ("18", "BEAST_FRIEND", "5", "10", "14", "CLABDR04", "46", "0x20000000", "11", "0x00004012"),
)
CLASS_ROWS = (
    ("ASSASSIN", "4", "10", "2", "21", "7", "-1", "0", "17", "-1"),
    ("ARCHER", "12", "7", "3", "22", "8", "-1", "0", "18", "19"),
    ("BEAST_MASTER", "12", "9", "4", "23", "9", "-1", "0", "18", "19"),
    ("AVENGER", "11", "18", "5", "24", "10", "-1", "0", "20", "-1"),
    ("BERSERKER", "2", "1", "1", "25", "6", "-1", "0", "16", "-1"),
    ("ASSASIN", "4", "10", "2", "26", "7", "-1", "0", "17", "-1"),
    ("FERALAN", "12", "7", "3", "27", "8", "-1", "0", "18", "19"),
    ("BEASTMASTER", "12", "9", "4", "28", "9", "-1", "0", "18", "19"),
    ("BEAST_FRIEND", "11", "18", "5", "29", "10", "-1", "0", "20", "-1"),
    ("FALLEN_RANGER", "12", "16384", "4", "30", "9", "-1", "1", "18", "-1"),
    ("FALLEN_PALADIN", "6", "16384", "1", "31", "6", "-1", "1", "16", "-1"),
    ("THIEF", "4", "16384", "2", "32", "7", "-1", "0", "17", "-1"),
)


def _table(header: str, rows: tuple[tuple[str, ...], ...], default: str = "*") -> str:
    return "2DA V1.0\n" + default + "\n" + header + "\n" + "\n".join(
        " ".join(row) for row in rows
    ) + "\n"


def _rows(path: Path) -> list[list[str]]:
    return [line.split() for line in path.read_text(encoding="ascii").splitlines()[3:]
            if line.strip()]


class KitDescriptionTests(unittest.TestCase):
    def _create_game(
        self,
        *,
        kit_rows: tuple[tuple[str, ...], ...] = KIT_ROWS,
        class_rows: tuple[tuple[str, ...], ...] = CLASS_ROWS,
        tables: tuple[str, ...] = CLASS_TABLES,
    ) -> tuple[Path, dict[Path, bytes]]:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-kit-description-")
        self.addCleanup(temporary.cleanup)
        game = Path(temporary.name)
        override = game / "override"
        override.mkdir()
        shutil.copy2(WEIDU, game / "weidu.exe")
        bif = _write_marker_key_and_bif(game)

        # Use real, valid TLK indices without allocating the original game strings.
        entry_count = 64
        empty_tlk = struct.pack(
            "<8sHII", b"TLK V1  ", 0, entry_count, 0x12 + 26 * entry_count
        ) + struct.pack("<H8siiII", 0, b"\0" * 8, 0, 0, 0, 0) * entry_count
        lang_tlk = game / "lang/en_us/dialog.tlk"
        lang_tlk.parent.mkdir(parents=True)
        lang_tlk.write_bytes(empty_tlk)
        root_tlk = game / "dialog.tlk"
        root_tlk.write_bytes(empty_tlk)
        kitlist = override / "KITLIST.2DA"
        kitlist.write_text(
            _table("ROWNAME LOWER MIXED HELP ABILITIES PROFICIENCY UNUSABLE CLASS KITIDS", kit_rows),
            encoding="ascii",
        )
        for table in tables:
            (override / f"{table}.2DA").write_text(
                _table(
                    "CLASSID KITID LOWER DESCSTR MIXED BIOGRAPHY FALLEN BRIEFDESC FALLEN_NOTICE",
                    class_rows, default="-1",
                ), encoding="ascii",
            )
        stable_files = (game / "chitin.key", bif, lang_tlk, root_tlk, kitlist)
        originals = {path: path.read_bytes() for path in stable_files}
        return game, originals

    @staticmethod
    def _invoke(
        game: Path, tp2: str, operation: str = "--force-install-list"
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        process = subprocess.run(
            [
                str(game / "weidu.exe"), tp2, "--game", str(game),
                operation, "0", "--language", "0", "--use-lang",
                "en_US", "--no-exit-pause", "--quick-log",
            ],
            cwd=game, capture_output=True, encoding="utf-8", errors="replace",
            timeout=90, check=False,
        )
        return process, process.stdout + "\n" + process.stderr

    def _assert_stable_inputs(self, originals: dict[Path, bytes]) -> None:
        for path, original in originals.items():
            self.assertEqual(original, path.read_bytes(), str(path))

    def _run_helper(
        self,
        library: Path,
        calls: tuple[str, ...],
        *,
        kit_rows: tuple[tuple[str, ...], ...] = KIT_ROWS,
        class_rows: tuple[tuple[str, ...], ...] = CLASS_ROWS,
        tables: tuple[str, ...] = CLASS_TABLES,
    ) -> tuple[Path, str]:
        game, originals = self._create_game(
            kit_rows=kit_rows, class_rows=class_rows, tables=tables
        )
        override = game / "override"
        shutil.copy2(library, game / "kit_strref.tpa")

        actions = []
        for index, kit_name in enumerate(calls):
            actions.extend((
                f"LAF GET_KIT_STRREF STR_VAR kit_name = ~{kit_name}~ RET kit_strref END",
                f"PRINT ~AKCB_RETURN_{index}=%kit_strref%~",
            ))
        (game / "harness.tp2").write_text(
            "BACKUP ~backup~\nAUTHOR ~synthetic test~\n"
            "BEGIN ~Kit description fixture~\n"
            "INCLUDE ~kit_strref.tpa~\n" + "\n".join(actions) + "\n",
            encoding="ascii",
        )
        process, transcript = self._invoke(game, "harness.tp2")
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        self._assert_stable_inputs(originals)
        self.assertEqual(
            {"KITLIST.2DA", *(f"{table}.2DA" for table in tables)},
            {path.name.upper() for path in override.iterdir()},
        )
        return override, transcript

    def _assert_returns(self, transcript: str, expected: list[int]) -> None:
        found = re.findall(r"^AKCB_RETURN_\d+=(-?\d+)\s*$", transcript, re.MULTILINE)
        self.assertEqual(expected, [int(value) for value in found], transcript)

    def test_bundled_helpers_match(self) -> None:
        for library in LIBRARIES[1:]:
            with self.subTest(library=str(library)):
                self.assertEqual(LIBRARIES[0].read_bytes(), library.read_bytes())

    def test_aliases_update_all_class_tables_and_preserve_other_cells(self) -> None:
        expected = [list(row) for row in CLASS_ROWS]
        for row, strref in zip(expected, (11, 12, 13, 14, 15, 11, 12, 13, 14)):
            row[4] = str(strref)
        for library in LIBRARIES:
            with self.subTest(library=str(library)):
                override, transcript = self._run_helper(
                    library, ("asSaSin", "FERALAN", "BEASTMASTER", "BEAST_FRIEND", "BERSERKER")
                )
                self._assert_returns(transcript, [11, 12, 13, 14, 15])
                for table in CLASS_TABLES:
                    self.assertEqual(expected, _rows(override / f"{table}.2DA"), table)

    def test_same_symbol_on_first_data_row_is_updated(self) -> None:
        rows = (CLASS_ROWS[4], CLASS_ROWS[-1])
        expected = [list(row) for row in rows]
        expected[0][4] = "15"
        for library in LIBRARIES:
            with self.subTest(library=str(library)):
                override, transcript = self._run_helper(
                    library, ("BERSERKER",), class_rows=rows
                )
                self._assert_returns(transcript, [15])
                for table in CLASS_TABLES:
                    self.assertEqual(expected, _rows(override / f"{table}.2DA"), table)

    def test_absent_optional_tables_do_not_prevent_lookup(self) -> None:
        for library in LIBRARIES:
            for tables in ((), ("CLASTEXT",)):
                with self.subTest(library=str(library), tables=tables):
                    override, transcript = self._run_helper(
                        library, ("ASSASIN",), tables=tables
                    )
                    self._assert_returns(transcript, [11])
                    if tables:
                        self.assertEqual("11", _rows(override / "CLASTEXT.2DA")[0][4])

    def test_unknown_and_empty_kit_names_leave_descriptions_unchanged(self) -> None:
        rows = CLASS_ROWS + (("MISSING_KIT", "4", "99", "2", "33", "7", "-1", "0", "17", "-1"),)
        for library in LIBRARIES:
            with self.subTest(library=str(library)):
                override, transcript = self._run_helper(
                    library, ("MISSING_KIT", ""), class_rows=rows
                )
                self._assert_returns(transcript, [-1, -1])
                for table in CLASS_TABLES:
                    self.assertEqual([list(row) for row in rows], _rows(override / f"{table}.2DA"))

    def test_invalid_description_refs_do_not_replace_class_descriptions(self) -> None:
        for library in LIBRARIES:
            for invalid in ("-1", "*", "not_a_number"):
                with self.subTest(library=str(library), invalid=invalid):
                    kit_rows = tuple(
                        (*row[:4], invalid, *row[5:]) if row[1] == "ASSASIN" else row
                        for row in KIT_ROWS
                    )
                    override, transcript = self._run_helper(
                        library, ("ASSASIN",), kit_rows=kit_rows
                    )
                    self._assert_returns(transcript, [-1])
                    for table in CLASS_TABLES:
                        self.assertEqual(
                            [list(row) for row in CLASS_ROWS],
                            _rows(override / f"{table}.2DA"), table,
                        )

    def _create_tail_game(
        self,
        components: tuple[int, ...],
        *,
        kit_rows: tuple[tuple[str, ...], ...] = KIT_ROWS,
    ) -> tuple[Path, dict[Path, bytes], dict[str, bytes]]:
        game, originals = self._create_game(kit_rows=kit_rows)
        shutil.copytree(TAIL_DIR, game / TAIL_DIR.name)
        (game / "WeiDU.log").write_text(
            "".join(
                "~ARTISANSKITPACK/ARTISANSKITPACK.TP2~ "
                f"#0 #{component} // synthetic installed prerequisite\n"
                for component in components
            ), encoding="ascii",
        )
        before = {path.name.upper(): path.read_bytes() for path in (game / "override").iterdir()}
        return game, originals, before

    def test_public_tail_only_repairs_installed_kits_and_uninstalls_exactly(self) -> None:
        game, originals, before = self._create_tail_game((7004, 2010, 5200))
        process, transcript = self._invoke(game, TAIL_TP2)
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        self._assert_stable_inputs(originals)
        expected = [list(row) for row in CLASS_ROWS]
        for index, strref in ((0, 11), (1, 12), (3, 14), (5, 11), (6, 12), (8, 14)):
            expected[index][4] = str(strref)
        for table in CLASS_TABLES:
            self.assertEqual(expected, _rows(game / "override" / f"{table}.2DA"), table)

        process, transcript = self._invoke(game, TAIL_TP2, "--force-uninstall-list")
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY REMOVED", transcript)
        self._assert_stable_inputs(originals)
        self.assertEqual(
            before,
            {path.name.upper(): path.read_bytes() for path in (game / "override").iterdir()},
        )

    def test_public_tail_without_supported_components_leaves_resources_unchanged(self) -> None:
        game, originals, before = self._create_tail_game((99999,))
        process, transcript = self._invoke(game, TAIL_TP2)
        self.assertNotEqual(0, process.returncode, transcript)
        self.assertIn("no supported Artisan's Kitpack", transcript)
        self.assertIn("NOT INSTALLED DUE TO ERRORS", transcript)
        self._assert_stable_inputs(originals)
        self.assertEqual(
            before,
            {path.name.upper(): path.read_bytes() for path in (game / "override").iterdir()},
        )

    def test_public_tail_missing_selected_kit_rolls_back_other_repairs(self) -> None:
        kit_rows = tuple(row for row in KIT_ROWS if row[1] != "BEAST_FRIEND")
        game, originals, before = self._create_tail_game((2010, 5200), kit_rows=kit_rows)
        process, transcript = self._invoke(game, TAIL_TP2)
        self.assertNotEqual(0, process.returncode, transcript)
        self.assertIn("no valid KITLIST HELP string", transcript)
        self.assertIn("NOT INSTALLED DUE TO ERRORS", transcript)
        # Prove the failure followed an actual earlier repair, making unchanged
        # final resources evidence of rollback rather than an untouched input.
        repaired = "FERALAN campaign descriptions linked to existing string 12"
        self.assertIn(repaired, transcript)
        self.assertLess(transcript.index(repaired), transcript.index("no valid KITLIST HELP string"))
        self._assert_stable_inputs(originals)
        self.assertEqual(
            before,
            {path.name.upper(): path.read_bytes() for path in (game / "override").iterdir()},
        )


if __name__ == "__main__":
    unittest.main()
