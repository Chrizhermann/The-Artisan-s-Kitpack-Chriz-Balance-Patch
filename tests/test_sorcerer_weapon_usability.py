"""Sorcerer class weapon grants of the EEex weapon usability system.

Kitpack's ``C0PR#CL.SPL`` grants per-weapon stats (opcode 326 on SPLPROT row
105, the class check) from each class's WEAPPROF column. WEAPPROF has no
SORCERER column; since upstream 7464043 sorcerers received no class weapons.
These tests run the real generator, Kitpack's regeneration tweak and the
live-install tail with WeiDU in synthetic games. They do not simulate EEex.
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    ROOT,
    WEIDU,
    _raw_tree,
    _write_marker_key_and_bif,
)


MOD_FOLDER = ROOT / "ArtisansKitpack"
GENERATOR = MOD_FOLDER / "eeex/profs_eeex.tpa"
REGENERATOR = MOD_FOLDER / "lib/profs_eeex_patch.tpa"
# The class weapon grants the generator and the tweak write (WEAPPROF_CLASS).
CLASS_GRANTS = MOD_FOLDER / "eeex/class_weapon_grants.tpa"
CLASS_GRANTS_INCLUDE = b"INCLUDE ~%MOD_FOLDER%/eeex/class_weapon_grants.tpa~"
BASE_SPL = MOD_FOLDER / "eeex/profs/C0PR#CL.spl"
BLANK_CLAB = MOD_FOLDER / "eeex/2da/blankclab.2da"
PATCH_DIR = ROOT / "live-patch/AKCB_SORCERER_WEAPONS"
PATCH_TP2 = PATCH_DIR / "setup-AKCB_SORCERER_WEAPONS.tp2"
# The WEAPPROF_CLASS entry whose absence reproduces the pre-fix generator.
SORCERER_ARRAY_LINE = re.compile(rb"^[ \t]*~SORCERER~[ \t]*=>[ \t]*4[ \t]*\r?\n", re.MULTILINE)

MAGE, SORCERER, CLASS_ROW, MARKER = 1, 19, 105, 99999
CLASSES = (
    "MAGE", "FIGHTER", "CLERIC", "THIEF", "BARD", "PALADIN", "FIGHTER_MAGE",
    "FIGHTER_CLERIC", "FIGHTER_THIEF", "FIGHTER_MAGE_THIEF", "DRUID", "RANGER",
    "MAGE_THIEF", "CLERIC_MAGE", "CLERIC_THIEF", "FIGHTER_DRUID",
    "FIGHTER_MAGE_CLERIC", "CLERIC_RANGER", "SORCERER", "MONK", "SHAMAN",
)
CLASS_IDS = {name: index for index, name in enumerate(CLASSES, start=1)}
# WEAPPROF data rows 8-27 in table order, with their proficiency stat ids.
WEAPONS = (
    ("BASTARDSWORD", 89), ("LONGSWORD", 90), ("SHORTSWORD", 91), ("AXE", 92),
    ("TWOHANDEDSWORD", 93), ("KATANA", 94), ("SCIMITARWAKISASHININJATO", 95),
    ("DAGGER", 96), ("WARHAMMER", 97), ("CLUB", 115), ("SPEAR", 98),
    ("HALBERD", 99), ("FLAILMORNINGSTAR", 100), ("MACE", 101),
    ("QUARTERSTAFF", 102), ("CROSSBOW", 103), ("LONGBOW", 104),
    ("SHORTBOW", 105), ("DART", 106), ("SLING", 107),
)
ALL_WEAPONS = frozenset(name for name, _ in WEAPONS)
VANILLA_MAGE = frozenset({"DAGGER", "QUARTERSTAFF", "DART", "SLING"})
CLERIC = frozenset({"WARHAMMER", "CLUB", "FLAILMORNINGSTAR", "MACE", "QUARTERSTAFF", "SLING"})
DRUID = frozenset({"SCIMITARWAKISASHININJATO", "DAGGER", "CLUB", "SPEAR", "QUARTERSTAFF", "DART", "SLING"})
THIEF = frozenset({
    "LONGSWORD", "SHORTSWORD", "KATANA", "SCIMITARWAKISASHININJATO", "DAGGER",
    "CLUB", "QUARTERSTAFF", "CROSSBOW", "SHORTBOW", "DART", "SLING",
})
MONK = frozenset({"CLUB", "DAGGER", "QUARTERSTAFF", "CROSSBOW", "DART", "SLING"})
# WEAPPROF header positions are engine constants: base classes at 3-20, MONK
# at 50 and SHAMAN at 59. Kit columns fill the gaps.
CLASS_COLUMNS = {
    "MAGE": 3, "FIGHTER": 4, "CLERIC": 5, "THIEF": 6, "BARD": 7, "PALADIN": 8,
    "DRUID": 9, "RANGER": 10, "FIGHTER_MAGE": 11, "FIGHTER_CLERIC": 12,
    "FIGHTER_THIEF": 13, "FIGHTER_MAGE_THIEF": 14, "MAGE_THIEF": 15,
    "CLERIC_MAGE": 16, "CLERIC_THIEF": 17, "FIGHTER_DRUID": 18,
    "FIGHTER_MAGE_CLERIC": 19, "CLERIC_RANGER": 20, "MONK": 50, "SHAMAN": 59,
}


def _class_weapons(mage: frozenset[str]) -> dict[str, frozenset[str]]:
    fighter_like = ALL_WEAPONS
    return {
        "MAGE": mage, "FIGHTER": fighter_like, "CLERIC": CLERIC, "THIEF": THIEF,
        "BARD": THIEF, "PALADIN": fighter_like, "DRUID": DRUID,
        "RANGER": fighter_like, "FIGHTER_MAGE": fighter_like,
        "FIGHTER_CLERIC": fighter_like, "FIGHTER_THIEF": fighter_like,
        "FIGHTER_MAGE_THIEF": fighter_like, "MAGE_THIEF": THIEF | mage,
        "CLERIC_MAGE": CLERIC | mage, "CLERIC_THIEF": CLERIC | THIEF,
        "FIGHTER_DRUID": fighter_like, "FIGHTER_MAGE_CLERIC": fighter_like,
        "CLERIC_RANGER": fighter_like, "MONK": MONK, "SHAMAN": DRUID,
    }


def _weapprof(mage: frozenset[str]) -> bytes:
    labels = ["ID", "NAME_REF", "DESC_REF"] + [f"KIT{index}" for index in range(3, 61)]
    for name, position in CLASS_COLUMNS.items():
        labels[position] = name
    labels[56] = "DRAGON_DISCIPLE"
    labels[60] = "C0_TEST_SORC"
    allowed = _class_weapons(mage)
    allowed["DRAGON_DISCIPLE"] = mage
    allowed["C0_TEST_SORC"] = mage | {"LONGSWORD"}  # kit columns do not feed class grants
    rows = [(f"BG1_ROW{index}", index) for index in range(8)]
    rows += list(WEAPONS)
    rows += [("2HANDED", 111), ("SWORDANDSHIELD", 112), ("SINGLEWEAPON", 113), ("2WEAPON", 114)]
    lines = ["2DA V1.0", "0", "        " + " ".join(labels)]
    for label, ident in rows:
        cells = [str(ident), "0", "0"]
        for column in labels[3:]:
            cells.append("2" if label in allowed.get(column, frozenset()) else "0")
        lines.append(f"{label} " + " ".join(cells))
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def _splprot() -> bytes:
    rows = []
    for index in range(110):
        if index == 0:
            rows.append("0_EA>=0 0x10a 0 4")
        elif index == 43:
            rows.append("43_SOURCE 0x100 * *")  # vanilla ships non-numeric cells
        elif index == CLASS_ROW:
            rows.append("105_CLASS=n 0x10d -1 1")
        else:
            rows.append(f"{index}_SYNTHETIC {index} -1 1")
    text = "2DA V1.0\r\n0xffff\r\n          STAT VALUE RELATION\r\n" + "\r\n".join(rows) + "\r\n"
    return text.encode("ascii")


def _ids(entries: dict[int, str]) -> bytes:
    lines = ["IDS V1.0"] + [f"{value} {name}" for value, name in sorted(entries.items())]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def _read_ids(path: Path) -> dict[str, int]:
    symbols = {}
    for line in path.read_text(encoding="ascii").splitlines()[1:]:
        if len(fields := line.split()) == 2:
            symbols[fields[1]] = int(fields[0], 0)
    return symbols


def _read_2da_rows(path: Path) -> list[tuple[str, ...]]:
    """Data rows in SPLPROT numbering: row 0 is the first line after the header."""
    lines = [line.split() for line in path.read_text(encoding="ascii").splitlines()]
    return [tuple(fields) for fields in lines[3:] if fields]


KITLIST = (
    b"2DA V1.0\r\n*\r\n"
    b"         ROWNAME LOWER MIXED HELP ABILITIES PROFICIENCY UNUSABLE CLASS KITIDS\r\n"
    b"0        RESERVE * * * * * * * *\r\n"
    b"1        DRAGON_DISCIPLE 1 2 3 CLABSO01 56 0x00004000 19 0x4023\r\n"
    b"2        C0_TEST_SORC 1 2 3 C0TSTSO 60 0x00004000 19 0x4040\r\n"
    b"3        C0_NO_TABLE 1 2 3 C0NOCLAB 4 0x00000000 2 0x4041\r\n"
)
BASE_CLABS = (
    "CLABBA01", "CLABDR01", "CLABFI01", "CLABMO01", "CLABPA01", "CLABPR01",
    "CLABRN01", "CLABTH01", "CLABMA01", "CLABSO01", "CLABSH01", "C0TSTSO",
)
# Vanilla-like sorcerer weapons: usable by fighters and mages, but not by
# every class, so the generator replaces their class bits with an op319 gate.
# name: (item type, proficiency, usability dword, stats.ids proficiency stat)
GATED_SORCERER_WEAPONS = {
    "DAGGER": (16, 96, 0x00000080, "C0_PROFICIENCYDAGGER"),  # not cleric
    "QUARTERSTAFF": (26, 102, 0x00020000, "C0_PROFICIENCYQUARTERSTAFF"),  # not fighter/thief
    "DART": (24, 106, 0x00000080, "C0_PROFICIENCYDART"),  # not cleric
    "SLING": (18, 107, 0x00002000, "C0_PROFICIENCYSLING"),  # not fighter/mage
}


def _item(item_type: int, proficiency: int, usability: int) -> bytes:
    data = bytearray(0x72)
    data[0:8] = b"ITM V1  "
    struct.pack_into("<II", data, 0x08, 0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into("<HI", data, 0x1C, item_type, usability)
    data[0x31] = proficiency
    struct.pack_into("<IHIHH", data, 0x64, 0x72, 0, 0x72, 0, 0)
    return bytes(data)


def _item_equipped_effects(data: bytes) -> list[bytes]:
    effect_offset, first, count = struct.unpack_from("<IHH", data, 0x6A)
    return [data[effect_offset + (first + i) * 0x30 : effect_offset + (first + i + 1) * 0x30]
            for i in range(count)]


def _creature(class_id: int) -> bytes:
    """Empty CRE V1.0 with EFF V2 effects and no items, spells or effects."""
    end = 0x2D4 + 0x50
    data = bytearray(end)
    data[0:8] = b"CRE V1.0"
    struct.pack_into("<II", data, 0x08, 0xFFFFFFFF, 0xFFFFFFFF)
    data[0x33] = 1
    data[0x273] = class_id
    struct.pack_into("<11I", data, 0x2A0, end, 0, end, 0, end, 0, 0x2D4, end, 0, end, 0)
    data[0x2D4:0x2D4 + 0x4C] = b"\xff" * 0x4C
    return bytes(data)


def _effect(
    opcode: int,
    *,
    target: int = 2,
    power: int = 0,
    parameter1: int = 0,
    parameter2: int = 0,
    timing: int = 0,
    resist: int = 0,
    duration: int = 0,
    probability1: int = 100,
    resource: str = "",
    special: int = 0,
) -> bytes:
    return struct.pack(
        "<HBBIIBBIBB8sIIIiI",
        opcode, target, power, parameter1, parameter2, timing, resist,
        duration, probability1, 0, resource.encode("ascii").ljust(8, b"\0"),
        0, 0, 0, 0, special,
    )


def _grant(class_id: int, weapon: int, **fields: int) -> bytes:
    values = {"parameter1": class_id, "parameter2": CLASS_ROW, "special": MARKER}
    values.update(fields)
    return _effect(326, resource=f"C0PR#{weapon}", **values)


def _as_sorcerer(block: bytes) -> bytes:
    return block[:4] + struct.pack("<I", SORCERER) + block[8:]


def _build_spl(abilities: list[list[bytes]], casting: Sequence[bytes] = (), *,
               casting_first: bool = False) -> bytes:
    base = BASE_SPL.read_bytes()
    header, template = bytearray(base[:0x72]), base[0x72:0x9A]
    table: list[bytes] = []
    casting_index = 0
    if casting_first:
        table.extend(casting)
    ability_blocks = bytearray()
    for effects in abilities:
        block = bytearray(template)
        struct.pack_into("<HH", block, 0x1E, len(effects), len(table))
        ability_blocks += block
        table.extend(effects)
    if casting and not casting_first:
        casting_index = len(table)
        table.extend(casting)
    struct.pack_into("<IHIHH", header, 0x64, 0x72, len(abilities),
                     0x72 + len(ability_blocks), casting_index, len(casting))
    return bytes(header + ability_blocks + b"".join(table))


def _parse_spl(data: bytes) -> tuple[list[list[bytes]], list[bytes]]:
    """Return ability and casting effects; reject overlaps and stray bytes."""
    if data[:8] != b"SPL V1  ":
        raise ValueError("not an SPL V1 resource")
    ability_offset, ability_count, effect_offset, cast_first, cast_count = struct.unpack_from(
        "<IHIHH", data, 0x64
    )
    ranges = [(cast_first, cast_count)] if cast_count else []
    for index in range(ability_count):
        count, first = struct.unpack_from("<HH", data, ability_offset + index * 0x28 + 0x1E)
        ranges.append((first, count))
    used = sorted(position for first, count in ranges for position in range(first, first + count))
    if used != list(range(len(used))) or len(data) != effect_offset + len(used) * 0x30:
        raise ValueError(f"effect table is not a disjoint cover: {ranges}")

    def blocks(first: int, count: int) -> list[bytes]:
        return [data[effect_offset + (first + i) * 0x30 : effect_offset + (first + i + 1) * 0x30]
                for i in range(count)]

    abilities = [blocks(first, count) for first, count in ranges[1 if cast_count else 0 :]]
    return abilities, blocks(cast_first, cast_count)


def _fields(block: bytes) -> tuple[int, int, int, str]:
    opcode, parameter1, parameter2 = struct.unpack_from("<H2xII", block)
    resource = block[0x14:0x1C].split(b"\0", 1)[0].decode("ascii").upper()
    return opcode, parameter1, parameter2, resource


def _grants(effects: list[bytes], class_id: int) -> list[str]:
    return [
        resource
        for opcode, parameter1, parameter2, resource in map(_fields, effects)
        if opcode == 326 and parameter2 == CLASS_ROW and parameter1 == class_id
    ]


def _expected(mage: frozenset[str], class_name: str) -> list[str]:
    column = "MAGE" if class_name == "SORCERER" else class_name
    allowed = _class_weapons(mage)[column]
    return [f"C0PR#{ident}" for name, ident in WEAPONS if name in allowed]


class SyntheticGame:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.override = root / "override"
        self.override.mkdir(parents=True)
        shutil.copy2(WEIDU, root / "weidu.exe")
        _write_marker_key_and_bif(root)
        for path in (root / "lang/en_us/dialog.tlk", root / "dialog.tlk"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ONE_EMPTY_STRING_TLK)
        (self.override / "CLASS.IDS").write_bytes(
            _ids({value: name for name, value in CLASS_IDS.items()})
        )
        (self.override / "unrelated.txt").write_bytes(b"preserve this resource\r\n")
        self.stable_inputs = {
            relative: (root / relative).read_bytes()
            for relative in ("chitin.key", "data/akcbtest.bif", "dialog.tlk")
        }

    def run(self, tp2: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "weidu.exe"), tp2, "--game", str(self.root), *arguments,
             "--language", "0", "--use-lang", "en_US", "--no-exit-pause", "--quick-log"],
            cwd=self.root, capture_output=True, encoding="utf-8", errors="replace",
            timeout=300, check=False,
        )

    def c0pr_cl(self) -> bytes:
        return (self.override / "C0PR#CL.SPL").read_bytes()


class GeneratorGame(SyntheticGame):
    """Inputs for Kitpack's first-run generator; on_load script compilation is skipped."""

    def __init__(self, root: Path, *, mage: frozenset[str] = VANILLA_MAGE) -> None:
        super().__init__(root)
        files = {
            "WEAPPROF.2DA": _weapprof(mage),
            "SPLPROT.2DA": _splprot(),
            "STATS.IDS": _ids({value: f"SYNTHETIC_STAT_{value}" for value in range(203)}),
            "KITLIST.2DA": KITLIST,
            # Present means installed: on_load_eeex.tpa then skips the BAF
            # compilation, which needs the full script IDS set.
            "C0PR#EF.BCS": b"SC\r\nSC\r\n",
        }
        for item_type, proficiency, usability, _ in GATED_SORCERER_WEAPONS.values():
            files[f"AKCB{proficiency}.ITM"] = _item(item_type, proficiency, usability)
        files["AKCBRING.ITM"] = _item(10, 0, 0)
        files["AKCBSORC.CRE"] = _creature(SORCERER)
        for name, data in files.items():
            (self.override / name).write_bytes(data)
        for table in BASE_CLABS:
            shutil.copyfile(BLANK_CLAB, self.override / f"{table}.2DA")
        # The generator before the fix: its class weapon grants without SORCERER.
        legacy_grants = root / "legacy_class_weapon_grants.tpa"
        source, removed = SORCERER_ARRAY_LINE.subn(b"", CLASS_GRANTS.read_bytes())
        if removed != 1:
            raise AssertionError("class_weapon_grants.tpa must map SORCERER exactly once")
        legacy_grants.write_bytes(source)
        legacy = root / "legacy_profs_eeex.tpa"
        generator = GENERATOR.read_bytes()
        if generator.count(CLASS_GRANTS_INCLUDE) != 1:
            raise AssertionError("profs_eeex.tpa must include class_weapon_grants.tpa exactly once")
        legacy.write_bytes(generator.replace(
            CLASS_GRANTS_INCLUDE, f"INCLUDE ~{legacy_grants.as_posix()}~".encode("ascii")))
        (root / "harness.tp2").write_text(
            "BACKUP ~harness-backup~\n"
            "AUTHOR ~Sorcerer weapon usability regression tests~\n"
            "ALWAYS\n"
            f"  OUTER_SPRINT MOD_FOLDER ~{MOD_FOLDER.as_posix()}~\n"
            "  INCLUDE ~%MOD_FOLDER%/lib/functions.tph~\n"
            "END\n"
            "BEGIN ~Fixed generator~ DESIGNATED 0\n"
            f"INCLUDE ~{GENERATOR.as_posix()}~\n"
            "BEGIN ~Generator before the fix~ DESIGNATED 1\n"
            f"INCLUDE ~{legacy.as_posix()}~\n"
            "BEGIN ~Update EEex-based Weapon Usability Changes~ DESIGNATED 2\n"
            f"INCLUDE ~{REGENERATOR.as_posix()}~\n",
            encoding="utf-8",
            newline="\n",
        )


class SorcererWeaponTestCase(unittest.TestCase):
    def _temporary_root(self, prefix: str) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix=prefix)
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / "game"

    def _generator_game(self, **kwargs: frozenset[str]) -> GeneratorGame:
        return GeneratorGame(self._temporary_root("akcb-sorc-gen-"), **kwargs)

    def _transcript(self, process: subprocess.CompletedProcess[str]) -> str:
        return f"{process.stdout}\n{process.stderr}"

    def _assert_installed(self, game: SyntheticGame, process: subprocess.CompletedProcess[str],
                          *, warnings: bool = False) -> str:
        transcript = self._transcript(process)
        # WeiDU 249 exits with 3 when a component installed with warnings.
        self.assertEqual(3 if warnings else 0, process.returncode, transcript)
        expected = "INSTALLED WITH WARNINGS" if warnings else "SUCCESSFULLY INSTALLED"
        self.assertIn(expected, transcript, transcript)
        for relative, original in game.stable_inputs.items():
            self.assertEqual(original, (game.root / relative).read_bytes(), relative)
        return transcript

    def _install_harness(self, game: GeneratorGame, component: str) -> None:
        self._assert_installed(game, game.run("harness.tp2", "--force-install-list", component))

    def _install_tail(self, game: SyntheticGame, *, warnings: bool = False) -> str:
        if not (game.root / PATCH_DIR.name).exists():
            shutil.copytree(PATCH_DIR, game.root / PATCH_DIR.name)
        process = game.run(f"{PATCH_DIR.name}/{PATCH_TP2.name}", "--force-install-list", "0")
        return self._assert_installed(game, process, warnings=warnings)

    def _uninstall_tail(self, game: SyntheticGame) -> None:
        process = game.run(f"{PATCH_DIR.name}/{PATCH_TP2.name}", "--force-uninstall-list", "0")
        transcript = self._transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertNotIn("NOT UNINSTALLED", transcript, transcript)


class GeneratorTests(SorcererWeaponTestCase):
    def _assert_sorcerers_mirror_mages(self, data: bytes, mage: frozenset[str]) -> None:
        (effects,), casting = _parse_spl(data)
        self.assertEqual([], casting)
        expected = _expected(mage, "MAGE")
        self.assertEqual(expected, _grants(effects, MAGE))
        self.assertEqual(expected, _grants(effects, SORCERER))
        mage_blocks = [block for block in effects if _fields(block)[:3] == (326, MAGE, CLASS_ROW)]
        tail = effects[-len(expected):]
        self.assertEqual([_as_sorcerer(block) for block in mage_blocks], tail,
                         "sorcerer grants must copy the mage grants and come last")
        last_reset = max(i for i, block in enumerate(effects) if _fields(block)[0] == 321)
        first_grant = min(i for i, block in enumerate(effects) if _fields(block)[0] == 326)
        self.assertLess(last_reset, first_grant, "stat resets must precede every grant")

    def test_fresh_install_grants_every_class_its_weapprof_column(self) -> None:
        game = self._generator_game()
        self._install_harness(game, "0")
        (effects,), _ = _parse_spl(game.c0pr_cl())
        for name, class_id in CLASS_IDS.items():
            with self.subTest(class_name=name):
                self.assertEqual(_expected(VANILLA_MAGE, name), _grants(effects, class_id))
        self.assertEqual(["C0PR#96", "C0PR#102", "C0PR#106", "C0PR#107"], _grants(effects, SORCERER))
        self._assert_sorcerers_mirror_mages(game.c0pr_cl(), VANILLA_MAGE)
        for table in ("CLABSO01", "C0TSTSO"):
            self.assertIn(b"AP_C0PR#CL", (game.override / f"{table}.2DA").read_bytes(), table)

    def test_each_gated_sorcerer_weapon_is_unlocked_by_a_sorcerer_grant(self) -> None:
        game = self._generator_game()
        self._install_harness(game, "0")
        stats = _read_ids(game.override / "STATS.IDS")
        splprot = _read_2da_rows(game.override / "SPLPROT.2DA")
        sorcerer = _grants(_parse_spl(game.c0pr_cl())[0][0], SORCERER)
        for name, (_, proficiency, _, stat_name) in GATED_SORCERER_WEAPONS.items():
            with self.subTest(weapon=name):
                item = (game.override / f"AKCB{proficiency}.ITM").read_bytes()
                self.assertEqual(0, struct.unpack_from("<I", item, 0x1E)[0], "class bits cleared")
                gates = [block for block in _item_equipped_effects(item) if _fields(block)[0] == 319]
                self.assertEqual(1, len(gates), gates)
                self.assertEqual(3, gates[0][3], "power 3: usable only by a SPLPROT match")
                row = struct.unpack_from("<I", gates[0], 0x08)[0]
                self.assertEqual((stat_name, str(stats[stat_name]), "1", "1"), splprot[row])
                (grant_effects,), _ = _parse_spl((game.override / f"C0PR#{proficiency}.SPL").read_bytes())
                stat_writes = [struct.unpack_from("<I", block, 0x2C)[0]
                               for block in grant_effects if _fields(block)[0] == 401]
                self.assertEqual([stats[stat_name]], stat_writes)
                self.assertIn(f"C0PR#{proficiency}", sorcerer)
        self.assertEqual([], _item_equipped_effects((game.override / "AKCBRING.ITM").read_bytes()))

    def test_sorcerer_grants_follow_the_installed_mage_column(self) -> None:
        mage = frozenset({"SHORTSWORD", "DAGGER", "QUARTERSTAFF", "DART"})
        game = self._generator_game(mage=mage)
        self._install_harness(game, "0")
        self.assertEqual(["C0PR#91", "C0PR#96", "C0PR#102", "C0PR#106"],
                         _grants(_parse_spl(game.c0pr_cl())[0][0], SORCERER))
        self._assert_sorcerers_mirror_mages(game.c0pr_cl(), mage)

    def test_generator_before_the_fix_reproduces_the_regression(self) -> None:
        game = self._generator_game()
        self._install_harness(game, "1")
        (effects,), _ = _parse_spl(game.c0pr_cl())
        self.assertEqual([], _grants(effects, SORCERER))
        self.assertEqual(_expected(VANILLA_MAGE, "MAGE"), _grants(effects, MAGE))

    def test_update_tweak_regenerates_sorcerer_grants_like_a_fresh_install(self) -> None:
        fresh = self._generator_game()
        self._install_harness(fresh, "0")
        legacy = self._generator_game()
        self._install_harness(legacy, "1")
        self._install_harness(legacy, "2")
        self.assertEqual(fresh.c0pr_cl(), legacy.c0pr_cl())
        self._install_harness(fresh, "2")
        self.assertEqual(legacy.c0pr_cl(), fresh.c0pr_cl(), "regeneration must not duplicate grants")


class TailOnGeneratedInstallTests(SorcererWeaponTestCase):
    def _assert_tail_equals_fresh_install(self, mage: frozenset[str]) -> None:
        fresh = self._generator_game(mage=mage)
        self._install_harness(fresh, "0")
        legacy = self._generator_game(mage=mage)
        self._install_harness(legacy, "1")
        before = _raw_tree(legacy.override)
        transcript = self._install_tail(legacy)
        self.assertIn("added", transcript)
        self.assertEqual(_raw_tree(fresh.override), _raw_tree(legacy.override))
        self._uninstall_tail(legacy)
        self.assertEqual(before, _raw_tree(legacy.override))

    def test_tail_on_install_before_fix_matches_fresh_fixed_install(self) -> None:
        self._assert_tail_equals_fresh_install(VANILLA_MAGE)

    def test_tail_matches_fresh_install_for_a_changed_mage_column(self) -> None:
        self._assert_tail_equals_fresh_install(frozenset({"SHORTSWORD", "DAGGER", "CLUB", "QUARTERSTAFF"}))

    def test_tail_leaves_a_fixed_install_byte_identical(self) -> None:
        game = self._generator_game()
        self._install_harness(game, "0")
        before = _raw_tree(game.override)
        transcript = self._install_tail(game)
        self.assertIn("already receive every class weapon", transcript)
        self.assertEqual(before, _raw_tree(game.override))
        self._uninstall_tail(game)
        self.assertEqual(before, _raw_tree(game.override))


class TailPatchTests(SorcererWeaponTestCase):
    def _game(self, spl: bytes | None, *, class_ids: dict[int, str] | None = None) -> SyntheticGame:
        game = SyntheticGame(self._temporary_root("akcb-sorc-tail-"))
        if class_ids is not None:
            (game.override / "CLASS.IDS").write_bytes(_ids(class_ids))
        if spl is not None:
            (game.override / "C0PR#CL.SPL").write_bytes(spl)
        return game

    def _assert_rejected(self, game: SyntheticGame, marker: str) -> str:
        before = _raw_tree(game.override)
        shutil.copytree(PATCH_DIR, game.root / PATCH_DIR.name)
        process = game.run(f"{PATCH_DIR.name}/{PATCH_TP2.name}", "--force-install-list", "0")
        transcript = self._transcript(process)
        self.assertNotIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertIn(marker, transcript, transcript)
        self.assertEqual(before, _raw_tree(game.override))
        return transcript

    def test_adds_only_missing_grants_and_keeps_unrelated_effects(self) -> None:
        resets = [_effect(321, resource=f"C0PR#{weapon}") for weapon in (96, 102, 106, 107)]
        pips = [_effect(326, parameter2=426, resource="C0PR#96")]
        mage = [_grant(MAGE, weapon) for weapon in (96, 102, 106, 107)]
        unrelated = [
            _effect(326, parameter1=MAGE, parameter2=CLASS_ROW, resource="AKTEST01", special=MARKER),
            _effect(326, parameter1=MAGE, parameter2=419, resource="C0PR#89"),
            _grant(CLASS_IDS["THIEF"], 90),
        ]
        sorcerer_dagger = _grant(SORCERER, 96, special=0, target=1)
        effects = resets + pips + mage + unrelated + [sorcerer_dagger] + [mage[1]]
        game = self._game(_build_spl([effects]))
        before = _raw_tree(game.override)
        self._install_tail(game)
        (after,), casting = _parse_spl(game.c0pr_cl())
        self.assertEqual([], casting)
        self.assertEqual(effects + [_as_sorcerer(mage[1]), _as_sorcerer(mage[2]), _as_sorcerer(mage[3])], after)
        self._uninstall_tail(game)
        self.assertEqual(before, _raw_tree(game.override))

    def test_old_style_sorcerer_grants_are_kept_as_they_are(self) -> None:
        old_style = [_effect(321, resource="C0PR#96")]
        for class_id in (MAGE, SORCERER):
            old_style += [_grant(class_id, weapon, target=1, special=0) for weapon in (96, 102, 106, 107)]
        game = self._game(_build_spl([old_style]))
        before = _raw_tree(game.override)
        transcript = self._install_tail(game)
        self.assertIn("already receive every class weapon", transcript)
        self.assertEqual(before, _raw_tree(game.override))

    def test_each_ability_gets_its_own_copies_and_indices_stay_consistent(self) -> None:
        first = [_effect(321, resource="C0PR#96"), _grant(MAGE, 96), _grant(MAGE, 107, timing=1)]
        second = [_grant(MAGE, 102, target=1), _grant(SORCERER, 102, target=1), _grant(MAGE, 106)]
        casting = [_effect(139, target=1, parameter1=12345)]
        for casting_first in (False, True):
            with self.subTest(casting_first=casting_first):
                game = self._game(_build_spl([first, second], casting, casting_first=casting_first))
                self._install_tail(game)
                abilities, after_casting = _parse_spl(game.c0pr_cl())
                self.assertEqual(casting, after_casting)
                self.assertEqual(
                    [first + [_as_sorcerer(first[1]), _as_sorcerer(first[2])],
                     second + [_as_sorcerer(second[2])]],
                    abilities,
                )

    def test_install_without_mage_grants_warns_and_changes_nothing(self) -> None:
        game = self._game(_build_spl([[_effect(321, resource="C0PR#96"), _grant(CLASS_IDS["FIGHTER"], 96)]]))
        before = _raw_tree(game.override)
        transcript = self._install_tail(game, warnings=True)
        self.assertIn("grants mages no class weapons", transcript)
        self.assertEqual(before, _raw_tree(game.override))

    def test_missing_dispatcher_skips_without_mutation(self) -> None:
        game = self._game(None)
        self._assert_rejected(game, "SKIPPING")

    def test_malformed_or_unresolvable_inputs_fail_before_mutation(self) -> None:
        valid = _build_spl([[_grant(MAGE, 96)]])
        truncated = bytearray(valid)
        struct.pack_into("<H", truncated, 0x72 + 0x1E, 5)
        shared = _build_spl([[_grant(MAGE, 96)], [_grant(MAGE, 102)]])
        shared = bytearray(shared)
        struct.pack_into("<HH", shared, 0x72 + 0x28 + 0x1E, 1, 0)
        no_sorcerer = {value: name for name, value in CLASS_IDS.items() if name != "SORCERER"}
        cases = {
            "is not an SPL V1 resource": (b"SPL V2  " + valid[8:], None),
            "effects beyond the end of the file": (bytes(truncated), None),
            "shared by several abilities": (bytes(shared), None),
            "too short for an SPL V1 header": (valid[:0x40], None),
            "must define both MAGE and SORCERER": (valid, no_sorcerer),
        }
        for reason, (spl, class_ids) in cases.items():
            with self.subTest(reason=reason):
                game = self._game(spl, class_ids=class_ids)
                transcript = self._assert_rejected(game, "NOT INSTALLED DUE TO ERRORS")
                self.assertIn(reason, transcript)


if __name__ == "__main__":
    unittest.main()
