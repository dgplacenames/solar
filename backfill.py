"""
Fills in every date from INSTALL_DATE to yesterday that isn't already
archived, posting each to Mastodon. Safe to re-run - already-archived
dates are skipped.

Usage:
    python backfill.py                  # from INSTALL_DATE to yesterday
    python backfill.py 2026-08-12       # override the start date
"""

import os
import sys
import time
from datetime import date, datetime, timedelta

from daily_pipeline import check_env, run_pipeline_for_date

# The first full day of data - install day (11 Aug) had a partial start.
INSTALL_DATE = "2026-08-12"


def daterange(start_str: str, end_str: str):
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    d = start
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def main():
    start_date = sys.argv[1] if len(sys.argv) > 1 else INSTALL_DATE
    end_date = (date.today() - timedelta(days=1)).isoformat()  # yesterday

    if start_date > end_date:
        print(f"Nothing to backfill: start date {start_date} is after "
              f"yesterday ({end_date}).")
        return

    check_env(need_mastodon=True)

    dates = list(daterange(start_date, end_date))
    print(f"Backfilling {len(dates)} day(s): {start_date} to {end_date}\n")

    done, skipped, failed = 0, 0, 0

    for d in dates:
        archive_path = os.path.join("archive", f"{d}.json")
        if os.path.exists(archive_path):
            print(f"{d}: already archived, skipping")
            skipped += 1
            continue

        success = run_pipeline_for_date(d, post=True)
        if success:
            done += 1
        else:
            failed += 1
            print(f"{d}: failed, will need a manual re-run later")

        time.sleep(1)  # be polite to the API between requests

    print(f"\nDone. {done} backfilled, {skipped} already had data, "
          f"{failed} failed.")
    if failed:
        print("Re-run this script to retry the failed date(s) - "
              "already-succeeded days will be skipped automatically.")


if __name__ == "__main__":
    main()
