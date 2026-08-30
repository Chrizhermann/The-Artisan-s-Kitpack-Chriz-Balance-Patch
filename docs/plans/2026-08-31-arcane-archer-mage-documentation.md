# Arcane Archer/Mage Documentation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:executing-plans to implement this plan task-by-task.

**Goal:** Surface the kit's existing spell-slot penalty and finish a compact README ledger of fork changes.

**Architecture:** Preserve the installed mechanics. Update only the inline WeiDU help text and the root Markdown ledger.

**Tech Stack:** WeiDU TPA, Markdown, PowerShell verification

---

### Task 1: Document the existing behavior

**Files:**
- Modify: `ArtisansKitpack/lib/aamage.tpa:34-40`
- Modify: `README.md:27-47`

**Step 1: Run the documentation contract and verify RED**

Assert that the kit description contains `May cast one fewer spell per level per day.`,
that `Changes vs upstream` is the README's final section, and that it names Berserker,
Arcane Archer/Mage, and the Arcane Trickster fix. Expected: FAIL because those docs are
not present in their final form.

**Step 2: Make the minimal edits**

Add the established disadvantage sentence to `kit_description`. Move the existing
README ledger below the license, rename it `Changes vs upstream`, preserve the Berserker
entry, and add concise Arcane Archer/Mage and Arcane Trickster entries.

**Step 3: Verify GREEN and syntax**

Re-run the documentation contract, parse-check `aamage.tpa` and the core TP2 with the
bundled WeiDU binary, confirm `C0AAINN.SPL` still contains exactly one opcode 42
`parameter1=-1`, `parameter2=511` effect, and run `git diff --check`.

**Step 4: Commit**

```powershell
git add -- ArtisansKitpack/lib/aamage.tpa README.md
git commit -m "docs: explain Arcane Archer Mage spell slots"
```
