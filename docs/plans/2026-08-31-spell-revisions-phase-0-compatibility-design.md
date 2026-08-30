# Spell Revisions Compatibility Phase 0 Design

## Goal

Prevent known-broken Artisan's Kitpack and Bardic Wonders components from
entering recommended Spell Revisions installations while the underlying code
is redesigned and tested properly.

## Confirmed boundary

Favored Soul component `30001` is the cause of the traced global priest
spellbook failure. Its installer scans ordinary `SPPR` resources, hides them,
and replaces native Cleric, Druid, Paladin, and Ranger delivery with generated
CLAB rows. Spell Revisions and later spell/progression mods can invalidate that
snapshot. Omitting Favored Soul from a clean install avoids this global
Ranger/Cleric delivery failure.

That boundary does not mean every interaction between these mods is safe.
The audit also confirmed component-local fixed-resource failures:

| Mod | Component | Confirmed issue | Phase 0 recommendation |
|---|---:|---|---|
| Artisan's Kitpack | `30001` Favored Soul | Replaces global priest delivery using stale/misclassified spell metadata | Omit from all recommended installations for now |
| Artisan's Kitpack | `8101` / `8102` Pale Master spell choices | Copies physical `SPPRxxx` slots whose meanings change under Spell Revisions | Omit on Spell Revisions installations |
| Artisan's Kitpack NPC | `5102` Red Wizard Edwin | Removes `SPWI106`, which Spell Revisions uses for permitted Conjuration spell Obscuring Mist | Omit on Spell Revisions installations |
| Artisan's Kitpack NPC | `10004` Sacred Fist Rasaad | Adds obsolete/disabled Spell Revisions priest resources and relies on a later cleanup pass | Omit on Spell Revisions installations pending a source fix |
| Bardic Wonders | `1006` Darkbloom | Copies fixed priest slots and receives the wrong spells under Spell Revisions | Omit on Spell Revisions installations |

The base Pale Master kit (`8001`) is not excluded by this policy; only its two
optional priest-spell subcomponents are.

## Phase 0 implementation

Phase 0 changes documentation only:

1. Add a prominent compatibility warning beside the Artisan's Kitpack
   installation instructions.
2. List the exact components recommended collections must omit.
3. Explain that removing Favored Soul from an established stack is not
   equivalent to never installing it; use a clean rebuild or correctly
   reinstall all later components.
4. Add a corresponding Darkbloom warning to the Bardic Wonders balance-patch
   README.
5. Record the deferred implementation work in both READMEs so it remains
   visible until completed.

No TP2, SPL, CLAB, HIDESPL, Lua, collection manifest, or installed-game file is
changed in Phase 0.

## Deferred implementation work

### Artisan's Kitpack

- Redesign Favored Soul as a kit-specific spell-choice registry. Native priest
  delivery must remain authoritative; the component must not globally hide
  normal priest spells or re-grant them through base/custom kit CLABs.
- Resolve Spell Revisions spell identities semantically through current
  `SPELL.IDS` symbols/effective resources rather than assuming physical
  `SPPRxxx` filenames.
- Classify priest membership from the complete short at SPL offset `0x20`,
  accepting only exact `0x0000`, `0x4000`, and `0x8000` values. Never mutate a
  spell header to exclude an HLA or disabled resource.
- Rework Pale Master spell imports to resolve the intended spell or use the
  bundled fallback when the symbol is unavailable.
- Make Red Wizard and Sacred Fist NPC spellbook edits operate on semantic
  school/spell identity and test them with SR's final spellbook fixer.
- Add install/uninstall fixtures covering vanilla, Spell Revisions, later
  divine spell packs, ranger-table changes, multiclasses, and existing/custom
  kits.

### Bardic Wonders

- Replace Darkbloom's fixed-slot imports with semantic spell resolution and
  validated bundled fallbacks.
- Audit the other fixed `SPPRxxx` clones in New Bard Spells, Troubadour, and
  Deathsinger under both vanilla and Spell Revisions.
- Make New Bard Spells/Gallant integration independent of component order.
- Add install/uninstall fixtures that assert the resulting spell names,
  mechanics, type, level, and class availability.

## Verification

- Both README warnings must name the exact component numbers.
- The warnings must distinguish global Favored Soul corruption from
  component-local wrong-spell bugs.
- The READMEs must state that implementation fixes are deferred.
- `git diff --check` must pass in both repositories.
- Only documentation paths may be staged and committed; unrelated existing
  Bardic Wonders changes must remain untouched.
