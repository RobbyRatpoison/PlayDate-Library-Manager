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
- The first page you open after launching now appears faster.
- Changing the Library's sort, grouping, filters or shown libraries now updates the list right away instead of reloading the page.
- The Library now follows games being installed or uninstalled while it's open, including which group they sit in.
- Editing a game now moves it to its new place in the Library straight away.
- Added a Cover Shape filter that finds covers that don't fit the card in the view you're using.
- Automatic SteamGridDB art now picks the best-fitting image and tries the next one if a download fails.

### Fixes

- Fixed Xbox stopping a day or so after connecting.
- Fixed connecting EA with a pasted link or error page appearing to work when it hadn't.
- Fixed covers briefly showing as missing when a page loads.
- Fixed a newer update not being offered right after a failed update was rolled back.
- Fixed two Epic games that share a title, such as a game and its standalone expansion, looking identical.
