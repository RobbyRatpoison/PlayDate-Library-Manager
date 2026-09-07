# Contributing

## Reporting Bugs

The quickest way to reach the developer is the [Discord](https://discord.gg/ESqXvFWkFe) or a comment on the [PlayDate thread on SteamGifts](https://www.steamgifts.com/discussion/vxHo8/) — that's where essentially all reports come in. From inside the app, **System → Support → Send Log to Developer** attaches your log plus version/OS info to a report.

GitHub issues also work: include a clear description, steps to reproduce, and your OS and Python version.

## Submitting Changes

1. Fork the repo and create a branch for your change
2. Run the checks below, and manually verify anything they don't cover
3. Open a pull request with a clear description of what you changed and why

## Tests and lint

```bash
pip install -r requirements-dev.txt
pytest tests/       # pure-logic tests (filter tree -> SQL, PAGYWOSG classification, appinfo.vdf parsing, review weighting, ...)
ruff check .        # pyflakes rules only -- unused imports/vars, undefined names
```

CI runs both on every push and pull request to `main`/`dev` (`.github/workflows/tests.yml`, Python 3.11 and 3.14). The test suite deliberately covers pure logic only -- no Flask routes, database, or UI -- so manual verification is still expected for anything outside that. When you touch a tested function (`build_tree_sql`, `is_safe_sql`, `classify_category`, `parse_appinfo`, `review_score_label`, ...), run the suite; when you add a `classify_category` branch or an `OP_REGISTRY` op, add a test case.

## Plugins

Non-Steam library sources (GOG, Epic, EA App, etc.) are **not part of this repo** -- each is its own GitHub repo, installed at runtime like any third-party plugin. To write one, see [`PLUGINS.md`](PLUGINS.md) for the full API and lifecycle.
