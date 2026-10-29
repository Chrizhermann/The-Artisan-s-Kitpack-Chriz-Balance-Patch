"""Kits that borrow the Shapeshifter's item usability bit.

The Invisible Blade, the Elementalist and Bardic Wonders' Dancer cannot wear
armor through the Shapeshifter's KITLIST.2DA UNUSABLE bit 0x10000000. Item
files also set that bit wherever druids may not use an item, so katanas, the
Rogue's Potion of Frost Giant Strength and some mage scrolls were closed to
those kits. ``c0_free_borrowed_shapeshifter_bit`` (lib/shapeshifter_kit_bit.tpa)
takes the bit off for them and keeps every other kit with the bit blocked
through opcode 319 kit checks. These tests run it with WeiDU in synthetic games,
through the installers' own lines; they do not simulate the engine's
usability check.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_monk_shaman_weapon_grants import _always, _code_lines, _components
from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    ROOT,
    WEIDU,
    _raw_tree,
    _write_marker_key_and_bif,
)

MOD_FOLDER = ROOT / "ArtisansKitpack"
MAIN_TP2 = MOD_FOLDER / "ArtisansKitpack.TP2"
TWEAK_TP2 = ROOT / "ArtisansKitpack_tweak/ArtisansKitpack_tweak.TP2"
LIBRARY = MOD_FOLDER / "lib/shapeshifter_kit_bit.tpa"
REGENERATOR = MOD_FOLDER / "lib/profs_eeex_patch.tpa"
LIBRARY_INCLUDE = "INCLUDE ~%MOD_FOLDER%/lib/shapeshifter_kit_bit.tpa~"
CLASS_GRANTS_INCLUDE = "INCLUDE ~%MOD_FOLDER%/eeex/class_weapon_grants.tpa~"
CALL = "LAF c0_free_borrowed_shapeshifter_bit END"
MARKER = "C0SHAPE_"

SHAPESHIFTER_BIT = 0x10000000
# KITIDS values of the synthetic KITLIST.2DA.
SHAPESHIFTER = 0x4011
GRIZZLY_BEAR = 0x4022
BERSERKER = 0x4001
DANCER = 0x402E
ELEMENTALIST = 0x4044
INVISIBLE_BLADE = 0x4048
MIXED_THIEF = 0x4050  # a thief kit with the bit and the Assassin's bit
SHAMAN_KIT = 0x4051  # a shaman kit with the bit: no shaman kits own item bits

KITLIST_HEAD = (
    "2DA V1.0\r\n*\r\n"
    "         ROWNAME LOWER MIXED HELP ABILITIES PROFICIENCY UNUSABLE CLASS KITIDS\r\n"
    "0        RESERVE * * * * * * * *\r\n"
)
KIT_ROWS = {
    BERSERKER: "1 BERSERKER 1 2 3 CLABFI02 30 0x00000001 2 0x4001",
    SHAPESHIFTER: "17 SHAPESHIFTER 1 2 3 CLABDR03 45 0x10000000 11 0x00004011",
    GRIZZLY_BEAR: "34 GRIZZLY_BEAR 1 2 3 CLABFI01 62 0xFFFFFFFF 2 0x00004022",
    DANCER: "46 C0DANCE 1 2 3 C0DANCE 67 0x10000000 5 0x0000402E",
    ELEMENTALIST: "68 C0ELEM 1 2 3 C0ELEM 89 0x10000000 11 0x00004044",
    INVISIBLE_BLADE: "72 C0_INVISIBLE_BLADE 1 2 3 C0INVBL 93 0x10000000 4 0x00004048",
    MIXED_THIEF: "80 C0_TEST_MIXED 1 2 3 C0TSTMX 94 0x10040000 4 0x00004050",
    SHAMAN_KIT: "81 C0_TEST_SHAMAN 1 2 3 C0TSTSH 95 0x10000000 21 0x00004051",
}
VANILLA_KITS = (BERSERKER, SHAPESHIFTER, GRIZZLY_BEAR)


def _kitlist(kits: tuple[int, ...]) -> bytes:
    return (KITLIST_HEAD + "".join(f"{KIT_ROWS[kit]}\r\n" for kit in kits)).encode("ascii")


def _effect(opcode: int, *, target: int = 1, power: int = 0, parameter1: int = 0,
            parameter2: int = 0, timing: int = 2, resource: str = "", special: int = 0) -> bytes:
    return struct.pack(
        "<HBBIIBBIBB8sIIIiI",
        opcode, target, power, parameter1, parameter2, timing, 0, 0, 100, 0,
        resource.encode("ascii").ljust(8, b"\0"), 0, 0, 0, 0, special,
    )


def _proficiency_gate() -> bytes:
    """The EEex weapon usability gate Kitpack's generator puts on katanas."""
    return _effect(319, target=2, power=3, parameter2=448)


def _item(item_type: int, usability: int, kits: int, *, equipped: tuple[bytes, ...] = (),
          ability: tuple[bytes, ...] | None = None, globals_first: bool = True,
          signature: bytes = b"ITM V1  ") -> bytes:
    """An ITM V1 with its kit bits, equipped effects and at most one ability."""
    header = bytearray(0x72)
    header[0:8] = signature
    struct.pack_into("<II", header, 0x08, 0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into("<HI", header, 0x1C, item_type, usability)
    for offset, shift in ((0x29, 24), (0x2B, 16), (0x2D, 8), (0x2F, 0)):
        header[offset] = (kits >> shift) & 0xFF
    struct.pack_into("<I", header, 0x34, 1234)  # price, to see the rest stay as it was
    abilities = b""
    ability_effects: tuple[bytes, ...] = ()
    if ability is not None:
        ability_effects = ability
    effects_offset = 0x72 + (0x38 if ability is not None else 0)
    global_index = 0 if globals_first else len(ability_effects)
    ability_index = len(equipped) if globals_first else 0
    if ability is not None:
        block = bytearray(0x38)
        block[0] = 1  # melee
        struct.pack_into("<HH", block, 0x1E, len(ability_effects), ability_index)
        abilities = bytes(block)
    struct.pack_into("<IHIHH", header, 0x64, 0x72, 1 if ability is not None else 0,
                     effects_offset, global_index, len(equipped))
    effects = equipped + ability_effects if globals_first else ability_effects + equipped
    return bytes(header) + abilities + b"".join(effects)


def _kits(data: bytes) -> int:
    return data[0x29] << 24 | data[0x2B] << 16 | data[0x2D] << 8 | data[0x2F]


def _equipped(data: bytes) -> list[bytes]:
    offset, first, count = struct.unpack_from("<IHH", data, 0x6A)
    return [data[offset + (first + i) * 0x30: offset + (first + i + 1) * 0x30] for i in range(count)]


def _ability_effects(data: bytes) -> list[bytes]:
    abilities, count, offset = struct.unpack_from("<IHI", data, 0x64)
    blocks = []
    for index in range(count):
        number, first = struct.unpack_from("<HH", data, abilities + index * 0x38 + 0x1E)
        blocks += [data[offset + (first + i) * 0x30: offset + (first + i + 1) * 0x30] for i in range(number)]
    return blocks


def _kit_checks(data: bytes) -> list[int]:
    """parameter1 of each opcode 319 "not usable by" kit check this pass wrote."""
    checks = []
    for effect in _equipped(data):
        opcode, target, power, parameter1, parameter2, timing = struct.unpack_from("<HBBIIB", effect)
        resource = effect[0x14:0x1C].rstrip(b"\0").decode("ascii")
        special = struct.unpack_from("<I", effect, 0x2C)[0]
        if opcode == 319 and resource == MARKER:
            checks.append(parameter1)
            if (target, power, parameter2, timing, special) != (1, 0, 9, 2, 0):
                raise AssertionError(f"unexpected kit check fields {effect.hex()}")
    return checks


ITEMS = {
    # name: (item bytes, kit bits afterwards, kit checks added) when every kit
    # above is in KITLIST.2DA before the Invisible Blade component runs.
    "AKKATANA": (_item(20, 0x4004D780, 0x3F020000), 0x2F020000,
                 {SHAPESHIFTER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
    "AKSWEPT": (_item(20, 0x00000000, 0x3F020000, equipped=(_proficiency_gate(),)), 0x2F020000,
                {SHAPESHIFTER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
    # Rogue's Potion of Frost Giant Strength.
    "AKPOTION": (_item(9, 0x6030FD80, 0xF803803A), 0xE803803A,
                 {SHAPESHIFTER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
    # A mage scroll as Spell Revisions and Kitpack's thief overhaul leave it:
    # the thief kits are blocked, so the Invisible Blade stays blocked too.
    "AKSCRLSR": (_item(11, 0x60625E80, 0x7F1F0100, equipped=(_effect(319, power=2, parameter2=554),)),
                 0x6F1F0100, {SHAPESHIFTER, ELEMENTALIST, INVISIBLE_BLADE, SHAMAN_KIT}),
    # The same scroll as BG2:EE ships it: thieves may not read it by class.
    "AKSCRLVN": (_item(11, 0x60725E80, 0x78038238), 0x68038238,
                 {SHAPESHIFTER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
    # A kit check another mod put there already is not added twice.
    "AKSSGATE": (_item(20, 0x4004D780, 0x3F020000, equipped=(_effect(319, parameter1=SHAPESHIFTER,
                                                                     parameter2=9),)),
                 0x2F020000, {ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
    # Equipped effects before or after the ability's effects.
    "AKALTGL": (_item(20, 0x4004D780, 0x3F020000, equipped=(_proficiency_gate(),),
                      ability=(_effect(12, target=2, parameter1=5, timing=1),), globals_first=True),
                0x2F020000, {SHAPESHIFTER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
    "AKALTAB": (_item(20, 0x4004D780, 0x3F020000, equipped=(_proficiency_gate(),),
                      ability=(_effect(12, target=2, parameter1=5, timing=1),), globals_first=False),
                0x2F020000, {SHAPESHIFTER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT}),
}
UNCHANGED = {
    # Body armor keeps the Shapeshifter's own rule.
    "AKARMOR": _item(2, 0x00000000, 0x10000004),
    # Usable by only a few kits (Entropy): thief and bard kits are blocked.
    "AKWHITE": _item(19, 0xFFFFFF80, 0x7FDFFFFF),
    # Handmaiden's Mace: the bard kits are blocked and thieves may not use it.
    "AKMACE": _item(17, 0xFD7F384C, 0x7EE20038),
    "AKNOBIT": _item(20, 0x4004D780, 0x2F020000),
    "AKSHORT": b"ITM V1  " + b"\x10" * 0x40,
    "AKV11": _item(20, 0x4004D780, 0x3F020000, signature=b"ITM V1.1"),
}


class KitBitGame:
    def __init__(self, root: Path, kits: tuple[int, ...]) -> None:
        self.root = root
        self.override = root / "override"
        self.override.mkdir(parents=True)
        shutil.copy2(WEIDU, root / "weidu.exe")
        _write_marker_key_and_bif(root)
        for path in (root / "lang/en_us/dialog.tlk", root / "dialog.tlk"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ONE_EMPTY_STRING_TLK)
        (self.override / "KITLIST.2DA").write_bytes(_kitlist(kits))
        for name, (data, _, _) in ITEMS.items():
            (self.override / f"{name}.ITM").write_bytes(data)
        for name, data in UNCHANGED.items():
            (self.override / f"{name}.ITM").write_bytes(data)
        (self.override / "unrelated.txt").write_bytes(b"preserve this resource\r\n")
        # SCS's drow katana, copied in by a mod installed after the kits.
        (root / "late").mkdir()
        (root / "late/AKLATE.ITM").write_bytes(_item(20, 0x4004D780, 0x3F020000))

    def run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "weidu.exe"), "harness.tp2", "--game", str(self.root), *arguments,
             "--language", "0", "--use-lang", "en_US", "--no-exit-pause", "--quick-log"],
            cwd=self.root, capture_output=True, encoding="utf-8", errors="replace",
            timeout=300, check=False,
        )

    def item(self, name: str) -> bytes:
        return (self.override / f"{name}.ITM").read_bytes()


def _tail_after(lines: list[str], include: str) -> list[str]:
    if lines.count(include) != 1:
        raise AssertionError(f"the component must have {include} exactly once")
    return lines[lines.index(include) + 1:]


def _harness() -> str:
    """Components built from the installers' own lines."""
    always = _always(MAIN_TP2)
    for line in (CLASS_GRANTS_INCLUDE, LIBRARY_INCLUDE):
        if line not in always:
            raise AssertionError(f"the main installer's ALWAYS block no longer has {line}")
    main = _components(MAIN_TP2)
    elementalist = _tail_after(main["5001"], "INCLUDE ~%MOD_FOLDER%/lib/Elementalist.tpa~")
    invisible_blade = _tail_after(main["7005"], "INCLUDE ~%MOD_FOLDER%/lib/Invisible_Blade.tpa~")
    tweak = _components(TWEAK_TP2)["7205"][1:]

    def append(kit: int) -> str:
        return f"APPEND ~KITLIST.2DA~ ~{KIT_ROWS[kit]}~"

    def component(name: str, number: int, lines: list[str]) -> str:
        return "\n".join([f"BEGIN ~{name}~ DESIGNATED {number}", *lines]) + "\n"

    return (
        "BACKUP ~harness-backup~\n"
        "AUTHOR ~Shapeshifter kit bit tests~\n"
        "ALWAYS\n"
        f"  OUTER_SPRINT MOD_FOLDER ~{MOD_FOLDER.as_posix()}~\n"
        f"  {CLASS_GRANTS_INCLUDE}\n"
        f"  {LIBRARY_INCLUDE}\n"
        "END\n"
        + component("Elementalist Druid Kit", 5001, [append(ELEMENTALIST), *elementalist])
        + component("Invisible Blade Thief Kit", 7005, [append(INVISIBLE_BLADE), *invisible_blade])
        + component("Dancer of Bardic Wonders, which does not call the pass", 1005, [append(DANCER)])
        + component("Items of a later mod", 20, [
            "COPY_EXISTING ~AKKATANA.ITM~ ~override/AKCLONE.ITM~",
            "COPY ~late/AKLATE.ITM~ ~override~",
        ])
        + component("Invisible Blade tweak for items and kits added later", 7205, tweak)
        + component("The pass once more", 7206, [CALL])
    )


class ShapeshifterKitBitTestCase(unittest.TestCase):
    def _game(self, kits: tuple[int, ...]) -> KitBitGame:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-sskit-")
        self.addCleanup(temporary.cleanup)
        game = KitBitGame(Path(temporary.name) / "game", kits)
        (game.root / "harness.tp2").write_text(_harness(), encoding="utf-8", newline="\n")
        return game

    def _install(self, game: KitBitGame, *components: int) -> None:
        process = game.run("--force-install-list", *map(str, components))
        transcript = f"{process.stdout}\n{process.stderr}"
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertNotIn("INSTALLED WITH WARNINGS", transcript, transcript)

    def _assert_freed(self, original: bytes, data: bytes, kits: int, checks: set[int]) -> None:
        self.assertEqual(kits, _kits(data))
        added = _kit_checks(data)
        self.assertEqual(sorted(checks), sorted(added), "one kit check per kit that stays blocked")
        # Everything else stays as it was: the header but for byte 0x29 and
        # the equipped effect count, the old effects, the ability's effects.
        skip = {0x29, 0x70, 0x71}
        self.assertEqual([b for i, b in enumerate(original[:0x72]) if i not in skip],
                         [b for i, b in enumerate(data[:0x72]) if i not in skip])
        self.assertEqual(_equipped(original), [e for e in _equipped(data) if e[0x14:0x1C].rstrip(b"\0") != MARKER.encode()])
        self.assertEqual(_ability_effects(original), _ability_effects(data))


class AllKitsPresentTests(ShapeshifterKitBitTestCase):
    """The Dancer, the Elementalist and two other kits with the bit come first."""

    KITS = (*VANILLA_KITS, DANCER, ELEMENTALIST, MIXED_THIEF, SHAMAN_KIT)

    def test_invisible_blade_component_frees_the_items_and_keeps_every_other_kit_blocked(self) -> None:
        game = self._game(self.KITS)
        before = _raw_tree(game.root)
        self._install(game, 7005)
        for name, (original, kits, checks) in ITEMS.items():
            with self.subTest(item=name):
                self._assert_freed(original, game.item(name), kits, checks)
        for name, original in UNCHANGED.items():
            with self.subTest(item=name):
                self.assertEqual(original, game.item(name))
        self.assertEqual(before["OVERRIDE/UNRELATED.TXT"], (game.override / "unrelated.txt").read_bytes())

    def test_a_second_call_changes_nothing(self) -> None:
        game = self._game(self.KITS)
        self._install(game, 7005)
        after_first = _raw_tree(game.override)
        self._install(game, 7206)
        self.assertEqual(after_first, _raw_tree(game.override))

    def test_uninstalling_restores_every_file(self) -> None:
        game = self._game(self.KITS)
        before = _raw_tree(game.override)
        self._install(game, 7005, 7205)
        process = game.run("--force-uninstall-list", "7205", "7005")
        transcript = f"{process.stdout}\n{process.stderr}"
        self.assertEqual(0, process.returncode, transcript)
        self.assertEqual(before, _raw_tree(game.override))


class InstallOrderTests(ShapeshifterKitBitTestCase):
    def test_elementalist_alone_changes_no_item(self) -> None:
        game = self._game(VANILLA_KITS)
        before = _raw_tree(game.override)
        self._install(game, 5001)
        after = _raw_tree(game.override)
        self.assertEqual({name for name in after if name != "OVERRIDE/KITLIST.2DA"},
                         {name for name in before if name != "OVERRIDE/KITLIST.2DA"})
        for name, data in before.items():
            if name.endswith(".ITM"):
                self.assertEqual(data, after[name], name)

    def test_reference_order_with_later_dancer_and_items(self) -> None:
        # Elementalist, Invisible Blade, then Bardic Wonders' Dancer, then a
        # mod that clones a katana and adds its own, then the tweak.
        game = self._game(VANILLA_KITS)
        self._install(game, 5001, 7005)
        katana = game.item("AKKATANA")
        self.assertEqual(0x2F020000, _kits(katana))
        self.assertEqual({SHAPESHIFTER, ELEMENTALIST}, set(_kit_checks(katana)))
        # Only the Dancer would gain the scroll: it stays as it was until then.
        self.assertEqual(ITEMS["AKSCRLSR"][0], game.item("AKSCRLSR"))
        self._install(game, 1005, 20)
        self.assertEqual(katana, game.item("AKCLONE"), "a copy keeps the fix")
        self.assertEqual(0x3F020000, _kits(game.item("AKLATE")))
        self._install(game, 7205)
        self.assertEqual(katana, game.item("AKKATANA"), "the Dancer may use it already")
        self.assertEqual(katana, game.item("AKCLONE"))
        late = game.item("AKLATE")
        self.assertEqual(0x2F020000, _kits(late))
        self.assertEqual({SHAPESHIFTER, ELEMENTALIST}, set(_kit_checks(late)))
        scroll = game.item("AKSCRLSR")
        self.assertEqual(0x6F1F0100, _kits(scroll))
        self.assertEqual({SHAPESHIFTER, ELEMENTALIST, INVISIBLE_BLADE}, set(_kit_checks(scroll)))
        after = _raw_tree(game.override)
        self._install(game, 7206)
        self.assertEqual(after, _raw_tree(game.override))

    def test_a_druid_kit_added_after_the_invisible_blade_gets_its_kit_checks(self) -> None:
        game = self._game(VANILLA_KITS)
        self._install(game, 7005)
        self.assertEqual([SHAPESHIFTER], _kit_checks(game.item("AKKATANA")))
        self._install(game, 5001)
        for name in ("AKKATANA", "AKSWEPT", "AKPOTION", "AKALTAB"):
            with self.subTest(item=name):
                self.assertEqual({SHAPESHIFTER, ELEMENTALIST}, set(_kit_checks(game.item(name))))

    def test_without_kits_that_borrow_the_bit_nothing_changes(self) -> None:
        game = self._game(VANILLA_KITS)
        before = _raw_tree(game.override)
        self._install(game, 7206)
        self.assertEqual(before, _raw_tree(game.override))


class InstallerTests(unittest.TestCase):
    def test_kit_components_call_the_pass_after_adding_their_kit(self) -> None:
        main = _components(MAIN_TP2)
        for number, include in (("5001", "INCLUDE ~%MOD_FOLDER%/lib/Elementalist.tpa~"),
                                ("7005", "INCLUDE ~%MOD_FOLDER%/lib/Invisible_Blade.tpa~")):
            with self.subTest(component=number):
                self.assertEqual(CALL, _tail_after(main[number], include)[0])

    def test_both_installers_define_the_pass(self) -> None:
        for path in (MAIN_TP2, TWEAK_TP2):
            with self.subTest(installer=path.name):
                self.assertIn(LIBRARY_INCLUDE, _always(path))

    def test_the_tweaks_for_later_mods_call_the_pass(self) -> None:
        tweak = _components(TWEAK_TP2)
        self.assertEqual([CALL], tweak["7205"][1:])
        self.assertNotIn("REQUIRE", " ".join(tweak["7205"]))
        self.assertIn("INCLUDE ~%MOD_FOLDER%/lib/profs_eeex_patch.tpa~", tweak["1010000"])
        lines = _code_lines(REGENERATOR.read_text(encoding="latin-1"))
        self.assertEqual([LIBRARY_INCLUDE, CALL], lines[-2:])


if __name__ == "__main__":
    unittest.main()
