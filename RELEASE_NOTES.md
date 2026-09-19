# Release Notes

## v1.11.1
### Improvements

- Added a `PlayDate.command` file for launching PlayDate on macOS with a double-click.
- The macOS launcher now finds a compatible Python, or tells you what to install and continues once you have.
- PlayDate.app now has its own icon on macOS.

### Fixes

- Fixed system-wide Flatpak installs failing to update with no explanation. PlayDate now warns you first and says how to update.
- Fixed PlayDate not opening when another program, such as macOS's AirPlay Receiver, is using its usual port. If you use the PlayDate Companion userscript, update it.
- Fixed copy and paste sometimes not working with the Qt renderer.
- Fixed updates on Linux going to the wrong Flatpak copy when PlayDate is installed both system-wide and for your user.
