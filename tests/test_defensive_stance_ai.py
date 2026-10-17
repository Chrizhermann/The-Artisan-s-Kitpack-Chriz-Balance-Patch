from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_shapeshifter_personal_space import (
    ONE_EMPTY_STRING_TLK,
    _raw_tree,
    _write_marker_key_and_bif,
)


ROOT = Path(__file__).resolve().parents[1]
WEIDU = ROOT / "Setup-ArtisansKitpack.exe"
MAIN_LIB = ROOT / "ArtisansKitpack/lib/defensive_stance_ai.tpa"
PATCH_DIR = ROOT / "live-patch/AKCB_DEFENSIVE_STANCE_AI"
PATCH_TP2 = "AKCB_DEFENSIVE_STANCE_AI/setup-AKCB_DEFENSIVE_STANCE_AI.tp2"
GATE = 'Global("BDAI_DISABLE_SPECIAL","LOCALS",0)'

# Only the IDS entries the fixtures use; values match BG2:EE.
IDS = {
    "TRIGGER.IDS": """0x400F Global(S:Name*,S:Area*,I:Value*)
0x4018 Range(O:Object*,I:Range*)
0x402A NumCreatureGT(O:Object*,I:Number*)
0x402B ActionListEmpty()
0x4031 HaveSpellRES(S:Spell*)
0x4041 GlobalTimerNotExpired(S:Name*,S:Area*)
0x4043 InParty(O:Object*)
0x4045 CheckStatGT(O:Object*,I:Value*,I:StatNum*Stats)
0x4089 OR(I:OrCount*)
0x40E2 CheckSpellState(O:Object*,I:State*splstate)""",
    "ACTION.IDS": """0 NoAction()
30 SetGlobal(S:Name*,S:Area*,I:Value*)
31 Spell(O:Target*,I:Spell*Spell)
31 SpellRES(S:RES*,O:Target*)
36 Continue()
86 SetInterrupt(I:State*Boolean)
113 ForceSpellRES(S:RES*,O:Target)
115 SetGlobalTimer(S:Name*,S:Area*,I:Time*GTimes)
160 ApplySpellRES(S:RES*,O:Target)
181 ReallyForceSpellRES(S:RES*,O:Target)""",
    "OBJECT.IDS": "0 Nothing\n1 Myself\n12 NearestEnemyOf\n18 LastSeenBy",
    "SPLSTATE.IDS": "81 DEFENSIVE_STANCE",
    "STATS.IDS": "34 LEVEL",
    "BOOLEAN.IDS": "0 FALSE\n1 TRUE",
    "GTIMES.IDS": "6 ONE_ROUND",
    "SPELL.IDS": "4144 KENSAI_KIA",
    "EA.IDS": "0 ANYONE\n200 EVILCUTOFF",
}

UNRELATED = """IF
  Global("BDAI_RESET","GLOBAL",1)
THEN
  RESPONSE #100
    SetGlobal("BDAI_RESET","GLOBAL",0)
    Continue()
END
"""
# The vanilla BG2:EE block already reads the option.
GATED_STANCE = """IF
  Global("BDAI_DISABLE_SPECIAL","LOCALS",0)
  HaveSpellRES("SPDWD02")
  !CheckSpellState(Myself,DEFENSIVE_STANCE)
  Range(NearestEnemyOf(Myself),6)
  OR(2)
    CheckStatGT(LastSeenBy(Myself),12,LEVEL)
    NumCreatureGT([EVILCUTOFF],3)
  !GlobalTimerNotExpired("BD_Cast","LOCALS")
THEN
  RESPONSE #100
    SetInterrupt(FALSE)
    SetGlobalTimer("BD_Cast","LOCALS",ONE_ROUND)
    SpellRES("SPDWD02",Myself)
    SetInterrupt(TRUE)
END
"""
# Another ability without the option is out of scope and must stay as it is.
OTHER_ABILITY = """IF
  ActionListEmpty()
  InParty(Myself)
THEN
  RESPONSE #100
    Spell(Myself,KENSAI_KIA)
END
"""
# EET's BG1-only block from BDDEFAI-eb.baf.
EET_BG1_STANCE = """IF
{gate}  Global("ENDOFBG1","GLOBAL",0)
  HaveSpellRES("SPDWD02")
  !CheckSpellState(Myself,DEFENSIVE_STANCE)
  Range(NearestEnemyOf(Myself),6)
  OR(2)
    CheckStatGT(LastSeenBy(Myself),6,LEVEL)
    NumCreatureGT([EVILCUTOFF],3)
  !GlobalTimerNotExpired("BD_Cast","LOCALS")
THEN
  RESPONSE #100
    SetInterrupt(FALSE)
    SetGlobalTimer("BD_Cast","LOCALS",ONE_ROUND)
    SpellRES("SPDWD02",Myself)
    SetInterrupt(TRUE)
END
"""
# An OR group first, lower-case resref, another cast action and two responses.
OR_FIRST_STANCE = """IF
{gate}  OR(2)
    CheckStatGT(LastSeenBy(Myself),6,LEVEL)
    NumCreatureGT([EVILCUTOFF],3)
  HaveSpellRES("spdwd02")
THEN
  RESPONSE #50
    ForceSpellRES("spdwd02",Myself)
  RESPONSE #50
    Continue()
END
"""
# Only the conditions name the stance; the block casts something else.
CONDITION_ONLY = """IF
  HaveSpellRES("SPDWD02")
  InParty(Myself)
THEN
  RESPONSE #100
    ApplySpellRES("SPWI101",Myself)
END
"""
# A different form of the option check is the author's own condition.
OTHER_OPTION_FORM = """IF
  !Global("BDAI_DISABLE_SPECIAL","LOCALS",1)
  HaveSpellRES("SPDWD02")
THEN
  RESPONSE #100
    ReallyForceSpellRES("SPDWD02",Myself)
END
"""
COMPANION_STANCE = """IF
{gate}  HaveSpellRES("SPDWD02")
  Range(NearestEnemyOf(Myself),6)
THEN
  RESPONSE #100
    ApplySpellRES("SPDWD02",Myself)
END
"""


def _gate(template: str, gated: bool) -> str:
    return template.format(gate=f"  {GATE}\n" if gated else "")


def default_script(gated: bool) -> str:
    return "\n".join((
        UNRELATED,
        GATED_STANCE,
        OTHER_ABILITY,
        _gate(EET_BG1_STANCE, gated),
        _gate(OR_FIRST_STANCE, gated),
        CONDITION_ONLY,
        OTHER_OPTION_FORM,
    ))


def companion_script(gated: bool) -> str:
    return "\n".join((UNRELATED, _gate(COMPANION_STANCE, gated)))


PARTYAI = (
    "2DA V1.0\n"
    "BDDEFAI\n"
    "          AI_SCRIPT\n"
    "COMPANION BDCOMPC\n"
    "PLAIN     bdplainc\n"
    "MISSING   BDMISSC\n"
    "DEFAULT2  BDDEFAI\n"
)


class SyntheticPartyAIGame:
    def __init__(self, temporary: tempfile.TemporaryDirectory[str]) -> None:
        self.root = Path(temporary.name) / "game"
        self.root.mkdir()
        self.override = self.root / "override"
        self.override.mkdir()
        self.work = Path(temporary.name) / "work"
        self.work.mkdir()
        shutil.copy2(WEIDU, self.root / "weidu.exe")
        shutil.copytree(PATCH_DIR, self.root / PATCH_DIR.name)
        _write_marker_key_and_bif(self.root)
        for name, body in IDS.items():
            (self.override / name).write_text(f"IDS V1.0\n{body}\n", encoding="ascii", newline="\n")
        for path in (self.root / "lang/en_US/dialog.tlk", self.root / "dialog.tlk"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ONE_EMPTY_STRING_TLK)

    def compile(self, name: str, baf: str) -> bytes:
        source = self.work / f"{name}.baf"
        source.write_text(baf, encoding="ascii", newline="\n")
        process = self._weidu("--out", str(self.work), str(source))
        compiled = self.work / f"{name}.bcs"
        if not compiled.is_file():
            raise AssertionError(self.transcript(process))
        data = compiled.read_bytes()
        compiled.unlink()
        return data

    def add_script(self, name: str, baf: str) -> bytes:
        data = self.compile(name, baf)
        (self.override / f"{name}.BCS").write_bytes(data)
        return data

    def write_partyai(self, text: str, newline: str = "\n") -> None:
        (self.override / "PARTYAI.2DA").write_bytes(text.replace("\n", newline).encode("ascii"))

    def run(self, *operations: str) -> subprocess.CompletedProcess[str]:
        arguments = [argument for operation in operations for argument in (operation, "0")]
        return self._weidu(PATCH_TP2, *arguments, "--language", "0", "--no-exit-pause", "--quick-log")

    def _weidu(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "weidu.exe"), *arguments, "--game", str(self.root), "--use-lang", "en_US"],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )

    @staticmethod
    def transcript(process: subprocess.CompletedProcess[str]) -> str:
        return f"{process.stdout}\n{process.stderr}".strip()

    def installed(self) -> bool:
        log = self.root / "WeiDU.log"
        return log.is_file() and re.search(
            r"(?mi)^~AKCB_DEFENSIVE_STANCE_AI/SETUP-AKCB_DEFENSIVE_STANCE_AI\.TP2~\s+#0\s+#0\b",
            log.read_text(encoding="utf-8", errors="replace"),
        ) is not None


def _without_weidu_scratch(tree: dict[str, bytes]) -> dict[str, bytes]:
    # WeiDU deletes its own ADD_SPELL scratch file on every run; no fixture has one.
    return {name: data for name, data in tree.items() if name != "ADD_SPELL.IDS"}


class DefensiveStanceAITests(unittest.TestCase):
    def _game(self) -> SyntheticPartyAIGame:
        self.assertTrue((PATCH_DIR / "setup-AKCB_DEFENSIVE_STANCE_AI.tp2").is_file())
        temporary = tempfile.TemporaryDirectory(prefix="akcb-dsai-")
        self.addCleanup(temporary.cleanup)
        return SyntheticPartyAIGame(temporary)

    def _standard_game(self, newline: str = "\n") -> SyntheticPartyAIGame:
        game = self._game()
        game.add_script("BDDEFAI", default_script(gated=False))
        game.add_script("BDCOMPC", companion_script(gated=False))
        game.add_script("BDPLAINC", "\n".join((UNRELATED, OTHER_ABILITY)))
        # A creature script outside PARTYAI has no "Use special abilities" option.
        game.add_script("ENEMYDD", companion_script(gated=False))
        game.write_partyai(PARTYAI, newline)
        return game

    def _install(self, game: SyntheticPartyAIGame) -> str:
        process = game.run("--force-install-list")
        transcript = game.transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertTrue(game.installed(), transcript)
        return transcript

    def _assert_gated_tree(self, game: SyntheticPartyAIGame, before: dict[str, bytes]) -> None:
        after = _raw_tree(game.override)
        expected = dict(before)
        expected["BDDEFAI.BCS"] = game.compile("expected_default", default_script(gated=True))
        expected["BDCOMPC.BCS"] = game.compile("expected_companion", companion_script(gated=True))
        self.assertEqual(set(expected), set(after))
        for name in sorted(expected):
            self.assertEqual(expected[name], after[name], name)

    def test_gates_only_ungated_stance_blocks_of_smart_party_scripts(self) -> None:
        for newline in ("\n", "\r\n"):
            with self.subTest(partyai_newline=repr(newline)):
                game = self._standard_game(newline)
                before = _raw_tree(game.override)
                transcript = self._install(game)
                self._assert_gated_tree(game, before)
                self.assertIn("BDDEFAI.BCS now checks \"Use special abilities\" in 2 block(s)", transcript)
                self.assertIn("BDCOMPC.BCS now checks \"Use special abilities\" in 1 block(s)", transcript)

    def test_default_script_name_comes_from_partyai(self) -> None:
        game = self._game()
        game.add_script("XYZDEFAI", default_script(gated=False))
        # Not named by PARTYAI here, so it is not a smart party script.
        game.add_script("BDDEFAI", default_script(gated=False))
        game.write_partyai("2DA V1.0\nXYZDEFAI\n          AI_SCRIPT\n")
        before = _raw_tree(game.override)
        self._install(game)
        after = _raw_tree(game.override)
        self.assertEqual(game.compile("expected", default_script(gated=True)), after["XYZDEFAI.BCS"])
        self.assertEqual(before["BDDEFAI.BCS"], after["BDDEFAI.BCS"])
        self.assertEqual({k: v for k, v in before.items() if k != "XYZDEFAI.BCS"},
                         {k: v for k, v in after.items() if k != "XYZDEFAI.BCS"})

    def test_uninstall_restores_and_reinstall_matches(self) -> None:
        game = self._standard_game()
        before = _raw_tree(game.override)
        self._install(game)
        first = _raw_tree(game.override)

        process = game.run("--force-uninstall-list")
        transcript = game.transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertNotIn("NOT UNINSTALLED", transcript, transcript)
        self.assertEqual(before, _without_weidu_scratch(_raw_tree(game.override)))

        process = game.run("--force-uninstall-list", "--force-install-list")
        transcript = game.transcript(process)
        self.assertEqual(0, process.returncode, transcript)
        self.assertEqual(first, _raw_tree(game.override))

    def test_already_gated_scripts_stay_byte_identical(self) -> None:
        game = self._game()
        game.add_script("BDDEFAI", default_script(gated=True))
        game.add_script("BDCOMPC", companion_script(gated=True))
        game.add_script("BDPLAINC", "\n".join((UNRELATED, OTHER_ABILITY)))
        game.write_partyai(PARTYAI)
        before = _raw_tree(game.override)
        transcript = self._install(game)
        self.assertEqual(before, _raw_tree(game.override))
        self.assertIn('already checks "Use special abilities"', transcript)

    def test_game_without_partyai_is_not_patched(self) -> None:
        game = self._game()
        game.add_script("BDDEFAI", default_script(gated=False))
        before = _raw_tree(game.override)
        process = game.run("--force-install-list")
        transcript = game.transcript(process)
        self.assertNotIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertIn("no PARTYAI.2DA", transcript, transcript)
        self.assertFalse(game.installed())
        self.assertEqual(before, _without_weidu_scratch(_raw_tree(game.override)))

    def test_unreadable_partyai_fails_without_mutation(self) -> None:
        game = self._game()
        game.add_script("BDDEFAI", default_script(gated=False))
        game.write_partyai("BDDEFAI\nAI_SCRIPT\nCOMPANION BDCOMPC\n")
        before = _raw_tree(game.override)
        process = game.run("--force-install-list")
        transcript = game.transcript(process)
        self.assertNotIn("SUCCESSFULLY INSTALLED", transcript, transcript)
        self.assertIn("PARTYAI.2DA is not a readable 2DA table", transcript, transcript)
        self.assertFalse(game.installed())
        self.assertEqual(before, _without_weidu_scratch(_raw_tree(game.override)))


class DefensiveStanceAISourceTests(unittest.TestCase):
    def test_live_patch_carries_the_main_library(self) -> None:
        self.assertEqual(MAIN_LIB.read_bytes(), (PATCH_DIR / "lib/defensive_stance_ai.tpa").read_bytes())

    def test_both_vanguard_components_gate_the_party_ai(self) -> None:
        call = re.compile(
            r"^INCLUDE ~%MOD_FOLDER%/lib/defensive_stance_ai\.tpa~\r?\n"
            r"LAF akcb_gate_defensive_stance_party_ai END\r?$",
            re.MULTILINE,
        )
        for name in ("dwarvendefender.tpa", "vanguard.tpa"):
            with self.subTest(component=name):
                source = (ROOT / "ArtisansKitpack/lib" / name).read_text(encoding="utf-8")
                self.assertEqual(1, len(call.findall(source)))


if __name__ == "__main__":
    unittest.main()
