# Chriz Balance Patch v1.6.0

## Archer rebalance

- **Manyshot's extra projectiles are removed.** With EEex installed, Aimed Shot replaces it at level 7: one arrow or bolt deals 50% more physical damage, rounded down, then recharges for six seconds. A miss spends the bonus. There are no level-13 or level-20 upgrades. Ammunition effects occur normally, and the attack keeps its original damage type and weapon-protection rules.
- **Called Shot has a modest, saveable slow.** For its ten-second activation, successful ranged hits reduce movement by 25% for two rounds on a failed save vs. Death, with no save penalty. Repeated failed saves refresh the duration instead of stacking. Dexterity halving and the lost attack per round are removed.
- **Called Shot keeps a small damage boost.** From level 16, it grants +2 missile weapon damage during the activation, independent of the target's slow save. Daily uses begin at level 4 and increase every four levels.
- **Farsighted, Sniper and Greater Called Shot are removed.** The Archer uses ordinary sight range and critical chance, and retains access to Hardiness. Rapid Shot and the existing kit restrictions remain.
- **The late Manyshot item component is now a cleanup.** Component 20101 removes legacy Manyshot effects from items. Aimed Shot automatically supports bows and crossbows added by later mods.

All three main TP2 installers report `chriz-v1.6.0`. This release includes the previous balance changes and does not add new counters to late-game missile immunity or spell protections.

## Installation

Install Archer Overhaul (component 2010) using the full package. Install EEex first to receive Aimed Shot; without EEex, all other Archer changes apply and the replacement bonus is omitted.

Use the package for a fresh installation or a planned mod-stack rebuild. Replacing the source folder alone does not update installed game resources. This release does not include an Archer live-patch or migrate abilities already stored in saved characters. Existing Spell Revisions component exclusions in the README still apply.

## Verification

71 automated tests passed, including 20 Archer tests covering real WeiDU output, all EEex/Ranger-overhaul combinations, saving throws, level progression, descriptions, HLA choices, legacy item cleanup, reinstall and exact override restoration. The production Aimed Shot code was exercised with Lua 5.1 and EEex-shaped test objects. Seven WeiDU 249 syntax checks passed for the three main installers and four Archer includes.

The owner explicitly waived in-game playtesting for this release. These results establish source and synthetic behavior, not live-engine verification. No installed game or saved character was modified during release preparation.

Original kits and mod architecture by Artemius_I / The Artisan.
