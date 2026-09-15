# Fighter modal tradeoffs

This optional WeiDU tail updates an existing **Artisan Fighter Overhaul
(component 1100)** to the current Power Attack and Expertise tradeoffs:
2 points normally and 4 points for their improved versions. Fresh installations
of the balance patch already contain these values.

It changes the four shared installed payload spells in place, preserving their
other effects and installed string references. It updates the existing English
modal wording in the entry spells and Fighter descriptions. Barbarian, Divine
Champion, Rashemi Berserker and Dwarven Defender references are included when
present and describe these modals; existing nonmodal descriptions, such as a
vanilla Barbarian row, are preserved. Those optional kits are not prerequisites. Different campaign tables
may use different description strings, and each referenced string is updated.

The patch supports the original English 3/6 wording and the current 2/4 wording.
It stops and rolls back on unexpected modal stat values, effect shapes, duplicate
stat effects, missing required descriptions, or unsupported modal wording. It
does not replace whole kit descriptions or translate other languages.

## Install and uninstall

1. Close the game and its loader.
2. Copy this `AKCB_FIGHTER_MODALS` folder to the intended game directory.
3. Copy a current WeiDU executable there as `setup-AKCB_FIGHTER_MODALS.exe`.
4. Run it and install component 0 after the existing mod stack.

To uninstall, run the same installer and remove component 0. WeiDU restores the
previous resource bytes and description text. Do not reinstall the earlier
Fighter component just to apply this update.

Restart the game after installation or removal, and turn any active Power Attack
or Expertise modal off and on so its effects use the current resources.

## Verification

`python -m unittest discover -s tests -p test_fighter_modals.py -v` runs the
portable regression suite from the repository root. It builds disposable minimal
games from repository resources and synthetic tables and strings. It checks
source-equivalent stat values, optional kits, preservation of other effects and
text, idempotence, failed-install rollback, and exact uninstall restoration.
WeiDU normalizes the flags of rewritten TLK entries to 7; the suite separately
checks that known normalization and restoration of original flags on uninstall.
The suite does not read or modify a full game installation or saved game.
