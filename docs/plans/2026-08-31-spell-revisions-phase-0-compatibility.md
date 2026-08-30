# Spell Revisions Compatibility Phase 0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:executing-plans to implement this plan task-by-task.

**Goal:** Publish precise README warnings that keep confirmed-broken components out of recommended Spell Revisions installations and preserve the deferred repair backlog.

**Architecture:** This phase changes documentation only. The Artisan's Kitpack README owns the global priest-delivery warning and its component-local exclusions; the Bardic Wonders README owns its Darkbloom warning. Each repository receives a path-limited commit so unrelated Bardic Wonders work remains unstaged.

**Tech Stack:** Markdown, Git, PowerShell, ripgrep

---

### Task 1: Document Artisan's Kitpack exclusions

**Files:**
- Modify: `README.md`
- Reference: `docs/plans/2026-08-31-spell-revisions-phase-0-compatibility-design.md`

**Step 1: Add the installation warning**

Immediately after the setup executable list, add a GitHub warning callout that
states:

- Favored Soul `30001` is not recommended on any current installation.
- On Spell Revisions installations, omit Pale Master spell choices `8101` and
  `8102`, Red Wizard Edwin `5102`, and Sacred Fist Rasaad `10004`.
- The base Pale Master kit `8001` is not excluded.
- Removing Favored Soul from an established stack requires a clean rebuild or
  correct reinstallation of later components.

**Step 2: Add the deferred-fixes checklist**

Record semantic resource resolution, Favored Soul's non-invasive redesign,
NPC spellbook fixes, and compatibility fixtures as deferred implementation
work. Link to the Phase 0 design document for the full backlog.

**Step 3: Verify the README**

Run:

```powershell
rg -n "30001|8101|8102|5102|10004|Deferred compatibility fixes" README.md
git diff --check
git diff -- README.md
```

Expected: all component numbers and the deferred heading are present; diff
check exits `0`; only the intended README content is shown.

**Step 4: Commit**

```powershell
git add -- README.md docs/plans/2026-08-31-spell-revisions-phase-0-compatibility.md docs/plans/2026-08-31-spell-revisions-phase-0-compatibility.md.tasks.json
git commit -m "docs: warn about Spell Revisions component conflicts"
```

### Task 2: Document Bardic Wonders Darkbloom exclusion

**Files:**
- Modify: `C:\src\private\Bardic-Wonders-Chriz-Balance-Patch\README.md`

**Step 1: Reconfirm the dirty-worktree boundary**

Run:

```powershell
git status --short
```

Expected: the pre-existing Abettor, song, test, documentation, and tool work is
still visible. Do not stage or modify it.

**Step 2: Add the Darkbloom warning**

Add a GitHub warning callout stating that Spell Revisions collections should
omit Darkbloom `1006` because its fixed `SPPRxxx` imports resolve to the wrong
spells. State that this is kit-local and distinct from Favored Soul's global
priest delivery bug.

**Step 3: Preserve the deferred backlog**

Record semantic Darkbloom imports, audit of other priest-spell clones, Gallant
order independence, and vanilla/SR fixtures as deferred work.

**Step 4: Verify and commit only README.md**

Run:

```powershell
rg -n "1006|Darkbloom|Deferred compatibility fixes" README.md
git diff --check -- README.md
git diff -- README.md
git add -- README.md
git diff --cached --name-status
git commit -m "docs: warn about Darkbloom Spell Revisions conflict"
```

Expected: the staged path list contains only `README.md`; all pre-existing
changes remain unstaged after the commit.

### Task 3: Cross-repository verification

**Files:**
- Verify: `README.md`
- Verify: `C:\src\private\Bardic-Wonders-Chriz-Balance-Patch\README.md`

**Step 1: Verify exact warning coverage**

Run the component-number searches from Tasks 1 and 2 again from each
repository. Read the rendered Markdown structure for heading/callout/list
clarity.

**Step 2: Verify repository state**

Run in both repositories:

```powershell
git status --short --branch
git log -2 --oneline
```

Expected: the Artisan's Kitpack task branch is clean with the design and Phase
0 documentation commits. Bardic Wonders retains only its pre-existing unrelated
working-tree changes and has one new README-only commit.

**Step 3: Report deferred scope accurately**

Report that Phase 0 is documentation policy, not a compatibility code fix, and
name every component excluded from recommended Spell Revisions collections.
