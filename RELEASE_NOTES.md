# Release Notes

## v1.11.2
### New

- Optional, customizable info tooltip when hovering a game cover in the Library. (suggested by Colosso)
- Metacritic scores from Steam, available to sort and filter by, plus Critic % and an editable Description in the edit window and list mode. (suggested by Colosso)
- Per-library artwork source settings: choose and reorder Steam, SteamGridDB or the store's own art. (suggested by Colosso)
- The Playnite import now lets you choose which of date added, last played and time played to import. (suggested by Colosso)
- Add Game (in the menu): add a game by hand from a Steam search, or as a custom entry. (prompted by Mayanaise)
- Tutorial rewritten to follow the app page by page, with a search box and links to the dialogs it mentions.

### Improvements

- Game descriptions are now saved instead of fetched every time.
- Fill Missing Data now also fills achievement counts, and descriptions for games from other stores.

### Fixes

- Fixed capitalised game names sorting ahead of all lowercase ones, including in the duplicate search and CSV export. (reported by Mayanaise)
- Fixed a game disappearing when its copies on different platforms were linked against the platform priority order. The priority order now always decides which copy is shown.
- Fixed external gamepads reporting wrong stick and trigger values on Steam Deck.
