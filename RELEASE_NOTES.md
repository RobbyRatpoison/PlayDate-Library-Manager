# Release Notes

## v2026.10.4
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
- Added a Cover Shape filter for covers that don't fit the card.
- Automatic SteamGridDB art now picks the best fit and retries on failure.

### Fixes

- Fixed Xbox stopping a day or so after connecting.
- Fixed connecting EA with a pasted link or error page appearing to work when it hadn't.
- Fixed covers briefly showing as missing when a page loads.
- Fixed a newer update not being offered right after a failed update was rolled back.
- Fixed two Epic games with the same title looking identical.
