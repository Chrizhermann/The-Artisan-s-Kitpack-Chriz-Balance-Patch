-- Aimed Shot: one stronger arrow/bolt, with a six-second recharge from firing.
-- The level-7 CLAB grants op408 referencing AKCBAS; no item patches are needed.
if not EEex_Active then return end

local marker = "AKCBASCD"
local projectileKey = "AKCB_AimedShot"
local physicalDamage = {
    [0x00000000] = true, -- crushing
    [0x00100000] = true, -- piercing (some self-generated arrows)
    [0x00800000] = true, -- missile
    [0x01000000] = true, -- slashing
}

local function isArrowOrBolt(sprite)
    local equipment = sprite.m_equipment
    local weapon = equipment.m_items:get(equipment.m_selectedWeapon)
    if not weapon or not weapon.pRes or not weapon.pRes.pHeader then return false end
    local header = weapon.pRes.pHeader
    local abilityIndex = equipment.m_selectedWeaponAbility
    if abilityIndex < 0 or abilityIndex >= header.abilityCount then return false end
    -- Native GetAbility uses the correct ability stride. EEex's lowercase
    -- getAbility helper uses Item_Header_st.sizeof for nonzero indexes.
    local ability = weapon:GetAbility(abilityIndex)
    if not ability or ability.type ~= 2 then return false end -- ranged attack
    local itemType = header.itemType
    -- Ordinary ammunition and launchers using their own ammunition ability.
    return itemType == 5 or itemType == 31 or itemType == 15 or itemType == 27
end

local function isRecharging(sprite)
    local found = false
    EEex_Utility_IterateCPtrList(sprite.m_timedEffectList, function(effect)
        if effect.m_effectId == 206 and effect.m_res:get() == marker then
            found = true
            return true
        end
    end)
    return found
end

AKCBAS = {
    projectileMutator = function(context)
        local aux = EEex_GetUDAux(context.projectile)
        aux[projectileKey] = nil
        if context.decodeSource ~= EEex_Projectile_DecodeSource.CGameSprite_Swing then return end
        local sprite = context.originatingSprite
        if not sprite or not isArrowOrBolt(sprite) or isRecharging(sprite) then return end

        -- This runs at projectile creation, including projectiles with no damage
        -- effect because the attack missed. It never waits for an on-hit effect.
        -- A normal timed effect persists across saves and cannot be reset by a
        -- target/weapon change. It grants immunity only to this unused resref.
        sprite:applyEffect({
            effectID = 206,
            res = marker,
            durationType = 0,
            duration = 6,
            noSave = true,
            m_flags = 2,
            m_sourceRes = marker,
            sourceID = sprite.m_id,
            sourceTarget = sprite.m_id,
        })
        aux[projectileKey] = true
    end,

    effectMutator = function(context)
        if context.addEffectSource ~= EEex_Projectile_AddEffectSource.CGameSprite_Swing then return end
        local aux = EEex_GetUDAux(context.projectile)
        if not aux[projectileKey] then return end
        local effect = context.effect
        -- Swing adds the rolled base weapon damage. LoadProjectile adds item
        -- riders: those deliberately never enter this branch. Modify the same
        -- engine effect so resistance, Stoneskin and weapon protections still
        -- see an ordinary weapon hit, with no second packet or extra projectile.
        if effect.m_effectId ~= 12 then return end
        aux[projectileKey] = nil
        if not physicalDamage[effect.m_dWFlags] or effect.m_effectAmount <= 0 then return end
        effect.m_effectAmount = math.floor(effect.m_effectAmount * 1.5)
    end,
}
