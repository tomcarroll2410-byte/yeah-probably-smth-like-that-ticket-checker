#!/usr/bin/env python3
"""
Eventbrite ticket-availability check (single run).
----------------------------------------------------
Meant to be triggered on a schedule (GitHub Actions, cron, etc.) rather
than looped forever in one process.

WHY THIS VERSION: Eventbrite's ticket-availability widget is populated by
client-side JavaScript after the page loads, and ticketing sites commonly
also serve a generic/cached page to requests that don't look like a real
browser. A plain `requests.get()` never sees past either of those, so it
tends to report "sold out" no matter what's actually true. This version
uses a real (headless) browser via Playwright instead, which actually
loads and runs the page the way your phone or laptop browser would.

ONE-TIME LOCAL SETUP (do this once, to test before deploying):
  pip install playwright requests
  playwright install chromium

RUN:
  python3 check_tickets.py

The ntfy topic is read from the NTFY_TOPIC environment variable (falls
back to the placeholder below if unset -- change that placeholder either
way, since ntfy topics aren't private).
"""

import os
import sys

import requests
from playwright.sync_api import sync_playwright

URL = "https://www.eventbrite.ie/e/youth-lates-tickets-2003201998101"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "youth-lates-watch-CHANGE-THIS-RANDOM-STRING")
SOLD_OUT_PHRASES = ("sold out", "ticket sales have ended")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def fetch_rendered_text(url: str, timeout_ms: int = 20000) -> str:
    """Load the page in a real headless browser and return its visible text."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=BROWSER_UA)
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(2000)  # let any last-moment widgets finish rendering
        text = page.inner_text("body")
        browser.close()
        return text


def looks_sold_out(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in SOLD_OUT_PHRASES)


def notify(message: str) -> None:
    print(f"[NOTIFY] {message}")
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Youth Lates tickets may be available!",
                "Priority": "urgent",
                "Tags": "tada",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"  (push notification failed, check the page now anyway: {exc})")


def main() -> int:
    try:
        text = fetch_rendered_text(URL)
    except Exception as exc:
        print(f"check failed, will just try again next scheduled run: {exc}")
        return 0

    sold_out = looks_sold_out(text)
    print("sold out" if sold_out else "NOT sold out \u2014 tickets may be available")

    if not sold_out:
        notify(f"Youth Lates tickets may be available now: {URL}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
