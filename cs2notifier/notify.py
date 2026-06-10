"""Telegram delivery: format an update + analysis into messages and send them."""
import html as _html

import requests

from .analyze import ARROWS

TG_SEND = "https://api.telegram.org/bot{token}/sendMessage"
TG_GETUPDATES = "https://api.telegram.org/bot{token}/getUpdates"
TG_LIMIT = 4096  # Telegram hard cap per message.


def _esc(text):
    return _html.escape(text or "", quote=False)


def _format_body(clean_contents):
    """Patch notes -> Telegram HTML, bolding [ SECTION ] header lines."""
    out = []
    for line in clean_contents.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            out.append(f"<b>{_esc(stripped)}</b>")
        else:
            out.append(_esc(line))
    return "\n".join(out)


def _format_analysis(analysis):
    lines = ["", "━━━━━━━━━━━━━━━", "💹 <b>Price impact analysis</b>"]

    claude = analysis.get("claude")
    if claude and isinstance(claude, dict):
        if claude.get("summary"):
            lines.append(f"<i>{_esc(claude['summary'])}</i>")
        for f in claude.get("findings", []) or []:
            arrow = ARROWS.get(str(f.get("direction", "neutral")).lower(), "➖")
            mag = f.get("magnitude")
            conf = f.get("confidence")
            tags = " ".join(
                t for t in (f"mag:{mag}" if mag else "", f"conf:{conf}" if conf else "") if t
            )
            lines.append(f"\n{arrow} <b>{_esc(str(f.get('target','')))}</b>"
                         + (f"  <i>({_esc(tags)})</i>" if tags else ""))
            if f.get("reason"):
                lines.append(_esc(str(f["reason"])))
        lines.append("\n<i>— AI analysis (Claude)</i>")
    else:
        # Heuristics-only view.
        for f in analysis.get("heuristics", []):
            arrow = ARROWS.get(f["direction"], "➖")
            lines.append(f"\n{arrow} <b>{_esc(f['target'])}</b>  <i>(conf:{_esc(f['confidence'])})</i>")
            lines.append(_esc(f["reason"]))
        lines.append("\n<i>— rule-based heuristics</i>")

    prices = analysis.get("prices") or []
    if prices:
        lines.append("\n💲 <b>Current Steam Market prices</b>")
        for p in prices:
            price = p.get("median_price") or p.get("lowest_price") or "n/a"
            vol = f" (vol {p['volume']})" if p.get("volume") else ""
            lines.append(f"• {_esc(p['name'])}: <b>{_esc(price)}</b>{_esc(vol)}")

    return "\n".join(lines)


def build_message(update, analysis):
    title = update.get("title", "Counter-Strike 2 Update")
    when = update.get("date_str", "")
    header = f"🔫 <b>{_esc(title)}</b>"
    if when:
        header += f"\n🕒 {_esc(when)}"
    body = _format_body(update.get("clean_contents", ""))
    footer = f'\n\n<a href="{_esc(update.get("url",""))}">Full patch notes »</a>'
    analysis_block = _format_analysis(analysis) if analysis else ""
    return f"{header}\n\n{body}\n{analysis_block}{footer}"


def _chunk(text, limit=TG_LIMIT):
    """Split a long message on line boundaries, keeping each piece under the limit."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        # A single very long line: hard-split it.
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def send_telegram(token, chat_id, text, timeout=20):
    """Send (chunked) HTML message. Returns True on full success."""
    ok = True
    for piece in _chunk(text):
        resp = requests.post(
            TG_SEND.format(token=token),
            json={
                "chat_id": chat_id,
                "text": piece,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        if not resp.ok:
            ok = False
            print(f"[notify] Telegram error {resp.status_code}: {resp.text[:300]}")
    return ok


def get_chat_ids(token, timeout=20):
    """Helper for setup: list chat ids that have messaged the bot."""
    resp = requests.get(TG_GETUPDATES.format(token=token), timeout=timeout)
    resp.raise_for_status()
    found = []
    for upd in resp.json().get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            found.append((chat["id"], chat.get("title") or chat.get("username") or chat.get("first_name", "")))
    return found
