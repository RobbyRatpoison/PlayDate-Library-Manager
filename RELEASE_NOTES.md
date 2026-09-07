# Release Notes

## v1.10.4
### Improvements

- PlayDate opens faster, and now shows the logo on a splash screen during startup instead of a blank (or briefly white) window.
- Newly added platforms — from installing a plugin, say — now show up everywhere right away instead of starting hidden. The "Auto-hide new platforms" setting has been removed; hide a platform yourself from the filter panel if you want.
- The Plugin Catalog no longer has a separate "beta" section. Every plugin, including Amazon Games and Rockstar Games, is now grouped only by how well it's confirmed to work on your system (Working / Untested / Broken).
- Two new plugins in the catalog: **Legacy Games** (working on Linux — install opens the launcher, launch and uninstall are automated) and **Xbox / Game Pass for PC** (imports your library; install and launch are Windows-only).

### Fixes

- Linux Qt renderer: fixed plugin account login popups getting stuck on a blank white window instead of loading the sign-in page.
- Linux: when a non-Steam plugin can't run a Windows game because Wine, GE-Proton, or umu-launcher is missing, PlayDate now says exactly what to install instead of crashing or showing a vague error — and the Plugins modal flags it up front.
