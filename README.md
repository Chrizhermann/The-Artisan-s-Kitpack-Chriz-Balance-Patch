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

Then select the components you want.

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
  **In Extremis, rebuilt in v2.0:** to-hit becomes a *penalty* that deepens with your
  wounds (−1/−2/−4), melee damage +1/+2/+4 and physical resistance both **double
  while Enraged**; APR (—/+½/+1) sits in the level-1 base; physical resistance is
  gated to level 14 (dual-class-proof) — SR installs 4/8/15% → 8/16/30% enraged,
  vanilla 3/6/10% → 6/12/20%. Rage scaling is delivered by an opcode-326 branch that
  checks `STATE_ENRAGED` each round. A tail-installable retrofit for live games lives
  in `live-patch/AKCB_BERSERKER`.

- **Arcane Archer / Mage (component 1001)** — already receives one fewer Mage spell
  slot at every spell level; its description now makes that explicit.

- **Arcane Trickster (components 20001 and 8004)** — Stealth Caster correctly
  recognizes Improved Invisibility for both the Mage / Thief and Sorcerer variants.
