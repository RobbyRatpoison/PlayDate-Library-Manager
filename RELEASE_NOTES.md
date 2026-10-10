# Release Notes

## v2026.10.4
### New

- Added a Cover Shape filter for covers that don't fit the card.
- Added a From Steam button for artwork on games that also exist on Steam.
- Added a Crop button for artwork, with a draggable image.

### Improvements

- GOG purchase dates now import straight from your account, with no userscript.
- EA purchase dates now import straight from your account, with no userscript.
- Plugins now check that your login still works instead of failing silently.
- Humble logins now renew themselves so they don't lapse.
- The SteamGridDB picker now lists images closest to the right aspect ratio first and sets apart the ones that don't match.
- Pages now appear about half a second sooner when you open them.
- The Home page now loads much faster with very large libraries.
- The Library page now loads noticeably faster with thousands of games, and much faster when you come back to it.
- The first page after launch now appears faster.
- Sorting, grouping and filtering the Library no longer reloads the page.
- The Library now updates when games are installed or uninstalled.
- Edited games now move to their new place straight away.
- The artwork tab now opens on the view you're in.
- Automatic SteamGridDB art now picks the best fit and retries on failure.
- Artwork now prefers Steam art and the right shape, switchable in Settings.
- Games from other libraries are now matched to Steam automatically.

### Fixes

- Fixed Xbox stopping a day or so after connecting.
- Fixed connecting EA with a pasted link or error page appearing to work when it hadn't.
- Fixed covers briefly showing as missing when a page loads.
- Fixed a newer update not being offered right after a failed update was rolled back.
- Fixed two Epic games with the same title looking identical.
- Fixed bulk artwork scraping ignoring the chosen source for non-Steam games.
