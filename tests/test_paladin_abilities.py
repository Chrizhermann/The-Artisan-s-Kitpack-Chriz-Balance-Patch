from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_magekiller_witchbane import _spell_effects
from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    ROOT,
    WEIDU,
    _raw_tree,
    _write_marker_key_and_bif,
)


MOD = ROOT / "ArtisansKitpack"
PATCH = ROOT / "live-patch/AKCB_PALADIN"
DETECT = "GA_SPCL212"
DEVA = "GA_SPCL923"
INHERITED = {3000: "CLABPA01", 3010: "CLABPA02", 3003: "CLABPA03", 3011: "CLABPA04", 3002: "C0MF"}


def _table(data: bytes) -> tuple[list[str], list[list[str]]]:
    lines = [line.split("//", 1)[0].strip() for line in data.decode("ascii").splitlines()]
    lines = [line for line in lines if line]
    if lines[0].upper().split() != ["2DA", "V1.0"]:
        raise ValueError("Expected a 2DA V1.0 table")
    header = lines[2].split()
    rows = [line.split() for line in lines[3:]]
    if any(len(row) != len(header) + 1 for row in rows):
        raise ValueError("Malformed 2DA row width")
    return header, rows


def _clab(*, detect_level: int | None = None) -> bytes:
    cells = ["****"] * 40
    if detect_level is not None:
        cells[detect_level - 1] = DETECT
    return (
        "2DA V1.0\r\n****\r\n " + " ".join(map(str, range(1, 41)))
        + "\r\nCUSTOM42 " + " ".join(cells)
        + "\r\nUNRELATED GA_SPCL211 " + " ".join(["****"] * 39) + "\r\n"
    ).encode("ascii")


def _hla(*, total_columns: int = 10, allowed: int = 20, deva: bool = True) -> bytes:
    # WeiDU's column count includes the row label. Both classic and extended
    # HLA layouts are used by actual mods.
    header = "ABILITY ICON STRREF MIN_LEV MAX_LEVEL NUM_ALLOWED PREREQUISITE EXCLUDED_BY"
    rows = [
        ["73", "GA_SPCL900", "custom", "1001", "8", "40", "7", "REQ_A", "EXC_A"],
        ["CUSTOM", DEVA if deva else "GA_SPCL924", "devaicon", "1002", "12", "99", str(allowed), "REQ_B", "EXC_B"],
        ["2", "AP_SPPR726", "clericon", "1003", "1", "98", "8", "REQ_C", "EXC_C"],
        ["FALLEN", "GA_SPCL935", "falleni", "1004", "3", "97", "5", "REQ_D", "EXC_D"],
    ]
    if total_columns == 10:
        header += " ALIGNMENT_RESTRICT"
        for row, alignment in zip(rows, ("*", "0x15", "0x12", "0x11")):
            row.append(alignment)
    elif total_columns != 9:
        raise ValueError("Expected 9 or 10 columns including row labels")
    return ("2DA V1.0\r\n*\r\n " + header + "\r\n" + "\r\n".join("  ".join(row) for row in rows) + "\r\n").encode("ascii")


def _hla_resources() -> dict[str, bytes]:
    # Preserve vanilla repeatability and existing mod choices, including disabled
    # and single-pick Deva, in both supported table layouts. Every table also
    # contains cleric and Fallen HLA rows with their own limits and prerequisites.
    resources = {
        f"LU{width}_{allowed}.2DA": _hla(total_columns=width, allowed=allowed)
        for width in (9, 10)
        for allowed in (0, 1, 2, 20, 99)
    }
    resources.update({
        "LUPA0.2DA": _hla(total_columns=9),
        "LUNONE.2DA": _hla(deva=False),
        "OTHER.2DA": _hla(),
    })
    return resources


def _leading_actions(name: str, boundary: str) -> str:
    """Use the complete real COPY/CLAB actions, up to a named next section."""
    source = (MOD / "lib" / name).read_text(encoding="utf-8")
    prefix, separator, _ = source.partition(boundary)
    if not separator or not prefix.lstrip().startswith("COPY "):
        raise AssertionError(f"Cannot identify complete leading production actions in {name}")
    return prefix


class SyntheticPaladinGame:
    def __init__(self, root: Path, *, resources: dict[str, bytes] | None = None,
                 installed: tuple[int, ...] = tuple(INHERITED), actions: str | None = None) -> None:
        self.root = root
        self.override = root / "override"
        self.override.mkdir(parents=True)
        shutil.copy2(WEIDU, root / "weidu.exe")
        _write_marker_key_and_bif(root)
        for relative in ("lang/en_us/dialog.tlk", "dialog.tlk"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ONE_EMPTY_STRING_TLK)
        if resources is None:
            resources = {f"{name}.2DA": _clab() for name in INHERITED.values()}
            resources.update({f"{name}.2DA": _clab() for name in ("CLABPA06", "C0DIV", "C0MART")})
            resources.update(_hla_resources())
            resources["UNRELATED.TXT"] = b"preserve this resource\r\n"
        for name, data in resources.items():
            (self.override / name).write_bytes(data)
        if installed:
            (root / "WeiDU.log").write_text(
                "".join(f"~ARTISANSKITPACK/ARTISANSKITPACK.TP2~ #0 #{component} // synthetic prerequisite\n" for component in installed),
                encoding="utf-8", newline="\n",
            )
        if actions is None:
            shutil.copytree(PATCH, root / PATCH.name)
            self.tp2 = "AKCB_PALADIN/setup-AKCB_PALADIN.tp2"
        else:
            self.tp2 = "paladin-test.tp2"
            (root / self.tp2).write_text(
                "BACKUP ~paladin-test-backup~\nAUTHOR ~Paladin regression tests~\n"
                "BEGIN ~Paladin production-action harness~\n"
                f"OUTER_SPRINT MOD_FOLDER ~{MOD.as_posix()}~\n" + actions,
                encoding="utf-8", newline="\n",
            )
        self.before = _raw_tree(self.override)
        self.stable_inputs = {
            relative: (root / relative).read_bytes()
            for relative in ("chitin.key", "data/akcbtest.bif", "dialog.tlk", "lang/en_us/dialog.tlk")
        }

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "weidu.exe"), self.tp2, "--game", str(self.root),
             *[argument for operation in operations for argument in (operation, "0")],
             "--language", "0", "--use-lang", "en_US", "--no-exit-pause", "--quick-log"],
            cwd=self.root, capture_output=True, encoding="utf-8", errors="replace", timeout=90, check=False,
        )

    def assert_stable(self, testcase: unittest.TestCase) -> None:
        for relative, original in self.stable_inputs.items():
            testcase.assertEqual(original, (self.root / relative).read_bytes(), relative)


class PaladinSourceTests(unittest.TestCase):
    def test_packaged_detect_evil_recharges_itself_by_remove_then_add(self) -> None:
        effects = _spell_effects((MOD / "Paladin/spells/SPCL212.SPL").read_bytes())
        recharge = [effect for effect in effects if effect.opcode in (171, 172) and effect.resource == "SPCL212"]
        self.assertEqual([172, 171], [effect.opcode for effect in recharge])
        self.assertTrue(all(effect.target == 1 for effect in recharge))


class PaladinInstallerTests(unittest.TestCase):
    """Real WeiDU regression coverage; character spellbooks and HLA UI need live testing."""

    def _game(self, **kwargs: object) -> SyntheticPaladinGame:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-paladin-")
        self.addCleanup(temporary.cleanup)
        return SyntheticPaladinGame(Path(temporary.name) / "game", **kwargs)

    def _install(self, game: SyntheticPaladinGame, *operations: str) -> dict[str, bytes]:
        process = game.run(*(operations or ("--force-install-list",)))
        transcript = process.stdout + "\n" + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        self.assertNotIn("ERROR", transcript)
        game.assert_stable(self)
        return _raw_tree(game.override)

    def _uninstall(self, game: SyntheticPaladinGame) -> None:
        process = game.run("--force-uninstall-list")
        transcript = process.stdout + "\n" + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertNotIn("NOT UNINSTALLED", transcript)
        self.assertEqual(game.before, _raw_tree(game.override))
        game.assert_stable(self)

    def _assert_detect(self, data: bytes, *, level: int = 1, count: int = 1) -> None:
        header, rows = _table(data)
        grants = [(header[column - 1], cell.upper()) for row in rows for column, cell in enumerate(row) if column and cell.upper() == DETECT]
        self.assertEqual([(str(level), DETECT)] * count, grants)

    def _assert_hlas_unchanged(self, before: dict[str, bytes], after: dict[str, bytes]) -> None:
        self.assertEqual(
            {name: data for name, data in before.items() if name.startswith("LU") and name.endswith(".2DA")},
            {name: data for name, data in after.items() if name.startswith("LU") and name.endswith(".2DA")},
        )

    def test_fresh_parent_and_cavalier_keep_level_one_detect_blackguard_removes_it(self) -> None:
        actions = "INCLUDE ~%MOD_FOLDER%/lib/functions.tph~\n"
        actions += _leading_actions("Paladin.tpa", "// CHARISMA")
        actions += _leading_actions("Cavalier.tpa", "// ICONS")
        actions += _leading_actions("Blackguard.tpa", "// ICONS")
        game = self._game(actions=actions)
        after = self._install(game)
        self._assert_detect(after["CLABPA01.2DA"])
        self._assert_detect(after["CLABPA02.2DA"])
        self._assert_detect(after["CLABPA06.2DA"], count=0)
        self.assertEqual((MOD / "Paladin/spells/SPCL212.SPL").read_bytes(), after["SPCL212.SPL"])
        self._assert_hlas_unchanged(game.before, after)
        self._uninstall(game)

    def test_tail_restores_all_installed_inherited_clabs_and_uninstalls_byte_exact(self) -> None:
        game = self._game()
        after = self._install(game)
        self.assertEqual(set(game.before), set(after))
        for name, original in game.before.items():
            if name in {f"{value}.2DA" for value in INHERITED.values()}:
                self._assert_detect(after[name])
                before_header, before_rows = _table(original)
                after_header, after_rows = _table(after[name])
                self.assertEqual(before_header, after_header)
                self.assertEqual(before_rows, after_rows[:-1])
                self.assertEqual(["GA_SPCL212"] + ["****"] * 39, after_rows[-1][1:])
            else:
                self.assertEqual(original, after[name], name)
        self._assert_hlas_unchanged(game.before, after)
        self._uninstall(game)

    def test_tail_only_repairs_clabs_for_installed_components(self) -> None:
        game = self._game(installed=(3000,))
        after = self._install(game)
        self._assert_detect(after["CLABPA01.2DA"])
        for name in ("CLABPA02", "CLABPA03", "CLABPA04", "C0MF", "CLABPA06", "C0DIV", "C0MART"):
            self.assertEqual(game.before[f"{name}.2DA"], after[f"{name}.2DA"], name)

    def test_tail_does_not_duplicate_existing_grant_even_in_later_column(self) -> None:
        for level in (1, 17):
            with self.subTest(level=level):
                resources = {"CLABPA01.2DA": _clab(detect_level=level), "LUPA0.2DA": _hla(allowed=1)}
                game = self._game(resources=resources, installed=(3000,))
                after = self._install(game)
                self.assertEqual(game.before, after)
                self._assert_detect(after["CLABPA01.2DA"], level=level)

    def test_tail_is_idempotent_on_already_patched_resources(self) -> None:
        first = self._game()
        after = self._install(first)
        second = self._game(resources=after)
        self.assertEqual(after, self._install(second))
        self._uninstall(second)

    def test_tail_paired_reinstall_matches_first_result(self) -> None:
        game = self._game()
        first = self._install(game)
        self.assertEqual(first, self._install(game, "--force-uninstall-list", "--force-install-list"))
        self._uninstall(game)

    def test_tail_without_paladin_overhaul_skips_without_resource_changes(self) -> None:
        game = self._game(installed=(3010,))
        process = game.run("--force-install-list")
        transcript = process.stdout + "\n" + process.stderr
        self.assertIn("SKIPPING", transcript)
        self.assertNotIn("SUCCESSFULLY INSTALLED", transcript)
        self.assertEqual(game.before, _raw_tree(game.override))
        game.assert_stable(self)


if __name__ == "__main__":
    unittest.main()
