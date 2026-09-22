"""Run the production Lua against EEex-shaped objects; not engine acceptance."""

from pathlib import Path
import unittest

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


LUA = Path(__file__).resolve().parents[1] / "ArtisansKitpack/lua/M_AKCBAR.lua"

STUBS = r"""
EEex_Active = true
EEex_Projectile_DecodeSource = {CGameSprite_Swing = 15}
EEex_Projectile_AddEffectSource = {CGameSprite_Swing = 12}
now = 0
local auxiliary = {}
function EEex_GetUDAux(object)
    if not auxiliary[object] then auxiliary[object] = {} end
    return auxiliary[object]
end
function EEex_Utility_IterateCPtrList(list, callback)
    for _, effect in ipairs(list) do
        if effect.expires > now and callback(effect) then break end
    end
end
function resref(text) return {get = function() return text end} end
function newWeapon(itemType, abilityType)
    return {
        pRes = {pHeader = {itemType = itemType, abilityCount = 1}},
        abilities = {[0] = {type = abilityType or 2}},
        GetAbility = function(self, index) return self.abilities[index] end,
        getAbility = function() error('The lowercase EEex helper has an incorrect ability stride') end,
    }
end
function newSprite(itemType)
    local sprite = {m_id = 11, m_timedEffectList = {}, applications = {}}
    sprite.weapon = newWeapon(itemType or 5)
    sprite.m_equipment = {
        m_selectedWeapon = 11, m_selectedWeaponAbility = 0,
        m_items = {get = function() return sprite.weapon end},
    }
    function sprite:applyEffect(effect)
        table.insert(self.applications, effect)
        table.insert(self.m_timedEffectList, {
            m_effectId = effect.effectID,
            m_res = resref(effect.res),
            expires = now + effect.duration * 15,
        })
    end
    return sprite
end
function fire(sprite, source)
    local projectile = {}
    AKCBAS.projectileMutator({
        originatingSprite = sprite, projectile = projectile,
        decodeSource = source or 15,
    })
    return projectile
end
function addDamage(projectile, amount, source, flags, opcode)
    local effect = {
        m_effectId = opcode or 12, m_effectAmount = amount,
        m_dWFlags = flags or 0x00800000,
        m_flags = 123, m_savingThrow = 4, m_special = 17,
        m_sourceRes = 'ORIGINAL', m_projectileType = 1,
    }
    AKCBAS.effectMutator({
        projectile = projectile, effect = effect, addEffectSource = source or 12,
    })
    return effect
end
"""


@unittest.skipIf(LuaRuntime is None, "lupa is required to execute production Lua")
class ArcherFirstShotTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(STUBS)
        self.lua.execute(LUA.read_text(encoding="utf-8"))
        self.g = self.lua.globals()

    def damage(self, sprite, amount=10):
        return self.g.addDamage(self.g.fire(sprite), amount).m_effectAmount

    def test_first_projectile_only_and_recharge_boundary(self):
        sprite = self.g.newSprite()
        self.assertEqual(self.damage(sprite), 15)
        for tick in (0, 1, 9, 18, 45, 89):
            self.g.now = tick  # Dense fire also represents Rapid Shot/haste.
            self.assertEqual(self.damage(sprite), 10)
        self.g.now = 90
        self.assertEqual(self.damage(sprite), 15)
        self.assertEqual(len(sprite.applications), 2)

    def test_miss_spends_bonus_before_any_damage_callback(self):
        sprite = self.g.newSprite()
        self.g.fire(sprite)  # Miss: projectile exists, no weapon damage added.
        self.assertEqual(self.damage(sprite), 10)
        self.g.now = 90
        self.assertEqual(self.damage(sprite), 15)

    def test_projectiles_keep_their_own_bonus_while_in_flight(self):
        sprite = self.g.newSprite()
        first, second = self.g.fire(sprite), self.g.fire(sprite)
        self.assertEqual(self.g.addDamage(second, 10).m_effectAmount, 10)
        self.assertEqual(self.g.addDamage(first, 10).m_effectAmount, 15)
        self.assertEqual(self.g.addDamage(first, 10).m_effectAmount, 10)

    def test_only_arrows_bolts_and_self_ammunition_launchers(self):
        for item_type in (5, 31, 15, 27):
            with self.subTest(item_type=item_type):
                self.assertEqual(self.damage(self.g.newSprite(item_type)), 15)
        for item_type in (14, 18, 24, 16, 25):
            with self.subTest(item_type=item_type):
                sprite = self.g.newSprite(item_type)
                self.assertEqual(self.damage(sprite), 10)
                self.assertEqual(len(sprite.applications), 0)
        sprite = self.g.newSprite(15)
        sprite.weapon = self.g.newWeapon(15, 1)  # melee ability on a bow
        self.assertEqual(self.damage(sprite), 10)

    def test_spells_and_secondary_projectiles_cannot_spend_or_receive_bonus(self):
        sprite = self.g.newSprite()
        for source in (4, 13, 22, 24):
            projectile = self.g.fire(sprite, source)
            self.assertEqual(self.g.addDamage(projectile, 10).m_effectAmount, 10)
        self.assertEqual(len(sprite.applications), 0)
        self.assertEqual(self.damage(sprite), 15)

    def test_alternate_ranged_ability_uses_its_actual_index(self):
        sprite = self.g.newSprite(15)
        sprite.weapon.abilities[0].type = 1
        sprite.weapon.abilities[1] = self.lua.table_from({"type": 2})
        sprite.weapon.pRes.pHeader.abilityCount = 2
        self.assertEqual(self.damage(sprite), 10)
        sprite.m_equipment.m_selectedWeaponAbility = 1
        self.assertEqual(self.damage(sprite), 15)
        for invalid_index in (-1, 2):
            other = self.g.newSprite(15)
            other.m_equipment.m_selectedWeaponAbility = invalid_index
            self.assertEqual(self.damage(other), 10)
            self.assertEqual(len(other.applications), 0)

    def test_ammunition_riders_and_protection_fields_are_untouched(self):
        projectile = self.g.fire(self.g.newSprite())
        rider = self.g.addDamage(projectile, 8, 9)
        elemental_rider = self.g.addDamage(projectile, 6, 9, 0x00080000)
        self.assertEqual(rider.m_effectAmount, 8)
        self.assertEqual(elemental_rider.m_effectAmount, 6)
        base = self.g.addDamage(projectile, 9)
        self.assertEqual(base.m_effectAmount, 13)
        self.assertEqual(base.m_dWFlags, 0x00800000)
        self.assertEqual(base.m_flags, 123)
        self.assertEqual(base.m_savingThrow, 4)
        self.assertEqual(base.m_special, 17)
        self.assertEqual(base.m_sourceRes, "ORIGINAL")
        self.assertEqual(base.m_projectileType, 1)

    def test_physical_damage_type_of_self_generated_arrows_is_preserved(self):
        for flags in (0x00000000, 0x00100000, 0x00800000, 0x01000000):
            sprite = self.g.newSprite(15)
            effect = self.g.addDamage(self.g.fire(sprite), 10, 12, flags)
            self.assertEqual(effect.m_effectAmount, 15)
            self.assertEqual(effect.m_dWFlags, flags)

    def test_non_physical_or_zero_damage_is_not_converted_to_bonus_damage(self):
        for flags, amount in ((0x00080000, 10), (0x00800001, 10), (0x00800000, 0), (0x00800000, -2)):
            sprite = self.g.newSprite()
            effect = self.g.addDamage(self.g.fire(sprite), amount, 12, flags)
            self.assertEqual(effect.m_effectAmount, amount)
            self.assertEqual(len(sprite.applications), 1)

    def test_recharge_is_per_actor_and_survives_weapon_target_and_lua_state_changes(self):
        first, second = self.g.newSprite(), self.g.newSprite()
        self.assertEqual(self.damage(first), 15)
        self.assertEqual(self.damage(second), 15)
        first.weapon = self.g.newWeapon(31, 2)
        first.m_targetId = 999
        self.assertEqual(self.damage(first), 10)
        # Engine saves restore timed effects, not transient projectile UDAux.
        restored = self.g.newSprite()
        restored.m_timedEffectList = first.m_timedEffectList
        self.lua.execute("EEex_GetUDAux = function(object) object.aux = object.aux or {}; return object.aux end")
        self.assertEqual(self.damage(restored), 10)
        self.g.now = 90
        self.assertEqual(self.damage(restored), 15)
        timer = first.applications[1]
        self.assertEqual(timer.effectID, 206)
        self.assertEqual(timer.res, "AKCBASCD")
        self.assertEqual(timer.duration, 6)
        self.assertEqual(timer.m_flags, 2)
        self.assertTrue(timer.noSave)

    def test_no_eeex_bootstrap_does_nothing(self):
        runtime = LuaRuntime()
        runtime.execute("EEex_Active = false")
        runtime.execute(LUA.read_text(encoding="utf-8"))
        self.assertIsNone(runtime.globals().AKCBAS)


if __name__ == "__main__":
    unittest.main()
