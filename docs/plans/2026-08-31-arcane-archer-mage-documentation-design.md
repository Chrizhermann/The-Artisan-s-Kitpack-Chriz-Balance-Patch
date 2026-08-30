# Arcane Archer/Mage Documentation Design

## Goal

Document the kit's existing one-fewer-wizard-spell-slot penalty and keep a
complete, compact ledger of this fork's user-facing changes at the end of the
README.

## Design

- Do not change mechanics: `C0AAINN.SPL` already applies one opcode 42 `-1`
  modifier to wizard spell levels 1-9, inherited by Arcane Archer/Mage.
- Add the established disadvantage wording to the kit's full description:
  "May cast one fewer spell per level per day."
- Move and rename the README ledger to `Changes vs upstream` at the end, keeping
  Berserker and adding Arcane Archer/Mage plus the Arcane Trickster fix.

## Verification

Parse-check the edited TPA and core TP2, confirm the existing slot effect remains
single and unchanged, and run whitespace/diff checks.
