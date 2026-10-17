# Mystic Fire balance — deferred

User decision, September 28, 2026: revisit this in a later Artisan patch release.
This is a discussion item, not an approved nerf or a blocker for the upcoming
collection release. Keep the arcane-paladin fantasy and current kit defaults.

## Why revisit it

A player reports that Mystic Fire makes some mage fights too easy, especially
through Shatter Spell and unrestricted mage-scroll access. Treat that report as
a useful lead, not proof of the exact cause or a complete balance assessment.
Challenge-run chat reactions alone should not decide the kit's design.

## Source starting points

Checked against repository HEAD `b413295`; no live-game test was performed.

- Core kit **3002**, in `ArtisansKitpack/ArtisansKitpack.TP2`, includes
  `ArtisansKitpack/lib/MysticFire.tpa`. Its description grants a limited selection
  of mage spells alongside the paladin's spellcasting.
- `MysticFire.tpa` describes **Shatter Spell** as empowering the next attack
  within two rounds to remove the target's combat protections, plus a save vs.
  spells at -2 to avoid 100% spell failure for two rounds. It grants one daily
  use initially and additional uses every six levels. Its EEex-specific
  description says the effect bypasses weapon protections even when the attack
  itself is negated. These are source-described mechanics; confirm the installed
  spell delivery and current EEex behavior before changing them.
- **3202**, in `ArtisansKitpack_tweak/ArtisansKitpack_tweak.TP2`, is a separate
  optional component, **Allow Wands and Mage Scrolls**. It requires core 3002 and
  EEex and includes `ArtisansKitpack/lib/mystic_fire_items.tpa`. Do not conflate
  this broad item access with the core kit's limited spell list. Component
  **3302** is a different spellbook/HLA option.

## Later review

1. Check Shatter Spell's combined protection removal, weapon-protection bypass
   and spell failure against actual mage defenses in the default SCS/SR setup.
   Include the supported non-SR setup when choosing a solution.
2. Discuss which part should be reduced while preserving a distinct arcane
   paladin. A casting-time increase, narrower removal, changed bypass, or altered
   spell-failure effect are possibilities, not agreed changes. Casting time
   alone may not address the strength of the successful hit.
3. Assess component 3202 separately. Limiting scroll schools or changing its
   collection default would require a new user decision; neither is approved.
4. Once a design is chosen, keep descriptions aligned with implementation and
   define focused acceptance checks. Existing-save support or hotpatch delivery
   must be assessed then, not promised by this note.

No implementation, default-selection change, release or live-game action is
authorized by this deferred plan. Warlock investigation and balancing are also
explicitly deferred and are outside this task.
