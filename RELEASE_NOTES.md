# Release Notes

## v1.10.5 - Pending
### Improvements

- Game cards can now show a **platform badge** using each store's icon (Steam, GOG, Epic, and every other official plugin) instead of a plain text label. Turn it on, resize it, or swap in your own icon from View > Card Badges.
- The Plugins window is tidier: each plugin shows its platform logo, and an available update now appears right next to the version.

## v1.10.4 - 2026-09-07
### Improvements

- Newly added platforms now show up everywhere right away instead of starting hidden. The "Auto-hide new platforms" setting has been removed; hide a platform yourself from the filter panel if you want.
- Two new plugins in the catalog: **Legacy Games** and **Xbox / Game Pass for PC**. For Xbox, installing and launching games only works on Windows.
- PlayDate opens faster, and now shows the logo on a splash screen during startup instead of a blank (or briefly white) window.

### Fixes

- Linux Qt renderer: fixed plugin account login popups getting stuck on a blank white window instead of loading the sign-in page.
- Linux: when a non-Steam plugin can't run a Windows game because of missing prerequisites, PlayDate now says exactly what to install.
