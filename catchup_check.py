"""
Safety net for daily_pipeline.py. Run every 2 hours - if yesterday's
archive is missing (e.g. the 06:00 run failed), retries and posts late.
Once yesterday's data exists, later checks are a fast no-op.

Usage:
    python catchup_check.py
"""

import os
from datetime import date, timedelta

from daily_pipeline import check_env, run_pipeline_for_date

yesterday = (date.today() - timedelta(days=1)).isoformat()
archive_path = os.path.join("archive", f"{yesterday}.json")


def main():
    if os.path.exists(archive_path):
        print(f"{yesterday} already archived - nothing to do.")
        return

    print(f"{yesterday} is missing - attempting catch-up run...")
    check_env(need_mastodon=True)
    success = run_pipeline_for_date(yesterday, post=True, late_note=True)

    if success:
        print(f"Catch-up succeeded for {yesterday}.")
    else:
        print(f"Catch-up failed for {yesterday} - will try again next scheduled run.")


if __name__ == "__main__":
    main()
