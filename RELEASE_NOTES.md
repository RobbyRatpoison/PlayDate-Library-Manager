# Release Notes

## v1.11.3
### New

- Manually added games can now be launched directly, using an executable set in the edit window; installed status updates automatically based on it.
- Manually added games now get their own platform badge/icon instead of a plain text label.

### Fixes

- Fixed a startup crash when `config.json` was corrupted or malformed — PlayDate now moves the bad file aside and starts fresh instead of failing to launch. (reported by Celine)
