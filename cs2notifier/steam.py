"""Steam data access: news/update feed, BBCode cleaning, and market prices."""
import html
import re

import requests

NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
PRICE_URL = "https://steamcommunity.com/market/priceoverview/"

HEADERS = {"User-Agent": "cs2-updates-notifier/1.0 (+https://github.com)"}


def fetch_news(app_id="730", count=10, timeout=20):
    """Return the most recent news items for an app (newest first)."""
    resp = requests.get(
        NEWS_URL,
        params={"appid": app_id, "count": count, "maxlength": 0},
        headers=HEADERS,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("appnews", {}).get("newsitems", [])


def is_update(item):
    """True if a news item is an actual game patch (not a generic announcement)."""
    tags = item.get("tags") or []
    if "patchnotes" in tags:
        return True
    title = (item.get("title") or "").lower()
    return "update" in title and "counter-strike" in title


def latest_update(items):
    """First item (newest) that looks like a real patch, or None."""
    for item in items:
        if is_update(item):
            return item
    return None


def bbcode_to_text(raw):
    """Convert Steam's BBCode patch notes into clean, readable plain text.

    Section headers like ``\\[ MISC ]`` are preserved as ``[ MISC ]`` lines so the
    notifier can bold them; list items become bullets.
    """
    if not raw:
        return ""
    s = raw
    # Steam escapes literal brackets used for section headers.
    s = s.replace("\\[", "[").replace("\\]", "]")
    # List items -> bullets.
    s = re.sub(r"\[\*\]", "\n• ", s)
    s = s.replace("[/*]", "")
    # Drop links but keep their visible text.
    s = re.sub(r"\[url=[^\]]*\]", "", s)
    s = s.replace("[/url]", "")
    # Images add nothing useful as text.
    s = re.sub(r"\[img\][^\[]*\[/img\]", "", s)
    # Paragraphs -> newlines.
    s = s.replace("[p]", "\n").replace("[/p]", "\n")
    s = s.replace("[list]", "").replace("[/list]", "")
    # Strip any remaining bbcode tag that starts with a letter (b, i, h1, code, ...).
    # Header lines like "[ MISC ]" have a space after "[" and are NOT removed.
    s = re.sub(r"\[/?[a-zA-Z][^\]]*\]", "", s)
    s = html.unescape(s)

    lines = [ln.strip() for ln in s.splitlines()]

    # A "[*]" bullet followed by a "[p]" lands the marker and its text on separate
    # lines ("•" then "text"); rejoin them.
    merged = []
    i = 0
    while i < len(lines):
        if lines[i] == "•":
            j = i + 1
            while j < len(lines) and lines[j] == "":
                j += 1
            if j < len(lines):
                merged.append("• " + lines[j])
                i = j + 1
                continue
        merged.append(lines[i])
        i += 1

    # Drop blank lines; insert one blank line before each "[ SECTION ]" header.
    out = []
    for ln in merged:
        if ln == "":
            continue
        is_header = ln.startswith("[") and ln.endswith("]")
        if is_header and out:
            out.append("")
        out.append(ln)
    return "\n".join(out).strip()


def get_price(market_hash_name, app_id="730", currency="1", timeout=15):
    """Best-effort live Steam Market price. Returns a dict or None on any failure."""
    try:
        resp = requests.get(
            PRICE_URL,
            params={
                "appid": app_id,
                "currency": currency,
                "market_hash_name": market_hash_name,
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("success"):
            return None
        return {
            "name": market_hash_name,
            "median_price": data.get("median_price"),
            "lowest_price": data.get("lowest_price"),
            "volume": data.get("volume"),
        }
    except (requests.RequestException, ValueError):
        return None
