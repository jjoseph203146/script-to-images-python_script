"""Style preset and prompt-building helpers for Beyond the Baseline.

Kept separate from generate_images.py so the visual identity can be tuned
in one place without touching the generation/CLI logic.
"""

import re

CHANNEL_NAME = "Beyond the Baseline"

# Recurring visual identity applied to every shot unless the line clearly
# calls for something else.
STYLE_PRESET = (
    "minimalist flat 2D cartoon illustration, 16:9 widescreen, "
    "faceless fictional tennis character, large white circular head, "
    "two small black oval eyes, tiny simple mouth, thin dark limbs, "
    "simplified athletic body, not realistic, no logos, no watermark"
)

# When a narration line mentions any of these, it's worth spending a few
# extra words on court geometry / positioning so the model doesn't default
# to something generic.
COURT_GEOMETRY_KEYWORDS = (
    "court", "baseline", "net", "serve", "serving", "rally", "backhand",
    "forehand", "ace", "deuce", "match point", "sideline", "doubles",
    "singles", "umpire", "chair umpire", "tiebreak", "volley", "lob",
    "return", "opponent",
)

COURT_GEOMETRY_DETAIL = (
    "clear tennis court geometry with baseline, service boxes, and net "
    "correctly positioned, simple flat court coloring"
)


def needs_court_geometry(line: str) -> bool:
    lowered = line.lower()
    return any(keyword in lowered for keyword in COURT_GEOMETRY_KEYWORDS)


def build_prompt(line: str, aspect: str = "16:9") -> str:
    """Build a short, usable image prompt from a narration line."""
    line = line.strip()
    style = STYLE_PRESET
    if aspect and aspect != "16:9":
        style = style.replace("16:9 widescreen", f"{aspect} aspect ratio")

    parts = [line, style]
    if needs_court_geometry(line):
        parts.append(COURT_GEOMETRY_DETAIL)

    return ", ".join(p.strip().rstrip(".") for p in parts if p.strip())


def sanitize_filename(text: str, max_words: int = 6, max_len: int = 40) -> str:
    """Turn a narration line into a safe, short filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()[:max_words]
    slug = "_".join(words)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = "shot"
    return slug[:max_len].rstrip("_")
