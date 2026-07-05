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

## Balance changes vs upstream

- **Berserker Overhaul (component 1003)** — reworked 2026-07-05, full spec in
  `docs/plans/2026-07-05-berserker-rebalance-design.md`: Enrage HP drain and
  missing-HP damage ladder removed; Enrage grants stun/sleep/hold/charm/fear/
  morale-failure immunity while raging (v1.2 — confusion/feeblemind dropped,
  fear/morale moved into the rage from the permanent passive); In Extremis
  offense rescaled to +1/+2/+4 (v1.2) with scaling physical resistance
  (+5/+10/+15% on Spell Revisions installs, +5/+8/+10% vanilla) and softened
  AC penalties (−2/−3/−4); level riders rescaled in v1.1 (movement/saves
  +1/+2/+4, APR —/+½/+1, luck —/+1/+2); ranged weapons banned outright with a
  Cavalier-style −4 thrown-mode penalty (v1.2); Reckless Frenzy deleted;
  Hardiness restored to the HLA table; the upstream tier-3 save-bonus header
  bug fixed. A tail-installable retrofit for live games lives in
  `live-patch/AKCB_BERSERKER`.

## License / usage

Follow the upstream project's terms. This fork inherits them — any
redistribution should credit Artemius_I first and link to the current
website above.
