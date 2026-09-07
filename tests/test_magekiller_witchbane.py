from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    ROOT,
    WEIDU,
    _raw_tree,
    _write_marker_key_and_bif,
)


LIBRARY = ROOT / "ArtisansKitpack/lib/magekiller_witchbane.tpa"
PUBLICATION = {
    "AKWBANE.SPL",
    "AKWBHIT.EFF",
    "AKWBHIT.SPL",
    "AKWBFAIL.SPL",
    "AKWBANE.BAM",
}
HLA_TABLE = (
    b"2DA V1.0\r\n"
    b"*\r\n"
    b"          ABILITY      ICON STRREF MIN_LEV MAX_LEVEL NUM_ALLOWED "
    b"PREREQUISITE EXCLUDED_BY ALIGNMENT_RESTRICT\r\n"
    b"C0MKIL1   AP_C0MK#008  *    *      1       99        3           "
    b"*            *           *\r\n"
    b"C0MKIL3   GA_SPCL904   *    *      1       99        16          "
    b"*            *           *\r\n"
    b"EMPTY     *            *    *      *       *         *           "
    b"*            *           *\r\n"
)


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _resref(data: bytes, offset: int) -> str:
    return data[offset : offset + 8].split(b"\0", 1)[0].decode("ascii").upper()


@dataclass(frozen=True)
class Effect:
    opcode: int
    target: int
    parameter1: int
    parameter2: int
    timing: int
    duration: int
    resist_dispel: int
    resource: str
    save_type: int
    save_bonus: int
    special: int

    @classmethod
    def packed(cls, data: bytes, offset: int) -> Effect:
        return cls(
            opcode=_u16(data, offset),
            target=data[offset + 0x02],
            parameter1=_u32(data, offset + 0x04),
            parameter2=_u32(data, offset + 0x08),
            timing=data[offset + 0x0C],
            duration=_u32(data, offset + 0x0E),
            resist_dispel=data[offset + 0x0D],
            resource=_resref(data, offset + 0x14),
            save_type=_u32(data, offset + 0x24),
            save_bonus=struct.unpack_from("<i", data, offset + 0x28)[0],
            special=_u32(data, offset + 0x2C),
        )

    @classmethod
    def external(cls, data: bytes) -> Effect:
        if data[:8] != b"EFF V2.0" or len(data) < 0x110:
            raise ValueError("Expected a complete EFF V2.0 resource")
        return cls(
            opcode=_u32(data, 0x10),
            target=_u32(data, 0x14),
            parameter1=_u32(data, 0x1C),
            parameter2=_u32(data, 0x20),
            timing=_u32(data, 0x24),
            duration=_u32(data, 0x28),
            resist_dispel=_u32(data, 0x5C),
            resource=_resref(data, 0x30),
            save_type=_u32(data, 0x40),
            save_bonus=struct.unpack_from("<i", data, 0x44)[0],
            special=_u32(data, 0x48),
        )


def _spell_effects(data: bytes) -> list[Effect]:
    """Read actual casting/ability slices, rejecting malformed effect ranges."""
    if data[:8] != b"SPL V1  ":
        raise ValueError("Expected an SPL V1 resource")
    abilities, count = _u32(data, 0x64), _u16(data, 0x68)
    effects_offset = _u32(data, 0x6A)
    slices = [(_u16(data, 0x6E), _u16(data, 0x70))]
    for index in range(count):
        ability = abilities + index * 0x28
        if ability + 0x28 > len(data):
            raise ValueError("Truncated SPL ability")
        slices.append((_u16(data, ability + 0x20), _u16(data, ability + 0x1E)))
    indices = sorted({index for first, count in slices for index in range(first, first + count)})
    if indices and effects_offset + (indices[-1] + 1) * 0x30 > len(data):
        raise ValueError("Truncated SPL effects")
    return [Effect.packed(data, effects_offset + index * 0x30) for index in indices]


class SyntheticWitchbaneGame:
    def __init__(self, root: Path, *, eeex: bool) -> None:
        self.root = root
        self.override = root / "override"
        self.override.mkdir(parents=True)
        shutil.copy2(WEIDU, root / "weidu.exe")
        _write_marker_key_and_bif(root)
        for path in (root / "lang/en_us/dialog.tlk", root / "dialog.tlk"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ONE_EMPTY_STRING_TLK)
        (self.override / "LUC0MKIL.2DA").write_bytes(HLA_TABLE)
        (self.override / "unrelated.txt").write_bytes(b"preserve this resource\r\n")
        if eeex:
            (self.override / "M___EEex.lua").write_bytes(b"-- synthetic EEex bootstrap\n")
        self.before = _raw_tree(self.override)
        self.stable_inputs = {
            relative: (root / relative).read_bytes()
            for relative in ("chitin.key", "data/akcbtest.bif", "dialog.tlk")
        }
        self.tp2 = root / "witchbane-test.tp2"
        self.tp2.write_text(
            "BACKUP ~witchbane-backup~\n"
            "AUTHOR ~Witchbane regression tests~\n"
            "BEGIN ~Witchbane installer harness~\n"
            f"OUTER_SPRINT MOD_FOLDER ~{(ROOT / 'ArtisansKitpack').as_posix()}~\n"
            "INCLUDE ~%MOD_FOLDER%/lib/hla_actions.tpa~\n"
            "INCLUDE ~%MOD_FOLDER%/lib/magekiller_witchbane.tpa~\n",
            encoding="utf-8",
            newline="\n",
        )

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.root / "weidu.exe"),
                self.tp2.name,
                "--game", str(self.root),
                *[argument for operation in operations for argument in (operation, "0")],
                "--language", "0",
                "--use-lang", "en_US",
                "--no-exit-pause",
                "--quick-log",
            ],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )


class WitchbaneInstallerTests(unittest.TestCase):
    """Real WeiDU install contracts; these do not simulate EEex combat."""

    def _game(self, *, eeex: bool = True) -> SyntheticWitchbaneGame:
        self.assertTrue(LIBRARY.is_file(), f"Missing production library: {LIBRARY}")
        temporary = tempfile.TemporaryDirectory(prefix="akcb-witchbane-")
        self.addCleanup(temporary.cleanup)
        return SyntheticWitchbaneGame(Path(temporary.name) / "game", eeex=eeex)

    def _install(self, game: SyntheticWitchbaneGame, *operations: str) -> dict[str, bytes]:
        process = game.run(*(operations or ("--force-install-list",)))
        transcript = process.stdout + "\n" + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        for relative, original in game.stable_inputs.items():
            self.assertEqual(original, (game.root / relative).read_bytes(), relative)
        return _raw_tree(game.override)

    def test_without_eeex_leaves_hla_table_resources_and_strings_unchanged(self) -> None:
        game = self._game(eeex=False)
        after = self._install(game)
        self.assertEqual(game.before, after)
        self.assertEqual(
            ONE_EMPTY_STRING_TLK,
            (game.root / "lang/en_us/dialog.tlk").read_bytes(),
        )

    def test_install_adds_one_hla_preserves_existing_choices_and_uninstalls_exactly(self) -> None:
        game = self._game()
        after = self._install(game)
        self.assertEqual(PUBLICATION, set(after) - set(game.before))
        for relative, original in game.before.items():
            if relative != "LUC0MKIL.2DA":
                self.assertEqual(original, after[relative], relative)

        rows = [line.split() for line in after["LUC0MKIL.2DA"].decode("ascii").splitlines()[3:]]
        choices = [row for row in rows if len(row) == 10 and row[1] == "GA_AKWBANE"]
        self.assertEqual(1, len(choices), rows)
        self.assertEqual("1", choices[0][6])
        self.assertEqual("AP_C0MK#008", choices[0][7])
        for ability, picks in (("AP_C0MK#008", "3"), ("GA_SPCL904", "16")):
            retained = [row for row in rows if len(row) == 10 and row[1] == ability]
            self.assertEqual(1, len(retained), rows)
            self.assertEqual(picks, retained[0][6])
        self.assertNotIn(b"C0MK#010", after["LUC0MKIL.2DA"].upper())

        process = game.run("--force-uninstall-list")
        transcript = process.stdout + "\n" + process.stderr
        self.assertEqual(0, process.returncode, transcript)
        self.assertNotIn("NOT UNINSTALLED", transcript, transcript)
        self.assertEqual(game.before, _raw_tree(game.override))

    def test_melee_bypass_debuff_save_consumption_and_nonstacking_contract(self) -> None:
        after = self._install(self._game())
        activation = after["AKWBANE.SPL"]
        self.assertEqual(4, _u16(activation, 0x1C), "HLA must grant an innate ability")
        self.assertEqual(1, _u32(activation, 0x34), "Use normal innate memorization")
        self.assertEqual(1, _u16(activation, 0x68))
        ability = _u32(activation, 0x64)
        self.assertEqual(5, activation[ability + 0x0C], "Arm the caster")
        self.assertEqual("AKWBANE", _resref(activation, 0x3A))
        self.assertEqual("AKWBANE", _resref(activation, ability + 0x04))
        for helper in ("AKWBHIT.SPL", "AKWBFAIL.SPL"):
            self.assertEqual(_u32(activation, 0x08), _u32(after[helper], 0x08),
                             "Helper combat feedback must use Witchbane's name")
        activation_effects = _spell_effects(activation)
        hooks = [effect for effect in activation_effects if effect.opcode == 248]
        self.assertEqual(1, len(hooks), activation_effects)
        hook = hooks[0]
        self.assertEqual("AKWBHIT", hook.resource)
        self.assertEqual(1, hook.special & 1, "EEex weapon-protection bypass bit")
        self.assertEqual((0, 12), (hook.timing, hook.duration))
        self.assertFalse(any(effect.opcode == 249 for effect in activation_effects))

        delivery = Effect.external(after["AKWBHIT.EFF"])
        self.assertEqual((146, "AKWBHIT"), (delivery.opcode, delivery.resource))
        # Opcode 248 chooses the struck creature and ignores the EFF target
        # field (IESDP EFF V2 body); the inherited donor's target=1 is valid.
        self.assertEqual(1, delivery.parameter2, "Cast the bridge instantly")
        self.assertEqual(2, delivery.resist_dispel)
        self.assertEqual(0, delivery.save_type & 0x1F, "Saving must not prevent consumption")
        hit = _spell_effects(after["AKWBHIT.SPL"])
        debuff = _spell_effects(after["AKWBFAIL.SPL"])
        consume = [effect for effect in hit if effect.opcode == 321 and effect.resource == "AKWBANE"]
        self.assertEqual(1, len(consume), hit)
        self.assertEqual(1, consume[0].target, "Consume the attacker's armed strike")
        self.assertEqual(0, consume[0].save_type & 0x1F)
        self.assertEqual((1, 2), (consume[0].timing, consume[0].resist_dispel))

        failure = [effect for effect in debuff if effect.opcode == 60]
        self.assertEqual(1, len(failure), debuff)
        self.assertEqual((50, 0, 0, 12), (
            failure[0].parameter1, failure[0].parameter2,
            failure[0].timing, failure[0].duration,
        ))
        self.assertEqual(2, failure[0].target)
        # A single save can gate the child spell or the actual debuff effect.
        save_gates = [
            effect for effect in hit + debuff
            if effect.target == 2 and effect.save_type & 0x1F
            and (effect.opcode == 60 or (
                effect.opcode == 146 and effect.resource == "AKWBFAIL"
            ))
        ]
        self.assertTrue(save_gates, "Hostile debuff needs a Save vs. Spell")
        for gate in save_gates:
            self.assertEqual(1, gate.save_type & 0x1F)
            self.assertEqual(0, gate.save_bonus)
        wrappers = [effect for effect in hit if effect.opcode == 146 and effect.resource == "AKWBFAIL"]
        self.assertEqual(1, len(wrappers), hit)
        self.assertLess(hit.index(consume[0]), hit.index(wrappers[0]))
        self.assertEqual(1, wrappers[0].resist_dispel, "Hostile wrapper checks Magic Resistance")
        self.assertEqual(3, failure[0].resist_dispel, "Avoid a second MR roll; allow dispelling")
        nonstacking = [
            effect for effect in debuff
            if (
            effect.opcode in {206, 318, 321, 324}
            and effect.resource == "AKWBFAIL" and effect.target == 2
            )
        ]
        self.assertTrue(nonstacking, "Debuff needs protection from or removal of its previous instance")
        for effect in nonstacking:
            if effect.opcode == 321:
                self.assertLess(debuff.index(effect), debuff.index(failure[0]))

        # No weapon damage, enchantment change, Breach or generic dispel belongs
        # anywhere in this chain. Resource removal may affect only our own state.
        permitted = {60, 139, 142, 146, 206, 318, 321, 324}
        for effect in [delivery, *hit, *debuff]:
            self.assertIn(effect.opcode, permitted, effect)
            if effect.opcode == 321:
                self.assertIn(effect.resource, {"AKWBANE", "AKWBFAIL"})

    def test_paired_reinstall_has_identical_resources_and_no_duplicate_hla(self) -> None:
        game = self._game()
        first = self._install(game)
        second = self._install(game, "--force-uninstall-list", "--force-install-list")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
