# Archer rebalance

Implemented on `codex/archer-rebalance`. Source and synthetic checks only;
live-engine acceptance is pending. This change does not patch an installed
game, migrate a saved character, or publish a release.

## Rules

| Feature | Revised behavior |
| --- | --- |
| Manyshot | Removed, including its level-13 and level-20 upgrades and launcher/animation patches. |
| Aimed Shot | EEex only, level 7. One arrow or bolt gains 50% physical damage, rounded down; six-second recharge starts when it is fired. A miss spends it. |
| Called Shot | Existing 10-second activation; one daily use at level 4 and another every four levels. Successful ranged hits attempt a 25% movement penalty for 12 seconds. Save vs. Death, modifier 0. Failed saves refresh the duration; successful saves leave any previous slow unchanged. |
| Called Shot damage | At level 16, +2 missile weapon damage for the activation. Part of ordinary weapon damage, independent of the hostile saving throw. |
| Farsighted / Sniper | Removed; ordinary sight range and critical chance. |
| High-level abilities | Hardiness retained; Greater Called Shot removed. |
| Other kit rules | Rapid Shot, d8 hit dice, ranged accuracy progression, and the melee/proficiency restrictions retained. |

Late-game missile immunity and spell defenses receive no new counter here.
The Archer's existing strength is the reason for reducing these additions.

## Delivery and compatibility

The opening-arrow rule uses a **six-second recharge**, not a claimed hook into
the engine's personal combat-round boundary. Exposed attack-frame fields do
not establish a reliable round identity, particularly across interrupted
attacks. The description therefore states the recharge explicitly.

The level-7 CLAB grants an EEex opcode408 projectile mutator. It recognizes
ordinary arrows/bolts and ranged ammunition abilities on bows/crossbows, spends
the recharge at projectile creation, and changes only the engine's base
physical-damage effect from `CGameSprite_Swing`. Item riders added through
`CGameSprite_LoadProjectile` are untouched. It neither creates a second damage
effect nor changes protection-bypass flags. The recharge is an ordinary
non-dispellable timed effect, so it persists in saves without transient Lua
state. No ticking poll or item-by-item bonus patches are needed.
The native `CItem:GetAbility` lookup is used for alternate ability indexes;
the inspected EEex lowercase helper uses the wrong struct stride. Physical
damage keeps its original type, including piercing self-generated arrows.

EEex must be installed before component 2010 to enable Aimed Shot. Without
EEex, the component still applies all the reductions and offers no replacement
for Manyshot. The two descriptions accurately reflect that install branch.
Component 20101 is retained as a compatibility cleanup: it removes only the
old `C0ARCP01` through `C0ARCP24` equipped EFF references. It cannot reintroduce
extra projectiles, and preserves unrelated launcher effects.

Called Shot puts its saving throw on the existing EFF dispatcher. Only a
failed save reaches the cleanup and replacement slow. Its level-16 damage
bonus is a self-applied opcode286 modifier. Standard movement opcode126 is
used instead of the old opcode176; ordinary opcode immunity can block it.
Bare opcode163 does not universally remove percentage movement effects, so
Free Action is not claimed to work for every possible modded implementation.

Old Farsighted/Sniper and Greater Called Shot spell helpers are inert, and the
old stun EFF is harmless. Existing saves can still contain previously granted
innates, passive effects or item instances. Reinstalling is not proof of a
complete saved-character migration; no HLA refund or live-save retrofit is
included. Test with a newly generated Archer first.

## Validation

2026-09-22 result: **71 tests passed** (51 existing tests and 20 Archer tests).
The latest Archer run used Lua 5.1. All four Archer includes and the tweak TP2
passed WeiDU 249 parsing; `git diff --check` passed.

- Real WeiDU synthetic-game fixtures inspect the produced spell/effect graph,
  save fields, level headers, CLAB grants, HLA choices, descriptions and item
  cleanup. Reinstall and byte-exact override restoration are checked.
- Production Lua is executed with EEex-shaped test objects. Cases cover
  misses, rapid successive shots, the six-second boundary, independent actors,
  weapon/target changes, restored timed effects, ammunition riders and damage
  metadata. These tests require Python's `lupa` package; without it they report
  a skip, not a pass for Lua execution.
- WeiDU parsing and the repository's full Python test suite are run before
  handoff. These checks cannot establish engine callback order, projectile
  behavior, or live combat results.

## Required engine playtest

1. At levels 6/7, 12/13 and 19/20, compare ordinary arrows, bolts and launchers
   with unlimited ammunition. Only level 7 adds Aimed Shot; no level adds
   extra projectiles. Slings, thrown weapons and melee attacks do not gain it.
2. Force normal misses and critical misses, then attack again before six
   seconds. Neither miss may leave the bonus for a later hit. Check ordinary
   fire, Rapid Shot, Haste, Improved Haste and Time Stop. Check attack
   interruption and switching targets/weapons.
3. Check base damage, odd-value rounding and ordinary criticals. Fire/acid and
   other ammunition riders must occur once with their ordinary damage.
   Missile resistance, Stoneskin, Protection from Normal Missiles, Protection
   from Magical Weapons and Mantle must retain normal weapon behavior.
4. Save/load during recharge; rest and area changes must not leave the Archer
   permanently charging or reset an unexpired recharge. Repeat with two
   Archers so one actor cannot consume another's bonus.
5. At levels 4/8/12/16, verify the same modest slow and unmodified Death save.
   Repeated failed saves refresh one 12-second effect; successful saves leave
   its remaining duration alone. Check magic resistance and the actual Free
   Action spell/equipment in the intended installation. Dexterity and APR
   must remain unchanged.
6. At levels 15/16, verify the +2 Called Shot damage appears only at 16, expires
   after 10 seconds, and does not stack on recasting. A target's successful
   slow save must not remove that bonus.
7. Verify normal vision and stealth criticals, daily-use progression, and the
   HLA screen: Hardiness available, Greater Called Shot absent. Inspect old
   saves separately before designing any migration.

## Primary implementation references

- [EEex projectile callback contexts](https://github.com/Bubb13/EEex/blob/master/EEex/copy/EEex_scripts/EEex_Projectile.lua)
- [EEex combat-frame and base-damage hooks](https://github.com/Bubb13/InfinityLoader/blob/master/EEex-Core-Shared-Files/source/EEex.cpp)
- [Native CItem binding](https://github.com/Bubb13/InfinityLoader/blob/master/LuaBindings-v2.6.6.0/source/LuaBindings-v2.6.6.0/Generated/EEexLua_generated.cpp#L166665)
- [IESDP movement modifiers](https://gibberlings3.github.io/iesdp/opcodes/bgee.htm#op126),
  [ranged-hit effects](https://gibberlings3.github.io/iesdp/opcodes/bgee.htm#op249),
  [missile damage modifier](https://gibberlings3.github.io/iesdp/opcodes/bgee.htm#op286)
