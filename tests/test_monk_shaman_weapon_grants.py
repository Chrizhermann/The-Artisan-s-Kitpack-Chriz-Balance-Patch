"""Monk and shaman class weapon grants of the EEex weapon usability system.

C0PR#CL grants each class the weapons its WEAPPROF.2DA column allows, and an
"AP_C0PR#CL" entry at every level of the class and kit ability tables applies
C0PR#CL when a character joins the party and at each level-up. Two gaps:

- The generator wrote the class grants only on its first run. Monk Revisions
  lets monks put proficiency points into quarterstaves afterwards, so monks
  were not granted quarterstaves unless the "Update EEex-based Weapon
  Usability Changes" tweak ran later.
- The generator never gave the shaman's own ability table CLABSH01 an
  "AP_C0PR#CL", so shamans without a kit could equip every weapon until
  Kitpack's helper creature applied C0PR#CL.

These tests run the real generator and tweak, the real WEAPPROF change of
Monk Revisions (lib/monk_staves.tpa) and the real lines that Monk Revisions
and the Favored Soul component now run after their changes, with WeiDU in
synthetic games and in both install orders. The model of
test_kit_weapon_grants then compares the weapons C0PR#CL gives. It is not
EEex; the in-game lab check covers the engine.
"""

from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from test_kit_weapon_grants import (
    CL,
    KG,
    KitChainGame,
    KitWeaponGrantTestCase,
    Model,
    _files,
)
from test_shapeshifter_personal_space import _raw_tree
from test_sorcerer_weapon_usability import (
    BLANK_CLAB,
    CLASS_IDS,
    GENERATOR,
    MARKER,
    MOD_FOLDER,
    MONK,
    REGENERATOR,
    WEAPONS,
    _fields,
    _grants,
    _parse_spl,
)


MONK_STAVES = MOD_FOLDER / "lib/monk_staves.tpa"
MONK_REVISION = MOD_FOLDER / "lib/MonkRevision.tpa"
MAIN_TP2 = MOD_FOLDER / "ArtisansKitpack.TP2"
ENTRY = "AP_C0PR#CL"
# The WEAPPROF data column of the monk class (header position 50).
MONK_COLUMN = 51
# The synthetic monk column before Monk Revisions, like the vanilla one: no
# quarterstaves.
MONK_BEFORE = MONK - {"QUARTERSTAFF"}

# A class_weapon_grants.tpa call right after a line: blank and comment lines,
# the INCLUDE and one LAF.
CALL_AFTER = re.compile(
    r"\A[ \t]*\r?\n(?:[ \t]*\r?\n|[ \t]*//[^\n]*\n)*"
    r"[ \t]*INCLUDE ~%MOD_FOLDER%/eeex/class_weapon_grants\.tpa~[ \t]*\r?\n"
    r"[ \t]*LAF (?P<function>\w+) END[ \t]*(?:\r?\n|\Z)"
)


def _call_after(path: Path, anchor: str) -> tuple[str, str, str]:
    """The class_weapon_grants.tpa call right after the line `anchor`: text, function, rest of the file."""
    text = path.read_text(encoding="latin-1")
    if text.count(anchor) != 1:
        raise AssertionError(f"{path.name} must contain {anchor} exactly once")
    at = text.index(anchor) + len(anchor)
    call = CALL_AFTER.match(text[at:])
    if call is None:
        raise AssertionError(f"{path.name}: no class_weapon_grants.tpa call right after {anchor}")
    return call.group(0), call.group("function"), text[at + call.end():]


def _monk_staves_profs() -> str:
    """monk_staves.tpa's quarterstaff proficiency for monk columns, as Monk Revisions runs it."""
    text = MONK_STAVES.read_text(encoding="latin-1")
    start = text.index("DEFINE_ACTION_FUNCTION mod_monk_profs")
    call = re.compile(r"^LAF mod_monk_profs END[^\n]*\n", re.MULTILINE).search(text, start)
    if call is None:
        raise AssertionError("monk_staves.tpa no longer calls mod_monk_profs")
    block = text[start:call.end()]
    if "SET_2DA_ENTRY_LATER wweapprof 25 (col + 1) 5" not in block:
        raise AssertionError("monk_staves.tpa no longer gives monk columns quarterstaff proficiency")
    return block


def _table(rows: dict[str, dict[int, str]]) -> bytes:
    """An ability table with 50 level columns; each row maps levels to entries."""
    lines = ["2DA V1.0", "****", " " * 12 + " ".join(f"{level:<11}" for level in range(1, 51)).rstrip()]
    for name, cells in rows.items():
        lines.append(f"{name:<12}" + " ".join(f"{cells.get(level, '****'):<11}" for level in range(1, 51)).rstrip())
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


# Like the vanilla shaman table: spells at some levels, an innate at level 1.
SHAMAN_TABLE = _table({
    "ABILITY1": {1: "GA_AKSH1", 4: "GA_AKSH2", 6: "GA_AKSH3", 8: "GA_AKSH4", 10: "GA_AKSH5",
                 12: "GA_AKSH6", 14: "GA_AKSH7"},
    "ABILITY2": {}, "ABILITY3": {}, "ABILITY4": {}, "ABILITY5": {},
    "ABILITY6": {1: "AP_AKSH0"},
})
# A later mod's shaman table: both rows are taken at level 1.
REPLACED_SHAMAN_TABLE = _table({
    "ABILITY1": {1: "GA_AKSHX1", 2: "GA_AKSHX2", 9: "GA_AKSHX3"},
    "ABILITY2": {1: "AP_AKSHX0", 50: "AP_AKSHX9"},
})
FAVORED_SOUL_TABLE = _table({"ABILITY1": {1: "GA_AKFS1", 3: "GA_AKFS2"}})
SHAMAN_KIT_TABLE = _table({"ABILITY1": {2: "GA_AKSK1"}})
FAVORED_SOUL_KIT = "4        C0_TEST_FS 1 2 3 C0TSTFS 60 0x00000000 21 0x4050"
SHAMAN_KIT = "5        C0_TEST_SHK 1 2 3 C0TSTSK 60 0x00000000 21 0x4051"

STEPS = {  # step: (tp2, component)
    "generator": ("harness.tp2", "0"),
    "tweak": ("harness.tp2", "2"),
    "Eldritch Knight sorcerer": ("chains.tp2", "10"),
    "Monk Revisions before the fix": ("monks.tp2", "40"),
    "Monk Revisions": ("monks.tp2", "41"),
    "kit added after the generator": ("monks.tp2", "42"),
    "Favored Soul": ("monks.tp2", "43"),
    "later mod replaces the shaman table": ("monks.tp2", "44"),
    "later mod adds a shaman kit": ("monks.tp2", "45"),
    "generator again": ("monks.tp2", "46"),
    "Monk Revisions' new lines again": ("monks.tp2", "47"),
    "later mod adds an effect to C0PR#CL": ("monks.tp2", "48"),
}


class MonkShamanGame(KitChainGame):
    """A kit chain game with a vanilla-like monk column and shaman table, and monks.tp2."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        weapprof = self.override / "WEAPPROF.2DA"
        lines = weapprof.read_bytes().decode("ascii").split("\r\n")
        row = next(index for index, line in enumerate(lines) if line.split()[:1] == ["QUARTERSTAFF"])
        cells = lines[row].split()
        if cells[MONK_COLUMN] != "2":
            raise AssertionError("the synthetic WEAPPROF no longer lets monks use quarterstaves")
        cells[MONK_COLUMN] = "0"
        lines[row] = " ".join(cells)
        weapprof.write_bytes("\r\n".join(lines).encode("ascii"))
        (self.override / "CLABSH01.2DA").write_bytes(SHAMAN_TABLE)

        tables = root / "tables"
        tables.mkdir()
        for name, data in (("CLABSH01", REPLACED_SHAMAN_TABLE), ("C0TSTFS", FAVORED_SOUL_TABLE),
                           ("C0TSTSK", SHAMAN_KIT_TABLE)):
            (tables / f"{name}.2DA").write_bytes(data)
        generator = f"INCLUDE ~{GENERATOR.as_posix()}~"
        profs = _monk_staves_profs()
        monk_call, _, _ = _call_after(MONK_REVISION, "INCLUDE ~%MOD_FOLDER%/lib/monk_staves.tpa~")
        favored_soul_call, _, _ = _call_after(MAIN_TP2, "INCLUDE ~%MOD_FOLDER%/lib/FavoredSoul.tpa~")

        def kit(row: str, table: str) -> list[str]:
            return [f"APPEND ~KITLIST.2DA~ ~{row}~", f"COPY ~{(tables / f'{table}.2DA').as_posix()}~ ~override~"]

        components = {
            40: ("Monk Revisions' quarterstaff proficiency before the fix", [profs]),
            41: ("Monk Revisions' quarterstaff proficiency", [profs, monk_call]),
            42: ("A kit added after the generator, before the fix", [generator, *kit(FAVORED_SOUL_KIT, "C0TSTFS")]),
            43: ("Favored Soul-like kit", [generator, *kit(FAVORED_SOUL_KIT, "C0TSTFS"), favored_soul_call]),
            44: ("A later mod replaces the shaman table",
                 [f"COPY ~{(tables / 'CLABSH01.2DA').as_posix()}~ ~override~"]),
            45: ("A later mod adds a shaman kit", kit(SHAMAN_KIT, "C0TSTSK")),
            46: ("Another component that includes the generator", [generator]),
            47: ("Monk Revisions' new lines again", [monk_call]),
            48: ("A later mod adds its own effect to C0PR#CL", [
                "COPY_EXISTING ~C0PR#CL.SPL~ ~override~",
                "  LPF ADD_SPELL_EFFECT INT_VAR opcode = 139 target = 2 parameter1 = 4242 END",
            ]),
        }
        lines = [
            "BACKUP ~monks-backup~",
            "AUTHOR ~Monk and shaman weapon grant regression tests~",
            "ALWAYS",
            f"  OUTER_SPRINT MOD_FOLDER ~{MOD_FOLDER.as_posix()}~",
            "  INCLUDE ~%MOD_FOLDER%/lib/functions.tph~",
            "END",
        ]
        for number, (label, body) in components.items():
            lines += [f"BEGIN ~{label}~ DESIGNATED {number}", *body]
        (root / "monks.tp2").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _expected_grants(allowed: frozenset[str]) -> list[str]:
    return [f"C0PR#{ident}" for name, ident in WEAPONS if name in allowed]


def _special(block: bytes) -> int:
    return struct.unpack_from("<I", block, 0x2C)[0]


def _cells(data: bytes) -> dict[tuple[str, int], str]:
    """The cells of an ability table by row name and level."""
    lines = [line.split() for line in data.decode("ascii").splitlines()]
    levels = [int(level) for level in lines[2]]
    cells = {}
    for fields in lines[3:]:
        if not fields:
            continue
        if len(fields) != len(levels) + 1:
            raise AssertionError(f"row {fields[0]} has {len(fields) - 1} cells for {len(levels)} levels")
        for level, cell in zip(levels, fields[1:]):
            cells[(fields[0], level)] = cell
    return cells


class MonkShamanTestCase(KitWeaponGrantTestCase):
    def _game(self) -> MonkShamanGame:
        return MonkShamanGame(self._temporary_root("akcb-monk-shaman-"))

    def _steps(self, game: MonkShamanGame, *steps: str) -> None:
        """Install the steps one WeiDU run each, in the given order."""
        for step in steps:
            tp2, component = STEPS[step]
            self._assert_installed(game, game.run(tp2, "--force-install-list", component))

    def _table(self, game: MonkShamanGame, name: str) -> bytes:
        return (game.override / f"{name}.2DA").read_bytes()

    def _assert_c0pr_cl_everywhere(self, before: bytes, after: bytes) -> None:
        """One AP_C0PR#CL at every level; every other entry of the table stays where it was."""
        old, new = _cells(before), _cells(after)
        self.assertEqual(list(range(1, 51)), sorted({level for _, level in new}))
        for (row, level), cell in old.items():
            if cell != "****":
                self.assertEqual(cell, new.get((row, level)), f"{row} at level {level}")
        for level in range(1, 51):
            rows = [row for (row, at), cell in new.items() if at == level and cell == ENTRY]
            self.assertEqual(1, len(rows), f"level {level}: {rows}")
        for (row, level), cell in new.items():
            if cell not in ("****", ENTRY):
                self.assertEqual(old.get((row, level)), cell, f"{row} at level {level}")
        for row in {row for row, _ in new} - {row for row, _ in old}:
            self.assertTrue(row.startswith("fl#row"), row)

    def _assert_no_c0pr_cl(self, data: bytes) -> None:
        self.assertNotIn(ENTRY.encode("ascii"), data)


class MonkQuarterstaffTests(MonkShamanTestCase):
    def test_monk_revisions_after_the_generator_grants_monks_quarterstaves(self) -> None:
        before_fix = self._game()
        self._steps(before_fix, "generator", "Monk Revisions before the fix")
        fixed = self._game()
        self._steps(fixed, "generator", "Monk Revisions")
        (old,), _ = _parse_spl(before_fix.spl(CL))
        (new,), _ = _parse_spl(fixed.spl(CL))
        self.assertEqual(_expected_grants(MONK_BEFORE), _grants(old, CLASS_IDS["MONK"]), "the gap")
        self.assertEqual(_expected_grants(MONK), _grants(new, CLASS_IDS["MONK"]))
        for name, class_id in CLASS_IDS.items():
            if name != "MONK":
                with self.subTest(class_name=name):
                    self.assertEqual(_grants(old, class_id), _grants(new, class_id))

    def test_both_install_orders_give_the_same_c0pr_cl(self) -> None:
        generator_first = self._game()
        self._steps(generator_first, "generator", "Monk Revisions")
        monk_revisions_first = self._game()
        self._steps(monk_revisions_first, "Monk Revisions", "generator")
        self.assertEqual(monk_revisions_first.spl(CL), generator_first.spl(CL))

    def test_c0pr_cl_gives_monks_quarterstaves(self) -> None:
        cases = {
            "before the fix": (("generator", "Monk Revisions before the fix"), MONK_BEFORE),
            "Monk Revisions after the generator": (("generator", "Monk Revisions"), MONK),
            "Monk Revisions first": (("Monk Revisions", "generator"), MONK),
        }
        for label, (steps, expected) in cases.items():
            with self.subTest(order=label):
                game = self._game()
                self._steps(game, *steps)
                monk = Model(_files(game.override), "MONK")
                monk.apply(CL)
                self.assertEqual(expected, monk.weapons())

    def test_without_eeex_weapon_usability_only_weapprof_changes(self) -> None:
        game = self._game()
        before = _raw_tree(game.override)
        self._steps(game, "Monk Revisions")
        after = _raw_tree(game.override)
        self.assertEqual({"WEAPPROF.2DA"}, {name for name in after if after[name] != before.get(name)})
        self.assertEqual(set(before), set(after))

    def test_other_effects_keep_their_place_and_kit_grants_stay_last(self) -> None:
        game = self._game()
        self._steps(game, "Eldritch Knight sorcerer", "later mod adds an effect to C0PR#CL")
        (before,), _ = _parse_spl(game.spl(CL))
        self._steps(game, "Monk Revisions")
        (after,), casting = _parse_spl(game.spl(CL))
        self.assertEqual([], casting)
        self._assert_kg(game, ["C0PR#EK"])
        kg = [block for block in before if _fields(block)[::3] == (326, KG)]
        others = [block for block in before if _special(block) != MARKER and block not in kg]
        self.assertEqual(others + kg, [block for block in after if _special(block) != MARKER],
                         "every other effect stays, in its order, with C0PR#KG last")
        first = next(index for index, block in enumerate(before) if _special(block) == MARKER)
        grants = [block for block in after if _special(block) == MARKER]
        self.assertEqual(grants, after[first:first + len(grants)], "the class grants stay where they were")
        self.assertEqual(_expected_grants(MONK), _grants(grants, CLASS_IDS["MONK"]))
        other_order = self._game()
        self._steps(other_order, "Monk Revisions", "Eldritch Knight sorcerer")
        (fresh,), _ = _parse_spl(other_order.spl(CL))
        self.assertEqual([block for block in fresh if _special(block) == MARKER], grants)

    def test_repeated_calls_change_nothing(self) -> None:
        game = self._game()
        self._steps(game, "Eldritch Knight sorcerer", "Monk Revisions", "Favored Soul")
        before = _raw_tree(game.override)
        self._steps(game, "Monk Revisions' new lines again", "generator again")
        self.assertEqual(before, _raw_tree(game.override))
        # The tweak also regates items and SPLPROT rows on its own; the files
        # the shared code writes stay as they are.
        self._steps(game, "tweak")
        after = _raw_tree(game.override)
        tables = [name for name in before if name.startswith(("CLAB", "C0TST")) and name.endswith(".2DA")]
        self.assertIn("CLABSH01.2DA", tables)
        for name in [*tables, "WEAPPROF.2DA", "KITLIST.2DA", f"{CL}.SPL", f"{KG}.SPL"]:
            self.assertEqual(before[name], after.get(name), name)


class ShamanTableTests(MonkShamanTestCase):
    def test_generator_gives_the_shaman_table_c0pr_cl_at_every_level(self) -> None:
        game = self._game()
        self._steps(game, "generator")
        self._assert_c0pr_cl_everywhere(SHAMAN_TABLE, self._table(game, "CLABSH01"))

    def test_a_missing_shaman_table_is_created_from_the_blank_table(self) -> None:
        game = self._game()
        (game.override / "CLABSH01.2DA").unlink()
        self._steps(game, "generator")
        self._assert_c0pr_cl_everywhere(BLANK_CLAB.read_bytes(), self._table(game, "CLABSH01"))

    def test_tweak_restores_a_replaced_shaman_table_and_covers_later_kits(self) -> None:
        game = self._game()
        self._steps(game, "generator", "later mod replaces the shaman table", "later mod adds a shaman kit")
        self._assert_no_c0pr_cl(self._table(game, "CLABSH01"))
        self._assert_no_c0pr_cl(self._table(game, "C0TSTSK"))
        before = _raw_tree(game.override)
        self._steps(game, "tweak")
        after = _raw_tree(game.override)
        self._assert_c0pr_cl_everywhere(REPLACED_SHAMAN_TABLE, self._table(game, "CLABSH01"))
        self._assert_c0pr_cl_everywhere(SHAMAN_KIT_TABLE, self._table(game, "C0TSTSK"))
        changed = {name for name in after if name.endswith(".2DA") and after[name] != before.get(name)}
        self.assertEqual({"CLABSH01.2DA", "C0TSTSK.2DA"}, changed)

    def test_favored_soul_gives_its_new_kit_table_c0pr_cl(self) -> None:
        before_fix = self._game()
        self._steps(before_fix, "generator", "kit added after the generator")
        self._assert_no_c0pr_cl(self._table(before_fix, "C0TSTFS"))
        for steps in (("generator", "Favored Soul"), ("Favored Soul",)):
            with self.subTest(steps=steps):
                game = self._game()
                self._steps(game, *steps)
                self._assert_c0pr_cl_everywhere(FAVORED_SOUL_TABLE, self._table(game, "C0TSTFS"))
                self._assert_c0pr_cl_everywhere(SHAMAN_TABLE, self._table(game, "CLABSH01"))


class PlacementTests(unittest.TestCase):
    """Where the generator, the tweak, Monk Revisions and the Favored Soul call the shared code."""

    def test_monk_revisions_rebuilds_the_class_grants_after_changing_weapprof(self) -> None:
        _, function, _ = _call_after(MONK_REVISION, "INCLUDE ~%MOD_FOLDER%/lib/monk_staves.tpa~")
        self.assertEqual("c0_build_class_weapon_grants", function)

    def test_favored_soul_component_ends_with_the_ability_table_pass(self) -> None:
        _, function, rest = _call_after(MAIN_TP2, "INCLUDE ~%MOD_FOLDER%/lib/FavoredSoul.tpa~")
        self.assertEqual("c0_add_c0pr_cl_to_ability_tables", function)
        self.assertRegex(rest, r"\A(?:\s|//[^\n]*)*(?:\Z|BEGIN\b)", "nothing may follow it in the component")

    def test_generator_and_tweak_share_one_class_map(self) -> None:
        generator = GENERATOR.read_text(encoding="latin-1")
        build = generator.index("LAF c0_build_class_weapon_grants END")
        tables = generator.index("LAF c0_add_c0pr_cl_to_ability_tables END")
        sync = generator.rindex("LAF c0_sync_kit_weapon_grants END")
        self.assertLess(build, tables)
        self.assertLess(tables, sync)
        for path in (GENERATOR, REGENERATOR):
            text = path.read_text(encoding="latin-1")
            with self.subTest(path=path.name):
                self.assertEqual(1, text.count("INCLUDE ~%MOD_FOLDER%/eeex/class_weapon_grants.tpa~"))
                self.assertEqual(1, text.count("LAF c0_build_class_weapon_grants END"))
                self.assertEqual(1, text.count("LAF c0_add_c0pr_cl_to_ability_tables END"))
        maps = [path.relative_to(MOD_FOLDER).as_posix() for path in MOD_FOLDER.rglob("*.tp*")
                if re.search(r"ACTION_DEFINE_ASSOCIATIVE_ARRAY\s+WEAPPROF_CLASS\b",
                             path.read_text(encoding="latin-1"))]
        self.assertEqual(["eeex/class_weapon_grants.tpa"], maps)


if __name__ == "__main__":
    unittest.main()
