# Holm Solar

Daily solar generation tracker for a small home installation in Holm,
Orkney. Fetches data from a Solis inverter's cloud API once a day, builds
a chart, archives the figures, posts the result to Mastodon, and publishes
a small dashboard via GitHub Pages.

Live site: https://dgplacenames.github.io/solar

## How it works

Three GitHub Actions workflows do all the work:

- **`.github/workflows/daily.yml`** - runs at 06:00 local time (two cron
  entries approximate the BST/GMT switch, since Actions schedules always
  run in UTC), processing *yesterday's* data - SolisCloud retains it
  reliably by then, avoiding any question of whether generation had
  finished for the day. Fetches the data, archives it, builds the chart,
  posts to Mastodon, commits the results back to the repo.
- **`.github/workflows/catchup.yml`** - runs every 2 hours as a safety
  net. If the daily run failed (e.g. SolisCloud was down), this retries
  and posts late with a note. Once a day's data exists, later checks are
  a fast no-op.
- **`.github/workflows/backfill.yml`** - manual only, run once from the
  Actions tab to fill in history from install date onward, posting each
  day to Mastodon.

## Repo layout

```
daily_pipeline.py      Main script - fetch, archive, chart, post
catchup_check.py        Safety-net retry job
backfill.py              One-off historical backfill
solis_auth.py            SolisCloud API request signing
discover_inverter.py     One-off setup: finds your inverter ID/SN
check_retention.py       Diagnostic: checks how far back SolisCloud data goes
index.html, gallery.html, about.html, styles.css, overview.js, gallery.js
                          The site itself
data/summary.json        Per-day index the site reads: date, kwh, first/last
                          generation time
images/                  Daily chart PNGs (same ones posted to Mastodon)
archive/                 Detailed per-day readings (~5 min intervals)
```

## Local setup

```
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
python discover_inverter.py   # one-off, gets your INVERTER_ID/SN
python daily_pipeline.py --preview   # quick look, no side effects
python daily_pipeline.py --no-post   # full run, skip Mastodon
```

## GitHub setup

1. **Repo secrets** (Settings -> Secrets and variables -> Actions):
   `SOLIS_KEY_ID`, `SOLIS_KEY_SECRET`, `SOLIS_INVERTER_ID`,
   `SOLIS_INVERTER_SN`, `MASTODON_INSTANCE_URL`, `MASTODON_ACCESS_TOKEN`
2. **Actions permissions**: Settings -> Actions -> General -> Workflow
   permissions -> "Read and write permissions" (needed so the workflows
   can commit new charts/data back to the repo).
3. **Pages**: Settings -> Pages -> Deploy from branch -> `main` / root.
4. Run **Backfill historical data** once manually from the Actions tab.
5. The daily and catch-up workflows then take over automatically.

## Notes

- `eToday` from the API only reports to 0.1 kWh precision - all figures
  are formatted to one decimal place throughout, since showing more would
  imply false precision.
- Chart colour and axis scales are fixed (not auto-scaled per day/month/
  year) so any two periods are genuinely comparable - a pale bar always
  means low output, not just "the weakest of what's shown right now."
