#!/usr/bin/env python3
"""
UCLA class seat tracker.

Reads classes.txt, checks each UCLA Schedule of Classes "Class Detail" page,
and sends a phone notification through ntfy.sh when a class opens up
(or a waitlist spot appears). Remembers the last status in state.json.

Uses only Python's standard library -- nothing to install.

Usage:
    python check_classes.py          # normal check
    python check_classes.py --test   # just send a test notification
"""

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLASSES_FILE = ROOT / "classes.txt"
STATE_FILE = ROOT / "state.json"

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

USER_AGENT = "Mozilla/5.0 (personal UCLA class seat checker; checks a few pages every few minutes)"
FAIL_ALERT_AFTER = 3          # warn you after this many failed checks in a row
GOOD_STATES = {"OPEN", "WAITLIST"}


# --------------------------------------------------------------------------- #
# Reading classes.txt
# --------------------------------------------------------------------------- #
def load_classes():
    if not CLASSES_FILE.exists():
        sys.exit("classes.txt is missing.")
    classes = []
    for line_no, raw in enumerate(CLASSES_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            print(f"classes.txt line {line_no}: missing '|' between name and URL -- skipped")
            continue
        name, url = (part.strip() for part in line.split("|", 1))
        if not url.startswith("http"):
            print(f"classes.txt line {line_no}: '{url}' doesn't look like a URL -- skipped")
            continue
        classes.append({"name": name or url, "url": url})
    if not classes:
        sys.exit("classes.txt has no classes in it yet. Add lines like:  Psych 10 Lec 1 | https://sa.ucla.edu/...")
    return classes


# --------------------------------------------------------------------------- #
# Fetching and reading a page
# --------------------------------------------------------------------------- #
def fetch(url):
    last_error = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = e
            time.sleep(3)
    raise RuntimeError(f"couldn't load page: {last_error}")


def html_to_text(page):
    page = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    page = html.unescape(page)
    return re.sub(r"\s+", " ", page).strip()


def _int(m, group=1):
    return int(m.group(group)) if m else None


def parse_status(text):
    """
    Turn the page text into a simple state:
      OPEN      - seats available
      WAITLIST  - class is full but the waitlist has room
      FULL      - class and waitlist full (or no waitlist)
      CLOSED    - closed by department / not open for enrollment
      CANCELLED - section cancelled
      UNKNOWN   - couldn't find the enrollment info on the page
    """
    # Class Detail pages say e.g. "Open: 23 of 216 Left" / "Closed: Class Full (73)"
    status_word = re.search(r"\b(Open|Closed|Waitlist|Cancell?ed|Tentative)\s*:", text, re.I)
    left_of = re.search(r"(\d+)\s+of\s+(\d+)\s+Left", text, re.I)
    enrolled = re.search(r"(\d+)\s+of\s+(\d+)\s+Enrolled", text, re.I)
    spots = re.search(r"(\d+)\s+Spots?\s+Left", text, re.I) or left_of
    class_full = re.search(r"Class\s+Full\s*\((\d+)\)", text, re.I)
    wl_taken = re.search(r"(\d+)\s+of\s+(\d+)\s+Taken", text, re.I)
    wl_full = re.search(r"Waitlist\s+Full\s*\((\d+)\)", text, re.I)
    no_wl = re.search(r"No\s+Waitlist", text, re.I)
    closed_dept = re.search(r"Closed\s+by\s+Dept", text, re.I)
    cancelled = re.search(r"\bCancell?ed\b", text, re.I)

    details = {}
    parts = []
    if enrolled:
        details["enrolled"], details["capacity"] = _int(enrolled, 1), _int(enrolled, 2)
        parts.append(f"{details['enrolled']}/{details['capacity']} enrolled")
    elif class_full:
        details["capacity"] = _int(class_full)
        parts.append(f"class full ({details['capacity']})")
    if spots:
        details["spots_left"] = _int(spots)
        n = details["spots_left"]
        parts.append(f"{n} spot{'s' if n != 1 else ''} left")
    if wl_taken:
        details["waitlist_taken"], details["waitlist_cap"] = _int(wl_taken, 1), _int(wl_taken, 2)
        parts.append(f"waitlist {details['waitlist_taken']}/{details['waitlist_cap']}")
    elif wl_full:
        parts.append(f"waitlist full ({_int(wl_full)})")
    elif no_wl:
        parts.append("no waitlist")

    found_anything = any([status_word, enrolled, spots, class_full, wl_taken, wl_full, closed_dept])
    word = status_word.group(1).lower() if status_word else ""
    wl_room = bool(wl_taken and details["waitlist_taken"] < details["waitlist_cap"])

    if word.startswith("cancel"):
        state = "CANCELLED"
    elif word == "open":
        state = "OPEN"
    elif word == "waitlist":
        state = "WAITLIST"
    elif word == "closed" and closed_dept:
        state = "CLOSED"
        parts.insert(0, "closed by dept")
    elif word == "closed":
        state = "WAITLIST" if wl_room else "FULL"
    elif word == "tentative":
        state = "CLOSED"
        parts.insert(0, "tentative")
    elif cancelled and not (enrolled or spots):
        state = "CANCELLED"
    elif details.get("spots_left", 0) > 0:
        state = "OPEN"
    elif closed_dept:
        state = "CLOSED"
        parts.insert(0, "closed by dept")
    elif wl_taken and details["waitlist_taken"] < details["waitlist_cap"]:
        state = "WAITLIST"
    elif enrolled and details["enrolled"] < details["capacity"] and re.search(r"\bOpen\b", text):
        # Seats free but no "Spots Left" line -- still treat as open
        state = "OPEN"
    elif found_anything:
        state = "FULL"
    else:
        state = "UNKNOWN"

    summary = ", ".join(parts) if parts else "no enrollment info found"
    return state, summary


# --------------------------------------------------------------------------- #
# Notifications (ntfy.sh)
# --------------------------------------------------------------------------- #
def notify(title, message, click_url=None, priority=3, tags=None):
    print(f"  -> NOTIFY: {title} | {message}")
    if not NTFY_TOPIC:
        print("     (NTFY_TOPIC isn't set, so nothing was sent to your phone)")
        return
    payload = {"topic": NTFY_TOPIC, "title": title, "message": message, "priority": priority}
    if tags:
        payload["tags"] = tags
    if click_url:
        payload["click"] = click_url
    req = urllib.request.Request(
        NTFY_SERVER,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
    except Exception as e:  # don't let a notification hiccup crash the run
        print(f"     notification failed: {e}")


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    if "--test" in sys.argv:
        notify("Class tracker test", "If you see this, notifications work! 🎉", priority=3, tags=["white_check_mark"])
        return

    classes = load_classes()
    old_state = load_state()
    new_state = {}
    first_time = []

    for c in classes:
        name, url = c["name"], c["url"]
        prev = old_state.get(url, {})
        print(f"\n{name}\n  {url}")

        try:
            state, summary = parse_status(html_to_text(fetch(url)))
        except Exception as e:
            state, summary = "UNKNOWN", str(e)

        print(f"  status: {state} ({summary})")

        if state == "UNKNOWN":
            fails = prev.get("fails", 0) + 1
            entry = dict(prev, fails=fails)
            if fails == FAIL_ALERT_AFTER:
                notify(f"⚠️ Can't read {name}",
                       f"Failed {fails} checks in a row ({summary}). Check the URL in classes.txt.",
                       click_url=url, priority=3, tags=["warning"])
            new_state[url] = entry
            continue

        new_state[url] = {"name": name, "state": state, "summary": summary, "fails": 0}
        old = prev.get("state")

        if old is None:
            first_time.append(f"{name}: {state} ({summary})")
        elif state != old:
            if state == "OPEN":
                notify(f"🟢 {name} is OPEN", f"{summary}. Go enroll on MyUCLA now!",
                       click_url="https://my.ucla.edu", priority=5, tags=["rotating_light"])
            elif state == "WAITLIST":
                notify(f"🟡 {name}: waitlist spot", f"{summary}. You can join the waitlist on MyUCLA.",
                       click_url="https://my.ucla.edu", priority=4, tags=["hourglass"])
            elif old in GOOD_STATES:
                notify(f"🔴 {name} filled up again", summary, click_url=url, priority=2)
            else:
                print(f"  (changed {old} -> {state}, not alert-worthy)")

        time.sleep(1)  # be polite to UCLA's server

    if first_time:
        notify("Class tracker is watching", "\n".join(first_time), priority=3, tags=["eyes"])

    if new_state != old_state:
        save_state(new_state)
        print("\nSaved new status to state.json")
    else:
        print("\nNo changes.")


if __name__ == "__main__":
    main()
