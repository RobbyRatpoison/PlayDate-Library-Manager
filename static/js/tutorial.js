// -- Tutorial modal --------------------------------------------------------
// Table of contents + per-section step cards. Content authored here is trusted
// static copy (not user/API data), so step bodies are assigned via innerHTML
// to allow basic formatting rather than run through escHtml().

const TUTORIAL_SECTIONS = [
    {
        id: 'getting-started',
        title: 'Getting Started',
        steps: [
            {
                title: 'Welcome to PlayDate',
                body: `<p>PlayDate is a local game library manager for your Steam collection, with optional support for GOG, Epic, and other non-Steam launchers through plugins.</p>
                       <p>This tutorial is a quick tour of everything - jump to any section from the list, or work through it top to bottom. You can reopen it anytime from the hamburger menu (☰) → Tutorial.</p>`,
            },
            {
                title: 'Three main pages',
                body: `<p>The nav bar at the top always has three pages:</p>
                       <ul>
                         <li><strong>Home</strong> - curated shelves of games (Recently Played, Unfinished, and whatever else you set up).</li>
                         <li><strong>Library</strong> - your full collection, with filters and bulk tools.</li>
                         <li><strong>Pick 6</strong> - a "what should I play next" picker.</li>
                       </ul>
                       <p>Everything else - settings, plugins, emulators, backups - lives behind the hamburger button (☰) in the top-left.</p>`,
            },
            {
                title: 'Gamepad friendly',
                body: `<p>Every menu, modal, and library view in PlayDate can be driven entirely with a gamepad - this app is built with Steam Deck in mind. D-pad/stick to move, A to confirm, B to back out.</p>
                       <p>Gamepad support can be toggled, remapped, or diagnosed from Settings → Gamepad.</p>`,
            },
        ],
    },
    {
        id: 'home-shelves',
        title: 'Home & Shelves',
        steps: [
            {
                title: 'What are shelves?',
                body: `<p>The Home page shows your library as a set of horizontal shelves, like "Unfinished," "Recently Added," or a random pick. Each shelf is a <strong>filter</strong> (which games it can show) plus a <strong>sort</strong> (the order they come in).</p>
                       <p>The filter can be one of PlayDate's built-in quick filters, one of your own saved filters, or a custom filter built just for that shelf. Filters are covered in more detail under Library &amp; Filters.</p>`,
            },
            {
                title: 'Editing the layout',
                body: `<p>Hamburger menu → <strong>Settings</strong> → <strong>Appearance</strong> → <strong>Edit Home Layout</strong> puts Home into edit mode. On the Home page itself, pressing <strong>E</strong> does the same. <strong>＋ ADD SHELF</strong> adds a shelf, the ⠿ handle drags one to a new spot, and ✕ removes it. <strong>✎ Edit</strong> on a shelf changes what it shows (see the next step).</p>
                       <p>Nothing is kept until you press <strong>SAVE LAYOUT</strong>; <strong>CANCEL</strong> throws your changes away and <strong>RESET</strong> goes back to the default layout.</p>`,
            },
            {
                title: 'What a shelf shows',
                body: `<p>In <strong>✎ Edit</strong>, the <strong>Filter</strong> menu picks which games a shelf draws from: a built-in quick filter (All Games, Installed, Not Installed, Never Played / Unfinished, Beaten / Completed, or a single completion status), one of your <strong>saved filters</strong>, or <strong>🔧 Custom Filter…</strong>, which opens the Filter Builder for just that shelf so there's nothing to save. A shelf can also be a widget instead (see Widgets).</p>
                       <p><strong>Sort by</strong> sets the order, ascending or descending, and <strong>Platforms shown</strong> limits the shelf to the platforms you tick, so one shelf can be Steam only while another shows everything.</p>`,
            },
            {
                title: 'Sizes, columns and game counts',
                body: `<p>Every shelf has a <strong>Height</strong> and a <strong>Games</strong> count. You can also drag the bottom edge of a row to resize it. <strong>Games</strong> is how many covers the shelf loads, and setting it to <strong>0 removes the limit</strong>: the shelf loads every match and scrolls sideways.</p>
                       <p><strong>＋ COLUMN</strong> splits a shelf into columns: click it, then click a shelf to add another one beside it. Each column has its own <strong>Width</strong>, or drag the divider between columns to resize them.</p>`,
            },
            {
                title: 'Widgets',
                body: `<p>A shelf doesn't have to show games. In <strong>✎ Edit</strong>, pick a widget instead: a <strong>Clock</strong>, a <strong>Completion Chart</strong> of your completion statuses, or an <strong>Achievement Chart</strong>, plus any widgets a plugin adds.</p>
                       <p>Widgets sit in the layout like any shelf, so you can resize them or put one in a column next to a game shelf.</p>`,
            },
            {
                title: 'Shelf priority',
                body: `<p>A game only appears on one shelf. Shelves are filled in priority order, and a shelf skips any game a higher-priority shelf already took, so it shows its next matches instead. <strong>⇅ SHELF PRIORITY</strong> in edit mode lets you drag shelves into the order you want them to claim games.</p>
                       <p>The switch beside each shelf takes it out of this entirely: it shows every game that matches, even ones shown elsewhere, and doesn't take games away from other shelves.</p>`,
            },
            {
                title: 'Random shelves',
                body: `<p>Set a shelf's sort to <strong>Random</strong> to get a fresh random set of games. A shelf sorted this way shows a shuffle icon (↻) next to its title - click it to reroll that shelf without leaving the page.</p>`,
            },
        ],
    },
    {
        id: 'library-filters',
        title: 'Library & Filters',
        steps: [
            {
                title: 'Grid or list view',
                body: `<p>The Library page defaults to a scrolling grid of cover art. Switch to <strong>list view</strong> from the VIEW menu for a compact, split-pane layout - a scrollable row list on the left and a detail/edit pane on the right, good for quickly working through a lot of games.</p>`,
            },
            {
                title: 'Search and quick filters',
                body: `<p>The search box at the top of the Library filters as you type. <strong>FILTERS</strong> opens the filter dialog, whose <strong>Quick</strong> row has one-click presets: All Games, Installed, Not Installed, Never Played / Unfinished, Beaten / Completed, and one for each completion status. While a filter is active, a <strong>✕ CLEAR</strong> button appears in the toolbar.</p>
                       <p>The platform buttons in the same dialog hide or show whole libraries (Steam, GOG, Epic and so on).</p>`,
            },
            {
                title: 'Building a filter',
                body: `<p><strong>Simple</strong> mode is a list of conditions - tags, genres, completion status, release date, playtime, review scores, developer and more - combined with <strong>AND</strong> (every condition must match) or <strong>OR</strong> (any one can match).</p>
                       <p><strong>Advanced</strong> mode adds nested groups, so you can ask for things like "(Puzzle OR Platformer) AND under 10 hours", and expressions where you write your own SQL condition for anything the menus can't say. <strong>APPLY</strong> shows the result and <strong>CLEAR ALL</strong> starts over.</p>`,
            },
            {
                title: 'Saved filters',
                body: `<p>Once you have a filter you like, save it. The <strong>Saved filters…</strong> menu loads one, and the buttons beside it save the current filter, rename a saved one, or delete it.</p>
                       <p>A saved filter can be reloaded from the Library, chosen as the filter for a Home shelf, used to narrow the pool Pick 6 draws from, and shared with other people through <strong>Filter Import / Export</strong> in the Data menu.</p>`,
            },
            {
                title: 'Bulk operations',
                body: `<p>Select multiple games in the grid (or list view) and use <strong>Bulk Ops</strong> to edit tags/status across all of them at once, or re-scrape metadata and cover art in bulk.</p>`,
            },
        ],
    },
    {
        id: 'editing-games',
        title: 'Editing a Game',
        steps: [
            {
                title: 'The edit panel',
                body: `<p>Open any game (grid card, or the detail pane in list view) to edit its completion status, tags, groups, developers, publishers, release date, and Date Added. Renaming a game makes PlayDate re-resolve its metadata from the new name.</p>`,
            },
            {
                title: 'Syncing data',
                body: `<p><strong>Sync Steam Data</strong> re-fetches a single game's store data, reviews, and tags. On non-Steam games the button uses that platform's own label.</p>
                       <p><strong>Fill Missing Data</strong> only fills fields that are currently empty (tags, review score, genres, developer, release date), by matching the game to a Steam page or PCGamingWiki. Your own edits and plugin data are never overwritten.</p>`,
            },
            {
                title: 'Cover art',
                body: `<p>Art comes from Steam first, then SteamGridDB as a fallback for anything Steam lacks (and for non-Steam games). Add a free SteamGridDB API key under Settings → Account to enable it. Art is cached locally and only re-fetched when you ask.</p>`,
            },
            {
                title: 'Duplicates and folders',
                body: `<p>The <strong>Duplicate of</strong> row lets you point a game at the copy you'd rather keep visible, on any platform. <strong>Open Folder</strong> opens the install location in your file manager.</p>`,
            },
        ],
    },
    {
        id: 'completion-status',
        title: 'Completion Status',
        steps: [
            {
                title: 'The five statuses',
                body: `<ul>
                         <li><strong>Never Played</strong> - untouched.</li>
                         <li><strong>Unfinished</strong> - started, not done.</li>
                         <li><strong>Beaten</strong> - your own call that you finished it.</li>
                         <li><strong>Completed</strong> - 100% of achievements.</li>
                         <li><strong>Won't Play</strong> - you judge it terrible or broken. Not just "not interested".</li>
                       </ul>
                       <p>Pick 6 and tag-similarity sorting treat these as real taste signals, so being honest here gives better suggestions.</p>`,
            },
            {
                title: 'Automatic updates',
                body: `<p>Settings → Library → <strong>Completion Sync</strong> can promote Never Played to Unfinished once you have playtime, mark a game Completed at 100% achievements, and drop Completed back to Beaten if a developer later adds achievements. Each is a separate toggle.</p>`,
            },
        ],
    },
    {
        id: 'date-import',
        title: 'Importing Purchase Dates',
        steps: [
            {
                title: 'Why import dates?',
                body: `<p>Steam and GOG don't expose accurate purchase/activation dates through their APIs, so PlayDate can pull them from your account's own history pages instead, using PlayDate Companion, a browser userscript (needs the Tampermonkey extension). Install it from <a href="https://github.com/RobbyRatpoison/PlayDate-Library-Manager/raw/refs/heads/main/steam_date_import.user.js" target="_blank">GitHub</a>.</p>`,
            },
            {
                title: 'Single game or bulk',
                body: `<p>Click the ↗ next to <strong>Date Added</strong> in a game's edit panel to import one game's date, or use the Library page's Bulk Ops → <strong>Date Importer</strong> tab to fetch dates for many games at once.</p>`,
            },
        ],
    },
    {
        id: 'pick6',
        title: 'Pick 6',
        steps: [
            {
                title: 'What Pick 6 does',
                body: `<p>Pick 6 answers "what should I play next?" - it weighs six signals (how similar a game's tags are to what you've enjoyed before, review score, how long it's been sitting unplayed, completion history, playtime, and release age) and surfaces six games weighted by that score, not just a strict top list.</p>`,
            },
            {
                title: 'Rerolling and filtering',
                body: `<p>Not feeling any of the six? Reroll for a new set. You can also apply a filter first (e.g. only GOG games, or only under 10 hours) to narrow the pool Pick 6 draws from.</p>`,
            },
        ],
    },
    {
        id: 'hltb',
        title: 'HowLongToBeat',
        steps: [
            {
                title: 'Completion times',
                body: `<p>PlayDate can match your games to HowLongToBeat and store how long each takes to finish. You can then sort and filter by it, for example to find something short for tonight.</p>`,
            },
            {
                title: 'Reviewing matches',
                body: `<p>Hamburger menu → <strong>HLTB</strong> lists matches by confidence. Confident ones are applied automatically. Weaker ones wait for you to confirm, pick another result, or search by hand. <strong>No page</strong> marks a game as having no HLTB entry so it isn't suggested again.</p>
                       <p><strong>Confirm all above threshold</strong> runs in the background with a progress button in the menu, so you can close the window.</p>`,
            },
        ],
    },
    {
        id: 'pagywosg',
        title: 'PAGYWOSG',
        steps: [
            {
                title: 'What is PAGYWOSG?',
                body: `<p>PAGYWOSG ("Play A Game You Won on SteamGifts") is a monthly community event on SteamGifts. Each event has its own set of category rules - PlayDate can read those live and build a matching filter for you automatically, instead of you checking your library against each category by hand.</p>`,
            },
            {
                title: 'Set your SteamGifts username',
                body: `<p>Some categories only count games <em>verified</em> for a specific player. Set your SteamGifts username in Settings so PlayDate can tell which verified entries are actually yours.</p>`,
            },
            {
                title: 'Building a filter',
                body: `<p>Open the PAGYWOSG tool from the hamburger menu's <strong>Community Tools</strong> section, pick the event, and PlayDate assembles and saves a filter matching that month's rules - ready to use like any other saved filter.</p>`,
            },
        ],
    },
    {
        id: 'blaeo',
        title: 'BLAEO',
        steps: [
            {
                title: 'What is BLAEO?',
                body: `<p>BLAEO (Backlog Assassins) is a community site for tracking your backlog completion status and custom lists. If you keep it up to date, PlayDate can sync those changes into your library instead of you re-entering them by hand.</p>`,
            },
            {
                title: 'Running a sync',
                body: `<p>Open the hamburger menu's <strong>Community Tools</strong> section and click <strong>Sync BLAEO</strong>. PlayDate fetches your BLAEO profile and shows a preview of proposed changes - completion status updates, list renames, additions, and removals.</p>`,
            },
            {
                title: 'Reviewing changes',
                body: `<p>Nothing is written until you choose. Check off which proposed changes to keep, then <strong>Apply Selected</strong> - or <strong>Discard</strong> to skip the sync entirely.</p>`,
            },
        ],
    },
    {
        id: 'community-extras',
        title: 'More Community Tools',
        steps: [
            {
                title: 'SteamGifts wins',
                body: `<p>Community Tools → <strong>Sync SteamGifts Wins</strong> imports your giveaway wins and tags received ones with a "Won on SteamGifts" group. It needs the PlayDate Companion userscript, because SteamGifts blocks direct scraping.</p>
                       <p>A normal sync is incremental. <strong>Full refresh</strong> re-checks every win and prunes stale ones. Wins that don't match a library game are listed with a reason, and some can be adopted in one click.</p>`,
            },
            {
                title: 'Play or Pay',
                body: `<p><strong>Sync Play or Pay Picks</strong> pulls the current picks into a saved filter, and cleans up groups left over from earlier cycles.</p>`,
            },
            {
                title: 'Monthly in a Month and Secret Santa',
                body: `<p>The <strong>Monthly in a Month</strong> builder makes a filter for candidate games by completion status, and can check them against the community sheet. <strong>Secret Santa / Snowballs</strong> has its own helper for that event.</p>`,
            },
        ],
    },
    {
        id: 'plugins',
        title: 'Plugins',
        steps: [
            {
                title: 'Beyond Steam',
                body: `<p>Steam is built into PlayDate directly. Everything else comes from plugins, which are optional and installed on demand. PlayDate has official plugins for GOG, Epic Games, EA App, Ubisoft Connect, Humble Bundle, itch.io, Amazon Games, Battle.net, IndieGala, Rockstar Games, Legacy Games, and Xbox / Game Pass.</p>`,
            },
            {
                title: 'Installing and managing plugins',
                body: `<p>Hamburger menu → <strong>Plugins</strong> has a <strong>Plugin Catalog</strong> where each official plugin installs with one click. It's sorted into Working, Untested, and Broken for the OS you're running, based on real reports. You can also install a third-party plugin from a zip file or a GitHub URL.</p>
                       <p>The same screen checks for updates (with an <strong>Update All</strong> button) and uninstalls plugins, with the option to remove that platform's games too. Installing, updating, or removing a plugin shows a <strong>Restart Now</strong> button.</p>`,
            },
            {
                title: 'Launchers on Linux',
                body: `<p>Some plugins need the store's own launcher. On Linux, PlayDate can set up a Wine or Proton prefix and install that launcher for you: open the plugin's card and click <strong>Configure Launcher</strong>. A green "Launcher ready" badge means it's set up; an amber warning explains what's missing.</p>
                       <p>Proton needs <strong>umu-run</strong> installed on the host. If it's missing, PlayDate falls back to a system Wine or tells you what to install.</p>`,
            },
            {
                title: 'Signing in',
                body: `<p>Plugins that need a login offer a sign-in window inside PlayDate. If a store's bot detection blocks that window on a captcha page, there's usually a paste option too: sign in in your normal browser, then paste the resulting code or key back into PlayDate.</p>`,
            },
            {
                title: 'Duplicate detection',
                body: `<p>Own the same game on two platforms? PlayDate can detect duplicates across all your connected platforms and let you pick which copy stays visible in your library.</p>`,
            },
        ],
    },
    {
        id: 'emulators',
        title: 'Emulators',
        steps: [
            {
                title: 'Tracking emulated games',
                body: `<p>Games you play through an emulator (retro consoles, handhelds, anything outside Steam/GOG/etc.) can be added to PlayDate too, so they show up in your library, shelves, and Pick 6 alongside everything else.</p>`,
            },
            {
                title: 'Adding an emulator',
                body: `<p>Hamburger menu → <strong>Emulators</strong> - pick a platform from the list to use a common preset, or add a custom entry pointing at your own emulator binary.</p>`,
            },
        ],
    },
    {
        id: 'cleanup',
        title: 'Blacklist & Junk Finder',
        steps: [
            {
                title: 'Removing games for good',
                body: `<p>Removing a game from the library adds it to the <strong>blacklist</strong>, so it doesn't come back on the next sync. Hamburger menu → <strong>Blacklist / Junk Finder</strong> shows the list, and you can remove entries from it to allow them back.</p>`,
            },
            {
                title: 'Find Library Junk',
                body: `<p>Imports sometimes pull in soundtracks, DLC, dev kits, and store apps. <strong>Find Library Junk</strong> scans for them by title pattern across every platform. Its <strong>Deep Plugin Scan</strong> re-checks a platform against its store, which is slower, so it only runs when you click it. Review the results and remove what you don't want.</p>`,
            },
            {
                title: 'Duplicate entries',
                body: `<p>Settings → Library → <strong>Find Duplicate Entries</strong> catches one store game imported twice, usually claimed in two bundles. This is separate from cross-platform duplicates, which the Duplicates settings handle.</p>`,
            },
        ],
    },
    {
        id: 'data',
        title: 'Backup & Data',
        steps: [
            {
                title: 'Backup and restore',
                body: `<p>Hamburger menu → <strong>Data</strong> → <strong>Backup &amp; Restore</strong> saves your library and settings to one zip you can restore later. PlayDate offers a backup before updating unless you made one in the last 24 hours.</p>`,
            },
            {
                title: 'Imports and exports',
                body: `<p>The Data menu also imports from another SQLite database or a Playnite backup (for Date Added), exports your library to CSV with the columns you choose, and shares saved filters through <strong>Filter Import / Export</strong>.</p>`,
            },
        ],
    },
    {
        id: 'settings',
        title: 'Settings Tour',
        steps: [
            {
                title: 'Account',
                body: `<p>Your Steam API key and SteamID, SteamGridDB key, SteamGifts username, and account switching. Without a Steam API key PlayDate still works from local Steam files, but achievements are skipped.</p>`,
            },
            {
                title: 'Appearance and Library',
                body: `<p><strong>Appearance</strong> covers theme colors, background image, and Edit Home Layout. <strong>Library</strong> covers completion sync, duplicate handling and platform priority, launch behavior, artwork sources, and the optional <strong>card tooltip</strong> shown when hovering a cover.</p>`,
            },
            {
                title: 'Tuning',
                body: `<p>Settings → <strong>Tuning</strong> exposes the formulas behind the suggestions with live sliders and graphs: tag similarity, how much to trust reviews with few votes, and the Pick 6 caps and blend. Saving recalculates the stored values. The six Pick 6 signal weights live on the Pick 6 page.</p>`,
            },
            {
                title: 'Advanced and support',
                body: `<p>Advanced has the window-resize tool for Steam Deck and, on Linux, the renderer toggle. It also has <strong>Send Log to Developer</strong> for when something breaks; your API keys are never included.</p>`,
            },
        ],
    },
    {
        id: 'linux-deck',
        title: 'Linux & Steam Deck',
        steps: [
            {
                title: 'Smoother scrolling on NVIDIA',
                body: `<p>On Linux, the default renderer can scroll the library grid choppily on NVIDIA's proprietary driver under Wayland. Settings → Advanced → <strong>Renderer</strong> switches to Qt/QtWebEngine, which fixes it. Source installs download it on demand; Flatpak swaps to a separate Qt build and carries your data over. It isn't offered on Steam Deck.</p>`,
            },
            {
                title: 'Flatpak updates',
                body: `<p>Prefer a <code>--user</code> Flatpak install. A <code>--system</code> install can't update itself from inside PlayDate because it needs administrator approval. If that happens, PlayDate shows the exact command to run yourself.</p>`,
            },
        ],
    },
    {
        id: 'gamepad-settings',
        title: 'Gamepad & Settings',
        steps: [
            {
                title: 'Controls',
                body: `<p>D-pad or the left stick moves focus, A confirms/activates, B backs out or closes a menu. This works the same way everywhere - home shelves, the library grid, every modal.</p>`,
            },
            {
                title: 'Configuring gamepad input',
                body: `<p>Settings → <strong>Gamepad</strong> has the gamepad toggle, button remapping, and a diagnostics view if a controller isn't behaving the way you expect.</p>`,
            },
            {
                title: 'More settings',
                body: `<p>Also worth knowing about: <strong>Appearance</strong> (theme colors, background image) and <strong>Data</strong> (backup/restore, CSV export, imports), under Settings and the hamburger menu.</p>`,
            },
        ],
    },
];

function openTutorialModal(sectionId) {
    document.getElementById('tutorial-modal').style.display = 'flex';
    if (!window._TUTORIAL_SEEN) {
        window._TUTORIAL_SEEN = true;
        fetch('/api/tutorial/seen', { method: 'POST' }).catch(() => {});
    }
    // Always render the ToC first (and size the modal to it, see
    // _tutShowToc()) even when opening straight into a section, so the
    // locked height is always the ToC's own natural height.
    _tutShowToc();
    if (sectionId) {
        _tutShowSection(sectionId, 0);
    }
}

function closeTutorialModal() {
    document.getElementById('tutorial-modal').style.display = 'none';
}

let _tutSection = null;
let _tutStep = 0;

function _tutShowToc() {
    _tutSection = null;
    _tutStep = 0;
    document.getElementById('tutorial-section-view').style.display = 'none';
    document.getElementById('tutorial-toc').style.display = 'block';
    _tutRenderToc();

    // Lock the modal to whatever height the ToC naturally takes up, so
    // switching to a step view (text length varies a lot between steps)
    // never resizes the modal or moves the Back/Sections/Next row.
    // Re-measured every time in case the section count ever changes.
    const modalContent = document.getElementById('tutorial-modal-content');
    modalContent.style.height = 'auto';
    const h = modalContent.getBoundingClientRect().height;
    modalContent.style.height = h + 'px';
}

function _tutRenderToc() {
    const toc = document.getElementById('tutorial-toc');
    toc.innerHTML = TUTORIAL_SECTIONS.map((s, i) =>
        `<button class="settings-item" data-modal-row="${i}" onclick="_tutShowSection('${s.id}')" style="justify-content:center; text-align:center;">${escHtml(s.title)}</button>`
    ).join('');
}

function _tutShowSection(sectionId, stepIndex) {
    const section = TUTORIAL_SECTIONS.find(s => s.id === sectionId);
    if (!section) return;
    _tutSection = section;
    _tutStep = Math.max(0, Math.min(stepIndex || 0, section.steps.length - 1));

    document.getElementById('tutorial-toc').style.display = 'none';
    document.getElementById('tutorial-section-view').style.display = 'flex';

    _tutRenderStep();
}

function _tutRenderStep() {
    const section = _tutSection;
    const step = section.steps[_tutStep];

    document.getElementById('tutorial-step-progress').textContent =
        `${section.title} - Step ${_tutStep + 1} of ${section.steps.length}`;
    document.getElementById('tutorial-step-title').textContent = step.title;
    document.getElementById('tutorial-step-body').innerHTML = step.body;

    document.getElementById('tutorial-next-btn').textContent =
        _tutStep === section.steps.length - 1 ? 'Done' : 'Next';
}

function _tutNext() {
    if (!_tutSection) return;
    if (_tutStep < _tutSection.steps.length - 1) {
        _tutStep++;
        _tutRenderStep();
    } else {
        _tutShowToc();
    }
}

function _tutBack() {
    if (!_tutSection) return;
    if (_tutStep > 0) {
        _tutStep--;
        _tutRenderStep();
    } else {
        _tutShowToc();
    }
}
