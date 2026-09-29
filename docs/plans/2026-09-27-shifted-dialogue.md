# Optional dialogue while shifted

Approved September 27, 2026. Separate optional/off-by-default QoL; Christopher
explicitly waived a separate manual playtest gate. Automated preservation checks
remain appropriate. Included in owner release `v4.81a-dev.85928f9-chriz.1`;
CEBG artifact pinning is a separate collection change.

The owner-release identity is `v4.81a-dev.85928f9-chriz.1`, following
the September 29 upstream-base-plus-revision naming decision. See the
[release notes](../releases/v4.81a-dev.85928f9-chriz.1.md).
The published legacy `chriz-v1.6.0` artifact remains intact. Publishing this
owner release does not itself update CEBG or any installed game.

## Scope

`ArtisansKitpack_tweak` component **51010**, label **AKCB_SHIFTED_DIALOGUE**.
Requires BG:EE/BG2:EE/EET and either main component 5100 (Shapeshifter) or 5002
(Hivemaster). Install after the selected kits and other mods changing their forms.
No EEex dependency is added: this is an ordinary installed-item patch.

The production include edits only equipped, self-targeted opcode 144 effects
with button 7 and timing 2 on `C0SS-W.ITM`, `C0SS-F.ITM`, and `C0PHIVE1..4.ITM`,
and only for the installed kit. These names originate in Artisan's Kitpack.
Patch the effective installed bytes, not copies of our source items. The base
and upgraded forms reuse these items; no generated resource names are assumed.
The current werewolf item `C0SS-F.ITM` has no Talk blocker and remains unchanged.
Missing form resources produce a warning without inventing a replacement item.

[IESDP opcode 144](https://gibberlings3.github.io/iesdp/opcodes/bgee.htm#op144)
identifies button 7 as Talk. We remove the form-specific restriction instead of
adding a global Enable Button effect. Other action restrictions, Silence,
polymorph effects, combat stats and level-14/15 Natural Spell behavior remain.
No dialogue, TLK, Lua, scripts, CLAB or save-file changes are made.

## Acceptance boundary

Real WeiDU tests on synthetic copies cover shipped form items, both/single/no-kit
selection, preservation of other effects and attack abilities, missing/already
unrestricted items, reinstall and byte-exact uninstall restoration. These are
installer checks, not proof of every scripted NPC interjection in the engine.

September 27 result: all five tests passed via
`python -m unittest discover -s tests -p test_shifted_dialogue.py -v`.
The missing-form case explicitly expects WeiDU's warning exit 3; other cases
require exit 0. The initial failing expectation was corrected in the test, not
by suppressing the production warning or accepting arbitrary nonzero exits.

September 29 release check: all five focused tests passed again with the final
versioned installer, alongside seven offline version tests. Christopher approved
the owner release for the next combined CEBG test package without an additional
standalone manual playtest.

No live game was opened or modified. A remaining dialogue case can be reported
and patched later; it is not a release blocker. This is not an existing-save
repair: already active form effects may require returning to natural form and
transforming again after a planned update. CEBG hotpatch support is not implied.
