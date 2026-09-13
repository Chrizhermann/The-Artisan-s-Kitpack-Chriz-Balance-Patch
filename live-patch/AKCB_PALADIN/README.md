# Paladin Detect Evil patch

Append this mini-mod after Artisan's Kitpack. It requires
the Paladin Overhaul (component 3000). Do not reinstall the middle of an
established mod stack to apply these changes.

## Behavior

- Restore one level-1 Detect Evil grant to the Paladin and installed Cavalier,
  Inquisitor, Undead Hunter, and Mystic Fire overhauls if the grant is missing.
  The installed spell is retained: Artisan's SPCL212 already refreshes itself
  after use. Existing grants are preserved without adding duplicates.
- All HLA tables and summon effects retain their existing behavior, including
  vanilla repeatable Summon Deva. Blackguard's Detect Evil prohibition remains.

## Install

1. Save and quit the game completely.
2. Copy `AKCB_PALADIN` into the game directory containing `chitin.key`.
3. Copy a WeiDU 249 setup executable to `Setup-AKCB_PALADIN.exe` there.
4. Run from that game directory:

```powershell
.\Setup-AKCB_PALADIN.exe --force-install-list 0 --language 0 --use-lang en_US --no-exit-pause
```

Launch the game again after installation.

Version 1.0.1 replaces the unreleased 1.0.0 build, which also capped Summon
Deva. To upgrade that build while it is still the last installed component,
replace the patch folder, then run the same command with both
`--force-uninstall-list 0 --force-install-list 0`. WeiDU restores the original
HLA tables from the old backup before installing the Detect Evil fix alone.

## Existing characters

The installer changes progression tables. It does not edit saves,
refund previously spent HLA points, or remove previously acquired Deva uses.
A character already missing Detect Evil needs one grant added separately;
first check that character's saved or live innate spellbook to avoid duplicates.
For a confirmed missing grant on the protagonist, the in-game console action is:

```lua
C:Eval('ActionOverride(Player1,AddSpecialAbility("SPCL212"))')
```

Run that repair once, let the engine process it, and check the Special Abilities
menu. Cast Detect Evil twice without resting, then save/reload and confirm it
remains available. Do not use the protagonist command for another party member.

Installer tests do not establish these live-engine results. Release of this
fix does not depend on a playtest; the existing-character grant can be tried later.

## Provenance

Artisan [documents Detect Evil at will](https://artisans-corner.com/the-artisans-kitpack/),
but its [Paladin installer](https://github.com/TheArtisanBG/The-Artisan-s-Kitpack/blob/85928f964f6965fd37980bf679d7eeb9af410256/ArtisansKitpack/lib/Paladin.tpa#L4-L12)
removes the grant, and Cavalier copies that parent table. Restoring the grant
corrects that contradiction.

Repeatable Summon Deva is vanilla behavior: the original `LUPA0.2DA` extracted
from BG2:EE's `DATA/25DEFLT.BIF` has `GA_SPCL923` with `NUM_ALLOWED=20`.
This patch preserves that limit. The inspected Spell Revisions v4.21-chriz.2
installation changes the summon resources but does not change this selection
limit.
