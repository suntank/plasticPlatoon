Plastic Platoon — development runtime

Linux: run ./play-portable.sh. Copy this entire folder to move the game.
Build instructions and complete source: https://github.com/suntank/plasticPlatoon
The executable and game module are based on Yamagi Quake II, GPL-2.0-or-later;
see LICENSE and the source headers for component notices.
Original project assets use GPL-2.0-or-later too; see ASSET-LICENSE.md and
asset-provenance.json for the owner's declaration and legacy-content exclusions.

WASD move, mouse look, left mouse fire, space jump, tilde console.
The launcher and new games start pp_sandstorm. From the console try:
  exec heavy_test.cfg
  exec rocket_test.cfg
  exec tank_test.cfg
  exec helicopter_test.cfg
  exec bedroom_solo.cfg
  exec sandkeep_solo.cfg
  exec sandwatch_solo.cfg

The generated palette, font and basic HUD remove the startup need for Quake II
PAKs. This is a development build from the cleaned public source snapshot.
Inherited optional feature references and presentation remain development work.
The new palette changes legacy indexed art; truecolor PNG skins are preferred.
Do not add or redistribute the original game's pak*.pak files.
Settings and saves are kept in baseq2 here; write access is required.
