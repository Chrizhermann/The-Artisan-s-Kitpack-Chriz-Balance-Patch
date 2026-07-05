# Berserker Overhaul — Rebalance Design Spec

**Status:** APPROVED (all balance decisions signed off by Chris, 2026-07-05).
**Fork:** The Artisan's Kitpack — Chriz Balance Patch.
**Scope:** component 1003 (`lib/Berserker.tpa`) + a live-install tail patch (`live-patch/AKCB_BERSERKER`) for the running EET game.

---

## 1. Problem statement

Artisan's Berserker Overhaul is a "wants to be at low HP" kit. On high difficulty
(SCS) that premise fails structurally:

1. The kit only turns on below 75/50/25% HP — exactly the window where SCS AI
   focus-fires wounded targets and where Power Word: Kill (< 60 HP, no save),
   Power Word: Stun and Finger of Death finish you.
2. In Extremis *increases* the AC penalty as HP falls (−2/−4/−6) — a death spiral.
3. Enrage drains 1 HP/second (up to 10–20 rounds), actively pushing the player
   into the kill zone during their own buff.
4. Enrage has **zero** status immunities — the vanilla kit's entire defensive
   identity (charm/confusion/hold/sleep/stun/feeblemind/…) was removed.
5. Hardiness was removed from the HLA table (replaced by the auto-granted
   Extend Rage), so the kit has no late-game physical mitigation at all.

## 2. Verified current mechanics (installed v6.0 == upstream master, traced 2026-07-05)

- **In Extremis** (`AP_C0BER#1X/2X/3X` → op272 permanent → op232 HPPercentLT
  76/50/26 → `c0ber#01/02/03`, re-cast ~every round, 12 s effects, 5 ability
  headers at min-level 1/7/10/14/20):
  op284 melee THAC0 +2/+4/+8; op73 damage +2/+4/+8 (op286 −2/−4/−8 cancels it
  for ranged); op0 AC −2/−4/−6; L7+ op126 move +2/+4/+8; L10+ op325 saves
  +2/+4/+8 (**bug:** tier 3 L10 header has +10); L14+ op1 APR +½/+1/+2;
  L20+ op22 luck +1/+3/+5; op206 blocks the matching Reckless Frenzy sub-spell.
- **Enrage** (`c0ber#00`, GA at 1 + every 4 levels): 2 rounds; melee hits refresh
  to 1 round via op248→`c0ber#09`; hard cap via `c0ber#08` (60 s) or `c0ber#h2`
  (120 s, unlocked by auto-HLA `AP_C0BER#H1` via op318 switches on `c0ber#i1`);
  +15 max HP (op18); **1 HP/s drain** (`c0ber#04` op17 −1 self-loop, floored at
  1 HP by op318 + splprot `C0CURHP` row); spellcasting disabled (op145×2,
  op144×4); **damage ladder** = 20 EFF/SPL pairs `c0ber#60–#6J` (op232 rungs at
  every ~5% missing HP, each +5% slashing/piercing/crushing via op332×3, max
  +100% at 1 HP); Winded (`c0ber#0x`, 5 rounds, −2 AC/melee THAC0/melee damage,
  blocks re-rage + all tiers) fires only when the full cap expires.
- **Reckless Frenzy** (`c0ber#05`, GA at 4): op214 menu → sets current HP to
  70/45/20% of max (op12 stunning "set to percentage", non-lethal).
- **Passive** (`c0ber#07`, AP at 1): permanent immunity to fear/morale/berserk
  (op101 vs 3/23/24/106 + morale lock); dwarves retitled "Battlerager".
- **HLA:** `luabbr` → `luFi1.2da` (SCS #4250 renamed AK's `LUC0BER.2DA`;
  contents identical): **GA_SPCL907 Hardiness removed**, `AP_C0BER#H1` added.

## 3. Approved design

### 3.1 In Extremis (rework)

| HP threshold | Melee THAC0/dmg | AC | Physical resist (all 4 types) SR / vanilla |
|---|---|---|---|
| < 76% | +2 (unchanged) | −2 (unchanged) | **+5% / +5%** |
| < 50% | +4 (unchanged) | **−3** (was −4) | **+10% / +8%** |
| < 26% | **+6** (was +8) | **−4** (was −6) | **+15% / +10%** |

- Riders unchanged: L7+ movement +2/+4/+8, L10+ saves +2/+4/+8, L14+ APR
  +½/+1/+2, L20+ luck +1/+3/+5.
- **Bugfix:** tier-3 op325 save bonus normalized to +8 in ALL headers (upstream
  has +10 in the L10 header).
- Resist = opcodes 86/87/88/89 (slashing/crushing/piercing/missile), cumulative
  (param2=0), added to **all 5 ability headers** of each tier spell, same
  12 s/timing-0 profile as the existing tier effects (cloned from the op73
  block so target/duration/dispel flags match exactly).
- op206 blocks of `C0BER#5A/5B/5C` deleted (Reckless Frenzy is gone).

**SR gate:** `MOD_IS_INSTALLED` Spell Revisions main component (#0). SR nerfs
Hardiness 40%-physical → 20%-all-types, so the kit may carry more of its own
physical mitigation there.

Stacking math (worst realistic tank axis, slash/pierce/crush):
- SR install: DoE 20 + Hardiness 20 + tier-3 15 = **55%** (crushing with
  Roranach's Horn: 105%, only while < 26% HP with an HLA burning).
- Vanilla gated: DoE 20 + Hardiness 40 + tier-3 10 = **70%**. Vanilla's
  DoE+Roranach+Hardiness = 110% crushing exists *without any kit help* —
  pre-existing, not a regression. Physical resistance > 100% does not heal in
  the EE engine (floors at immunity).

### 3.2 Enrage (rework)

**Removed:**
- The 1 HP/s drain: `c0ber#08`/`c0ber#h2` no longer cast `c0ber#04`.
  (`c0ber#04`, the splprot `C0CURHP` row, and the op321 cleanup references stay
  in place as harmless orphans/no-ops.)
- The entire damage ladder: 20× op177 removed from `c0ber#00` and `c0ber#09`,
  20× op272 removed from `c0ber#08`/`c0ber#h2`; the `c0ber#6*` clone loops are
  dropped from the installer. Decision: **deleted, not trimmed** — the kit's
  damage scaling now lives entirely in In Extremis.

**Added — status immunities while raging** (in the 12 s package of `c0ber#00`
AND the 6 s refresh package of `c0ber#09`, mirroring the installed vanilla
`spcl321` implementation, which is EE-Fixpack/SCS-hardened):

| Category | op101 immunity vs opcodes | Extras (mirrored from spcl321, granted categories only) |
|---|---|---|
| Stun | 45, 210 (Stun 90HP = Power Word: Stun) | op267 strrefs 14043/1280, op169 icon 55 |
| Sleep | 39, 217 (Unconsciousness 20HP) | op267 14001, op169 icons 14/130 |
| Hold/Paralysis | 175, 109 | — (spcl321 has no hold icon/string extras) |
| Charm | 5 | op296 spnwchrm/spmindat/spflayer, op267 8364/14780/14672, op169 icons 0/1/43 |
| Confusion | 128 | op296 spconfus, op267 14791/14782, op169 icons 2/3/47 |
| Feeblemind | 76 | op296 cdfeeble, op169 icon 48 |

- SCS *detectable-spells* op328 states set alongside (verified against
  `splstate.ids` + SCS's ssl/libdata consumption): 128 STUN_IMMUNITY,
  127 SLEEP_IMMUNITY, 131 HOLD_IMMUNITY, 119 CHARM_IMMUNITY,
  130 CONFUSION_IMMUNITY, 137 FEEBLEMIND_IMMUNITY — needed because SCS's DS
  scan ran at SCS install time and never sees tail-added op101s.
- op169 icon prevention is required because a blocked disabler's separate
  op142 portrait-icon effect is not stopped by op101 immunity to the disabler
  opcode; icon IDs resolved from `statdesc.2da`.
- spcl321's level-drain display-string suppressions (41495/40968/40969/40979/
  41616) are deliberately NOT copied — no drain immunity is granted, so drain
  feedback must stay visible (verifier catch, 2026-07-05).
- **Deliberately NOT immune:** maze (213), imprisonment (211), level drain
  (216), fear (24 — already permanent via `c0ber#07`), Power Word: Kill.
  SCS casters keep planar removal as a counter.

**Kept unchanged:** +15 max HP, spellcasting lock, 2-round base duration,
melee-hit refresh, 10/20-round caps + Extend Rage HLA switch, Winded.

### 3.3 Reckless Frenzy — DELETED

- `GA_C0BER#05` removed from the CLAB (level 4 grant gone).
- `c0ber#05/5a/5b/5c` + `c0ber#05.2da` remain as orphan files (Artisan's own
  style, cf. `c0ber#06`); the description paragraph is removed.
- Live playthrough: the already-granted innate is stripped with a shipped
  cleanup spell (op172 Remove Innate — removes known + memorized), run once
  from the console.

### 3.4 HLA table

- `GA_SPCL907` (Hardiness) **restored** (fork: drop the `patch_remove_hla`
  call; live: write the LUFI0-row-10 values into the FIRST all-asterisk
  placeholder row of `luFi1.2da` and the orphaned `LUC0BER.2DA` — matching how
  every proven HLA-adder works; a row appended after placeholder rows has no
  engine-verified precedent).
- `AP_C0BER#H1` (Extend Rage) kept.

### 3.5 Text

- Kit description rewritten (new In Extremis table incl. resist values —
  install-time variables, Enrage immunity list, Reckless Frenzy paragraph
  removed). (The installed strref turned out to be clean UTF-8 already — the
  earlier "cp1252 mojibake" observation was an extraction artifact; the rewrite
  is justified by the content changes alone.)
- Enrage ability description (`SAY UNIDENTIFIED_DESC` on `c0ber#00`) updated to
  match.
- CLAB Enrage-use levels: the **fork** normalizes to exactly every 4 levels
  (1,5,…,49 = 13 uses); the **live patch** keeps the installed grid
  (1,5,9,13,17,20,25,29,33,37,43,47 = 12 uses) — ACCEPTED divergence, only
  levels 20/21 and 41+ differ, not worth surgical 2DA column moves on the live
  file.

## 4. Implementation architecture

- **Fork (fresh installs):** all changes in `lib/Berserker.tpa` as post-COPY
  patch code (ALTER_EFFECT/DELETE_EFFECT/CLONE_EFFECT/ADD_SPELL_EFFECT) — no
  source-binary edits, so upstream merges stay clean.
- **Live install (this playthrough):** `live-patch/AKCB_BERSERKER` standalone
  WeiDU mod, tail-installed (never uninstall anything). Patches the *installed*
  override copies to the same end state; surgical CLAB edit preserves the
  `GA_C0FIG01`/`AP_C0FIG03` rows added by AK's Fighter overhaul; description
  updated via the same `GET_KIT_STRREF` + `STRING_SET_EVALUATE` mechanism AK
  uses.
- **Why no save surgery is needed:** the tiers are re-cast every round from the
  spell files (op272 permanents reference `.eff`/`.spl` by resref), Enrage
  reads its files on each cast, and the CLAB/HLA tables are only consulted at
  level-up. The one exception is removing the already-granted Reckless Frenzy
  innate (console one-liner, see §5).
- **Shared-resource check (DONE, 2026-07-05):** Minsc's Rashemi Berserker
  Ranger CLAB (`c0tbm.2da`) contains **no** `c0ber#` references (its rage is the
  GA_SPIN117 family) — the rework does not affect Minsc. Imoen's Trickster
  "Mimic: Enrage" (`C0TR#10A`, op171 → `c0ber#00`) grants the innate by resref
  and therefore picks up the rebalanced Enrage automatically (desired).
- **WeiDU wart for maintainers:** the built-in `ALTER_EFFECT` gates every field
  write on `parameter1 >= 0`, silently no-opping negative values — and WeiDU PE
  integers are 32-bit, so the unsigned-dword workaround (`0xFFFFFFFD`)
  re-evaluates to −3 and is ALSO skipped (empirically confirmed on the first
  install attempt: op0 stayed −4/−6). Negative writes therefore go through the
  custom `akcb_alter_p1_signed` patch function (direct header-walk +
  `WRITE_LONG`), defined in both implementations.

## 5. Applying to the running game (Kool Koveras, save `000000423-Gaming`)

1. Install `AKCB_BERSERKER` at the tail of the WeiDU stack.
2. Fully quit and relaunch the game (2DA caching).
3. In-game once, on the loaded save, console:
   `C:Eval('ReallyForceSpellRES("AKCBRFRM",Player1)')`
   (**unquoted** `Player1` — quoted protagonist references silently fail;
   `ReallyForceSpellRES`, not `ApplySpellRES`, which silently fails for
   override SPLs per the verified gotcha) — strips the Reckless Frenzy innate
   (op172 removes known + memorized).
4. Everything else self-applies: tier changes within one round, Enrage on next
   cast, Hardiness at the next HLA level-up (he is L6).

## 6. Test checklist (in-game, post-install)

- [ ] Kit description shows new text, clean bullets, correct resist numbers.
- [ ] Damage character below 75/50/25%: tier icons appear, AC −2/−3/−4
      (verify the −3/−4 specifically — they use the unsigned-dword write trick),
      resistances +5/+10/+15% visible on record screen.
- [ ] Tier 3 offense is +6, saves +8.
- [ ] Enrage: no HP tick-down; hold/stun/charm/confusion/sleep/feeblemind fail
      against the raging berserker (PW:Stun too); still vulnerable when not raging.
- [ ] Enrage refresh on melee hit + Winded after full cap still work.
- [ ] Reckless Frenzy gone from the innate bar after the console line.
- [ ] Hardiness appears in HLA choices at fighter level 15+ (test via
      `C:SetCurrentXP` on a throwaway save if desired) — HARD GATE: this
      verifies the first-empty-row HLA table write.
- [ ] Imoen's Trickster "Mimic: Enrage" still works and shows the reworked
      behavior (no HP drain).
