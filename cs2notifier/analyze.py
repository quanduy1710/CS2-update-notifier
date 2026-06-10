"""Price-impact analysis of a CS2 update.

Two layers:
  1. Heuristics  - free, rule-based keyword scan. Always runs.
  2. Claude (AI) - optional, richer reasoning. Runs only if ANTHROPIC_API_KEY is set.

Both produce findings in a common shape:
    {
      "target":    str,              # item / category affected
      "direction": "up"|"down"|"volatile"|"neutral",
      "confidence":"low"|"medium"|"high",
      "reason":    str,
    }
"""
import json
import re

# Direction → emoji used in the notification.
ARROWS = {"up": "📈", "down": "📉", "volatile": "🔀", "neutral": "➖"}

# Each rule: (compiled regex, target, direction, confidence, reason).
# Ordered roughly by how strongly the signal moves the market.
_RULES = [
    (
        r"\b(added|introduc\w+|new|released|now available)\b[^.\n]{0,60}\bcase\b",
        "Newly released case",
        "down",
        "medium",
        "A brand-new case is cheap at launch and floods the market with its knives/gloves, "
        "pushing those down short-term. Watch for the case that just LEFT the active drop pool.",
    ),
    (
        r"\b(drop pool|active pool|rare drop)\b",
        "Cases removed from the active drop pool",
        "up",
        "high",
        "Cases rotated OUT of the active drop pool stop dropping and become scarcer, so their "
        "price (and their rare knives/gloves) tends to climb over the following weeks.",
    ),
    (
        r"\b(no longer available|discontinued|retired|removed from sale|will be removed)\b",
        "Discontinued / retired items",
        "up",
        "high",
        "Items that can no longer be obtained typically appreciate as supply is capped.",
    ),
    (
        r"\boperation\b",
        "Operation items & pass",
        "volatile",
        "medium",
        "Operation launches drive a wave of new items and trading activity; operation-exclusive "
        "drops can spike, then settle once supply catches up.",
    ),
    (
        r"\b(souvenir)\b",
        "Souvenir packages",
        "volatile",
        "medium",
        "Souvenir package availability around events makes related skins volatile; rare souvenirs "
        "with good stickers can appreciate.",
    ),
    (
        r"\b(sticker capsule|autograph capsule|sticker)\b",
        "Stickers / capsules",
        "volatile",
        "medium",
        "Fresh capsules have high supply (prices dip), but foil/autograph stickers and "
        "tournament favourites often appreciate after the event ends.",
    ),
    (
        r"\b(major|championship|viewer pass|rmr|pick'?em)\b",
        "Tournament items (Major)",
        "volatile",
        "medium",
        "Major-related items (passes, team stickers, souvenirs) are highly volatile around the event.",
    ),
    (
        r"\b(charm|keychain)\b",
        "Charms / keychains",
        "volatile",
        "low",
        "New charm supply lowers common charm prices; rare patterns can hold value.",
    ),
    (
        r"\b(collection)\b",
        "Weapon collection items",
        "volatile",
        "low",
        "Changes to a collection shift demand among its skins and trade-up inputs.",
    ),
    (
        r"\b(glove|gloves|knife|knives)\b",
        "Knives / gloves",
        "volatile",
        "low",
        "Knife/glove changes (new finishes or supply shifts) move the high-tier market.",
    ),
]

# Keywords signalling a purely technical/gameplay patch with little market impact.
_NEUTRAL_HINTS = re.compile(
    r"\b(bug ?fix|stability|crash|convar|clipping|fps|optimi[sz]|hitbox|"
    r"animation|audio|sound|server|matchmaking|map|workshop|hud|spectat)\b",
    re.IGNORECASE,
)

# Try to extract a concrete "<Name> Case" so we can look up a live price.
_CASE_NAME_RE = re.compile(r"\b([A-Z][\w'&]+(?:\s+[A-Z0-9][\w'&]+){0,3})\s+Case\b")


def run_heuristics(text):
    findings = []
    seen = set()
    for pattern, target, direction, confidence, reason in _RULES:
        if re.search(pattern, text, re.IGNORECASE):
            if target in seen:
                continue
            seen.add(target)
            findings.append(
                {
                    "target": target,
                    "direction": direction,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
    if not findings:
        note = (
            "Mostly gameplay/technical changes — minimal direct impact on item prices."
            if _NEUTRAL_HINTS.search(text)
            else "No obvious economy-affecting changes detected in this update."
        )
        findings.append(
            {"target": "Overall market", "direction": "neutral", "confidence": "medium", "reason": note}
        )
    return findings


def extract_case_names(text, limit=4):
    """Pull likely '<Name> Case' strings for live price lookups."""
    names = []
    for match in _CASE_NAME_RE.finditer(text):
        name = match.group(1).strip() + " Case"
        if name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


# --------------------------------------------------------------------------- #
# Optional Claude layer
# --------------------------------------------------------------------------- #
_CLAUDE_PROMPT = """You are a Counter-Strike 2 in-game economy analyst. Read the patch \
notes below and predict the impact on the prices of CS2 items (cases, skins, knives, \
gloves, stickers, capsules, charms, souvenirs).

Reply with ONLY a JSON object, no prose, in exactly this shape:
{{
  "summary": "one or two sentence overall read on this update's market impact",
  "findings": [
    {{
      "target": "specific item or category",
      "direction": "up | down | volatile | neutral",
      "magnitude": "low | medium | high",
      "confidence": "low | medium | high",
      "reason": "why, grounded in CS2 economy mechanics (drop pools, supply, scarcity, demand)"
    }}
  ]
}}

Rules of thumb you know: a new case dilutes supply of its own contents (down short-term) \
while cases rotated OUT of the active drop pool grow scarce (up); discontinued/retired items \
appreciate; tournament stickers/souvenirs are volatile around events. Be concrete and only \
include findings the notes actually support.

PATCH TITLE: {title}

PATCH NOTES:
{notes}
"""


def run_claude(cfg, title, notes):
    """Return Claude's structured analysis dict, or None if unavailable/failed."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    try:
        client = Anthropic(api_key=cfg.anthropic_key)
        resp = client.messages.create(
            model=cfg.anthropic_model,
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": _CLAUDE_PROMPT.format(title=title, notes=notes[:6000]),
                }
            ],
        )
        raw = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        return _parse_claude_json(raw)
    except Exception as exc:  # network, auth, parse — never fatal to the run
        print(f"[analyze] Claude analysis skipped: {exc}")
        return None


def _parse_claude_json(raw):
    raw = raw.strip()
    # Tolerate ```json fences or surrounding text.
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


def analyze(cfg, update):
    """Full analysis for an update dict (expects 'title' and 'clean_contents')."""
    text = update.get("clean_contents", "")
    result = {
        "heuristics": run_heuristics(text),
        "claude": None,
        "prices": [],
    }
    if cfg.claude_enabled:
        result["claude"] = run_claude(cfg, update.get("title", ""), text)
    if cfg.fetch_prices:
        from .steam import get_price

        for name in extract_case_names(text):
            price = get_price(name, app_id=cfg.app_id, currency=cfg.currency)
            if price:
                result["prices"].append(price)
    return result
