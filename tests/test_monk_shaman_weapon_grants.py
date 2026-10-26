"""Monk and shaman class weapon grants of the EEex weapon usability system.

C0PR#CL grants each class the weapons its WEAPPROF.2DA column allows, and an
"AP_C0PR#CL" entry at every level of the class and kit ability tables applies
C0PR#CL when a character joins the party and at each level-up. Three gaps:

- The generator wrote the class grants only on its first run. Monk Revisions
  lets monks put proficiency points into quarterstaves afterwards, so monks
  were not granted quarterstaves unless the "Update EEex-based Weapon
  Usability Changes" tweak ran later.
- The generator never gave the shaman's own ability table CLABSH01 an
  "AP_C0PR#CL", so shamans without a kit could equip every weapon until
  Kitpack's helper creature applied C0PR#CL.
- Only the generator gave ability tables "AP_C0PR#CL". A kit or ability
  table that a component added after the generator's last run (Sacred and
  Enlightened Fist and the Ninja after the Favored Soul) had none, and
  neither had the levels that the main installer's ALWAYS block adds to
  40-level tables before every later component. Now every component of the
  main installer ends with the ability table pass, and so do the NPC and
  tweak components that add a kit or replace or rewrite an ability table.

These tests check where the installers run the pass, and run the real
generator and tweak, the real WEAPPROF change of Monk Revisions
(lib/monk_staves.tpa), the real extend_tables.tpa and the real lines that
Monk Revisions and the installers run, with WeiDU in synthetic games and in
several install orders. The model of test_kit_weapon_grants then compares the
weapons C0PR#CL gives. It is not EEex; the in-game lab check covers the
engine.
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
from test_shapeshifter_personal_space import ROOT, _raw_tree
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
NPC_TP2 = ROOT / "ArtisansKitpack_npc/ArtisansKitpack_npc.TP2"
TWEAK_TP2 = ROOT / "ArtisansKitpack_tweak/ArtisansKitpack_tweak.TP2"
INSTALLERS = (MAIN_TP2, NPC_TP2, TWEAK_TP2)
ENTRY = "AP_C0PR#CL"
# The ability table pass every main component ends with, and the line of the
# installers' ALWAYS blocks that defines it.
TAIL = "LAF c0_add_c0pr_cl_to_ability_tables END"
CLASS_GRANTS_INCLUDE = "INCLUDE ~%MOD_FOLDER%/eeex/class_weapon_grants.tpa~"
EXTEND_TABLES_INCLUDE = "INCLUDE ~%MOD_FOLDER%/lib/extend_tables.tpa~"
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


def _code(text: str) -> str:
    """WeiDU code without its comments."""
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL))


def _code_lines(text: str) -> list[str]:
    return [line.strip() for line in _code(text).splitlines() if line.strip()]


def _always(path: Path) -> list[str]:
    """The code lines of an installer's ALWAYS block."""
    lines = _code_lines(path.read_text(encoding="utf-8"))
    start = lines.index("ALWAYS")
    return lines[start + 1:lines.index("END", start)]


def _components(path: Path) -> dict[str, list[str]]:
    """The code lines of each component of an installer, by DESIGNATED number."""
    parts = re.split(r"(?m)^[ \t]*(?=BEGIN[ \t]+~)", _code(path.read_text(encoding="utf-8")))
    components = {}
    for part in parts[1:]:
        number = re.search(r"\bDESIGNATED[ \t]+(\d+)", part)
        if number is None or number.group(1) in components:
            raise AssertionError(f"{path.name}: a component without a unique DESIGNATED number")
        components[number.group(1)] = _code_lines(part)
    return components


def _resolve(reference: str) -> Path | None:
    """A file a Kitpack installer names, in this repository; None when it is not there."""
    current = ROOT
    for part in reference.replace("%MOD_FOLDER%", "ArtisansKitpack").replace("\\", "/").split("/"):
        if not current.is_dir():
            return None
        current = next((child for child in current.iterdir() if child.name.lower() == part.lower()), None)
        if current is None:
            return None
    return current if current.is_file() else None


def _is_ability_table(path: Path) -> bool:
    """A 2DA whose column headers are the levels 1, 2, ... like a class or kit ability table."""
    lines = [line.split() for line in path.read_text(encoding="latin-1").splitlines() if line.strip()]
    levels = lines[2] if len(lines) > 2 else []
    return bool(levels) and levels == [str(level) for level in range(1, len(levels) + 1)]


# The libraries the ALWAYS blocks include, and the generator and its tweak,
# which end their table changes with the pass themselves.
SHARED = frozenset(
    name.lower() for name in (
        "2daHandling.tph", "alter_script.tpa", "ClassSpellTool.tpa", "a7#add_kit_ex.tpa",
        "kit_strref.tpa", "RA_SPHERE_COMPAT.tpa", "eet.tph", "functions.tph", "hla_actions.tpa",
        "replace_multiline.tpa", "x_force.tph", "extend_tables.tpa", "class_weapon_grants.tpa",
        "kit_weapon_grants.tpa", GENERATOR.name, REGENERATOR.name,
    )
)
ADDS_A_KIT = re.compile(r"\bADD_KIT(?:_EX)?\b")
COPIES_A_TABLE = re.compile(r"^COPY(?:_EXISTING|_LARGE)?\s+~([^~]+)~\s+~([^~]+)~", re.IGNORECASE)
REMOVES_THE_ENTRY = re.compile(r"\bREPLACE_TEXTUALLY\b[^\n]*AP_C0PR#CL", re.IGNORECASE)


def _ability_table_writes(lines: list[str], seen: frozenset[str] = frozenset()) -> list[str]:
    """What in these lines, or in the files they include, adds a kit or replaces or rewrites an ability table.

    A heuristic for the NPC and tweak installers: ADD_KIT and ADD_KIT_EX, a
    CLAB table copied to another name, a copy of an ability table this
    repository ships, and "AP_C0PR#CL" taken out of a table. Entries that a
    component only adds to an existing table keep its "AP_C0PR#CL".
    """
    found = []
    for line in lines:
        if ADDS_A_KIT.search(line) or REMOVES_THE_ENTRY.search(line):
            found.append(line)
        elif copy := COPIES_A_TABLE.match(line):
            source, target = copy.groups()
            name = Path(source).name.lower()
            renamed = Path(target).suffix.lower() == ".2da" and Path(target).name.lower() != name
            shipped = _resolve(source)
            if (name.startswith("clab") and renamed) or (shipped is not None and _is_ability_table(shipped)):
                found.append(line)
        if include := re.match(r"^INCLUDE\s+~([^~]+)~", line):
            library = _resolve(include.group(1))
            if library is not None and library.name.lower() not in SHARED and library.name.lower() not in seen:
                text = library.read_text(encoding="latin-1")
                found += _ability_table_writes(_code_lines(text), seen | {library.name.lower()})
    return found


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


def _table(rows: dict[str, dict[int, str]], levels: int = 50) -> bytes:
    """An ability table with `levels` level columns; each row maps levels to entries."""
    lines = ["2DA V1.0", "****", " " * 12 + " ".join(f"{level:<11}" for level in range(1, levels + 1)).rstrip()]
    for name, cells in rows.items():
        lines.append(f"{name:<12}" + " ".join(f"{cells.get(level, '****'):<11}"
                                              for level in range(1, levels + 1)).rstrip())
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
# A monk kit that a component adds after the generator, like the Ninja.
MONK_KIT_TABLE = _table({"ABILITY1": {1: "GA_AKNI1", 5: "AP_AKNI2"}, "ABILITY2": {1: "AP_AKNI0"}})
# A 40-level class table that a component puts in place, like the Paladin
# Overhaul's CLABPA01; the main installer's ALWAYS block widens it to 50.
PALADIN_TABLE = _table({"ABILITY1": {1: "AP_AKPA1", 3: "GA_AKPA2", 40: "AP_AKPA9"},
                        "ABILITY2": {1: "GA_AKPA0"}}, levels=40)
FAVORED_SOUL_KIT = "4        C0_TEST_FS 1 2 3 C0TSTFS 60 0x00000000 21 0x4050"
SHAMAN_KIT = "5        C0_TEST_SHK 1 2 3 C0TSTSK 60 0x00000000 21 0x4051"
MONK_KIT = "6        C0_TEST_NIN 1 2 3 C0TSTNI 51 0x00000000 20 0x4052"

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
    "only the ability table pass": ("monks.tp2", "49"),
    "monk kit before the fix": ("kitpack.tp2", "50"),
    "monk kit": ("kitpack.tp2", "51"),
    "40-level paladin table": ("kitpack.tp2", "52"),
    "no table change before the fix": ("kitpack.tp2", "53"),
    "no table change": ("kitpack.tp2", "54"),
    "kit table loses AP_C0PR#CL": ("kitpack.tp2", "55"),
}


class MonkShamanGame(KitChainGame):
    """A kit chain game with a vanilla-like monk column and shaman table, monks.tp2 and kitpack.tp2."""

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
                           ("C0TSTSK", SHAMAN_KIT_TABLE), ("C0TSTNI", MONK_KIT_TABLE),
                           ("CLABPA01", PALADIN_TABLE)):
            (tables / f"{name}.2DA").write_bytes(data)
        generator = f"INCLUDE ~{GENERATOR.as_posix()}~"
        profs = _monk_staves_profs()
        monk_call, _, _ = _call_after(MONK_REVISION, "INCLUDE ~%MOD_FOLDER%/lib/monk_staves.tpa~")
        # The installers' own lines: the ALWAYS block includes and the pass
        # that ends the Favored Soul, Sacred and Enlightened Fist and Ninja
        # components.
        always = _always(MAIN_TP2)
        for line in (CLASS_GRANTS_INCLUDE, EXTEND_TABLES_INCLUDE):
            if line not in always:
                raise AssertionError(f"the main installer's ALWAYS block no longer has {line}")
        components = _components(MAIN_TP2)
        tails = {components[number][-1] for number in ("30001", "10003", "10004")}
        if tails != {TAIL}:
            raise AssertionError(f"the kit components no longer end with {TAIL}: {tails}")
        tail = tails.pop()

        def kit(row: str, table: str) -> list[str]:
            return [f"APPEND ~KITLIST.2DA~ ~{row}~", f"COPY ~{(tables / f'{table}.2DA').as_posix()}~ ~override~"]

        def tp2(name: str, backup: str, author: str, includes: list[str],
                components: dict[int, tuple[str, list[str]]]) -> None:
            lines = [
                f"BACKUP ~{backup}~",
                f"AUTHOR ~{author}~",
                "ALWAYS",
                f"  OUTER_SPRINT MOD_FOLDER ~{MOD_FOLDER.as_posix()}~",
                "  INCLUDE ~%MOD_FOLDER%/lib/functions.tph~",
                *(f"  {line}" for line in includes),
                "END",
            ]
            for number, (label, body) in components.items():
                lines += [f"BEGIN ~{label}~ DESIGNATED {number}", *body]
            (root / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

        tp2("monks.tp2", "monks-backup", "Monk and shaman weapon grant regression tests", [CLASS_GRANTS_INCLUDE], {
            40: ("Monk Revisions' quarterstaff proficiency before the fix", [profs]),
            41: ("Monk Revisions' quarterstaff proficiency", [profs, monk_call]),
            42: ("A kit added after the generator, before the fix", [generator, *kit(FAVORED_SOUL_KIT, "C0TSTFS")]),
            43: ("Favored Soul-like kit", [generator, *kit(FAVORED_SOUL_KIT, "C0TSTFS"), tail]),
            44: ("A later mod replaces the shaman table",
                 [f"COPY ~{(tables / 'CLABSH01.2DA').as_posix()}~ ~override~"]),
            45: ("A later mod adds a shaman kit", kit(SHAMAN_KIT, "C0TSTSK")),
            46: ("Another component that includes the generator", [generator]),
            47: ("Monk Revisions' new lines again", [monk_call]),
            48: ("A later mod adds its own effect to C0PR#CL", [
                "COPY_EXISTING ~C0PR#CL.SPL~ ~override~",
                "  LPF ADD_SPELL_EFFECT INT_VAR opcode = 139 target = 2 parameter1 = 4242 END",
            ]),
            49: ("A component that only ends with the ability table pass", [tail]),
        })
        # Like the main installer: extend_tables.tpa widens narrower tables
        # before every component.
        tp2("kitpack.tp2", "kitpack-backup", "Ability table pass regression tests",
            [EXTEND_TABLES_INCLUDE, CLASS_GRANTS_INCLUDE], {
                50: ("A monk kit added after the generator, before the fix", kit(MONK_KIT, "C0TSTNI")),
                51: ("A monk kit added after the generator", [*kit(MONK_KIT, "C0TSTNI"), tail]),
                52: ("A 40-level paladin table", [f"COPY ~{(tables / 'CLABPA01.2DA').as_posix()}~ ~override~", tail]),
                53: ("A later component that changes no table, before the fix", ["OUTER_SET c0_test_noop = 1"]),
                54: ("A later component that changes no table", ["OUTER_SET c0_test_noop = 1", tail]),
                55: ("A component that takes AP_C0PR#CL out of a kit table, like Dual-Classes Keep Kit Names", [
                    "COPY_EXISTING ~C0TSTNI.2DA~ ~override~",
                    "  REPLACE_TEXTUALLY ~AP_C0PR#CL~ ~****      ~",
                    "  LPF set_clab_2da_entries INT_VAR f_MinLevel = 1 f_MaxLevel = 1"
                    " STR_VAR f_Entry = AP_C0KT_6 END",
                    "  PRETTY_PRINT_2DA",
                    tail,
                ]),
            })


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


def _levels_with_entry(data: bytes) -> set[int]:
    return {level for (_, level), cell in _cells(data).items() if cell == ENTRY}


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

    def _assert_c0pr_cl_everywhere(self, before: bytes, after: bytes, levels: int = 50) -> None:
        """One AP_C0PR#CL at every level; every other entry of the table stays where it was."""
        old, new = _cells(before), _cells(after)
        self.assertEqual(list(range(1, levels + 1)), sorted({level for _, level in new}))
        for (row, level), cell in old.items():
            if cell != "****":
                self.assertEqual(cell, new.get((row, level)), f"{row} at level {level}")
        for level in range(1, levels + 1):
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
        self._steps(game, "Monk Revisions' new lines again", "generator again", "only the ability table pass")
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


class LateTableTests(MonkShamanTestCase):
    """Kits and ability tables that components add after the generator's last run."""

    def test_a_kit_added_after_the_generator_gets_c0pr_cl_from_its_own_component(self) -> None:
        before_fix = self._game()
        self._steps(before_fix, "generator", "Monk Revisions", "monk kit before the fix")
        self._assert_no_c0pr_cl(self._table(before_fix, "C0TSTNI"))
        orders = (
            ("generator", "Monk Revisions", "monk kit"),
            ("Monk Revisions", "generator", "monk kit"),
            ("Monk Revisions", "monk kit", "generator"),
        )
        for steps in orders:
            with self.subTest(steps=steps):
                game = self._game()
                self._steps(game, *steps)
                self._assert_c0pr_cl_everywhere(MONK_KIT_TABLE, self._table(game, "C0TSTNI"))
                self._assert_c0pr_cl_everywhere(SHAMAN_TABLE, self._table(game, "CLABSH01"))
                if steps[-1] == "monk kit":
                    # The pass wrote only the new kit's table.
                    self.assertEqual(["override/C0TSTNI.2DA", "override/KITLIST.2DA"],
                                     sorted(_written(game.root / "kitpack-backup", "51")))

    def test_a_replaced_table_gets_c0pr_cl_at_every_level_it_is_widened_to(self) -> None:
        game = self._game()
        self._steps(game, "generator", "40-level paladin table")
        self._assert_c0pr_cl_everywhere(PALADIN_TABLE, self._table(game, "CLABPA01"), levels=40)
        before_fix = self._game()
        self._steps(before_fix, "generator", "40-level paladin table", "no table change before the fix")
        widened = self._table(before_fix, "CLABPA01")
        self.assertEqual(list(range(1, 51)), sorted({level for _, level in _cells(widened)}))
        self.assertEqual(set(range(1, 41)), _levels_with_entry(widened), "the gap at levels 41 to 50")
        self._steps(game, "no table change")
        self._assert_c0pr_cl_everywhere(PALADIN_TABLE, self._table(game, "CLABPA01"))

    def test_a_component_that_takes_c0pr_cl_out_of_a_kit_table_puts_it_back(self) -> None:
        game = self._game()
        self._steps(game, "generator", "monk kit", "kit table loses AP_C0PR#CL")
        table = self._table(game, "C0TSTNI")
        self._assert_c0pr_cl_everywhere(MONK_KIT_TABLE, _bytes_without(table, "AP_C0KT_6"))
        self.assertEqual([1], [level for (_, level), cell in _cells(table).items() if cell == "AP_C0KT_6"])

    def test_without_eeex_weapon_usability_the_pass_changes_no_table(self) -> None:
        game = self._game()
        before = _raw_tree(game.override)
        self._steps(game, "monk kit", "40-level paladin table", "no table change")
        after = _raw_tree(game.override)
        self.assertEqual(set(before) | {"C0TSTNI.2DA"}, set(after))
        self.assertEqual({"KITLIST.2DA", "C0TSTNI.2DA", "CLABPA01.2DA"},
                         {name for name in after if after[name] != before.get(name)})
        self.assertEqual(MONK_KIT_TABLE, after["C0TSTNI.2DA"])
        for name, data in after.items():
            if name.endswith(".2DA"):
                with self.subTest(table=name):
                    self._assert_no_c0pr_cl(data)

    def test_a_pass_without_changes_writes_no_file(self) -> None:
        game = self._game()
        self._steps(game, "generator", "Monk Revisions", "monk kit", "40-level paladin table", "no table change")
        before = {path.name: path.stat().st_mtime_ns for path in game.override.iterdir()}
        tree = _raw_tree(game.override)
        self._steps(game, "only the ability table pass")
        self.assertEqual(tree, _raw_tree(game.override))
        self.assertEqual(before, {path.name: path.stat().st_mtime_ns for path in game.override.iterdir()})
        self.assertEqual([], _written(game.root / "monks-backup", "49"))


def _bytes_without(table: bytes, entry: str) -> bytes:
    """The table with `entry` replaced by ****, column widths kept."""
    return table.replace(entry.encode("ascii"), b"****".ljust(len(entry)))


def _written(backup: Path, component: str) -> list[str]:
    """The files WeiDU recorded as written by an installed component of a synthetic mod."""
    listing = backup / component / f"UNINSTALL.{component}"
    return [line.strip() for line in listing.read_text(encoding="latin-1").splitlines() if line.strip()]


class PlacementTests(unittest.TestCase):
    """Where the generator, the tweak, Monk Revisions and the installers call the shared code."""

    def test_monk_revisions_rebuilds_the_class_grants_after_changing_weapprof(self) -> None:
        _, function, _ = _call_after(MONK_REVISION, "INCLUDE ~%MOD_FOLDER%/lib/monk_staves.tpa~")
        self.assertEqual("c0_build_class_weapon_grants", function)

    def test_every_installer_defines_the_pass_in_its_always_block(self) -> None:
        for path in INSTALLERS:
            with self.subTest(installer=path.name):
                self.assertEqual(1, _always(path).count(CLASS_GRANTS_INCLUDE))

    def test_every_main_component_ends_with_the_ability_table_pass(self) -> None:
        # extend_tables.tpa widens narrower ability tables before every
        # component of the main installer, and any of them may add a kit or
        # replace a table.
        self.assertIn(EXTEND_TABLES_INCLUDE, _always(MAIN_TP2))
        components = _components(MAIN_TP2)
        self.assertGreaterEqual(len(components), 59)
        for number, lines in components.items():
            with self.subTest(component=number):
                self.assertEqual(TAIL, lines[-1])
                self.assertEqual(1, lines.count(TAIL))
        self.assertEqual(["INCLUDE ~%MOD_FOLDER%/lib/FavoredSoul.tpa~", TAIL], components["30001"][-2:],
                         "the Favored Soul adds its kit after the generator")

    def test_npc_and_tweak_components_that_write_ability_tables_end_with_the_pass(self) -> None:
        writers = {NPC_TP2: {"2001", "5102"}, TWEAK_TP2: {"1020000"}}
        for path, expected in writers.items():
            components = _components(path)
            with self.subTest(installer=path.name):
                self.assertNotIn(EXTEND_TABLES_INCLUDE, _always(path))
                found = {number for number, lines in components.items() if _ability_table_writes(lines)}
                self.assertEqual(expected, found)
                for number in expected:
                    self.assertEqual(TAIL, components[number][-1], number)
                    self.assertEqual(1, components[number].count(TAIL), number)

    def test_the_table_write_heuristic_finds_the_main_installers_kits_and_tables(self) -> None:
        components = _components(MAIN_TP2)
        for number in ("10003", "10004", "30001", "3004", "7004", "8002", "1010"):
            with self.subTest(component=number):
                self.assertTrue(_ability_table_writes(components[number]))
        for number in ("8101", "5111"):
            with self.subTest(component=number):
                self.assertEqual([], _ability_table_writes(components[number]))

    def test_generator_components_of_the_tweak_installer_end_with_the_generator(self) -> None:
        components = _components(TWEAK_TP2)
        for number, include in (("8204", GENERATOR), ("1010000", REGENERATOR)):
            with self.subTest(component=number):
                lines = components[number]
                at = next(index for index, line in enumerate(lines)
                          if line.startswith("INCLUDE") and line.endswith(f"/{include.name}~"))
                self.assertEqual([], _ability_table_writes(lines[at + 1:]))

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
