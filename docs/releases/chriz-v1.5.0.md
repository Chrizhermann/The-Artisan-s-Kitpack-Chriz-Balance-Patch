# Chriz Balance Patch v1.5.0

## Changes since v1.4.0

- **Cloak of Shadows lasts four rounds (24 seconds).** Its recurring invisible-state check, protection effects and fixed expiry share the new duration. Ability and Assassin kit descriptions match. Expose Weakness retains its separate three-round duration. The activation, invisibility requirement, recast cleanup and daily-use progression are unchanged.
- **Power Attack and Expertise use 2/4 tradeoffs.** Regular versions exchange a 2-point THAC0 penalty for 2 melee damage or 2 physical AC; improved versions use 4 points. Shared kit variants, Minsc's standalone Power Attack and their descriptions use the same values. Includes a focused Fighter retrofit for compatible existing installations.
- **Campaign Class descriptions use the installed kit text.** Correct the game-resource lookup, first-row handling and legacy aliases for Assassin, Archer, Beast Master and Avenger. The repair covers the available BG1, SoD and BG2 tables, fails safely on invalid references, and includes a focused existing-install component.

This release also contains all prior Paladin Detect Evil, Assassin, Magekiller Witchbane Strike, Hivemaster, Shield Bash, Berserker and Shapeshifter changes. The three main TP2 installers report `chriz-v1.5.0`.

## Playtest and verification scope

On September 16, the user accepted the recent Fighter, Paladin, Magekiller, Hivemaster and Class description changes in the combined EET test installation, then explicitly confirmed that Assassin works. This supersedes the earlier pending Assassin playtest status.

The subsequent increase from three to four rounds is checked through real WeiDU output: the protection durations, recurring checker and delayed expiry are all 24 seconds; the generated ability and kit descriptions say four rounds. A separate native run of the additional fourth round was not performed during release preparation.

All 51 regression tests passed. They cover spell effects, kit grants, descriptions, repeated installation and restoration. Sixteen focused WeiDU 249 syntax checks passed, including all three main TP2 files and the new retrofit installers. Focused retrofits preserve unrelated installed data and reject unsupported inputs. No game files or saved characters were changed during release preparation.

## Installation

Use the full archive for a fresh installation or a planned mod-stack rebuild. Replacing the mod's source folder alone does not update installed game resources.

For an established stack, use applicable components under `live-patch/` and their documented prerequisites. The Fighter, Class description, Paladin, Berserker and Shapeshifter retrofits each cover only their named scope; they do not perform a complete Kitpack upgrade. In particular, the four-round Cloak is installed by the updated Assassin component in the full installer.

Close the game before installing. Restart afterward; turn existing Fighter modals off and back on. Past level-up grants remain stored in existing characters, so a new installer does not silently migrate saved spellbooks.

The documented Spell Revisions component exclusions remain in force. The older aggregate playtest backlog and Berserker administrative-marker follow-up are separate unresolved issues, not fixes claimed by this release.

Original kits and mod architecture by Artemius_I / The Artisan.
