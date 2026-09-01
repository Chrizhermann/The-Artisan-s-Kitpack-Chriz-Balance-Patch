# The Artisan's Kitpack — Chriz Balance Patch

A personal balance-patch fork of **The Artisan's Kitpack** by **Artemius_I** (also known as **The Artisan** / **AionZ**). All kits, art, design, and mod architecture are the original author's work; this fork only adds balance tweaks and bug fixes on top of upstream.

## Credit & original author

The Artisan's Kitpack is designed and maintained by **Artemius_I**. If you enjoy the kits, please support him directly:

- **Website:** https://theartisanbg.github.io/The-Artisans-Corner/
- **Upstream repository:** https://github.com/TheArtisanBG/The-Artisan-s-Kitpack
- **Patreon:** https://www.patreon.com/Artemius_I
- **Discord:** https://discord.gg/MWraGyf

This fork exists strictly because I wanted a few balance knobs turned differently in my own install — it is not a replacement for, or a competing project against, the upstream mod.

## Installation

Same as upstream. Drop the mod folder into your BG2:EE / EET install and
run the relevant setup executable:

- `Setup-ArtisansKitpack.exe` — core kits
- `Setup-ArtisansKitpack_tweak.exe` — tweaks
- `Setup-ArtisansKitpack_npc.exe` — NPC kits

> [!WARNING]
> **SPELL REVISIONS COMPATIBILITY — PHASE 0**
>
> **Do not include Favored Soul (component `30001`) in recommended installs or
> mod collections for now.** Its current installer globally hides and
> re-delivers ordinary priest spells through generated CLAB files. With Spell
> Revisions—and especially with later divine-spell or ranger-progression
> components—that snapshot can corrupt Cleric, Druid, Paladin, Ranger, and
> multiclass spellbooks. Omitting Favored Soul from a clean install avoids the
> traced Ranger/Cleric delivery failure.
>
> Uninstalling Favored Soul in the middle of an established stack is not the
> same as never installing it. Use a clean rebuild or allow WeiDU to reinstall
> every later component from the restored state.

For recommended **Spell Revisions** installations, currently omit these exact
components:

| Installer | Component | Reason |
|---|---:|---|
| `Setup-ArtisansKitpack.exe` | `30001` Favored Soul | Globally replaces native priest spell delivery using install-time metadata. |
| `Setup-ArtisansKitpack.exe` | `8101` / `8102` Pale Master spell choices | Copies fixed `SPPRxxx` slots that contain different spells under SR. The base Pale Master kit (`8001`) is not excluded. |
| `Setup-ArtisansKitpack_npc.exe` | `5102` Red Wizard Edwin | Removes a fixed wizard slot that SR uses for the permitted Conjuration spell Obscuring Mist. |
| `Setup-ArtisansKitpack_npc.exe` | `10004` Sacred Fist Rasaad | Adds obsolete/disabled SR priest resources and relies on a later spellbook cleanup pass. |

Then select the components you want.

### Deferred compatibility fixes

Phase 0 is documentation policy, not a code-level compatibility fix. The
deferred work is recorded in the
[Spell Revisions compatibility design](docs/plans/2026-08-31-spell-revisions-phase-0-compatibility-design.md)
and includes:

- rebuilding Favored Soul as a kit-specific choice registry that leaves native
  priest delivery, `HIDESPL.2DA`, and ordinary class/kit CLABs alone;
- resolving intended spells through current semantic `SPELL.IDS` identities
  instead of physical `SPPRxxx` filenames;
- repairing the Pale Master, Red Wizard Edwin, and Sacred Fist Rasaad
  component-local assumptions; and
- adding vanilla/SR install-and-uninstall fixtures before any component is
  declared compatible again.

## License / usage

Follow the upstream project's terms. This fork inherits them — any
redistribution should credit Artemius_I first and link to the current
website above.

## Changes vs upstream

- **Berserker Overhaul (component 1003)** — reworked 2026-07-05, full spec in
  `docs/plans/2026-07-05-berserker-rebalance-design.md`. Highlights: all self-harm
  removed (Enrage HP drain + missing-HP damage ladder deleted, Reckless Frenzy
  deleted); Enrage grants stun/sleep/hold/charm/fear/morale-failure immunity while
  raging; ranged weapons banned outright with a Cavalier-style −4 thrown-mode
  penalty; Hardiness restored to the HLA table.
  **In Extremis, rebuilt in v2.0 and resistance-normalized in v2.1:** to-hit
  becomes a *penalty* that deepens with your wounds (−1/−2/−4), melee damage
  +1/+2/+4 and physical resistance both **double while Enraged**; APR
  (—/+½/+1) sits in the level-1 base. Physical resistance is delivered through
  the L14+ tier-spell headers and applies equally to slashing, crushing,
  piercing, and missile damage: the three wound tiers give base **totals** of 3/6/10%,
  doubling to Enraged **totals** of 6/12/20% on every install. These are tier
  totals, not cumulative bonuses across thresholds. Rage scaling is delivered
  by an opcode-326 branch that checks `STATE_ENRAGED` each round. A
  tail-installable retrofit for live games lives in `live-patch/AKCB_BERSERKER`.

- **Shapeshifter Overhaul custom sprites (components 5110/5111)** — the four
  greater-werewolf animation templates now use the humanoid pathfinding
  footprint (`personal_space=3` instead of 5), allowing the form to pass
  through standard doors without changing its sprite scale, selection circle,
  or movement speed. Existing installs can use the reversible semantic retrofit
  in `live-patch/AKCB_SHAPESHIFTER`.

- **Arcane Archer / Mage (component 1001)** — already receives one fewer Mage spell
  slot at every spell level; its description now makes that explicit.

- **Arcane Trickster (components 20001 and 8004)** — Stealth Caster correctly
  recognizes Improved Invisibility for both the Mage / Thief and Sorcerer variants.
