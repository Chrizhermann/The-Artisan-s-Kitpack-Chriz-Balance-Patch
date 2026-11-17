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


if __name__ == "__main__":
    unittest.main()
