name: Catch-up check

# Safety net for the daily job. Runs every 2 hours from 08:15 UTC onward
# (comfortably after the main job's 06:00 local slot in either BST or
# GMT) and checks whether yesterday's data exists yet - if the 06:00 run
# failed (e.g. SolisCloud was down), this retries and posts late rather
# than silently missing a day. Once yesterday's archive exists, every
# later check is a fast no-op.

on:
  schedule:
    - cron: '15 8-22/2 * * *'
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: solar-data-write
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: pip install -r requirements.txt

      - name: Run catch-up check
        env:
          SOLIS_KEY_ID: ${{ secrets.SOLIS_KEY_ID }}
          SOLIS_KEY_SECRET: ${{ secrets.SOLIS_KEY_SECRET }}
          SOLIS_INVERTER_ID: ${{ secrets.SOLIS_INVERTER_ID }}
          SOLIS_INVERTER_SN: ${{ secrets.SOLIS_INVERTER_SN }}
          MASTODON_INSTANCE_URL: ${{ secrets.MASTODON_INSTANCE_URL }}
          MASTODON_ACCESS_TOKEN: ${{ secrets.MASTODON_ACCESS_TOKEN }}
        run: python catchup_check.py

      - name: Commit and push if anything changed
        run: |
          git config user.name "solar-bot"
          git config user.email "actions@users.noreply.github.com"
          git add images data archive
          git diff --cached --quiet || git commit -m "Catch-up solar update: $(date -u +'%Y-%m-%d %H:%M')"
          git push
