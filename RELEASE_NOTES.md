# Release Notes

## v1.11.0
### New

- Added a Settings menu for tuning how tag similarity matching works.
- Added gamepad dead zone and repeat-speed settings.
- Added an Advanced Tuning menu on Pick 6 for adjusting how staleness, release date, and length affect picks.

### Improvements

- Reorganized the menu: frequently used tools moved up, account/appearance/library/gamepad settings consolidated into a new Settings menu, and HowLongToBeat given its own menu entry.
- Tag similarity now weighs how long you played a game, not just whether you finished it.
- The Qt/Chromium renderer option is now available on any Linux install, not just NVIDIA + Wayland.

### Fixes

- Fixed the Card Outline Rules and Card Badges screens not returning to Appearance when closed.
- Fixed filter condition value fields not being reachable with a gamepad.
- Fixed the on-screen keyboard losing focus while typing in a text field.
