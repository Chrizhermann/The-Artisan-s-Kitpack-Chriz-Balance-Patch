# Live-install tail patches

WeiDU mini-mods that retrofit this fork's balance changes onto an
**already-installed** upstream Artisan's Kitpack, so they can be appended at the
tail of a live install's WeiDU stack without uninstalling anything (the
never-uninstall rule for the main EET install).

Fresh installs don't need these — install the fork itself instead; the fork's
`lib/*.tpa` produce the same end state.

## AKCB_FIGHTER_MODALS

Updates the installed Fighter overhaul's Power Attack and Expertise to 2-point
tradeoffs, or 4 points for their improved versions, while retaining other
installed effects. Shared kit versions are updated where present. See the
[requirements and installation instructions](AKCB_FIGHTER_MODALS/README.md).

## AKCB_KIT_DESCRIPTIONS

Component 0 links campaign Class screens to the existing descriptions of
installed Artisan kits. It handles the Assassin, Archer, Beast Master and
Avenger name aliases and updates BG1, SoD and BG2 campaign tables when present.
It changes no kit abilities or saved characters and creates no dialogue strings.

Copy the complete `AKCB_KIT_DESCRIPTIONS` directory to the closed game's root,
copy a WeiDU 249 executable to `Setup-AKCB_KIT_DESCRIPTIONS.exe`, and run it with
`--force-install-list 0 --language 0 --use-lang en_US --no-exit-pause`.
Fully restart the game afterward. This repairs links to descriptions already
installed; it does not import newer kit rules from another version.

## AKCB_PALADIN

Restores the missing level-1 Detect Evil grant for the Paladin overhaul and
installed Cavalier, Inquisitor, Undead Hunter, and Mystic Fire overhauls.
Blackguard remains excluded, and all HLA limits retain their existing values.
Requires AK component 3000. See [installation and existing-character
instructions](AKCB_PALADIN/README.md). Version 1.0.1 also provides an upgrade
path from the unreleased combined Detect Evil/Deva build.

## AKCB_BERSERKER

Berserker Overhaul rebalance (see
`docs/plans/2026-07-05-berserker-rebalance-design.md` for the full spec and
rationale). Requires AK component 1003 installed.

From the game dir, after copying the `AKCB_BERSERKER` folder there and creating
`Setup-AKCB_BERSERKER.exe` as a copy of any WeiDU v24900 setup exe:

**FIRST INSTALL:**

```
./Setup-AKCB_BERSERKER.exe --force-install-list 0 --language 0 --no-exit-pause
```

**UPGRADE/REINSTALL** an already-installed v2.0 component:

```
./Setup-AKCB_BERSERKER.exe --force-uninstall-list 0 --force-install-list 0 --language 0 --no-exit-pause
```

Keep both force flags in the same invocation. `--force-install-list 0` alone is
a no-op when component 0 is already installed, while WeiDU's `--reinstall`
only reliably handles a component that is still at the top of the install
stack. The paired command also lets WeiDU unwind and restore any later
components if this former tail patch is no longer last.

Post-install, for each existing Berserker party member (once, in-game, fully
restarted client):

```
C:Eval('ReallyForceSpellRES("AKCBRFRM",Player1)')
```

(unquoted `Player1`; substitute the right PlayerN) — removes the deleted
Reckless Frenzy innate AND (v1.2) swaps the save-baked permanent passive for
the trimmed one (fear/morale immunity moves into Enrage; the −4 thrown-mode
penalty arrives). Safe to re-run; **run it again after upgrading from
v1.0/v1.1**. Everything else self-applies: In Extremis tiers within one round,
Enrage on its next cast, the ranged-weapon ban on load (unequip any bow/sling
first — it becomes unusable), Hardiness at the next HLA level-up.

**v2.1** keeps the v2.0 In Extremis rebuild (THAC0 penalty,
damage/resistance double while Enraged, resistance gated to L14, APR at the L1
base) and normalizes physical resistance on every install. Slashing, crushing,
piercing, and missile resistance now use base tier **totals** of 3/6/10% and
Enraged tier **totals** of 6/12/20%; the tiers are not cumulative across HP
thresholds. After installing or reinstalling/upgrading the WeiDU component,
this update needs **no additional console step**: the tier spells are re-cast
from the newly installed files every round, so the normalized values, the
rage-scaling op326 branch, and the level gates all take effect on the next load.
Only run `AKCBRFRM` if you haven't already for v1.2.

## AKCB_SHAPESHIFTER

Shapeshifter Overhaul pathfinding fix, component 0: the four custom
greater-werewolf animations (brown/grey/black/white) use
`personal_space=3`, the humanoid pathfinding footprint, instead of 5 so they
fit through standard doors. This changes engine size only; sprite scale,
selection circle (`ellipse=16`) and movement speed are unchanged. The regular
werewolf forms already use 3.

Requires Artisan's Kitpack custom-sprite component 5110 or 5111. With 5110,
NPC werewolves keep their vanilla animation slots and are untouched. With
5111, the user explicitly chose custom sprites for NPC werewolves too, so NPC
greater werewolves share the same corrected custom INIs.

The extended INI filenames are allocated per install. The patch resolves each
animation semantically through `ANIMATE.IDS` and never hardcodes an `e0xx.ini`
filename. Synthetic-game coverage uses deliberately remapped slots and checks
that exactly the four greater INIs change, malformed or missing resources roll
back, already-fixed inputs remain byte-identical, and uninstall restores the
entire override tree byte-exactly.

From the game directory, after copying the `AKCB_SHAPESHIFTER` folder there
and creating `Setup-AKCB_SHAPESHIFTER.exe` as a copy of a WeiDU v24900 setup
executable:

**FIRST INSTALL:**

```
./Setup-AKCB_SHAPESHIFTER.exe --force-install-list 0 --language 0 --no-exit-pause
```

**UPGRADE/REINSTALL:**

```
./Setup-AKCB_SHAPESHIFTER.exe --force-uninstall-list 0 --force-install-list 0 --language 0 --no-exit-pause
```

No console step is needed. Animation INIs are runtime data rather than
save-baked state: close the game before installing, restart it fully, and then
load the save. Undo by uninstalling component 0 through WeiDU.

Fresh installs of this fork reach the same end state directly from
`ArtisansKitpack/Druid/Shapeshifter/animations/werewolf_greater*/exxx.ini`.

## AKCB_DEFENSIVE_STANCE_AI

Smart party AI now respects the record screen's **Use special abilities**
option for Defensive Stance (`SPDWD02`). The default party AI script named by
`PARTYAI.2DA` (`BDDEFAI`) runs the protagonist and every NPC without their own
entry. EET appends a BG1-only Defensive Stance block to it that ignored the
option, so in BG1 the protagonist kept using the stance with the option off.
The BG2/SoD block already checked it.

Component 0 reads `PARTYAI.2DA` for the default and companion scripts. In each
installed script that casts the stance without reading the option, it adds
`Global("BDAI_DISABLE_SPECIAL","LOCALS",0)` as the block's first condition.
Other blocks keep their triggers, and scripts that need no change stay
byte-identical. If every stance block already checks the option, it changes
nothing and says so. A missing `PARTYAI.2DA` blocks the install, since such a
game has no smart party AI options; an unreadable one fails without changes.

No Kitpack component is required. Vanilla Dwarven Defenders use the same
`SPDWD02`, and the patch changes only scripts that already cast it. Synthetic-game
coverage checks LF and CRLF tables, a renamed default script, already-gated
blocks, unrelated blocks and scripts, and byte-exact uninstall and reinstall.

From the game directory, after copying the `AKCB_DEFENSIVE_STANCE_AI` folder
there and creating `Setup-AKCB_DEFENSIVE_STANCE_AI.exe` as a copy of a WeiDU
v24900 setup executable:

**FIRST INSTALL:**

```
./Setup-AKCB_DEFENSIVE_STANCE_AI.exe --force-install-list 0 --language 0 --no-exit-pause
```

**UPGRADE/REINSTALL:**

```
./Setup-AKCB_DEFENSIVE_STANCE_AI.exe --force-uninstall-list 0 --force-install-list 0 --language 0 --no-exit-pause
```

No console step is needed. Saves store only the script name, so close the game
before installing, restart it fully, and then load the save. Undo by
uninstalling component 0 through WeiDU.

Fresh installs of this fork apply the same change from component 1002
(Vanguard Fighter Kit) or 1007 (Dwarven Defender Overhaul + Vanguard).
