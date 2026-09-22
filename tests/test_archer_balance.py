"""Run the full Archer production include in disposable synthetic BG2EE games."""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_assassin_expose_weakness import ROOT, WEIDU, Effect, Spell, read_tlk_string
from test_fighter_modals import _tlk_entries, _write_tlk
from test_kit_descriptions import CLASS_ROWS, KIT_ROWS, _table
from test_shapeshifter_personal_space import _raw_tree, _write_marker_key_and_bif


INCLUDE = Path("ArtisansKitpack/lib/archer.tpa")
LIBRARIES = (
    "functions.tph", "hla_actions.tpa", "kit_strref.tpa", "archer.tpa",
    "archer-items.tpa", "archer_first_shot.tpa", "archer_called_shot.tpa",
)
PAYLOAD_DIRS = (
    Path("ArtisansKitpack/Ranger/Archer/2da"),
    Path("ArtisansKitpack/Ranger/Archer/spells"),
    Path("ArtisansKitpack/spells/rapidshot"),
    Path("ArtisansKitpack/bmp"),
)
PAYLOAD_FILES = (
    Path("ArtisansKitpack/2DAs/HPARCH.2da"),
    Path("ArtisansKitpack/spells/rapidshot.tpa"),
    Path("ArtisansKitpack/lua/M_AKCBAR.lua"),
)
LEGACY_MANYSHOT = {f"C0ARCP{number:02d}" for number in range(1, 25)}


def _rows(raw: bytes) -> list[list[str]]:
    return [line.split() for line in raw.decode("ascii").splitlines()[3:] if line.strip()]


def _grants(raw: bytes, resource: str) -> list[int]:
    return sorted(level for row in _rows(raw) for level, value in enumerate(row[1:], 1) if value.upper() == resource.upper())


def _effect(opcode: int, resource: str = "", *, target: int = 1, amount: int = 0) -> bytes:
    raw = bytearray(48)
    struct.pack_into("<HBBiiBBI", raw, 0, opcode, target, 0, amount, 0, 2, 2, 0)
    raw[18] = 100
    raw[20:28] = resource.encode("ascii").ljust(8, b"\0")
    return bytes(raw)


def _item(global_effects: list[bytes], abilities: list[list[bytes]]) -> bytes:
    """Native ITM V1 layout, including distinct equipped and ability slices."""
    header = bytearray(0x72)
    header[:8] = b"ITM V1  "
    struct.pack_into("<H", header, 0x1C, 15)  # bow
    struct.pack_into("<IHIHH", header, 0x64, 0x72, len(abilities), 0x72 + 0x38 * len(abilities), 0, len(global_effects))
    headers = bytearray()
    first = len(global_effects)
    for effects in abilities:
        ability = bytearray(0x38)
        ability[0] = 2  # ranged attack
        ability[2] = 1  # weapon button
        ability[12] = 1  # creature target
        ability[13] = 1
        struct.pack_into("<H", ability, 14, 30)
        struct.pack_into("<HH", ability, 0x1E, len(effects), first)
        struct.pack_into("<H", ability, 0x2A, 1)  # original projectile
        headers.extend(ability)
        first += len(effects)
    return bytes(header + headers) + b"".join(global_effects + [effect for effects in abilities for effect in effects])


def _item_slices(raw: bytes) -> tuple[list[Effect], list[list[Effect]], list[bytes]]:
    if raw[:8] != b"ITM V1  ":
        raise ValueError("expected ITM V1")
    headers, count, effects, global_first, global_count = struct.unpack_from("<IHIHH", raw, 0x64)

    def slice_effects(first: int, length: int) -> list[Effect]:
        return [Effect(raw[effects + index * 48:effects + (index + 1) * 48]) for index in range(first, first + length)]

    abilities = [raw[headers + index * 56:headers + (index + 1) * 56] for index in range(count)]
    return (
        slice_effects(global_first, global_count),
        [slice_effects(*reversed(struct.unpack_from("<HH", ability, 0x1E))) for ability in abilities],
        abilities,
    )


class SyntheticArcherGame:
    def __init__(self, root: Path, *, eeex: bool, ranger: bool) -> None:
        self.root = root
        self.eeex = eeex
        self.ranger = ranger
        root.mkdir()
        self.override = root / "override"
        self.override.mkdir()
        shutil.copy2(WEIDU, root / "weidu.exe")
        for directory in PAYLOAD_DIRS:
            shutil.copytree(ROOT / directory, root / directory)
        for relative in (*(Path("ArtisansKitpack/lib") / name for name in LIBRARIES), *PAYLOAD_FILES):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, root / relative)
        self.source = _raw_tree(root / "ArtisansKitpack")
        bif = _write_marker_key_and_bif(root)
        self.tlk = root / "lang/en_us/dialog.tlk"
        _write_tlk(self.tlk, [f"original string {number}" for number in range(64)])
        shutil.copy2(self.tlk, root / "dialog.tlk")
        self.original_tlk = self.tlk.read_bytes()
        self.immutable = {path: path.read_bytes() for path in (root / "chitin.key", bif, root / "dialog.tlk")}
        logs = []
        if eeex:
            logs.append("~EEEX/EEEX.TP2~ #0 #0 // Installed EEex fixture")
        if ranger:
            logs.append("~ARTISANSKITPACK/ARTISANSKITPACK.TP2~ #0 #2000 // Installed Ranger overhaul fixture")
            # Exercise the actual optional skill-table branch as well.
            shutil.copy2(ROOT / "ArtisansKitpack/lua/m_c0ran1.lua", self.override / "M_C0RAN1.LUA")
        (root / "WeiDU.log").write_text("\n".join(logs) + "\n", encoding="ascii")
        self.prerequisite_logs = logs

        clab_rows = []
        for name, entries in (
            ("KEEP", {2: "AP_SENTINEL"}),
            ("TOUGHNESS", {1: "AP_C0RNH1", 10: "AP_C0RNH10"}),
            ("CHARM", {1: "GA_SPCL311"}),
            ("TRAPS", {1: "GA_SPCL412"}),
        ):
            clab_rows.append((name, *(entries.get(level, "****") for level in range(1, 51))))
        tables = {
            "CLABRN01.2DA": _table(" ".join(map(str, range(1, 51))), tuple(clab_rows), "****"),
            "HPCLASS.2DA": _table("TABLE", (("FERALAN", "HPRANG"), ("RANGER", "HPRANG"), ("MONK", "HPMONK"))),
            "LUABBR.2DA": _table("ABBREVIATION", (("FERALAN", "RA0"), ("RANGER", "RA0"), ("FIGHTER", "FI0"))),
            "LURA0.2DA": _table(
                "ABILITY ICON STRREF MIN_LEV MAX_LEVEL NUM_ALLOWED PREREQUISITE EXCLUDED_BY ALIGNMENT_RESTRICT",
                (("1", "GA_SPCL907", "*", "*", "1", "99", "1", "*", "*", "*"),
                 ("2", "GA_C0ARCH01", "*", "*", "1", "99", "20", "*", "*", "*"),
                 ("3", "GA_SENTINEL", "*", "*", "1", "99", "1", "*", "*", "*")),
            ),
            "KITLIST.2DA": _table("ROWNAME LOWER MIXED HELP ABILITIES PROFICIENCY UNUSABLE CLASS KITIDS", (KIT_ROWS[2], KIT_ROWS[0])),
            "WEAPPROF.2DA": _table("FIGHTER FERALAN", tuple((str(row), "2", "3") for row in range(32)), "0"),
            "STATDESC.2DA": _table("DESCRIPTION BAM", (("0", "0", "STATE0"), ("1", "1", "STATE1")), "0"),
            "THIEFSCL.2DA": _table("MAGE FERALAN RANGER", tuple((str(row), "10", "20", "30") for row in range(8)), "0"),
            "CLASISKL.2DA": _table("MAGE FERALAN RANGER", tuple((str(row), "40", "50", "60") for row in range(8)), "0"),
        }
        for table in ("BGCLATXT", "CLASTEXT", "SODCLTXT"):
            tables[f"{table}.2DA"] = _table(
                "CLASSID KITID LOWER DESCSTR MIXED BIOGRAPHY FALLEN BRIEFDESC FALLEN_NOTICE",
                (CLASS_ROWS[1], CLASS_ROWS[-1]), "-1",
            )
        for name, data in tables.items():
            (self.override / name).write_text(data, encoding="ascii")
        equipped = [_effect(177, f"C0ARCP{number:02d}") for number in range(1, 13)]
        equipped.extend((_effect(177, "C0ARCP25"), _effect(177, "OTHER", amount=17)))
        first_ability = [_effect(177, f"C0ARCP{number:02d}", target=2) for number in range(13, 25)]
        first_ability.extend((_effect(12, target=2, amount=13), _effect(146, "C0ARCP01", target=2)))
        second_ability = [_effect(177, "C0ARCP1", target=2), _effect(174, "SENTINEL", target=2)]
        (self.override / "OLD_BOW.ITM").write_bytes(_item(equipped, [first_ability, second_ability]))
        (self.override / "CLEAN.ITM").write_bytes(_item([_effect(177, "KEEP")], [[_effect(12, target=2, amount=7)]]))
        (self.override / "TINY.ITM").write_bytes(b"short unrelated fixture")
        for name in ("SENTINEL.PRO", "6100.INI", "PROJECTL.IDS", "MISSILE.IDS", "ANIMATE.IDS"):
            (self.override / name).write_bytes(f"unchanged {name}\n".encode("ascii"))
        # A previously installed source spell must be restored exactly too.
        (self.override / "SPCL121.SPL").write_bytes(b"previous Called Shot override\n")
        patch = root / "AKCB_ARCHER_TEST/setup-AKCB_ARCHER_TEST.tp2"
        patch.parent.mkdir()
        patch.write_text(
            "BACKUP ~AKCB_ARCHER_TEST/backup~\nAUTHOR ~synthetic integration test~\n"
            "BEGIN ~Archer production include integration test~\n"
            "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
            + "".join(f"INCLUDE ~ArtisansKitpack/lib/{name}~\n" for name in ("functions.tph", "hla_actions.tpa", "kit_strref.tpa"))
            + f"INCLUDE ~{INCLUDE.as_posix()}~\n",
            encoding="utf-8",
        )
        self.before = _raw_tree(self.override)

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "weidu.exe"), "AKCB_ARCHER_TEST/setup-AKCB_ARCHER_TEST.tp2", "--game", str(self.root),
             *[argument for operation in (operations or ("--force-install-list",)) for argument in (operation, "0")],
             "--language", "0", "--use-lang", "en_us", "--no-exit-pause", "--quick-log"],
            cwd=self.root, capture_output=True, encoding="utf-8", errors="replace", timeout=90, check=False,
        )

    def spell(self, resource: str) -> Spell:
        return Spell(_raw_tree(self.override)[f"{resource.upper()}.SPL"])


class ArcherBalanceTests(unittest.TestCase):
    def _game(self, *, eeex: bool = False, ranger: bool = False) -> SyntheticArcherGame:
        temporary = tempfile.TemporaryDirectory(prefix="akcb-archer-integration-")
        self.addCleanup(temporary.cleanup)
        return SyntheticArcherGame(Path(temporary.name) / "game", eeex=eeex, ranger=ranger)

    def _install(self, game: SyntheticArcherGame, *operations: str) -> None:
        process = game.run(*operations)
        transcript = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript)
        self.assertNotIn("NOT INSTALLED DUE TO ERRORS", transcript)
        for path, before in game.immutable.items():
            self.assertEqual(before, path.read_bytes(), str(path))
        self.assertEqual(game.source, _raw_tree(game.root / "ArtisansKitpack"))

    def _assert_progression(self, game: SyntheticArcherGame) -> None:
        output = _raw_tree(game.override)
        clab = output["CLABRN02.2DA"]
        self.assertEqual(list(range(4, 51, 4)), _grants(clab, "GA_SPCL121"))
        self.assertEqual([7] if game.eeex else [], _grants(clab, "AP_AKCBAS01"))
        self.assertEqual([1], _grants(clab, "GA_C0ARC03"))
        self.assertEqual([12], _grants(clab, "AP_C0ARC03Z"))
        self.assertEqual([2], _grants(clab, "AP_SENTINEL"))
        for removed in (b"GA_SPCL311", b"GA_SPCL412", b"AP_C0RNH1", b"GA_C0ARCH01"):
            self.assertNotIn(removed, clab.upper())
        self.assertEqual(game.before["CLABRN01.2DA"], output["CLABRN01.2DA"])
        self.assertEqual(game.eeex, "M_AKCBAR.LUA" in output)
        self.assertEqual(game.eeex, "AKCBAS01.SPL" in output)
        if game.eeex:
            self.assertEqual((ROOT / "ArtisansKitpack/lua/M_AKCBAR.lua").read_bytes(), output["M_AKCBAR.LUA"])
            for effects in game.spell("AKCBAS01").abilities:
                self.assertEqual([(321, "AKCBAS01"), (408, "AKCBAS")], [(fx.opcode, fx.resource) for fx in effects])
                self.assertEqual((1, 9, 2), (effects[1].target, effects[1].timing, effects[1].raw[13]))
        called_shot = game.spell("SPCL121")
        self.assertEqual([1, 16], [struct.unpack_from("<H", header, 16)[0] for header in called_shot.headers])
        self.assertEqual(4, struct.unpack_from("<I", output["C0ARCCS1.EFF"], 0x40)[0])
        self.assertEqual([0, 1], [sum(effect.opcode == 286 for effect in effects) for effects in called_shot.abilities])

    def _assert_removed_features(self, game: SyntheticArcherGame) -> None:
        output = _raw_tree(game.override)
        original = Spell(game.source["RANGER/ARCHER/SPELLS/C0ARC00.SPL"])
        actual = game.spell("C0ARC00")
        self.assertEqual(original.raw[:0x64], actual.raw[:0x64])
        for before, after in zip(original.abilities, actual.abilities):
            retained = [fx.raw for fx in before if fx.opcode != 262 and not (fx.opcode == 272 and fx.resource in ("C0ARC00A", "C0ARC00B"))]
            self.assertEqual(retained, [fx.raw for fx in after])
            self.assertNotIn(301, [fx.opcode for fx in after])
        for resource in ("C0ARC00A", "C0ARC00B", "C0ARCH01"):
            self.assertEqual([], game.spell(resource).effects, resource)
        retired = output["C0ARCH1A.EFF"]
        self.assertEqual(0, struct.unpack_from("<I", retired, 0x10)[0])
        self.assertEqual((0, 0, 0, 0), struct.unpack_from("<IIII", retired, 0x1C))
        hlas = _rows(output["LUC0RA1.2DA"])
        self.assertIn("GA_SPCL907", [row[1] for row in hlas])
        self.assertIn("GA_SENTINEL", [row[1] for row in hlas])
        self.assertNotIn("GA_C0ARCH01", [row[1] for row in hlas])
        self.assertEqual(game.before["LURA0.2DA"], output["LURA0.2DA"])
        self.assertEqual("C0RA1", dict(_rows(output["LUABBR.2DA"]))["FERALAN"])
        self.assertEqual("HPARCH", dict(_rows(output["HPCLASS.2DA"]))["FERALAN"])

    def _assert_description(self, game: SyntheticArcherGame) -> None:
        description = read_tlk_string(game.tlk, 12)
        for phrase in ("ARCHER:", "Advantages:", "Disadvantages:", "Grand Mastery", "Rapid Shot modal", "4th level", "25%", "two rounds", "save vs. Death", "no saving throw penalty", "16th level", "+2 ranged weapon damage", "Hit Die: d8", "Two-Weapon Style"):
            self.assertIn(phrase, description)
        for obsolete in ("Manyshot", "Farsighted", "Sniper", "Greater Called Shot", "dexterity", "unmitigated", "%akcb_archer_first_shot_description%"):
            self.assertNotIn(obsolete.lower(), description.lower())
        if game.eeex:
            for phrase in ("7th level", "Aimed Shot", "six seconds", "50%", "rounded down", "A miss spends"):
                self.assertIn(phrase, description)
        else:
            self.assertNotIn("Aimed Shot", description)
        self.assertEqual(game.ranger, "does not gain Toughness bonus" in description)
        self.assertEqual(game.ranger, "May not Set Traps" in description)
        output = _raw_tree(game.override)
        for table in ("BGCLATXT.2DA", "CLASTEXT.2DA", "SODCLTXT.2DA"):
            rows = _rows(output[table])
            original = _rows(game.before[table])
            self.assertEqual("12", rows[0][4])
            self.assertEqual(original[0][:4] + ["12"] + original[0][5:], rows[0])
            self.assertEqual(original[1:], rows[1:])
        for table in ("THIEFSCL.2DA", "CLASISKL.2DA"):
            if not game.ranger:
                self.assertEqual(game.before[table], output[table])
            else:
                self.assertNotIn(b"CD_DELETE_ME", output[table])
                self.assertEqual(len(_rows(game.before[table])), len(_rows(output[table])))

    def test_full_installer_branches_and_descriptions(self) -> None:
        for eeex, ranger in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(eeex=eeex, ranger=ranger):
                game = self._game(eeex=eeex, ranger=ranger)
                self._install(game)
                self._assert_progression(game)
                self._assert_removed_features(game)
                self._assert_description(game)

    def test_item_cleanup_is_exact_and_does_not_generate_projectiles(self) -> None:
        game = self._game(eeex=True)
        self._install(game)
        output = _raw_tree(game.override)
        original_global, original_abilities, original_headers = _item_slices(game.before["OLD_BOW.ITM"])
        actual_global, actual_abilities, actual_headers = _item_slices(output["OLD_BOW.ITM"])
        for before, after in zip([original_global, *original_abilities], [actual_global, *actual_abilities]):
            retained = [fx.raw for fx in before if not (fx.opcode == 177 and fx.resource in LEGACY_MANYSHOT)]
            self.assertEqual(retained, [fx.raw for fx in after])
        for before, after in zip(original_headers, actual_headers):
            self.assertEqual(before[:0x1E], after[:0x1E])
            self.assertEqual(before[0x22:], after[0x22:])
        self.assertEqual(game.before["OLD_BOW.ITM"][:0x64], output["OLD_BOW.ITM"][:0x64])
        for name in ("CLEAN.ITM", "TINY.ITM", "SENTINEL.PRO", "6100.INI", "PROJECTL.IDS", "MISSILE.IDS", "ANIMATE.IDS"):
            self.assertEqual(game.before[name], output[name], name)
        self.assertEqual({name for name in game.before if name.endswith((".PRO", ".INI"))}, {name for name in output if name.endswith((".PRO", ".INI"))})

    def test_reinstall_and_uninstall_restore_exact_override(self) -> None:
        for eeex in (False, True):
            with self.subTest(eeex=eeex):
                game = self._game(eeex=eeex, ranger=eeex)
                self._install(game)
                installed = _raw_tree(game.override)
                expected = set(game.before)
                for directory in PAYLOAD_DIRS:
                    expected.update(_raw_tree(game.root / directory))
                expected.update(("CLABRN02.2DA", "LUC0RA1.2DA"))
                if eeex:
                    expected.update(("AKCBAS01.SPL", "M_AKCBAR.LUA"))
                self.assertEqual(expected, set(installed))
                self._install(game, "--force-uninstall-list", "--force-install-list")
                self.assertEqual(installed, _raw_tree(game.override))
                process = game.run("--force-uninstall-list")
                transcript = process.stdout + process.stderr
                self.assertEqual(0, process.returncode, transcript)
                self.assertIn("SUCCESSFULLY REMOVED", transcript)
                self.assertEqual(game.before, _raw_tree(game.override))
                self.assertEqual(_tlk_entries(game.original_tlk), _tlk_entries(game.tlk.read_bytes())[:64])
                for path, before in game.immutable.items():
                    self.assertEqual(before, path.read_bytes(), str(path))
                active_logs = [line for line in (game.root / "WeiDU.log").read_text().splitlines() if line.startswith("~")]
                self.assertEqual(len(game.prerequisite_logs), len(active_logs))
                self.assertFalse(list(game.root.rglob("*.IDS.INSTALLED")))


if __name__ == "__main__":
    unittest.main()
