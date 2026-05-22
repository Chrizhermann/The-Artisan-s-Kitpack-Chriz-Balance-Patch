function M_C0_MOD(effect, sprite)

    local array = EEex_Resource_Load2DA("C0EEex_M")

    local knownSpells = EEex_Utility_MapItrValues(3, EEex_Utility_ChainItrs(
        sprite:getKnownMageSpellsItr(1, 9),
        sprite:getKnownInnateSpellsItr(1, 9)
    ))

    local savedCastType
    return EEex_Utility_MutateItr(
        EEex_Actionbar_GetOp214ButtonDataItr(sprite:getValidSpellsWithAbilityItr(EEex_Utility_FilterItr(
            EEex_Utility_ApplyItr(array:getRowColumnsItr(nil, 0, 1), function(spellResRef, castType)
                savedCastType = castType
                return spellResRef
            end),
            function(spellResRef)
                return knownSpells[spellResRef:upper()] ~= nil
            end
        ))),
        function(buttonData)
            buttonData.m_abilityId.m_itemType = tonumber(savedCastType) or 3
        end
    )
end


function C0_InstallActionbarEnabledHook()

    EEex_Menu_LoadFile("C0_MODAL")

    local menu = EEex_Menu_Find("WORLD_ACTIONBAR")

    local listenToEngineEvent = function(eventRef, listener)
        local oldFunc = EEex_Menu_GetItemFunction(eventRef) or function() end
        EEex_Menu_SetItemFunction(eventRef, function()
            oldFunc()
            listener()
        end)
    end

    listenToEngineEvent(menu.reference_onOpen, C0_OnActionbarOpened)
    listenToEngineEvent(menu.reference_onClose, C0_OnActionbarOpened)

    local item = menu.items

    while item do
        local actionbar = item.button.actionBar
        if actionbar then
            local enabledRef = item.reference_enabled
            local oldEnable = EEex_Menu_GetItemFunction(enabledRef) or function() return true end
            EEex_Menu_SetItemFunction(enabledRef, function()
                return not B3Spell_ActionbarDisable and oldEnable()
            end)
        end
        item = item.next
    end
end
EEex_Menu_AddMainFileLoadedListener(C0_InstallActionbarEnabledHook)

function C0_OnActionbarOpened()
    Infinity_PopMenu("C0_Modal_Menu")
      C0_Modal_Menu = 0
end

Infinity_PopMenu('C0_Modal_Menu')
local screenWidth, screenHeight = Infinity_GetScreenSize()
function C0_ModalButtonOpen(config, state)
   if
      state == 106
      then
      Infinity_PushMenu('C0_Modal_Menu')
   end
   if
      state ~= 106
      then
      Infinity_PopMenu('C0_Modal_Menu')
   end
end
EEex_Actionbar_AddListener(C0_ModalButtonOpen)

function C0_ModalButtonActivate()
           EEex_Actionbar_RestoreLastState()
           EEex_GameObject_GetSelected():applyEffect({
                ["effectID"] = 146,
                ["effectAmount"] = 0,
                ["dwFlags"] = 1,
                ["res"] = "C0EEex_1",
            })
end
