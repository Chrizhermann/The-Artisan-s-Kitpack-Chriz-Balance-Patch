# Live-install tail patches

WeiDU mini-mods that retrofit this fork's balance changes onto an
**already-installed** upstream Artisan's Kitpack, so they can be appended at the
tail of a live install's WeiDU stack without uninstalling anything (the
never-uninstall rule for the main EET install).

Fresh installs don't need these — install the fork itself instead; the fork's
`lib/*.tpa` produce the same end state.

## AKCB_BERSERKER

Berserker Overhaul rebalance (see
`docs/plans/2026-07-05-berserker-rebalance-design.md` for the full spec and
rationale). Requires AK component 1003 installed.

Install (from the game dir, after copying the `AKCB_BERSERKER` folder there and
creating `Setup-AKCB_BERSERKER.exe` as a copy of any WeiDU v24900 setup exe):

```
./Setup-AKCB_BERSERKER.exe --force-install-list 0 --language 0 --no-exit-pause
```

Post-install, for each existing Berserker party member (once, in-game, fully
restarted client):

```
C:Eval('ReallyForceSpellRES("AKCBRFRM",Player1)')
```

(unquoted `Player1`; substitute the right PlayerN) — removes the deleted
Reckless Frenzy innate AND (v1.2) swaps the save-baked permanent passive for
the trimmed one (fear/morale immunity moves into Enrage; the −4 thrown-mode
penalty arrives). Safe to re-run; **run it again after upgrading from
v1.0/v1.1**. Everything else self-applies: In Extremis tiers within one round,
Enrage on its next cast, the ranged-weapon ban on load (unequip any bow/sling
first — it becomes unusable), Hardiness at the next HLA level-up.

**v2.0** (In Extremis rebuilt — THAC0 penalty, damage/resistance double while
Enraged, resistance regated to L14, APR at the L1 base) needs **no additional
console step**: the tier spells are re-cast from files every round, so the new
values, the rage-scaling op326 branch and the level gates all take effect on the
next load. Only run `AKCBRFRM` if you haven't already for v1.2.
