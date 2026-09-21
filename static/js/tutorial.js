// -- Tutorial modal --------------------------------------------------------
// Table of contents + per-section step cards. Content authored here is trusted
// static copy (not user/API data), so step bodies are assigned via innerHTML
// to allow basic formatting rather than run through escHtml().

// Links inside step text. Both are plain function declarations (hoisted), so the
// step bodies below can call them from `${...}` in their template strings.
//   tutOpen(action, html)          closes the tutorial and opens a dialog or page (see TUT_ACTIONS)
//   tutGo(sectionId, html, step?)  jumps to another tutorial section, or to one named step of it
function tutOpen(action, html) {
    return `<a class="tut-link" role="button" tabindex="0" data-tut-open="${action}">${html}</a>`;
}
function tutGo(sectionId, html, stepTitle) {
    return `<a class="tut-link" role="button" tabindex="0" data-tut-section="${sectionId}"${stepTitle ? ` data-tut-step="${stepTitle}"` : ''}>${html}</a>`;
}

// A button shown as an Xbox chip and its PlayStation twin, e.g. tutBtn('A', '✕', xboxColor, psColor).
// Colors are the same face-button brand colors the Gamepad Diagnostics screen uses
// (FACE_BTN_COLORS_XBOX / _PS in modal_tools.js); omit them for uncolored buttons.
function tutBtn(xbox, ps, xboxColor, psColor) {
    const chip = (label, color) => `<span class="tut-btn"${color ? ` style="--c:${color}"` : ''}>${label}</span>`;
    return `${chip(xbox, xboxColor)}<span class="tut-btn-sep">/</span>${chip(ps, psColor)}`;
}

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
                         <li>${tutGo('home-shelves', '<strong>Home</strong>')} - curated shelves of games (Recently Played, Unfinished, and whatever else you set up).</li>
                         <li>${tutGo('library-filters', '<strong>Library</strong>')} - your full collection, with filters and bulk tools.</li>
                         <li>${tutGo('pick6', '<strong>Pick 6</strong>')} - a "what should I play next" picker.</li>
                       </ul>
                       <p>Everything else - settings, plugins, emulators, backups - lives behind the hamburger button (☰) in the top-left.</p>`,
            },
            {
                title: 'Adding your games',
                body: `<p><strong>POPULATE PLAYDATE</strong> (hamburger menu) fills your library from your Steam account. It adds any games you own that PlayDate doesn't have yet, which show up right away, and then fills in the details in the background: store data, tags, reviews, cover art, ProtonDB ratings, HowLongToBeat times, and achievements (those need a Steam API key). It skips anything you've removed for good.</p>
                       <p>Populate also runs by itself each time PlayDate starts, so new purchases appear without you doing anything. You can run it yourself from the menu too. While it works, the button becomes a progress bar with a count and an estimated time, and clicking it stops the run.</p>
                       <p>To add one game yourself, even one you don't own, use hamburger menu → ${tutOpen('add-game', '<strong>Add Game</strong>')}: search Steam, or type a name for something that isn't on Steam.</p>`,
            },
            {
                title: 'Launching a game',
                body: `<p>Click a game's cover, on any page, to play it. A Steam game that isn't installed yet gets Steam's install prompt, and games from other stores start through their own plugin or launcher.</p>
                       <p>If you tend to click by accident, turn on ${tutOpen('library', 'Settings → Library')} → <strong>Require double-click to launch/install</strong> so a single click does nothing.</p>`,
            },
            {
                title: 'The right-click menu',
                body: `<p>Right-click any game, on Home, in the Library (grid or list), or in Pick 6, for quick actions without opening it: <strong>Launch</strong> or <strong>Install</strong>, view it in its store, open its achievements or Steam Community Hub (Steam games), set its <strong>completion status</strong> from a submenu, <strong>Edit</strong> it, or <strong>Uninstall</strong> or <strong>Delete</strong> it.</p>
                       <p>Delete asks whether to blacklist the game, so a later Populate doesn't bring it back.</p>`,
            },
            {
                title: 'Gamepad friendly',
                body: `<p>Every menu, modal, and library view in PlayDate can be driven entirely with a gamepad - this app is built with Steam Deck in mind. D-pad/stick to move, A to confirm, B to back out.</p>
                       <p>Gamepad support can be toggled, remapped, or diagnosed from ${tutOpen('gamepad', 'Settings → Gamepad')}.</p>`,
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
                       <p>The filter can be one of PlayDate's built-in quick filters, one of your own saved filters, or a custom filter built just for that shelf. Filters are covered in more detail under ${tutGo('library-filters', 'Library &amp; Filters')}.</p>`,
            },
            {
                title: 'Editing the layout',
                body: `<p>Hamburger menu → ${tutOpen('settings', '<strong>Settings</strong>')} → ${tutOpen('appearance', '<strong>Appearance</strong>')} → ${tutOpen('edit-home', '<strong>Edit Home Layout</strong>')} puts Home into edit mode. On the Home page itself, pressing <strong>E</strong> does the same. <strong>＋ ADD SHELF</strong> adds a shelf, the ⠿ handle drags one to a new spot, and ✕ removes it. <strong>✎ Edit</strong> on a shelf changes what it shows (see the next step).</p>
                       <p>Nothing is kept until you press <strong>SAVE LAYOUT</strong>; <strong>CANCEL</strong> throws your changes away and <strong>RESET</strong> goes back to the default layout.</p>`,
            },
            {
                title: 'What a shelf shows',
                body: `<p>In <strong>✎ Edit</strong>, the <strong>Filter</strong> menu picks which games a shelf draws from: a built-in quick filter (All Games, Installed, Not Installed, Never Played / Unfinished, Beaten / Completed, or a single completion status), one of your ${tutGo('library-filters', '<strong>saved filters</strong>', 'Saved filters')}, or <strong>🔧 Custom Filter…</strong>, which opens the ${tutGo('library-filters', 'Filter Builder', 'Building a filter')} for just that shelf so there's nothing to save. A shelf can also be a widget instead (see ${tutGo('home-shelves', 'Widgets', 'Widgets')}).</p>
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
                body: `<p>By default, a game only shows up on one shelf on your Home page. If a game fits several shelves, it goes on the one with the highest priority, and the other shelves show their next matching games instead.</p>
                       <p><strong>⇅ SHELF PRIORITY</strong> in edit mode lets you drag shelves into the order you want, with the most important shelf at the top.</p>
                       <p>Each shelf also has a switch to turn this off. A shelf with the switch off shows every game that matches its filter, even ones that appear on other shelves, and it never takes a game away from another shelf.</p>`,
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
                title: 'Layouts, sorting and grouping',
                body: `<p>The Library page defaults to a scrolling grid of cover art. <strong>VIEW</strong> changes how it looks and how it's ordered:</p>
                       <ul>
                         <li><strong>Layout</strong> - a Vertical or Horizontal cover grid, or <strong>List</strong>: a compact split-pane with a scrollable row list on the left and a detail and edit pane on the right, good for working through a lot of games quickly.</li>
                         <li><strong>Sort by</strong> - name, hours played, release date, review scores, Metacritic, how long a game takes to beat, achievement progress, tag similarity (how closely a game's tags match ones you've finished), or random. A button flips ascending and descending.</li>
                         <li><strong>Group by</strong> - splits the grid under headings such as install status, completion, release year or platform.</li>
                         <li>A <strong>card size</strong> slider.</li>
                       </ul>`,
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
                       <p>A saved filter can be reloaded from the Library, chosen as the filter for a Home shelf, used to narrow the pool Pick 6 draws from, and shared with other people through ${tutOpen('filter-io', '<strong>Filter Import / Export</strong>')} in the Data menu.</p>`,
            },
            {
                title: 'Selecting games and Bulk Ops',
                body: `<p><strong>Bulk Ops</strong> works on every game matching your current filter, or on just the ones you pick. To pick, choose <strong>Selected games</strong> in the dialog: it closes and the Library goes into select mode. Click covers to select them, then open Bulk Ops again. A <strong>selected ✕</strong> button in the toolbar shows the count and ends select mode.</p>
                       <p>The <strong>Edit</strong> tab changes tags, groups, completion status and other fields on all of them at once. The <strong>Re-scrape</strong> tab re-fetches store data, cover art, HowLongToBeat times, missing metadata and ProtonDB ratings in bulk, and the <strong>Date Importer</strong> tab pulls purchase dates (see ${tutGo('metadata', 'Purchase dates', 'Purchase dates')}).</p>`,
            },
            {
                title: 'Review scores',
                body: `<p>A game can carry several scores. <strong>Review %</strong> is the share of Steam reviews that are positive. <strong>Weighted %</strong> adjusts it for how many reviews there are, pulling scores with few reviews toward 50 so a handful of glowing reviews can't make a game look great (the strength is adjustable under ${tutOpen('tuning', 'Settings → Tuning')}). <strong>Critic %</strong> is the Metacritic score from Steam's store page, when there is one - many games don't have one.</p>
                       <p>You can sort and filter by all of them.</p>`,
            },
            {
                title: 'Card badges, outlines and tooltips',
                body: `<p>${tutOpen('appearance', 'Settings → Appearance')} can show ${tutOpen('card-badges', '<strong>card badges</strong>')} in a cover's corners (platform, installed, achievement %, review score, HowLongToBeat time) and ${tutOpen('card-outlines', '<strong>card outlines</strong>')}: colored borders from rules you put in order, where the first matching rule wins.</p>
                       <p>Under ${tutOpen('library', 'Settings → Library')} you can also turn on a <strong>card tooltip</strong> that shows details when you hover a cover in the grid, and choose which details it includes.</p>`,
            },
        ],
    },
    {
        id: 'pick6',
        title: 'Pick 6',
        steps: [
            {
                title: 'What Pick 6 does',
                body: `<p>Pick 6 answers "what should I play next?" by choosing six games from your library for you. Press <strong>PICK 6</strong> again whenever you want a fresh set. Each pick comes with a short reason, like "matches games you've beaten on Puzzle, Cozy" or "last played 2yr ago".</p>`,
            },
            {
                title: 'Random, Smart and Weighted',
                body: `<p>The mode buttons decide how the six are chosen:</p>
                       <ul>
                         <li><strong>Random</strong> - every game in the pool is equally likely.</li>
                         <li><strong>Smart</strong> - favors games whose tags match ones you've enjoyed (your beaten and completed games, or your most-played if you haven't beaten any yet) and games that are well reviewed. It only considers games at 70% positive reviews or better.</li>
                         <li><strong>Weighted</strong> - you decide how much each factor matters.</li>
                       </ul>
                       <p>Picks are drawn at random in proportion to their score, not simply the top of a ranked list, so you still get variety.</p>`,
            },
            {
                title: 'Weights',
                body: `<p>In Weighted mode, open <strong>Weights</strong> to set how much each factor counts: <strong>Tag Similarity</strong>, <strong>Review Score</strong>, <strong>Staleness</strong> (time since you last played it), <strong>Release Date</strong> and <strong>Length</strong> (from HowLongToBeat). Sliders go from -100 to +100, so you can push against a factor as well as for it, for example to lean toward shorter games or older releases.</p>
                       <p>Factors that can have a hard cut-off also have a limit box. It reads <strong>MIN</strong> while the factor's slider is positive (for example, reviews of at least 70%) and switches to <strong>MAX</strong> when the slider is negative (for example, with Staleness pushed negative, only games played within the last 90 days). The finer details (caps and the blend) are under ${tutOpen('tuning', 'Settings → Tuning')}.</p>`,
            },
            {
                title: 'Choosing the pool',
                body: `<p>Pick 6 only draws from games that pass your settings. Under <strong>Pool</strong>, turn on <strong>Use currently filtered games only</strong> to limit it to your active Library filter, for example only GOG games or only games under 10 hours; click the filter's name to change it. The <strong>Status</strong> buttons choose which completion statuses are eligible: Never Played, Unfinished, Beaten, Completed and Won't Play.</p>`,
            },
        ],
    },
    {
        id: 'editing-games',
        title: 'Editing a Game',
        steps: [
            {
                title: 'The edit panel',
                body: `<p>There are three ways to edit a game:</p>
                       <ul>
                         <li>The <strong>✎ pencil button</strong> on a game card. It's on in the Library by default; under ${tutOpen('appearance', 'Settings → Appearance')} the <strong>Edit Button</strong> section turns it on for Home and Pick 6 and moves it to a different corner.</li>
                         <li><strong>Right-click</strong> a game and choose <strong>Edit</strong>, on any page (see ${tutGo('getting-started', 'The right-click menu', 'The right-click menu')}).</li>
                         <li>In <strong>list view</strong>, editing is built in: select a game in the list and its fields are in the details pane beside it, with Save, Cancel, Sync and Delete buttons.</li>
                       </ul>
                       <p>The edit window has a <strong>Stats</strong> tab (completion status, playtime, dates, achievements, groups) and an <strong>Info</strong> tab (title, developers, tags, review scores, description). Renaming a game makes PlayDate re-resolve its metadata from the new name, and <strong>Open Folder</strong> opens the game's install location in your file manager. Cover art has a section of its own: see ${tutGo('cover-art', 'Cover Art')}.</p>`,
            },
            {
                title: 'Syncing data',
                body: `<p><strong>Sync Steam Data</strong> re-fetches a single game's store data, reviews, and tags. On non-Steam games the button uses that platform's own label.</p>
                       <p><strong>Fill Missing Data</strong> only fills fields that are currently empty (tags, review score, genres, developer, release date), by matching the game to a Steam page or PCGamingWiki. Your own edits and plugin data are never overwritten.</p>`,
            },
            {
                title: 'Duplicate games',
                body: `<p>If you own the same game on more than one platform, say Steam and GOG, PlayDate links the copies together and shows only one of them. The others stay in your library, just hidden.</p>
                       <p>Which copy you see depends on the platform priority list in ${tutOpen('library', 'Settings → Library')}. Drag your preferred platforms to the top and press <strong>Save Order</strong>: for every game, the copy on the highest platform in the list is the one that's shown. <strong>Detect Duplicates</strong> re-checks your library, for example after you add games.</p>
                       <p>PlayDate matches games by name on its own. When it can't, for example because two stores spell a title differently, open either copy and use its <strong>Duplicate of</strong> row to search for the copy on the other platform. From then on they count as one game, and the priority list still decides which one is shown, just as it does for automatic matches. <strong>Unlink</strong> removes a link you made yourself; copies PlayDate matched by name are linked again whenever detection runs.</p>
                       <p>To turn duplicate hiding off completely, untick <strong>Hide duplicate entries</strong> in the same place and every copy is shown.</p>`,
            },
        ],
    },
    {
        id: 'cover-art',
        title: 'Cover Art',
        steps: [
            {
                title: 'Where art comes from',
                body: `<p>Each game has three images: a <strong>vertical</strong> cover, a <strong>horizontal</strong> header, and a small <strong>icon</strong>. PlayDate gets them from a list of sources and tries each in turn until one has art:</p>
                       <ul>
                         <li><strong>Steam</strong> - the store's own images, for Steam games and for other games it can match to a Steam page by name.</li>
                         <li><strong>SteamGridDB</strong> - community-made art. It needs a free API key under ${tutOpen('account', 'Settings → Account')}.</li>
                         <li><strong>Store</strong> - a library's own art, for libraries whose plugin provides it.</li>
                       </ul>
                       <p>Art is saved on your computer and only fetched again when you ask.</p>`,
            },
            {
                title: 'Choosing sources for each library',
                body: `<p>${tutOpen('library', 'Settings → Library')} → <strong>Artwork Sources</strong> lists each library (Steam, and every plugin you've installed). Press <strong>Edit</strong> on one to set the order of sources for its <strong>Vertical</strong>, <strong>Horizontal</strong> and <strong>Icon</strong> art separately. <strong>Store</strong> only appears for the art types that library's plugin can supply.</p>
                       <ul>
                         <li>Drag a source up or down to change the order, or use the ▲ ▼ buttons (handy with a gamepad).</li>
                         <li>Untick a source to never use it for that library. Untick them all and no art is fetched at all.</li>
                         <li><strong>Reset to Default</strong> puts the library back to its normal order.</li>
                       </ul>
                       <p>A new order applies the next time art is fetched: for newly added games, when you re-scrape a game's art, or with Bulk Ops → Re-scrape → Artwork. Art you already have isn't replaced until then.</p>`,
            },
            {
                title: "Changing one game's art",
                body: `<p>In a game's edit window, the cover art area has a tab each for <strong>Vertical</strong>, <strong>Horizontal</strong> and <strong>Icon</strong>. It shows the current image and where it came from (its <strong>Source</strong>). Below it:</p>
                       <ul>
                         <li><strong>Re-scrape</strong> fetches it again using that library's source order.</li>
                         <li><strong>Custom URL</strong> takes an image address or a file on your computer.</li>
                         <li><strong>Browse SGDB</strong> lets you pick from SteamGridDB (needs the API key).</li>
                         <li><strong>Clear</strong> removes the image.</li>
                       </ul>
                       <p>In list view, the details pane's <strong>Art</strong> button opens the same window.</p>`,
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
                         <li><strong>Won't Play</strong> - you've decided not to play it, for whatever reason: it's broken, it's bad, or it just isn't for you.</li>
                       </ul>
                       <p>Pick 6 and tag-similarity sorting learn your taste from the games you mark Beaten or Completed, so keeping those honest gives better suggestions.</p>`,
            },
            {
                title: 'Automatic updates',
                body: `<p>${tutOpen('library', 'Settings → Library')} → <strong>Completion Sync</strong> can promote Never Played to Unfinished once you have playtime, mark a game Completed at 100% achievements, and drop Completed back to Beaten if a developer later adds achievements. Each is a separate toggle.</p>`,
            },
        ],
    },
    {
        id: 'metadata',
        title: 'Metadata',
        steps: [
            {
                title: 'Purchase dates',
                body: `<p>Steam, and some other stores such as GOG and EA, don't expose accurate purchase or activation dates through their APIs. PlayDate can pull them from your account's own order history pages instead, using PlayDate Companion, a browser userscript (needs the Tampermonkey extension). Install it from <a href="https://github.com/RobbyRatpoison/PlayDate-Library-Manager/raw/refs/heads/main/steam_date_import.user.js" target="_blank">GitHub</a>.</p>
                       <p>Libraries whose plugin can read purchase dates directly don't need the script.</p>
                       <p>Click the ↗ next to <strong>Date Added</strong> in a game's edit panel to import one game's date, or use the ${tutOpen('page-library', 'Library page')}'s Bulk Ops → <strong>Date Importer</strong> tab to fetch dates for many games at once.</p>`,
            },
            {
                title: 'HowLongToBeat',
                body: `<p>PlayDate can match your games to HowLongToBeat and store how long each takes to finish. You can then sort and filter by it, for example to find something short for tonight.</p>
                       <p>Hamburger menu → ${tutOpen('hltb', '<strong>HLTB</strong>')} lists matches by confidence. Confident ones are applied automatically. Weaker ones wait for you to confirm, pick another result, or search by hand. <strong>No page</strong> marks a game as having no HLTB entry so it isn't suggested again.</p>
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
                body: `<p>Some categories only count games <em>verified</em> for a specific player. Set your SteamGifts username in ${tutOpen('account', 'Settings → Account')} so PlayDate can tell which verified entries are actually yours.</p>`,
            },
            {
                title: 'Building a filter',
                body: `<p>Open the ${tutOpen('pagywosg', 'PAGYWOSG tool')} from the hamburger menu's ${tutOpen('community', '<strong>Community Tools</strong>')} section, pick the event, and PlayDate assembles and saves a filter matching that month's rules - ready to use like any other saved filter.</p>`,
            },
            {
                title: 'Secret Santa and Snowball gifts',
                body: `<p>Games you received in the Discord Secret Santa or Snowball events count as PAGYWOSG wins, even though you didn't win them on SteamGifts. ${tutOpen('santa', '<strong>Secret Santa / Snowballs</strong>')} (in ${tutOpen('community', 'Community Tools')}) is where you list them: find a single game, or add every game from a group at once.</p>
                       <p>Then tick <strong>Include Secret Santa / Snowballs gifts</strong> in the PAGYWOSG filter builder to add those games to the wins pool.</p>`,
            },
        ],
    },
    {
        id: 'blaeo',
        title: 'BLAEO',
        steps: [
            {
                title: 'What is BLAEO?',
                body: `<p>BLAEO (Backlog Assassins Extraordinaire) is a community site for tracking your backlog completion status and custom lists. If you keep it up to date, PlayDate can sync those changes into your library instead of you re-entering them by hand.</p>`,
            },
            {
                title: 'Running a sync',
                body: `<p>Open the hamburger menu's ${tutOpen('community', '<strong>Community Tools</strong>')} section and click <strong>Sync BLAEO</strong>. PlayDate fetches your BLAEO profile and shows a preview of proposed changes - completion status updates, list renames, additions, and removals.</p>`,
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
                body: `<p>${tutOpen('community', 'Community Tools')} → <strong>Sync SteamGifts Wins</strong> imports your giveaway wins and tags received ones with a "Won on SteamGifts" group. It needs the PlayDate Companion userscript, because SteamGifts blocks direct scraping.</p>
                       <p>A normal sync is incremental. <strong>Full refresh</strong> re-checks every win and prunes stale ones. Wins that don't match a library game are listed with a reason, and some can be adopted in one click.</p>`,
            },
            {
                title: 'Play or Pay',
                body: `<p>${tutOpen('community', 'Community Tools')} → <strong>Sync Play or Pay Picks</strong> pulls the current picks into a saved filter, and cleans up groups left over from earlier cycles.</p>`,
            },
            {
                title: 'Monthly in a Month',
                body: `<p>The ${tutOpen('miam', '<strong>Monthly in a Month</strong>')} builder makes a filter for candidate games by completion status, and can check them against the community sheet.</p>`,
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
                body: `<p>Hamburger menu → ${tutOpen('plugins', '<strong>Plugins</strong>')} has a <strong>Plugin Catalog</strong> where each official plugin installs with one click. It's sorted into Working, Untested, and Broken for the OS you're running, based on real reports. You can also install a third-party plugin from a zip file or a GitHub URL.</p>
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
                body: `<p>Own the same game on two platforms? PlayDate links the copies and shows only one, chosen by your platform priority order. See ${tutGo('editing-games', 'Duplicate games', 'Duplicate games')} for how to set that order, link copies by hand, or turn it off.</p>`,
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
                body: `<p>Hamburger menu → ${tutOpen('emulators', '<strong>Emulators</strong>')} - pick a platform from the list to use a common preset, or add a custom entry pointing at your own emulator binary.</p>`,
            },
        ],
    },
    {
        id: 'cleanup',
        title: 'Blacklist & Junk Finder',
        steps: [
            {
                title: 'Removing games for good',
                body: `<p>When you delete a game (right-click → Delete, or the Delete button in its edit window or list view), PlayDate asks you to confirm and then asks whether to <strong>blacklist</strong> it too. <strong>Blacklist and Delete</strong> means Populate skips the game from then on. Plain <strong>Delete</strong> leaves it free to come back the next time Populate runs, for example if it's still in your Steam library.</p>
                       <p>Hamburger menu → ${tutOpen('blacklist', '<strong>Blacklist / Junk Finder</strong>')} shows the blacklist, and you can remove entries from it to allow those games back.</p>`,
            },
            {
                title: 'Find Library Junk',
                body: `<p>Imports sometimes pull in soundtracks, DLC, dev kits, and store apps. <strong>Find Library Junk</strong> scans for them by title pattern across every platform. Its <strong>Deep Plugin Scan</strong> re-checks a platform against its store, which is slower, so it's kept separate from the quick scan. Review the results and remove what you don't want.</p>`,
            },
            {
                title: 'Duplicate entries',
                body: `<p>${tutOpen('library', 'Settings → Library')} → <strong>Find Duplicate Entries</strong> catches one store game imported twice, usually claimed in two bundles. This is separate from cross-platform duplicates (see ${tutGo('editing-games', 'Duplicate games', 'Duplicate games')}).</p>`,
            },
        ],
    },
    {
        id: 'data',
        title: 'Backup & Data',
        steps: [
            {
                title: 'Backup and restore',
                body: `<p>Hamburger menu → ${tutOpen('data', '<strong>Data</strong>')} → ${tutOpen('backup', '<strong>Backup &amp; Restore</strong>')} saves your library and settings to one zip you can restore later. PlayDate offers a backup before updating unless you made one in the last 24 hours.</p>`,
            },
            {
                title: 'Imports and exports',
                body: `<p>The Data menu also imports from another SQLite database, exports your library to CSV with the columns you choose, and shares saved filters through ${tutOpen('filter-io', '<strong>Filter Import / Export</strong>')}.</p>
                       <p>${tutOpen('playnite', '<strong>Import from Playnite</strong>')} reads a Playnite backup and shows what it contains before you commit. You choose which of <strong>date added</strong>, <strong>last played</strong> and <strong>time played</strong> to bring in, and whether to only fill in blanks or replace values PlayDate already has.</p>`,
            },
        ],
    },
    {
        id: 'settings',
        title: 'Settings Tour',
        steps: [
            {
                title: 'Account',
                body: `<p>${tutOpen('account', 'Settings → Account')} holds your Steam API key and SteamID, SteamGridDB key, SteamGifts username, and account switching. Without a Steam API key PlayDate still works from local Steam files, but achievements are skipped.</p>
                       <p>Each Steam account you add has its own game library, so switching accounts switches your whole collection. Add another with <strong>+ Add Account</strong>.</p>`,
            },
            {
                title: 'Appearance and Library',
                body: `<p>${tutOpen('appearance', '<strong>Appearance</strong>')} covers theme colors, background image, and Edit Home Layout. ${tutOpen('library', '<strong>Library</strong>')} covers completion sync, duplicate handling and platform priority, launch behavior, ${tutGo('cover-art', 'artwork sources', 'Choosing sources for each library')}, and the optional <strong>card tooltip</strong> shown when hovering a cover.</p>`,
            },
            {
                title: 'Tuning',
                body: `<p>Most people never need to touch this. ${tutOpen('tuning', 'Settings → <strong>Tuning</strong>')} holds the numbers behind PlayDate's calculated scores, each with a slider and a live graph of what it does, in three sections:</p>
                       <ul>
                         <li><strong>Tag Similarity</strong> - scores each game by how closely its tags match the games you've beaten or completed. It powers the Tag Similarity sort in the Library and Home, and it's the same taste profile Pick 6 uses.</li>
                         <li><strong>Review Scores</strong> - how many reviews a game needs before its Weighted % is trusted. Scores with fewer reviews are pulled toward 50.</li>
                         <li><strong>Pick 6 Scoring</strong> - how Pick 6 turns a game's staleness, release age and length into a score, and how Smart mode blends its factors.</li>
                       </ul>
                       <p>Saving Tag Similarity or Review Scores recalculates the stored scores for your whole library, with no re-scraping. The Pick 6 factor weights themselves live on the ${tutOpen('page-pick', 'Pick 6 page')}.</p>`,
            },
            {
                title: 'Advanced settings',
                body: `<p>${tutOpen('advanced', 'Settings → Advanced')} holds a few settings most people rarely change:</p>
                       <ul>
                         <li><strong>Auto-check updates</strong> - whether PlayDate looks for a new version on its own. You can always check by hand from the hamburger menu.</li>
                         <li><strong>Beta updates</strong> - opt in to test builds before they're released to everyone. They can be rough, so it's off by default.</li>
                         <li><strong>Renderer</strong> (Linux only) - switch to an alternate renderer that smooths choppy scrolling on some NVIDIA setups. See ${tutGo('linux-deck', 'Smoother scrolling on NVIDIA', 'Smoother scrolling on NVIDIA')}.</li>
                         <li><strong>Send Log to Developer</strong> - sends PlayDate's log and diagnostic details about your setup when something breaks. Your API keys are never included.</li>
                       </ul>`,
            },
        ],
    },
    {
        id: 'linux-deck',
        title: 'Linux & Steam Deck',
        steps: [
            {
                title: 'Smoother scrolling on NVIDIA',
                body: `<p>On Linux, the default renderer can scroll the library grid choppily on NVIDIA's proprietary driver under Wayland. ${tutOpen('advanced', 'Settings → Advanced')} → <strong>Renderer</strong> switches to Qt/QtWebEngine, which fixes it. Source installs download it on demand; Flatpak swaps to a separate Qt build and carries your data over. It isn't offered on Steam Deck.</p>`,
            },
            {
                title: 'Flatpak updates',
                body: `<p>Prefer a <code>--user</code> Flatpak install. A <code>--system</code> install can't update itself from inside PlayDate because it needs administrator approval. If that happens, PlayDate shows the exact command to run yourself.</p>`,
            },
        ],
    },
    {
        id: 'gamepad-settings',
        title: 'Gamepad',
        steps: [
            {
                title: 'Controls',
                body: `<p>The controls work the same way on every page and in every dialog. Each button is shown as its Xbox name with the PlayStation equivalent beside it:</p>
                       <ul>
                         <li><strong>D-pad</strong> or the <strong>left stick</strong> - move focus.</li>
                         <li>${tutBtn('A', '✕', '#3bb143', '#3a7bd5')} - confirm or activate. On a game, this launches it.</li>
                         <li>${tutBtn('B', '○', '#e0393e', '#e0393e')} - back out, or close a dialog.</li>
                         <li>${tutBtn('X', '□', '#3a7bd5', '#e05fa0')} - open the right-click menu for the focused game.</li>
                         <li>${tutBtn('Y', '△', '#f4c20d', '#3bb143')} - edit the focused game.</li>
                         <li>${tutBtn('Start', 'Options')} - launch the focused game, the same as A.</li>
                         <li>${tutBtn('Back', 'Share')} - open or close the hamburger menu.</li>
                         <li>${tutBtn('LB', 'L1')} and ${tutBtn('RB', 'R1')} - go to the previous or next page (Home, Library, Pick 6). They don't do anything while a dialog is open.</li>
                       </ul>`,
            },
            {
                title: 'Configuring gamepad input',
                body: `<p>${tutOpen('gamepad', 'Settings → <strong>Gamepad</strong>')} has the gamepad toggle, button remapping, and a diagnostics view if a controller isn't behaving the way you expect.</p>`,
            },
        ],
    },
];

// What each tutOpen() link does. The tutorial closes first (it sits above every
// other dialog), then the target opens. Only dialogs that exist on every page.
const TUT_ACTIONS = {
    // Settings and its sub-dialogs
    'settings':      () => openSettingsModal(),
    'account':       () => openAccountModal(),
    'appearance':    () => openAppearanceModal(),
    'library':       () => openLibraryModal(),
    'gamepad':       () => openGamepadModal(),
    'tuning':        () => openTuningModal(),
    'advanced':      () => openAdvancedModal(),
    'card-badges':   () => openCardBadgesModal(),
    'card-outlines': () => openCardOutlinesModal(),
    'send-log':      () => openSendLogModal(),
    // Hamburger menu tools
    'add-game':      () => openAddGameModal(),
    'plugins':       () => openPluginsModal(),
    'data':          () => openDataModal(),
    'emulators':     () => openEmulatorsModal(),
    'blacklist':     () => openBlacklistModal(),
    'hltb':          () => openHltbModal(),
    'community':     () => openCommunityModal(),
    // Inside Data / Community Tools / filters
    'backup':        () => openBackupModal(),
    'playnite':      () => openPlayniteModal(),
    'filter-io':     () => openFilterIoModal(),
    'pagywosg':      () => openPagModal(),
    'miam':          () => openMiamModal(),
    'santa':         () => openSantaModal(),
    'filters':       () => openFilterModal(),
    // Pages
    'edit-home':     () => { window.location.href = '/?edit=1'; },
    'page-home':     () => { window.location.href = '/'; },
    'page-library':  () => { window.location.href = '/library'; },
    'page-pick':     () => { window.location.href = '/pick'; },
};

function _tutRunAction(key) {
    const run = TUT_ACTIONS[key];
    if (!run) { console.warn('tutorial link: unknown action', key); return; }
    closeTutorialModal();
    setTimeout(() => {
        try { run(); } catch (e) { console.error('tutorial link failed:', key, e); }
    }, 0);
}

function _tutFollowSectionLink(a) {
    const section = TUTORIAL_SECTIONS.find(s => s.id === a.dataset.tutSection);
    if (!section) return;
    const step = a.dataset.tutStep ? section.steps.findIndex(s => s.title === a.dataset.tutStep) : 0;
    _tutShowSection(section.id, Math.max(0, step));
}

// One delegated handler for every link in every step (mouse, Enter/Space, gamepad A).
document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('#tutorial-modal a.tut-link');
    if (!a) return;
    e.preventDefault();
    if (a.dataset.tutSection) _tutFollowSectionLink(a);
    else if (a.dataset.tutOpen) _tutRunAction(a.dataset.tutOpen);
});
document.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('#tutorial-modal a.tut-link')) {
        e.preventDefault();
        e.target.click();
    }
});

function openTutorialModal(sectionId) {
    document.getElementById('tutorial-modal').style.display = 'flex';
    if (!window._TUTORIAL_SEEN) {
        window._TUTORIAL_SEEN = true;
        fetch('/api/tutorial/seen', { method: 'POST' }).catch(() => {});
    }
    // A fresh open starts with an empty search.
    _tutQuery = '';
    const searchEl = document.getElementById('tutorial-search');
    if (searchEl) searchEl.value = '';
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
let _tutQuery = '';

function _tutShowToc() {
    _tutSection = null;
    _tutStep = 0;
    document.getElementById('tutorial-section-view').style.display = 'none';
    document.getElementById('tutorial-toc-view').style.display = 'flex';

    // Lock the modal to whatever height the ToC naturally takes up, so
    // switching to a step view (text length varies a lot between steps)
    // never resizes the modal or moves the Back/Sections/Next row.
    // Measured with the FULL list (search set aside), so a filtered list
    // can't shrink the modal; the filter is re-applied right after.
    const query = _tutQuery;
    _tutQuery = '';
    _tutRenderToc();
    const modalContent = document.getElementById('tutorial-modal-content');
    modalContent.style.height = 'auto';
    const h = modalContent.getBoundingClientRect().height;
    modalContent.style.height = h + 'px';
    _tutQuery = query;
    _tutRenderToc();
}

// ── Search ────────────────────────────────────────────────────────────────────
// Plain text of every step (title + body without tags), lowercased, built once.
let _tutIndex = null;

function _tutBuildIndex() {
    const tmp = document.createElement('div');
    _tutIndex = TUTORIAL_SECTIONS.map(s => ({
        title: s.title.toLowerCase(),
        steps: s.steps.map(st => {
            tmp.innerHTML = st.body;
            return (st.title + ' ' + tmp.textContent).toLowerCase();
        }),
    }));
}

// Search terms: whitespace-separated words, all of which a section must contain.
function _tutTerms() {
    return _tutQuery.toLowerCase().split(/\s+/).filter(Boolean);
}

// For section index i: null if it doesn't match the current search, else
// {hits: how many steps match, first: index of the first such step}. A step
// "matches" when it has every term; if no single step has them all (the words
// are spread across steps), it falls back to steps that have any term.
function _tutMatch(i) {
    const terms = _tutTerms();
    if (!terms.length) return { hits: 0, first: 0 };
    if (!_tutIndex) _tutBuildIndex();
    const idx = _tutIndex[i];
    const all = idx.title + ' ' + idx.steps.join(' ');
    if (!terms.every(t => all.includes(t))) return null;
    let steps = idx.steps.map((text, n) => n).filter(n => terms.every(t => idx.steps[n].includes(t)));
    if (!steps.length) steps = idx.steps.map((text, n) => n).filter(n => terms.some(t => idx.steps[n].includes(t)));
    return { hits: steps.length, first: steps.length ? steps[0] : 0 };
}

function _tutRenderToc() {
    const toc = document.getElementById('tutorial-toc');
    const searching = _tutTerms().length > 0;
    const rows = [];
    TUTORIAL_SECTIONS.forEach((s, i) => {
        const m = _tutMatch(i);
        if (!m) return;
        const count = searching && m.hits ? `<span class="tut-count">${m.hits} ${m.hits === 1 ? 'step' : 'steps'}</span>` : '';
        rows.push(`<button class="settings-item" data-modal-row="${rows.length + 1}" onclick="_tutShowSection('${s.id}')" style="justify-content:center; text-align:center;">${escHtml(s.title)}${count}</button>`);
    });
    toc.innerHTML = rows.length
        ? rows.join('')
        : `<div style="text-align:center; color:var(--text-secondary); padding:22px 8px; font-size:0.9rem;">No sections match "${escHtml(_tutQuery.trim())}".</div>`;
}

function _tutSearch(value) {
    _tutQuery = value;
    _tutRenderToc();
}

// Enter in the search box opens the first matching section.
function _tutSearchKey(e) {
    if (e.key !== 'Enter') return;
    const first = document.querySelector('#tutorial-toc .settings-item');
    if (first) first.click();
}

// Wrap every occurrence of a search term under `root` in <mark class="tut-hl">.
// Walks text nodes only, so tags and attributes are never touched.
function _tutHighlight(root) {
    const terms = _tutTerms();
    if (!terms.length || !root) return;
    const escaped = terms.sort((a, b) => b.length - a.length).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const re = new RegExp('(' + escaped.join('|') + ')', 'gi');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
        const text = node.nodeValue;
        re.lastIndex = 0;
        if (!re.test(text)) return;
        re.lastIndex = 0;
        const frag = document.createDocumentFragment();
        let last = 0, m;
        while ((m = re.exec(text)) !== null) {
            if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
            const mark = document.createElement('mark');
            mark.className = 'tut-hl';
            mark.textContent = m[0];
            frag.appendChild(mark);
            last = m.index + m[0].length;
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(frag, node);
    });
}

function _tutShowSection(sectionId, stepIndex) {
    const i = TUTORIAL_SECTIONS.findIndex(s => s.id === sectionId);
    if (i < 0) return;
    const section = TUTORIAL_SECTIONS[i];
    _tutSection = section;
    // Coming from a search, open on the first step that actually has the term.
    const start = stepIndex !== undefined ? stepIndex : (_tutMatch(i) || { first: 0 }).first;
    _tutStep = Math.max(0, Math.min(start || 0, section.steps.length - 1));

    document.getElementById('tutorial-toc-view').style.display = 'none';
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
    _tutHighlight(document.getElementById('tutorial-step-title'));
    _tutHighlight(document.getElementById('tutorial-step-body'));
    // Gamepad navigation only sees elements with data-modal-row: give each link its own
    // row, in reading order and ahead of the Back / Sections / Next row (9).
    document.querySelectorAll('#tutorial-step-body a.tut-link').forEach((a, i) => {
        a.dataset.modalRow = String(1 + (i + 1) / 100);
    });

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
