# Sorcerer weapon usability patch

Append this mini-mod after Artisan's Kitpack on a game where sorcerers cannot
equip daggers, quarterstaves, darts or slings they have no proficiency pips in.
Every sorcerer kit is affected, the Dragon Disciple included; mages are not.

## Cause

With EEex, Kitpack clears the class usability bits of weapons that fighters
can use and gates each one with opcode 319 on a per-weapon stat instead.
`C0PR#CL.SPL` grants those stats from proficiency pips and from each class's
`WEAPPROF.2DA` column. Upstream commit
[7464043](https://github.com/TheArtisanBG/The-Artisan-s-Kitpack/commit/7464043fbf93fbd448401436181713de3737b72e)
(2026-02-21) replaced the hand-written class grants, which included sorcerer
daggers, quarterstaves, darts and slings, with grants generated from WEAPPROF
columns. WEAPPROF has no SORCERER column, so `C0PR#CL.SPL` now grants
sorcerers no class weapons at all. A gated weapon is then usable only when the
sorcerer has pips in it; weapons the install leaves ungated are not affected.
Upstream master (85928f9) is still affected.

## Behavior

- For each class weapon grant mages receive in the installed `C0PR#CL.SPL`,
  add the same grant for sorcerers: a byte copy of the mage entry with only
  the class changed. Sorcerers then use the weapons their engine proficiency
  column (MAGE) offers, as before the regression.
- Keep existing sorcerer grants without adding duplicates, as well as the
  grants of all other classes, the pip-based grants and every other effect.
  An already repaired file stays byte-identical.
- Kit extras are unchanged, for example the Eldritch Knight's or the Arcane
  Trickster's additional weapons.
- Skip when `C0PR#CL.SPL` does not exist, because the EEex usability system is
  not installed. Stop without changes if the spell's tables are malformed.

A fresh install of this fork gives the same file directly from
`ArtisansKitpack/eeex/profs_eeex.tpa`.

## Install

1. Save and quit the game completely.
2. Copy `AKCB_SORCERER_WEAPONS` into the game directory containing `chitin.key`.
3. Copy a WeiDU 249 setup executable to `Setup-AKCB_SORCERER_WEAPONS.exe` there.
4. Run from that game directory:

```powershell
.\Setup-AKCB_SORCERER_WEAPONS.exe --force-install-list 0 --language 0 --use-lang en_US --no-exit-pause
```

Launch the game again after installation. Reinstalling Kitpack's tweak
"Update EEex-based Weapon Usability Changes" from a build without this fix
regenerates the class grants without sorcerers; install this patch again after
such a reinstall.

## Existing characters

Saves need no migration: the class grants are not stored as part of the
character's build but reapplied from `C0PR#CL.SPL`. The class and kit
progression tables Kitpack patched apply it at each level-up. Kitpack's helper
creature `C0PR#EF` also makes the creatures in the protagonist's area reapply
it when the helper appears there. This helper path is read from the installed
scripts, not confirmed in a running game.

To refresh a sorcerer at once, open the console and let that character cast the
spell on themselves (replace `Player2` with the sorcerer's slot):

```lua
C:Eval('ActionOverride(Player2,ReallyForceSpellRES("C0PR#CL",Myself))')
```

The sorcerer must be the caster: the class grants set EEex's opcode 326 flag
that checks the caster's class instead of the target's. The spell clears and
then reapplies the class and pip weapon grants, so repeating it is harmless.
Afterwards a dagger, quarterstaff, dart or sling should fit into a weapon slot
without pips.

The clearing step also removes kit extras that separate Kitpack spells grant,
as every level-up does. For an Eldritch Knight or Arcane Trickster sorcerer,
reapply the kit's extra weapons the same way afterwards with `C0PR#EK` or
`C0PR#AT` in place of `C0PR#CL`.

Installer tests do not establish these in-game results.
