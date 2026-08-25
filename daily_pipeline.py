"""
The complete daily job: fetch a day's SolisCloud data, save a lightweight
archive, update the site's summary index, build the chart, and (unless
skipped) post it to Mastodon. Runs via GitHub Actions on a schedule - see
.github/workflows/daily.yml - but works identically run by hand or via cron
on a local machine.

Requires these environment variables (from .env locally, or repo secrets
in GitHub Actions):
    SOLIS_KEY_ID, SOLIS_KEY_SECRET, SOLIS_INVERTER_ID, SOLIS_INVERTER_SN
    MASTODON_INSTANCE_URL, MASTODON_ACCESS_TOKEN   (unless --no-post/--preview)

Usage:
    python daily_pipeline.py                # today, posts to Mastodon
    python daily_pipeline.py 2026-08-10      # specific date
    python daily_pipeline.py --no-post       # fetch/archive/chart, skip posting
    python daily_pipeline.py --preview       # fetch/chart only - no archive,
                                              # no summary update, no posting.
                                              # For a quick look without
                                              # touching any saved data.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")  # headless backend - required on CI runners, harmless locally
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
from dotenv import load_dotenv
from matplotlib.colors import LinearSegmentedColormap, Normalize

from solis_auth import solis_post

load_dotenv()

KEY_ID = os.environ.get("SOLIS_KEY_ID")
KEY_SECRET = os.environ.get("SOLIS_KEY_SECRET")
INVERTER_ID = os.environ.get("SOLIS_INVERTER_ID")
INVERTER_SN = os.environ.get("SOLIS_INVERTER_SN")
MASTODON_INSTANCE_URL = os.environ.get("MASTODON_INSTANCE_URL")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

# GitHub Pages URL, used in the Mastodon caption's About link.
SITE_URL = "https://dgplacenames.github.io/solar"

COLOUR_SCALE_MAX_WATTS = 1700
Y_AXIS_MAX_WATTS = 1800
BRIGHT_YELLOW = "#FFFF00"
RED = "#FF0000"
COLOUR_MAP = LinearSegmentedColormap.from_list("yellow_to_red", [BRIGHT_YELLOW, RED])

skip_post = "--no-post" in sys.argv
preview = "--preview" in sys.argv
if preview:
    skip_post = True
args = [a for a in sys.argv[1:] if a not in ("--no-post", "--preview")]
query_date = args[0] if args else date.today().isoformat()



def timezone_offset_for(query_date: str) -> int:
    """UTC offset for a given date (1=BST, 0=GMT), not just 'now'."""
    dt = datetime.strptime(query_date, "%Y-%m-%d").replace(
        tzinfo=ZoneInfo("Europe/London")
    )
    return int(dt.utcoffset().total_seconds() / 3600)


def check_env(need_mastodon: bool = True) -> None:
    required = {
        "SOLIS_KEY_ID": KEY_ID, "SOLIS_KEY_SECRET": KEY_SECRET,
        "SOLIS_INVERTER_ID": INVERTER_ID, "SOLIS_INVERTER_SN": INVERTER_SN,
    }
    if need_mastodon:
        required["MASTODON_INSTANCE_URL"] = MASTODON_INSTANCE_URL
        required["MASTODON_ACCESS_TOKEN"] = MASTODON_ACCESS_TOKEN
    missing = [k for k, v in required.items() if not v]
    if missing:
        sys.exit(f"Missing environment values: {', '.join(missing)}")


def fetch_day(query_date: str) -> list:
    payload = {
        "id": int(INVERTER_ID), "sn": INVERTER_SN,
        "money": "GBP", "time": query_date,
        "timeZone": timezone_offset_for(query_date),
    }
    result = solis_post(KEY_ID, KEY_SECRET, "/v1/api/inverterDay", payload)
    code = str(result.get("code"))
    if code != "0":
        raise RuntimeError(f"SolisCloud error {code}: {result.get('msg')}")
    return result.get("data", [])


def save_archive(query_date: str, points: list) -> str:
    trimmed = [
        {"dataTimestamp": p["dataTimestamp"], "timeStr": p["timeStr"],
         "pac": p["pac"], "eToday": p["eToday"]}
        for p in points
    ]
    os.makedirs("archive", exist_ok=True)
    out_path = os.path.join("archive", f"{query_date}.json")
    with open(out_path, "w") as f:
        json.dump(trimmed, f, separators=(",", ":"))
    return out_path


def update_summary(query_date: str, total_kwh: float, points: list) -> None:
    """Updates data/summary.json, replacing any existing entry for this date."""
    os.makedirs("data", exist_ok=True)
    summary_path = os.path.join("data", "summary.json")

    if os.path.exists(summary_path):
        with open(summary_path) as f:
            rows = json.load(f)
    else:
        rows = []

    first_time = points[0]["timeStr"].split(" ")[1][:5]  # "HH:MM"
    last_time = points[-1]["timeStr"].split(" ")[1][:5]

    rows = [r for r in rows if r["date"] != query_date]
    rows.append({"date": query_date, "kwh": round(total_kwh, 1),
                 "first": first_time, "last": last_time})
    rows.sort(key=lambda r: r["date"])

    with open(summary_path, "w") as f:
        json.dump(rows, f, separators=(",", ":"))


def build_chart(query_date: str, points: list) -> tuple:
    times = [datetime.fromtimestamp(int(p["dataTimestamp"]) / 1000) for p in points]
    watts = [float(p["pac"]) for p in points]

    widths = []
    for i in range(len(times) - 1):
        widths.append((times[i + 1] - times[i]).total_seconds() / 86400)
    widths.append(widths[-1] if widths else timedelta(minutes=5).total_seconds() / 86400)

    total_kwh = float(points[-1]["eToday"])

    norm = Normalize(vmin=0, vmax=COLOUR_SCALE_MAX_WATTS)
    colours = [COLOUR_MAP(norm(w)) for w in watts]

    fig, ax = plt.subplots(figsize=(13, 6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#1f77b4")

    ax.bar(times, watts, width=widths, align="edge", color=colours, edgecolor="none")
    date_obj = datetime.strptime(query_date, "%Y-%m-%d")
    date_str = f"{date_obj.day} {date_obj.strftime('%B %Y')}"
    first_time = points[0]["timeStr"].split(" ")[1][:5]
    last_time = points[-1]["timeStr"].split(" ")[1][:5]

    ax.set_title(
        f"Five Solar Panels in Orkney Generated {total_kwh:.1f} kWh\n"
        f"{first_time}-{last_time} \u00b7 {date_str}",
        color="black")
    ax.set_ylabel("Watts", color="black")
    ax.set_ylim(0, Y_AXIS_MAX_WATTS)
    ax.tick_params(colors="black")
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    ax.tick_params(which="minor", length=4, color="black")
    ax.tick_params(which="major", length=7, color="black")

    day_start = datetime.strptime(query_date, "%Y-%m-%d")
    ax.set_xlim(day_start, day_start + timedelta(days=1))
    ax.grid(True, axis="y", color="white", alpha=0.3)
    for spine in ax.spines.values():
        spine.set_color("black")

    fig.autofmt_xdate()
    plt.tight_layout()

    os.makedirs("images", exist_ok=True)
    out_path = os.path.join("images", f"pac_bars_{query_date}.png")
    plt.savefig(out_path, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path, total_kwh


def post_to_mastodon(image_path: str, caption: str, alt_text: str) -> None:
    with open(image_path, "rb") as f:
        media_resp = requests.post(
            f"{MASTODON_INSTANCE_URL}/api/v2/media",
            headers={"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"},
            files={"file": f},
            data={"description": alt_text},
        )
    media_resp.raise_for_status()
    media_id = media_resp.json()["id"]

    status_resp = requests.post(
        f"{MASTODON_INSTANCE_URL}/api/v1/statuses",
        headers={"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"},
        data={"status": caption, "media_ids[]": media_id},
    )
    status_resp.raise_for_status()
    print(f"Posted: {status_resp.json().get('url')}")


def run_pipeline_for_date(target_date: str, post: bool = True,
                           save: bool = True, late_note: bool = False) -> bool:
    """Fetch, archive, chart, and (optionally) post for target_date. Returns success."""
    if post and os.path.exists(os.path.join("archive", f"{target_date}.json")):
        print(f"{target_date} already archived - skipping to avoid a duplicate Mastodon post.")
        return True

    print(f"Fetching {target_date}...")
    try:
        points = fetch_day(target_date)
    except (requests.exceptions.RequestException, RuntimeError) as e:
        print(f"  Fetch failed: {e}")
        return False

    if not points:
        print(f"  No data points returned for {target_date}.")
        return False
    print(f"  {len(points)} points")

    if save:
        archive_path = save_archive(target_date, points)
        print(f"Archived: {archive_path}")

    chart_path, total_kwh = build_chart(target_date, points)
    print(f"Chart: {chart_path}")

    if save:
        update_summary(target_date, total_kwh, points)
        print(f"Summary updated: {target_date} -> {round(total_kwh, 1)} kWh")
    else:
        print("Preview mode: not touching archive/ or data/summary.json")

    if not post:
        print("Skipping Mastodon post")
        return True

    date_obj = datetime.strptime(target_date, "%Y-%m-%d")
    weekday = date_obj.strftime("%A")
    first_time = points[0]["timeStr"].split(" ")[1][:5]
    last_time = points[-1]["timeStr"].split(" ")[1][:5]
    date_label = f"{weekday} {date_obj.day} {date_obj.strftime('%B %Y')}"
    caption = (f"On {date_label}, my #solarpanels generated {total_kwh:.1f} kWh "
               f"of solar electricity.\n"
               f"Info: {SITE_URL}/about.html")

    alt_text = (
        f"Bar chart of solar power output in watts over the course of "
        f"{date_label}, for five solar panels in Holm, Orkney. Bars are "
        f"coloured yellow to red by intensity, yellow for low output and red "
        f"for high output. The panels generated {total_kwh:.1f} kWh in total, "
        f"active from {first_time} to {last_time}."
    )
    if late_note:
        print("Note: this is a late catch-up post - the scheduled run didn't complete.")
    post_to_mastodon(chart_path, caption, alt_text)
    return True


def main():
    check_env(need_mastodon=not skip_post)
    success = run_pipeline_for_date(query_date, post=not skip_post, save=not preview)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
