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
  missing-HP damage ladder removed; Enrage grants stun/sleep/hold/charm/
  confusion/feeblemind immunity while raging; In Extremis gains scaling
  physical resistance (+5/+10/+15% on Spell Revisions installs, +5/+8/+10%
  vanilla) with softened AC penalties (−2/−3/−4) and a trimmed tier-3 offense
  (+6); Reckless Frenzy deleted; Hardiness restored to the HLA table; tier-3
  save-bonus bug (+10 → +8) fixed. A tail-installable retrofit for live games
  lives in `live-patch/AKCB_BERSERKER`.

## License / usage

Follow the upstream project's terms. This fork inherits them — any
redistribution should credit Artemius_I first and link to the current
website above.
