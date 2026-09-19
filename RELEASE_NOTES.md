# Release Notes

## v1.11.1
### Improvements

- Added a `PlayDate.command` file for launching PlayDate on macOS with a double-click.
- The macOS launcher now finds a compatible Python, or tells you what to install and continues once you have.

### Fixes

- Fixed system-wide Flatpak installs failing to update with no explanation. PlayDate now warns you first and says how to update.
- Fixed updates on Linux going to the wrong Flatpak copy when PlayDate is installed both system-wide and for your user.
