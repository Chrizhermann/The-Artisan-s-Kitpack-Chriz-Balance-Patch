# Berserker Physical Resistance Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:executing-plans to implement this plan task-by-task.

**Goal:** Make the Berserker's In Extremis physical resistance use the same `3/6/10` base curve and `6/12/20` Enraged totals on every install, independent of Spell Revisions.

**Architecture:** Keep the existing `ie_r1/ie_r2/ie_r3` variable seam and every downstream opcode-86/87/88/89 and opcode-326 consumer. Replace the duplicated SR/non-SR configuration branches with one unconditional assignment set in both the clean installer and standalone retrofit, then update the public/current documentation while preserving the retired rationale as history.

**Tech Stack:** WeiDU TPA/TP2, Python standard-library `unittest`, Markdown, PowerShell, Git

---

### Task 1: Add the normalization regression test

**Files:**
- Create: `tests/test_berserker_resistance_values.py`
- Test: `tests/test_berserker_resistance_values.py`

**Step 1: Write the failing test**

Create a dependency-free test that reads both production installer sources and
asserts their complete executable resistance assignment list and absence of the
retired SR gate:

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "ArtisansKitpack/lib/Berserker.tpa",
    ROOT / "live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2",
)
ASSIGNMENT_RE = re.compile(
    r"^\s*OUTER_SET\s+ie_r([123])\s*=\s*(\d+)\s*$", re.MULTILINE
)
SR_GATE_RE = re.compile(
    r'MOD_IS_INSTALLED\s+["~]spell_rev/setup-spell_rev\.tp2["~]\s+0',
    re.IGNORECASE,
)


class BerserkerResistanceNormalizationTest(unittest.TestCase):
    def test_both_installers_use_one_unconditional_vanilla_curve(self):
        expected = [("1", "3"), ("2", "6"), ("3", "10")]
        for source in SOURCES:
            with self.subTest(source=source.relative_to(ROOT)):
                text = source.read_text(encoding="utf-8")
                self.assertEqual(ASSIGNMENT_RE.findall(text), expected)
                self.assertIsNone(SR_GATE_RE.search(text))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run the test to verify RED**

Run:

```powershell
python -m unittest tests.test_berserker_resistance_values -v
```

Expected: FAIL for both subtests because each source still has six assignments
beginning with `4/8/15` and contains the SR gate.

**Step 3: Commit the RED test**

```powershell
git add -- tests/test_berserker_resistance_values.py
git commit -m "test: require normalized Berserker resistance"
```

### Task 2: Normalize both installer paths

**Files:**
- Modify: `ArtisansKitpack/lib/Berserker.tpa:32-47`
- Modify: `live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2:14-39`
- Test: `tests/test_berserker_resistance_values.py`

**Step 1: Replace the fresh-install branch**

Replace the SR-specific comment and `ACTION_IF` block with:

```weidu
// CHRIZ BALANCE: In Extremis physical resistance uses one normalized curve on
// every install. v2.1: base per-tier resistance doubles while Enraged through
// an equal-magnitude op326 delta and remains gated to L14+ (see below).
//   base 3/6/10   enraged 6/12/20
OUTER_SET ie_r1 = 3
OUTER_SET ie_r2 = 6
OUTER_SET ie_r3 = 10
```

**Step 2: Replace the standalone retrofit branch and bump its version**

Change `VERSION ~2.0~` to `VERSION ~2.1~`, then use the same unconditional
assignment block in the standalone TP2.

**Step 3: Run the focused test to verify GREEN**

Run:

```powershell
python -m unittest tests.test_berserker_resistance_values -v
```

Expected: PASS.

**Step 4: Commit the production change**

```powershell
git add -- ArtisansKitpack/lib/Berserker.tpa live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2
git commit -m "fix: normalize Berserker physical resistance"
```

### Task 3: Update public and historical documentation

**Files:**
- Modify: `README.md:76-82`
- Modify: `docs/plans/2026-07-05-berserker-rebalance-design.md:56-96`
- Modify: `docs/plans/2026-07-05-berserker-rebalance-design.md:298-309`
- Modify: `docs/plans/2026-07-05-berserker-rebalance-design.md:367-375`
- Modify: `docs/plans/2026-07-05-berserker-rebalance-design.md:405-408`

**Step 1: Update the README**

Replace the SR/vanilla split with a single current statement:

```markdown
physical resistance is gated to level 14 and uses 3/6/10% at the three wound
tiers, doubling to 6/12/20% while Enraged on every install
```

**Step 2: Update the July design's present-tense contract**

Set the authoritative table, test expectations, and ceiling discussion to the
normalized curve. Add a dated supersession note explaining that v2.1 retired
the install-time SR branch; retain the former rationale only in explicitly
historical text.

**Step 3: Audit active prose**

Run:

```powershell
rg -n "4/8/15|8/16/30|higher on Spell Revisions|spell_rev/setup-spell_rev\.tp2" README.md ArtisansKitpack/lib/Berserker.tpa live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2
```

Expected: no matches. Historical matches are allowed only in dated design
documents that explicitly mark the branch retired or superseded.

**Step 4: Commit the documentation change**

```powershell
git add -- README.md docs/plans/2026-07-05-berserker-rebalance-design.md
git commit -m "docs: record normalized Berserker resistance"
```

### Task 4: Verify syntax, tests, and scope

**Files:**
- Verify: `ArtisansKitpack/lib/Berserker.tpa`
- Verify: `live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2`
- Verify: `tests/test_berserker_resistance_values.py`

**Step 1: Run complete test discovery**

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests PASS.

**Step 2: Run WeiDU parse checks**

```powershell
.\Setup-ArtisansKitpack.exe --nogame --parse-check TPA ArtisansKitpack/lib/Berserker.tpa
.\Setup-ArtisansKitpack.exe --nogame --parse-check TP2 live-patch/AKCB_BERSERKER/setup-AKCB_BERSERKER.tp2
```

Expected: both commands exit 0 with no parse error.

**Step 3: Check diff hygiene and live-game isolation**

```powershell
git diff --check HEAD~3..HEAD
git status --short
git diff --stat c125cae..HEAD
```

Expected: no whitespace errors; only the planned repository files changed;
nothing under `C:\Games` or the EET save directory was written.

**Step 4: Request an adversarial code review**

Ask a review agent to inspect the complete branch diff for missed executable
SR checks, inconsistent values, stale current documentation, versioning, and
test blind spots. Address every related finding and rerun Steps 1-3.
