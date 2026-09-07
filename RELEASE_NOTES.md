# Release Notes

## v1.10.3 - Pending
### Improvements

- Linux: added an experimental Qt renderer option (Settings → Renderer) to fix choppy library scrolling on NVIDIA + Wayland. On Flatpak, switching installs a separate app and removes the one you're switching from.
- Gamepad/d-pad navigation on the library and home pages now scrolls smoothly into view and no longer hides the focused card behind the top bar.
- Backups now include your custom background image and uploaded card-badge icons.
- Restoring a backup on a different machine no longer carries over settings tied to the old one (window size and position, renderer choice).
- "Send Log to Developer" now also includes your settings, library/plugin counts, and renderer info, for better bug diagnosis.

### Fixes

- The library page now shows a "Show All Games" button when a filter or hidden platform leaves nothing to display.
- Fixed a fresh setup with multiple plugins ending up with an empty library, if a plugin's games synced in right after connecting it. (reported by beckett)
