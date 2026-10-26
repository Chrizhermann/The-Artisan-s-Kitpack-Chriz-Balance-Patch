"""Kit weapon grants that survive C0PR#CL in the EEex weapon usability system.

C0PR#CL removes the effects of every weapon grant spell (its opcode 321
entries) before it grants the weapons of the creature's pips and class again.
Kit chains registered in the helper spell C0PR#XX apply the same grant spells,
so they lost their extra weapons at each C0PR#CL until Kitpack's helper creature
applied C0PR#XX again. Kitpack now rebuilds C0PR#KG from C0PR#XX and makes it
C0PR#CL's last effect.

These tests run the real generator, the "Update EEex-based Weapon Usability
Changes" tweak and the real chain blocks of the Eldritch Knight and Arcane
Trickster sorcerers, the Favored Soul, the Mystic Fire and the Monk kits with
WeiDU in synthetic games, next to synthetic chains of other mods. A small model
of opcodes 177, 318, 321, 326 and 401 then compares what creatures end up with.
It is not EEex; the in-game lab check covers the engine.
"""

from __future__ import annotations

import re
import shutil
import struct
import unittest
from pathlib import Path

from test_shapeshifter_personal_space import _raw_tree
from test_sorcerer_weapon_usability import (
    ALL_WEAPONS,
    CLASS_IDS,
    CLASS_ROW,
    DRUID,
    GENERATOR,
    MOD_FOLDER,
    THIEF,
    VANILLA_MAGE,
    WEAPONS,
    GeneratorGame,
    SorcererWeaponTestCase,
    SyntheticGame,
    _build_spl,
    _effect,
    _fields,
    _ids,
    _parse_spl,
)


SYNC_LIBRARY = MOD_FOLDER / "eeex/kit_weapon_grants.tpa"
KG, CL, XX = "C0PR#KG", "C0PR#CL", "C0PR#XX"
KITS = {
    "DRAGON_DISCIPLE": 0x4023,
    "C0EK_SORC": 0x4034,
    "C0_ARCANE_TRICKSTER_SORC": 0x4037,
    "C0_ENLIGHTENED_FIST": 0x4039,
    "C0_SACRED_FIST": 0x403A,
    "C0MF": 0x4043,
    "C0_FAVORED_SOUL": 0x4050,
}
# Marker stats the chain blocks expect in STATS.IDS. The generator adds its 20
# proficiency stats from 203 on, so these start above them.
MARKERS = {
    "C0_ELDRITCH_KNIGHT_EQUIPMENT": 223,
    "C0_MONK_EQUIPMENT": 224,
    "C0_MYSTIC_FIRE_EQUIPMENT": 225,
    "C0_SORC_THIEF_EQUIPMENT": 226,
    "IS_FAVORED_SOUL": 229,
}
# The real Kitpack chains: kit library, and whether the library itself lets
# C0PR#CL re-apply the chain right after registering it.
REAL_CHAINS = {
    "EK": ("lib/Eldritch_Knight_Sorc.tpa", True),
    "MO": ("lib/MonkRevision-Mystic.tpa", False),
    "FS": ("lib/FavoredSoul.tpa", True),
    "MF": ("lib/mystic_fire_items.tpa", False),
    "AT": ("lib/arcane_trickster_items.tpa", True),
}
SYNC_CALL = re.compile(
    r"\A(?:[ \t]*\r?\n|[ \t]*//[^\n]*\n)*"
    r"[ \t]*INCLUDE ~%MOD_FOLDER%/eeex/kit_weapon_grants\.tpa~[ \t]*\r?\n"
    r"[ \t]*LAF c0_sync_kit_weapon_grants END[ \t]*\r?\n"
)
AT_WEAPONS = frozenset({
    "LONGSWORD", "SHORTSWORD", "KATANA", "SCIMITARWAKISASHININJATO", "DAGGER", "CLUB",
    "QUARTERSTAFF", "CROSSBOW", "SHORTBOW", "DART", "SLING",
})
FAVORED_SOUL_WEAPONS = frozenset({
    "DAGGER", "CLUB", "SPEAR", "MACE", "QUARTERSTAFF", "CROSSBOW", "DART", "SLING",
})


def _chain_block(chain: str) -> str:
    """The real chain definition through its C0PR#XX registration and sync call."""
    library, synced = REAL_CHAINS[chain]
    text = (MOD_FOLDER / library).read_text(encoding="latin-1")
    first = text.index(f"~override/C0PR#{chain}.SPL~")
    first = text.rindex("\n", 0, first) + 1
    registration = re.compile(
        rf"^[^\n]*CLONE_EFFECT[^\n]*match_resource = C0PR#X1 resource = C0PR#{chain}\s+END[^\n]*\n",
        re.MULTILINE,
    ).search(text, first)
    if registration is None:
        raise AssertionError(f"{library} no longer registers C0PR#{chain} in C0PR#XX")
    end = registration.end()
    sync = SYNC_CALL.match(text[end:])
    if bool(sync) != synced:
        raise AssertionError(f"{library}: sync call after C0PR#{chain} is {'missing' if synced else 'unexpected'}")
    if sync:
        end += sync.end()
    return text[first:end]


def _spl(*effects: bytes) -> bytes:
    return _build_spl([list(effects)])


def _eff(opcode: int, resource: str, *, parameter1: int = 0, parameter2: int = 0) -> bytes:
    data = bytearray(0x110)
    data[0:16] = b"EFF V2.0EFF V2.0"
    struct.pack_into("<IIIii", data, 0x10, opcode, 1, 0, parameter1, parameter2)
    data[0x30:0x38] = resource.encode("ascii").ljust(8, b"\0")
    return bytes(data)


def _grants_of(*weapons: int) -> list[bytes]:
    return [_effect(326, target=1, resource=f"C0PR#{weapon}") for weapon in weapons]


def _synthetic_chains() -> dict[str, bytes]:
    """Chains other mods register in C0PR#XX, written before any install."""
    every_weapon = [ident for _, ident in WEAPONS]
    files = {
        # Like Kitpack's tracking dispatch: casts its own spells, grants nothing.
        "AKTRACK.SPL": _spl(_effect(146, target=1, parameter2=1, resource="AKTRACK1"),
                            _effect(326, target=1, resource="AKTRACK2")),
        "AKTRACK1.SPL": _spl(_effect(139, target=1, parameter1=7)),
        "AKTRACK2.SPL": _spl(_effect(321, target=1, resource="AKTRACK1")),
        # A marker-only kit chain, like Bardic Wonders' Gallant.
        "AKGAL.SPL": _spl(_effect(326, target=1, parameter1=CLASS_IDS["PALADIN"],
                                  parameter2=CLASS_ROW, resource="AKGAL1")),
        "AKGAL1.SPL": _spl(_effect(321, target=1, timing=9, resource="AKGAL1"),
                           _effect(401, target=1, timing=9, parameter1=1, parameter2=1, special=227)),
        # A weapon chain of a mod installed after Kitpack, like Bardic Wonders'
        # Mage/Bard multi-class: every weapon for mage/thieves.
        "AKMB.SPL": _spl(_effect(326, target=1, parameter1=CLASS_IDS["MAGE_THIEF"],
                                 parameter2=CLASS_ROW, resource="AKMB2")),
        "AKMB2.SPL": _spl(_effect(401, target=1, timing=9, parameter2=1, special=228),
                          *_grants_of(*every_weapon)),
        # A weapon chain that reaches its grant through an EFF file.
        "AKEFFW.SPL": _spl(_effect(326, target=1, parameter1=CLASS_IDS["CLERIC"],
                                   parameter2=CLASS_ROW, resource="AKEFFW1")),
        "AKEFFW1.SPL": _spl(_effect(177, target=1, timing=1, resource="AKEFFW")),
        "AKEFFW.EFF": _eff(326, "C0PR#96"),
        # Grants a long sword but also casts C0PR#CL (through an EFF file).
        "AKLOOP.SPL": _spl(*_grants_of(90), _effect(177, target=1, timing=1, resource="AKLOOP")),
        "AKLOOP.EFF": _eff(146, "C0PR#CL", parameter2=1),
        # A chain whose second spell is truncated.
        "AKBROKE.SPL": _spl(_effect(326, target=1, resource="AKBROKE1")),
        # Removes the axe grant from fighters, without blocking it.
        "AKNOAXE.SPL": _spl(_effect(326, target=1, parameter1=CLASS_IDS["FIGHTER"],
                                    parameter2=CLASS_ROW, resource="AKNOAXE1")),
        "AKNOAXE1.SPL": _spl(_effect(321, target=1, resource="C0PR#92")),
    }
    broken = bytearray(_spl(*_grants_of(96)))
    struct.pack_into("<H", broken, 0x72 + 0x1E, 3)  # claims three effects, holds one
    files["AKBROKE1.SPL"] = bytes(broken)
    return files


REGISTERED = {  # component: (label, C0PR#XX entry)
    12: ("Tracking-like chain", "AKTRACK"),
    16: ("Gallant-like marker chain", "AKGAL"),
    20: ("Later mod's weapon chain", "AKMB"),
    21: ("EFF-linked weapon chain", "AKEFFW"),
    22: ("Weapon chain that casts C0PR#CL", "AKLOOP"),
    23: ("Chain with a truncated spell", "AKBROKE"),
    24: ("Chain that removes a class weapon", "AKNOAXE"),
    25: ("Eldritch Knight chain registered twice", "C0PR#EK"),
}
CEBG_ORDER = ("10", "11", "12", "13", "14", "15", "16")


class KitChainGame(GeneratorGame):
    """A generator game with the helper spells and the real and synthetic chains."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        stats = {value: f"SYNTHETIC_STAT_{value}" for value in range(203)}
        stats.update({value: name for name, value in MARKERS.items()})
        (self.override / "STATS.IDS").write_bytes(_ids(stats))
        (self.override / "KIT.IDS").write_bytes(_ids({value: name for name, value in KITS.items()}))
        # on_load_eeex.tpa copies these unless C0PR#EF.BCS exists, which skips
        # its script compilation here.
        for name in ("C0PR#XX", "C0PR#X1", "C0PR#X2"):
            source = next(path for path in (MOD_FOLDER / "eeex/profs").iterdir()
                          if path.name.upper() == f"{name}.SPL")
            shutil.copyfile(source, self.override / f"{name}.SPL")
        for name, data in _synthetic_chains().items():
            (self.override / name).write_bytes(data)
        blocks = root / "blocks"
        blocks.mkdir()
        for chain in REAL_CHAINS:
            (blocks / f"{chain}.tpa").write_text(_chain_block(chain), encoding="latin-1", newline="")
        generator = f"INCLUDE ~{GENERATOR.as_posix()}~"
        on_load = "INCLUDE ~%MOD_FOLDER%/eeex/on_load_eeex.tpa~"

        def block(chain: str) -> str:
            return f"INCLUDE ~{(blocks / f'{chain}.tpa').as_posix()}~"

        components = {
            # The kit libraries include the generator (EK, FS and tweak 8204
            # for AT) or on_load_eeex.tpa (Monk, Mystic Fire) first.
            10: ("Eldritch Knight sorcerer", [generator, block("EK")]),
            11: ("Mystic and Sacred Fist", [on_load, block("MO")]),
            13: ("Favored Soul", [generator, block("FS")]),
            14: ("Mystic Fire wands and scrolls", [on_load, block("MF")]),
            15: ("Arcane Trickster sorcerer thief equipment", [generator, block("AT")]),
            30: ("Sync only", [f"INCLUDE ~{SYNC_LIBRARY.as_posix()}~", "LAF c0_sync_kit_weapon_grants END"]),
        }
        for number, (label, entry) in REGISTERED.items():
            components[number] = (label, [
                f"COPY_EXISTING ~{XX}.SPL~ ~override~",
                f"  LPF CLONE_EFFECT INT_VAR match_opcode = 326 STR_VAR match_resource = C0PR#X1 resource = {entry} END",
            ])
        lines = [
            "BACKUP ~chains-backup~",
            "AUTHOR ~Kit weapon grant regression tests~",
            "ALWAYS",
            f"  OUTER_SPRINT MOD_FOLDER ~{MOD_FOLDER.as_posix()}~",
            "  INCLUDE ~%MOD_FOLDER%/lib/functions.tph~",
            "END",
        ]
        for number in sorted(components):
            label, body = components[number]
            lines += [f"BEGIN ~{label}~ DESIGNATED {number}", *body]
        (root / "chains.tp2").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def spl(self, name: str) -> bytes:
        return (self.override / f"{name}.SPL").read_bytes()


def _xx_entries(data: bytes) -> list[tuple[str, bytes]]:
    abilities, casting = _parse_spl(data)
    return [(_fields(block)[3], block) for effects in abilities + [casting] for block in effects
            if _fields(block)[0] == 326]


def _expected_kg(xx: bytes, kept: list[str]) -> list[bytes]:
    """C0PR#XX's first entry for each kept chain, aimed at C0PR#CL's creature."""
    first = {}
    for resource, block in _xx_entries(xx):
        first.setdefault(resource, block)
    return [first[name][:2] + b"\x02" + first[name][3:] for name in kept]


def _without_kg(cl: bytes) -> bytes:
    abilities, casting = _parse_spl(cl)
    kept = [[block for block in effects if _fields(block)[::3] != (326, KG)] for effects in abilities]
    return _build_spl(kept, casting)


class Model:
    """Opcodes 146, 148, 177, 318, 321, 326 and 401 on one creature without pips.

    Persistent effects remember the spell that applied them, as the engine's
    source resource; opcode 321 removes them by that spell.
    """

    def __init__(self, files: dict[str, bytes], class_name: str, kit: str | None = None) -> None:
        self.files = files
        self.class_id = CLASS_IDS[class_name]
        self.kit_id = KITS[kit] if kit else 0
        rows = [line.split() for line in files["SPLPROT.2DA"].decode("ascii").splitlines()[3:] if line.split()]
        self.kit_check_row = next(index for index, row in enumerate(rows) if row[0] == "C0_KIT_CHECK")
        self.effects: list[tuple[str, int, int, int, str]] = []
        stats = {line.split()[1]: int(line.split()[0], 0)
                 for line in files["STATS.IDS"].decode("ascii").splitlines()[1:] if len(line.split()) == 2}
        self.weapon_stat = {stats[f"C0_PROFICIENCY{name}"]: name for name, _ in WEAPONS}

    def _condition(self, parameter1: int, parameter2: int) -> bool:
        if parameter2 == 0:  # SPLPROT row 0: EA >= 0, everyone
            return True
        if parameter2 == CLASS_ROW:
            return self.class_id == parameter1
        if parameter2 == self.kit_check_row:
            return self.kit_id == parameter1
        return False  # proficiency pips: these creatures have none

    def _blocked(self, resource: str) -> bool:
        return any(opcode == 318 and blocked == resource for _, opcode, _, _, blocked in self.effects)

    def apply(self, name: str, depth: int = 0) -> None:
        if depth > 16:
            raise AssertionError(f"runaway chain at {name}")
        data = self.files.get(f"{name}.SPL")
        if data is None:
            return
        abilities, casting = _parse_spl(data)
        for block in casting + (abilities[0] if abilities else []):
            opcode, parameter1, parameter2, resource = _fields(block)
            special = struct.unpack_from("<I", block, 0x2C)[0]
            self._effect(name, opcode, parameter1, parameter2, resource, special, depth)

    def _effect(self, source: str, opcode: int, parameter1: int, parameter2: int,
                resource: str, special: int, depth: int) -> None:
        if opcode == 321:
            self.effects = [effect for effect in self.effects if effect[0] != resource]
        elif opcode == 326:
            if self._condition(parameter1, parameter2) and not self._blocked(resource):
                self.apply(resource, depth + 1)
        elif opcode in (146, 148):
            if not self._blocked(resource):
                self.apply(resource, depth + 1)
        elif opcode == 177:
            data = self.files[f"{resource}.EFF"]
            inner, = struct.unpack_from("<I", data, 0x10)
            inner_p1, inner_p2 = struct.unpack_from("<ii", data, 0x1C)
            inner_resource = data[0x30:0x38].split(b"\0", 1)[0].decode("ascii").upper()
            self._effect(source, inner, inner_p1, inner_p2, inner_resource, 0, depth + 1)
        elif opcode == 318:
            self.effects.append((source, 318, 0, 0, resource))
        elif opcode == 401:
            self.effects.append((source, 401, special, parameter1, ""))

    def stats(self) -> dict[int, int]:
        values: dict[int, int] = {}
        for _, opcode, stat, value, _ in self.effects:
            if opcode == 401:
                values[stat] = value
        return values

    def weapons(self) -> frozenset[str]:
        return frozenset(self.weapon_stat[stat] for stat, value in self.stats().items()
                         if value == 1 and stat in self.weapon_stat)


def _files(override: Path) -> dict[str, bytes]:
    return {path.name.upper(): path.read_bytes() for path in override.iterdir() if path.is_file()}


class KitWeaponGrantTestCase(SorcererWeaponTestCase):
    def _game(self) -> KitChainGame:
        game = KitChainGame(self._temporary_root("akcb-kitgrants-"))
        self._install_harness(game, "0")
        return game

    def _install(self, game: KitChainGame, *components: str, warnings: bool = False) -> str:
        """Install chains.tp2 components one WeiDU run each, in the given order."""
        transcript = ""
        for component in components:
            process = game.run("chains.tp2", "--force-install-list", component)
            transcript += self._assert_installed(game, process, warnings=warnings)
        return transcript

    def _cl_effects(self, game: KitChainGame) -> list[bytes]:
        (effects,), casting = _parse_spl(game.spl(CL))
        self.assertEqual([], casting)
        return effects

    def _assert_kg(self, game: KitChainGame, kept: list[str]) -> None:
        (kg,), casting = _parse_spl(game.spl(KG))
        self.assertEqual([], casting)
        self.assertEqual(_expected_kg(game.spl(XX), kept), kg)
        effects = self._cl_effects(game)
        self.assertEqual((326, 0, 0, KG), _fields(effects[-1]), "C0PR#KG must be C0PR#CL's last effect")
        self.assertEqual(2, effects[-1][2], "C0PR#KG goes to C0PR#CL's creature")
        self.assertEqual(1, sum(1 for block in effects if _fields(block)[::3] == (326, KG)))


class RealChainTests(KitWeaponGrantTestCase):
    def test_cebg_order_keeps_only_the_weapon_chains_in_helper_order(self) -> None:
        game = self._game()
        cl_before = game.spl(CL)
        for component in CEBG_ORDER:
            self._install(game, component)
        self.assertEqual(
            ["C0PR#EK", "C0PR#MO", "AKTRACK", "C0PR#FS", "C0PR#MF", "C0PR#AT", "AKGAL", "C0PR#X1"],
            [resource for resource, _ in _xx_entries(game.spl(XX))],
        )
        self._assert_kg(game, ["C0PR#EK", "C0PR#FS", "C0PR#AT"])
        self.assertEqual(cl_before, _without_kg(game.spl(CL)), "everything else in C0PR#CL stays")

    def test_each_kit_library_lets_c0pr_cl_reapply_its_own_chain(self) -> None:
        for component, chain in (("10", "C0PR#EK"), ("13", "C0PR#FS"), ("15", "C0PR#AT")):
            with self.subTest(chain=chain):
                game = self._game()
                self._install(game, component)
                self._assert_kg(game, [chain])

    def test_chains_without_weapon_grants_add_nothing(self) -> None:
        game = self._game()
        before = _raw_tree(game.override)
        self._install(game, "11", "12", "14", "16", "30")
        after = _raw_tree(game.override)
        self.assertNotIn(f"{KG}.SPL", after)
        self.assertEqual(before[f"{CL}.SPL"], after[f"{CL}.SPL"])

    def test_creatures_keep_the_weapons_the_helper_gave_them(self) -> None:
        game = self._game()
        for component in CEBG_ORDER:
            self._install(game, component)
        files = _files(game.override)
        old = dict(files, **{f"{CL}.SPL": _without_kg(files[f"{CL}.SPL"])})
        helper_chains = [resource for resource, _ in _xx_entries(files[f"{XX}.SPL"]) if resource != "C0PR#X1"]
        kit_extras = {"Eldritch Knight sorcerer", "Arcane Trickster sorcerer", "Favored Soul",
                      "Eldritch Knight kit on a mage"}
        cases = {
            "Eldritch Knight sorcerer": ("SORCERER", "C0EK_SORC", ALL_WEAPONS),
            "Arcane Trickster sorcerer": ("SORCERER", "C0_ARCANE_TRICKSTER_SORC", AT_WEAPONS | VANILLA_MAGE),
            "Favored Soul": ("SHAMAN", "C0_FAVORED_SOUL", FAVORED_SOUL_WEAPONS),
            "sorcerer": ("SORCERER", None, VANILLA_MAGE),
            "Dragon Disciple": ("SORCERER", "DRAGON_DISCIPLE", VANILLA_MAGE),
            "mage": ("MAGE", None, VANILLA_MAGE),
            "Eldritch Knight kit on a mage": ("MAGE", "C0EK_SORC", ALL_WEAPONS),
            "shaman": ("SHAMAN", None, DRUID),
            "Mystic Fire paladin": ("PALADIN", "C0MF", ALL_WEAPONS),
            "thief": ("THIEF", None, THIEF),
        }
        for label, (class_name, kit, expected) in cases.items():
            with self.subTest(creature=label):
                # Before the fix: C0PR#CL, then the helper's chains (without
                # C0PR#X1, which did not reach party members in the lab) ...
                unfixed = Model(old, class_name, kit)
                unfixed.apply(CL)
                for chain in helper_chains:
                    unfixed.apply(chain)
                self.assertEqual(expected, unfixed.weapons(), "what the helper gives")
                # ... and the next C0PR#CL, as at a level-up, took kit weapons away.
                unfixed.apply(CL)
                if label in kit_extras:
                    self.assertLess(unfixed.weapons(), expected)
                else:
                    self.assertEqual(expected, unfixed.weapons())
                # Now a new creature has them from its first C0PR#CL on, and
                # every later C0PR#CL keeps them.
                fixed = Model(files, class_name, kit)
                fixed.apply(CL)
                self.assertEqual(expected, fixed.weapons())
                first_stats = fixed.stats()
                fixed.apply(CL)
                self.assertEqual(first_stats, fixed.stats())
                for chain in helper_chains:
                    fixed.apply(chain)
                fixed.apply(CL)
                self.assertEqual(expected, fixed.weapons(), "after the helper and another level-up")


class SyncTests(KitWeaponGrantTestCase):
    def _cebg_game(self) -> KitChainGame:
        game = self._game()
        for component in CEBG_ORDER:
            self._install(game, component)
        return game

    def test_a_second_sync_changes_nothing(self) -> None:
        game = self._cebg_game()
        before = _raw_tree(game.override)
        self._install(game, "30")
        self.assertEqual(before, _raw_tree(game.override))

    def test_a_later_mods_chain_needs_the_update_tweak_and_then_gets_in(self) -> None:
        game = self._cebg_game()
        self._install(game, "20")
        self.assertEqual(["C0PR#EK", "C0PR#FS", "C0PR#AT"],
                         [_fields(block)[3] for block in _parse_spl(game.spl(KG))[0][0]])
        cl_before = game.spl(CL)
        self._install_harness(game, "2")
        self._assert_kg(game, ["C0PR#EK", "C0PR#FS", "C0PR#AT", "AKMB"])
        self.assertEqual(cl_before, game.spl(CL), "the tweak regenerates C0PR#CL as it was")

    def test_sync_only_rewrites_c0pr_kg_when_c0pr_cl_already_ends_with_it(self) -> None:
        game = self._cebg_game()
        self._install(game, "20")
        before = _raw_tree(game.override)
        self._install(game, "30")
        after = _raw_tree(game.override)
        self.assertEqual({f"{KG}.SPL"}, {name for name in after if after[name] != before.get(name)})
        self.assertEqual(set(before), set(after))

    def test_update_tweak_on_a_synced_install_is_byte_identical(self) -> None:
        game = self._cebg_game()
        before = _raw_tree(game.override)
        self._install_harness(game, "2")
        after = _raw_tree(game.override)
        for name in (f"{CL}.SPL", f"{KG}.SPL", f"{XX}.SPL"):
            self.assertEqual(before[name], after[name], name)

    def test_eff_links_removals_loops_broken_chains_and_duplicates(self) -> None:
        game = self._game()
        self._install(game, "10", "20", "21", "22", "23", "24", "25")
        transcript = self._install(game, "30", warnings=True)
        self._assert_kg(game, ["C0PR#EK", "AKMB", "AKEFFW", "AKNOAXE"])
        self.assertIn("AKLOOP grants weapons but also applies C0PR#CL or C0PR#KG again", transcript)
        self.assertIn("AKBROKE could not be read (AKBROKE1.SPL)", transcript)
        self.assertNotIn("C0PR#X1 grants", transcript)

    def test_uninstalling_a_kit_restores_the_previous_grants(self) -> None:
        game = self._game()
        self._install(game, "10")
        before = _raw_tree(game.override)
        self._install(game, "15")
        self._assert_kg(game, ["C0PR#EK", "C0PR#AT"])
        process = game.run("chains.tp2", "--force-uninstall-list", "15")
        transcript = self._transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertEqual(before, _raw_tree(game.override))


class SyncInputTests(KitWeaponGrantTestCase):
    """C0PR#CL and C0PR#XX layouts other than the generator's."""

    def _game_with(self, cl: bytes, xx: bytes) -> SyntheticGame:
        game = SyntheticGame(self._temporary_root("akcb-kitgrants-input-"))
        files = {
            f"{CL}.SPL": cl,
            f"{XX}.SPL": xx,
            "AKW.SPL": _spl(*_grants_of(90, 94)),
            f"{KG}.SPL": None,
        }
        for name, data in files.items():
            if data is not None:
                (game.override / name).write_bytes(data)
        (game.root / "sync.tp2").write_text(
            "BACKUP ~sync-backup~\n"
            "AUTHOR ~Kit weapon grant regression tests~\n"
            "ALWAYS\n"
            f"  OUTER_SPRINT MOD_FOLDER ~{MOD_FOLDER.as_posix()}~\n"
            "  INCLUDE ~%MOD_FOLDER%/lib/functions.tph~\n"
            "END\n"
            "BEGIN ~Sync~ DESIGNATED 0\n"
            f"INCLUDE ~{SYNC_LIBRARY.as_posix()}~\n"
            "LAF c0_sync_kit_weapon_grants END\n",
            encoding="utf-8", newline="\n",
        )
        return game

    def _sync(self, game: SyntheticGame, *, warnings: bool = False) -> str:
        return self._assert_installed(game, game.run("sync.tp2", "--force-install-list", "0"), warnings=warnings)

    def test_every_ability_ends_with_c0pr_kg_and_casting_effects_stay(self) -> None:
        resets = [_effect(321, resource=f"C0PR#{weapon}") for weapon in (90, 94)]
        first = resets + [_effect(326, parameter1=CLASS_IDS["THIEF"], parameter2=CLASS_ROW, resource="C0PR#90")]
        second = [_effect(321, resource="C0PR#94"), _effect(139, parameter1=5)]
        casting = [_effect(139, target=1, parameter1=12345)]
        entry = _effect(326, target=4, power=100, parameter1=7, parameter2=9, timing=1, resist=2,
                        resource="AKW", special=3)
        xx = _build_spl([[entry, _effect(326, target=4, power=100, timing=1, resource="C0PR#X1")]])
        for casting_first in (False, True):
            with self.subTest(casting_first=casting_first):
                cl = _build_spl([first, second], casting, casting_first=casting_first)
                game = self._game_with(cl, xx)
                self._sync(game)
                abilities, after_casting = _parse_spl((game.override / f"{CL}.SPL").read_bytes())
                self.assertEqual(casting, after_casting)
                self.assertEqual([first, second], [effects[:-1] for effects in abilities])
                for effects in abilities:
                    self.assertEqual((326, 0, 0, KG), _fields(effects[-1]))
                (kg,), _ = _parse_spl((game.override / f"{KG}.SPL").read_bytes())
                self.assertEqual([entry[:2] + b"\x02" + entry[3:]], kg, "every other field is kept")
                before = _raw_tree(game.override)
                self._sync(game)
                self.assertEqual(before, _raw_tree(game.override))

    def test_unreadable_helper_or_dispatcher_warns_and_changes_nothing(self) -> None:
        cl = _build_spl([[_effect(321, resource="C0PR#90")]])
        xx = _build_spl([[_effect(326, target=4, resource="AKW")]])
        truncated = bytearray(xx)
        struct.pack_into("<H", truncated, 0x72 + 0x1E, 4)
        shared = bytearray(_build_spl([[_effect(321, resource="C0PR#90")], [_effect(139, parameter1=1)]]))
        struct.pack_into("<HH", shared, 0x72 + 0x28 + 0x1E, 1, 0)  # ability 1 reuses ability 0's effect
        # The ability table after the effect table: an insertion would move it.
        effects = _effect(321, resource="C0PR#90")
        ability_last = bytearray(cl[:0x72] + effects + cl[0x72:0x9A])
        struct.pack_into("<IHI", ability_last, 0x64, 0x72 + 0x30, 1, 0x72)
        struct.pack_into("<HH", ability_last, 0x72 + 0x30 + 0x1E, 1, 0)
        cases = {
            "C0PR#XX.SPL has an unreadable effect table": (cl, bytes(truncated)),
            "C0PR#CL.SPL has an unreadable effect table": (b"SPL V2  " + cl[8:], xx),
            "C0PR#CL.SPL has an unreadable effect table or one that cannot take new effects":
                (bytes(shared), xx),
            "cannot take new effects": (bytes(ability_last), xx),
        }
        for message, (cl_data, xx_data) in cases.items():
            with self.subTest(message=message):
                game = self._game_with(cl_data, xx_data)
                before = _raw_tree(game.override)
                transcript = self._sync(game, warnings=True)
                self.assertIn(message, transcript)
                self.assertEqual(before, _raw_tree(game.override))

    def test_missing_spells_are_skipped_and_long_chains_are_bounded(self) -> None:
        cl = _build_spl([[_effect(321, resource="C0PR#90")]])
        xx = _build_spl([[_effect(326, target=4, resource=name) for name in ("AKGONE", "AKLONG0", "AKW")]])
        game = self._game_with(cl, xx)
        for index in range(70):  # AKLONG0 -> AKLONG1 -> ... -> AKLONG69, which grants
            last = index == 69
            body = _grants_of(90) if last else [_effect(326, target=1, resource=f"AKLONG{index + 1}")]
            (game.override / f"AKLONG{index}.SPL").write_bytes(_spl(*body))
        transcript = self._sync(game, warnings=True)
        self.assertIn("AKLONG0 could not be read (more than 64 linked resources)", transcript)
        self.assertNotIn("AKGONE", transcript)
        (kg,), _ = _parse_spl((game.override / f"{KG}.SPL").read_bytes())
        self.assertEqual(["AKW"], [_fields(block)[3] for block in kg])

    def test_a_stale_c0pr_kg_is_emptied_when_no_chain_grants_weapons(self) -> None:
        cl = _build_spl([[_effect(321, resource="C0PR#90"), _effect(326, target=2, resource=KG)]])
        xx = _build_spl([[_effect(326, target=4, resource="AKTRACK1")]])
        game = self._game_with(cl, xx)
        (game.override / f"{KG}.SPL").write_bytes(_spl(_effect(326, target=2, resource="AKW")))
        (game.override / "AKTRACK1.SPL").write_bytes(_spl(_effect(139, target=1)))
        self._sync(game)
        (effects,), _ = _parse_spl((game.override / f"{CL}.SPL").read_bytes())
        self.assertEqual([_effect(321, resource="C0PR#90")], effects)
        self.assertEqual(([[]], []), _parse_spl((game.override / f"{KG}.SPL").read_bytes()))


if __name__ == "__main__":
    unittest.main()
