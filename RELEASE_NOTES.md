# Release Notes

## v1.12.0
### New

- Customizable mouse actions: choose what each mouse button does on a game cover, on a single or double click. (suggested by woutercools)
- Gamepad shortcuts for a game's store page, install folder, Steam achievements and Community Hub.
- Draw your own controller layout: pick a body shape, place the controls to match your controller, then press each one to record it.
- Choose a button and stick layout for each controller, remembered per controller.
- Choose how buttons are named (Xbox, PlayStation, Nintendo or Other), and rename any button yourself, such as C or Z.
- A Gamepad setting to read the controller directly on Linux, for controllers the browser maps wrongly.

### Improvements

- Gamepad Diagnostics is now Gamepad Setup, with a live drawing of the controller you can show or hide.
- Controllers without a standard layout are now recognised from a built-in list of known layouts.
- Gamepad Controls can clear any action except Confirm, and asks to swap or clear when you pick a button already in use.
- Gamepad Controls and Gamepad Setup are greyed out while gamepad input is off.
- Gamepad input is no longer labelled experimental.
- Mouse actions replace "Require double-click to launch/install". Your setting carries over.
- Automatic update checks now run at most once a day.
- If an update fails to start, PlayDate now puts the previous version back automatically, along with your library and settings as they were before the update, and tells you what happened. The failed version isn't offered again; a newer one is. This protects the update after this one, since it is the older version that sets up the safety net.

### Fixes

- Fixed "Reset to Defaults" in Gamepad Controls not updating the list until reopened.
- Fixed the update notification dot reappearing on every page load, and the Plugins dot staying lit after updating.
