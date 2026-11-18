"""WeiDU install/uninstall checks for the Eldritch Knight and Combat Casting projectiles."""
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from test_assassin_expose_weakness import ROOT, WEIDU, Spell
from test_shapeshifter_personal_space import ONE_EMPTY_STRING_TLK, _raw_tree, _write_marker_key_and_bif


MOD = ROOT / "ArtisansKitpack"
COMBAT = Path("effects/combat_casting")
AWARENESS = Path("MultiKit/Eldritch_Knight")
SENTINEL_PROJECTILE = 610


class SaveProjectileTests(unittest.TestCase):
    def test_installer_reuses_ids_and_overwrites_aura_dispatchers(self):
        for already_registered in (False, True):
            with self.subTest(already_registered=already_registered), tempfile.TemporaryDirectory() as directory:
                game = Path(directory)
                override = game / "override"
                override.mkdir()
                _write_marker_key_and_bif(game)
                (game / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
                (game / "lang/en_US").mkdir(parents=True)
                (game / "lang/en_US/dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
                source = game / "ArtisansKitpack"
                (source / "lib").mkdir(parents=True)
                shutil.copytree(MOD / COMBAT, source / COMBAT)
                shutil.copy2(MOD / "effects/combat_casting.tpa", source / "effects/combat_casting.tpa")
                (game / "WeiDU.log").write_text("")
                shutil.copytree(MOD / AWARENESS, source / AWARENESS)
                for name in ("functions.tph", "eldritch_knight_aura.tpa"):
                    shutil.copy2(MOD / "lib" / name, source / "lib" / name)
                (override / "STATDESC.2DA").write_text("2DA V1.0\n0\nSTRREF BAM\n0 0 TEST\n")
                projectiles = f"IDS V1.0\n{SENTINEL_PROJECTILE} OTHER\n"
                if already_registered:
                    projectiles += "565 C0EKCCP\n564 C0EK1P\n"
                    shutil.copy2(MOD / COMBAT / "c0ekcc.spl", override / "C0EKCC.SPL")
                (override / "PROJECTL.IDS").write_text(projectiles)
                (override / "MISSILE.IDS").write_text("IDS V1.0\n0 NONE\n")
                # Seed valid but edited PROs and SPL abilities. The component owns these fields.
                for source_file, name in (
                    (MOD / COMBAT / "c0ekccp.PRO", "C0EKCCP"),
                    (MOD / AWARENESS / "projectiles/C0EK1P.PRO", "C0EK1P"),
                ):
                    changed = bytearray(source_file.read_bytes())
                    changed[0x0C] &= ~0x40
                    changed[0x2C] |= 0x40
                    changed[0x206] ^= 0x3F
                    (override / f"{name}.PRO").write_bytes(changed)
                for source_file, name in (
                    (MOD / COMBAT / "c0ekcc1.spl", "C0EKCC1"),
                    (MOD / AWARENESS / "spells/c0ek1.spl", "C0EK1"),
                ):
                    changed = bytearray(source_file.read_bytes())
                    header = struct.unpack_from("<I", changed, 0x64)[0]
                    struct.pack_into("<H", changed, header + 0x26, SENTINEL_PROJECTILE + 1)
                    (override / f"{name}.SPL").write_bytes(changed)
                for name in ("INAREANP", "GREASE", "CLOUDKIL"):
                    (override / f"{name}.PRO").write_bytes(f"unrelated-{name}".encode())
                before = _raw_tree(override)
                (game / "test.tp2").write_text(
                    "BACKUP ~backup~\nAUTHOR ~test~\nBEGIN ~Production aura includes~\n"
                    "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
                    "INCLUDE ~ArtisansKitpack/lib/functions.tph~\n"
                    "INCLUDE ~ArtisansKitpack/lib/eldritch_knight_aura.tpa~\n"
                    "INCLUDE ~ArtisansKitpack/effects/combat_casting.tpa~\n"
                )

                def run(command):
                    result = subprocess.run(
                        [str(WEIDU), "test.tp2", "--no-auto-tp2", "--game", str(game),
                         "--use-lang", "en_US", "--language", "0", "--no-exit-pause", command, "0"],
                        cwd=game, text=True, capture_output=True, check=False, timeout=60,
                    )
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)

                run("--force-install-list")
                actual = {path.name.upper(): path for path in override.iterdir()}
                ids = {}
                for line in actual["PROJECTL.IDS"].read_text().splitlines()[1:]:
                    index, symbol, *_ = line.split()
                    self.assertNotIn(symbol.upper(), ids)
                    ids[symbol.upper()] = int(index, 0)
                self.assertEqual(SENTINEL_PROJECTILE, ids["OTHER"])
                if already_registered:
                    self.assertEqual(565, ids["C0EKCCP"])
                    self.assertEqual(564, ids["C0EK1P"])
                for spell, pro, expected in (
                    ("C0EKCC1", "C0EKCCP", MOD / COMBAT / "c0ekccp.PRO"),
                    ("C0EK1", "C0EK1P", MOD / AWARENESS / "projectiles/C0EK1P.PRO"),
                ):
                    result = actual[f"{pro}.PRO"].read_bytes()
                    self.assertEqual(expected.read_bytes(), result)
                    self.assertTrue(result[0x0C] & 0x40)
                    headers = Spell(actual[f"{spell}.SPL"].read_bytes()).headers
                    self.assertTrue(headers)
                    self.assertTrue(all(struct.unpack_from("<H", header, 0x26)[0] == ids[pro] + 1
                                        for header in headers))
                awareness = (source / AWARENESS / "spells/c0ek1.eff").read_bytes()
                self.assertEqual(146, struct.unpack_from("<I", awareness, 0x10)[0])
                self.assertEqual(b"C0EK1\0\0\0", awareness[0x30:0x38].upper())
                for name in ("INAREANP", "GREASE", "CLOUDKIL"):
                    self.assertEqual(f"unrelated-{name}".encode(), actual[f"{name}.PRO"].read_bytes())
                run("--force-uninstall-list")
                self.assertEqual(before, _raw_tree(override))


    def test_preseeded_tracking_gets_canonical_pulses_and_keeps_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            override = game / "override"
            override.mkdir()
            _write_marker_key_and_bif(game)
            (game / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
            (game / "WeiDU.log").write_text("")
            (game / "lang/en_US").mkdir(parents=True)
            (game / "lang/en_US/dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
            tracking = MOD / "Spells"
            dest = game / "ArtisansKitpack/Spells"
            shutil.copytree(tracking / "tracking", dest / "tracking")
            for name in ("tracking.tpa", "tracking_projectiles.tpa"):
                shutil.copy2(tracking / name, dest / name)
            shutil.copy2(tracking / "tracking/C0CL922.SPL", override)
            donor = (tracking / "tracking/projectile/C0TRKP01.PRO").read_bytes()
            stale = bytearray(donor)
            stale[0x0C] &= ~0x40
            for profile in range(1, 4):
                (override / f"C0TRKP0{profile}.PRO").write_bytes(stale)
            (override / "PROJECTL.IDS").write_text(
                "IDS V1.0\n718 C0TRKP01\n726 C0TRKP02\n733 C0TRKP03\n"
            )
            (override / "MISSILE.IDS").write_text("IDS V1.0\n0 NONE\n")
            (game / "test.tp2").write_text(
                "BACKUP ~backup~\nAUTHOR ~test~\nBEGIN ~Tracking mutation~\n"
                "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
                "INCLUDE ~ArtisansKitpack/Spells/tracking.tpa~\n"
            )
            for name in ("SPCL922f", "SPCL922G", "SPCL922H"):
                (override / f"{name}.SPL").write_bytes((tracking / "tracking" / f"{name}.SPL").read_bytes())
            before = _raw_tree(override)
            for operation in ("install", "uninstall"):
                result = subprocess.run(
                    [str(WEIDU), "test.tp2", "--no-auto-tp2", "--game", str(game),
                     "--use-lang", "en_US", "--language", "0", "--no-exit-pause", f"--force-{operation}-list", "0"],
                    cwd=game, text=True, capture_output=True, timeout=60,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                if operation == "install":
                    for i, (radius, number, spell) in enumerate(
                        ((800, 719, "SPCL922F"), (1200, 727, "SPCL922G"), (1600, 734, "SPCL922H")), 1
                    ):
                        expected = bytearray(donor)
                        struct.pack_into("<HH", expected, 0x204, radius, radius)
                        actual = (override / f"C0TRKP0{i}.PRO").read_bytes()
                        self.assertEqual(expected, actual)
                        self.assertTrue(actual[0x0C] & 0x40)
                        headers = Spell((override / f"{spell}.SPL").read_bytes()).headers
                        self.assertEqual({number}, {struct.unpack_from("<H", h, 0x26)[0] for h in headers})
                else:
                    self.assertEqual(before, _raw_tree(override))


    def test_conditional_and_repeating_aura_producers_overwrite_projectile_fields(self):
        auras = (
            ("PaleMaster", "PMPASS8B", "C0AKSVA"),
            ("Cavalier", "C0CAV02B", "C0AKSVA"),
            ("Hivemaster", "C0HIVEI2", "C0AKSVA"),
            ("Shapeshifter", "C0SS-HLB", "C0AKSVA"),
            ("Kensai", "C0KN#03A", "C0AKSVN"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            override = game / "override"
            override.mkdir()
            _write_marker_key_and_bif(game)
            (game / "dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
            (game / "lang/en_US").mkdir(parents=True)
            (game / "lang/en_US/dialog.tlk").write_bytes(ONE_EMPTY_STRING_TLK)
            (game / "WeiDU.log").write_text("")
            (override / "PROJECTL.IDS").write_text("IDS V1.0\n443 C0AKSVA\n510 C0AKSVN\n")
            (override / "MISSILE.IDS").write_text("IDS V1.0\n0 NONE\n")
            addon = game / "ArtisansKitpack"
            (addon / "lib").mkdir(parents=True)
            shutil.copy2(MOD / "lib/passive_projectile.tpa", addon / "lib")
            shutil.copytree(MOD / "Spells/save_projectiles", addon / "Spells/save_projectiles")
            for profile in ("C0AKSVA", "C0AKSVN"):
                data = bytearray((addon / f"Spells/save_projectiles/{profile}.PRO").read_bytes())
                data[0x0C] &= ~0x40
                data[0x2C] |= 0x40
                (override / f"{profile}.PRO").write_bytes(data)

            calls = []
            expected = {}
            for producer, spell, profile in auras:
                line = next(line for line in (MOD / f"lib/{producer}.tpa").read_text().splitlines()
                            if line.startswith("LAF c0ak_passive_projectile"))
                calls.append(line)
                donor = next(path for path in MOD.rglob("*.SPL")
                             if path.stem.upper() == spell)
                data = bytearray(donor.read_bytes())
                offset, count = struct.unpack_from("<IH", data, 0x64)
                for index in range(count):
                    struct.pack_into("<H", data, offset + index * 0x28 + 0x26, 1745)
                (override / f"{spell}.SPL").write_bytes(data)
                for index in range(count):
                    struct.pack_into("<H", data, offset + index * 0x28 + 0x26,
                                     444 if profile == "C0AKSVA" else 511)
                expected[spell] = bytes(data)
            (game / "test.tp2").write_text(
                "BACKUP ~backup~\nAUTHOR ~test~\nBEGIN ~Passive player abilities~\n"
                "OUTER_SPRINT MOD_FOLDER ~ArtisansKitpack~\n"
                "INCLUDE ~ArtisansKitpack/lib/passive_projectile.tpa~\n"
                + "\n".join(calls) + "\n"
            )
            before = _raw_tree(override)
            for operation in ("install", "uninstall"):
                result = subprocess.run(
                    [str(WEIDU), "test.tp2", "--no-auto-tp2", "--game", str(game),
                     "--use-lang", "en_US", "--language", "0", "--no-exit-pause",
                     f"--force-{operation}-list", "0"],
                    cwd=game, text=True, capture_output=True, timeout=60,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                if operation == "install":
                    for spell, desired in expected.items():
                        self.assertEqual(desired, (override / f"{spell}.SPL").read_bytes())
                    for profile in ("C0AKSVA", "C0AKSVN"):
                        self.assertEqual((addon / f"Spells/save_projectiles/{profile}.PRO").read_bytes(),
                                         (override / f"{profile}.PRO").read_bytes())
                else:
                    self.assertEqual(before, _raw_tree(override))


if __name__ == "__main__":
    unittest.main()
