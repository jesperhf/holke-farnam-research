# Holke-Farnam Research

A static investment journal with a live business cycle tracker. It is hosted free on GitHub Pages, and a scheduled GitHub Action refreshes the data and republishes the site every morning.

## What is in here

| Path | What it is |
| --- | --- |
| `content/journal/` | Journal entries in Markdown. One file per entry, with the date, title, summary, stance and tickers at the top. |
| `content/updates/` | Dated updates to past entries. Entries themselves are never edited after publishing. |
| `content/calls.json` | Every published call (price at publication, bear, base and bull values, buy level). Add rows; never edit old ones. |
| `content/positions.json` | Your positions as percentages of the portfolio, with average cost, base value (`target`), the model's value-by-discount-rate curve (`valueCurve`, `requiredReturn`) for the live return column, exit levels (`trimAbove`, `exitBelow`, `exitPlan`), closed positions and a trade log. Base values and curves come from each holding's workbook in `models/holdings/` (the `model` field links it). Drives the Positions page and every entry's disclosure. Never put dollar amounts or share counts here. |
| `content/site.json` | Site name, tagline, bio and links. |
| `models/` | The Excel workbooks offered for download. |
| `data/cycle.json` | Business cycle reading and history, rewritten daily from FRED. |
| `data/prices.json` | Latest prices for the scorecard, rewritten daily (best effort). |
| `scripts/update_data.py` | Pulls FRED series and prices. Standard library only. |
| `tools/import_schwab.py` | Converts a Schwab positions export into `positions.json`, writing percentages only. The CSV itself is never committed. |
| `scripts/build.py` | Turns everything above into the site in `_site/`. Needs `pip install markdown`. |
| `.github/workflows/site.yml` | The daily job: refresh data, build, publish. |

## One-time setup (about 15 minutes)

1. **Create a GitHub account** if you don't have one, then a new public repository (for example `holke-farnam-research`).
2. **Upload these files** to the repository, keeping the folder structure. The `.github` folder must come along; it is hidden on a Mac, so press Cmd+Shift+. in Finder to see it.
3. **Turn on Pages.** In the repository go to Settings > Pages and set Source to "GitHub Actions".
4. **Allow the job to save data.** Settings > Actions > General > Workflow permissions: choose "Read and write permissions".
5. **Run it once.** Actions tab > "Update data and publish site" > Run workflow. The first run pulls about 35 years of FRED data, replaces the October 19 seed reading, and fills in the history chart. After that it runs every morning on its own.
6. **Optional, recommended: a FRED API key.** The job works without one using FRED's public CSV downloads. A free key (fred.stlouisfed.org > My Account > API Keys) is more reliable. Add it under Settings > Secrets and variables > Actions as `FRED_API_KEY`.
7. **Optional: your own domain.** Buy a domain (for example holkefarnamresearch.com), then add it under Settings > Pages > Custom domain and follow GitHub's DNS instructions. Put the final address in `content/site.json` as `url` so the RSS feed links correctly.

## Before you share the link

- Load your positions into `content/positions.json` (run `tools/import_schwab.py` on a Schwab export, or ask Claude to do it). Until a snapshot is loaded, every entry shows a "disclosure not yet confirmed" line.
- Read the bio in `content/site.json` and change anything you don't want public.
- If you want to say how the research is produced, write it in `process_note` in `content/site.json`; it appears on the About page.

## Adding a new entry

1. Copy an existing file in `content/journal/`, rename it `YYYY-MM-DD-short-name.md`, and change the header lines (`slug` must match the short name).
2. Add any new calls as new rows in `content/calls.json` with today's date and price.
3. Commit. The site rebuilds within a couple of minutes.

## Preview on your own computer

```
pip install markdown
python scripts/build.py
python -m http.server --directory _site 8000
```

Then open http://localhost:8000.

## Notes on the data

- Cycle indicators come from FRED. The ISM manufacturing index is not on FRED and is licensed, so the tracker uses the Chicago Fed National Activity Index instead.
- The history line uses today's revised data aligned to the month measured, so it reads cleaner than what was known in real time.
- Prices come from Yahoo Finance's public chart data, with Stooq as a fallback. Any symbol that fails is listed under `errors` in `data/prices.json`. To set a price by hand, add `"manual": true` to its entry and the daily job will keep it.
