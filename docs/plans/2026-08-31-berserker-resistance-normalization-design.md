# Berserker Physical Resistance Normalization Design

**Date:** 2026-08-31
**Status:** Approved

## Goal

Give the Artisan's Kitpack Berserker rebalance the same In Extremis physical
resistance values with and without Spell Revisions:

| Wound tier | Base resistance | While Enraged |
|---|---:|---:|
| Below 76% HP | 3% | 6% |
| Below 50% HP | 6% | 12% |
| Below 26% HP | 10% | 20% |

The values remain available only from Berserker level 14 onward, apply equally
to slashing, crushing, piercing, and missile damage, and are tier totals rather
than cumulative bonuses.

## Production changes

Both installer paths will define `ie_r1`, `ie_r2`, and `ie_r3`
unconditionally as `3`, `6`, and `10`:

- `ArtisansKitpack/lib/Berserker.tpa` for clean component-1003 installs;
- `live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2` for the standalone
  retrofit component.

The Spell Revisions `MOD_IS_INSTALLED` branch will be removed. Existing
variable consumers remain unchanged, so the base opcode-86/87/88/89 effects,
the equal Enrage deltas, and generated kit descriptions all receive the
normalized values through the same delivery architecture.

The standalone retrofit component version will increase from `2.0` to `2.1`.

## Historical record

The retired branch used `4/8/15` base resistance (`8/16/30` while Enraged)
whenever Spell Revisions component 0 was present. Its rationale was that the
optional Revised Warrior HLAs component reduced Hardiness from 40% physical
resistance to 20% resistance to all damage types.

That policy is retired because Berserker kit balance should not vary with the
presence of an unrelated spell-overhaul component. Git history preserves the
exact former installer code; this document and the existing July rebalance
design preserve the rationale. No dormant or commented-out production branch
will remain.

## Documentation

The public README and present-tense portions of the July Berserker design will
describe the single `3/6/10` curve and `6/12/20` Enraged totals. Historical
sections may retain the former values only when explicitly labelled as
superseded.

## Verification

Implementation will follow a RED/GREEN cycle:

1. Add a dependency-free regression test covering both installer sources.
2. Confirm it fails because each source still contains the Spell Revisions
   check and two assignment sets.
3. Remove the checks and leave exactly one ordered `3/6/10` assignment set in
   each source.
4. Confirm the focused test and the complete repository test discovery pass.
5. Run WeiDU parse checks for both modified installer sources and audit the
   repository for active `4/8/15`, `8/16/30`, and Berserker-specific SR checks.

No command in this work changes the installed game or active saves. Updating
the live playthrough, if ever desired, is a separate explicitly authorized
operation.
