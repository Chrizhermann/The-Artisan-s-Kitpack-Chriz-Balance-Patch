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
Reckless Frenzy innate from the character. Everything else self-applies:
In Extremis tiers within one round, Enrage on its next cast, Hardiness at the
next HLA level-up.
