# Release Notes

## v1.11.0
### New

- Added a Tuning menu in Settings for adjusting tag similarity matching, review score weighting, and how Pick 6 scores staleness, release date, and length. Each section can be expanded, and graphs show how a change will reshape the result before you save it.
- Added gamepad dead zone and repeat-speed settings.

### Improvements

- Reorganized the menu: frequently used tools moved up, account/appearance/library/gamepad settings consolidated into a new Settings menu, and HowLongToBeat given its own menu entry.
- Tag similarity now weighs how long you played a game, not just whether you finished it.
- The Qt/Chromium renderer option is now available on any Linux install, not just NVIDIA + Wayland.

### Fixes

- Fixed the Flatpak version being unable to see other mounted drives (`/mnt`, `/media`, `/run/media`) when choosing a games folder.
- Fixed the Card Outline Rules and Card Badges screens not returning to Appearance when closed.
- Fixed filter condition value fields not being reachable with a gamepad.
- Fixed the on-screen keyboard losing focus while typing in a text field.
- Fixed Gamepad Diagnostics and Remap Buttons not detecting the controller on Steam Deck.
