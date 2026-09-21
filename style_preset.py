"""Style preset and prompt-building helpers for Beyond the Baseline.

Kept separate from generate_images.py so the visual identity can be tuned
in one place without touching the generation/CLI logic.

Prompts are built from the narration line plus a set of "variety pools"
(environment, camera framing, lighting, atmosphere, court geometry) so the
character and art direction stay consistent across every shot while the
finished video still gets visual variety instead of the same bench or
baseline shot repeated forty times. Selection is a stable hash of the shot
number + line (so re-running the same script reproduces the same prompts),
with a simple anti-repeat rule so no two shots in a row pick the same pool
entry.
"""

import hashlib
import re

CHANNEL_NAME = "Beyond the Baseline"

CHARACTER_LINE_SINGLE = (
    "Same Beyond the Baseline white circular-head character, "
    "minimalist flat 2D cartoon style, 16:9."
)
CHARACTER_LINE_MULTI = (
    "Same Beyond the Baseline white circular-head characters, "
    "polished flat 2D cartoon style, 16:9. Exactly two tennis players on one court."
)

CONSISTENCY_CLAUSE = (
    "Character proportions, colors, and design stay identical to every "
    "other shot in this series."
)

# Narration cues that mean a second player (or a rally/exchange) is on
# screen, which is when detailed court geometry actually matters.
MULTI_PLAYER_KEYWORDS = (
    "opponent", "rival", "versus", " vs ", "doubles", "partner",
    "comes back", "hits back", "returns it", "return it", "across the net",
    "match point", "break point", "rally", "volley exchange", "serves to",
    "serve to", "your serve is", "their return", "the crowd", "umpire",
)

IRREGULAR_VERBS = {
    "be": "is",
    "have": "has",
    "am": "is",
    "are": "is",
}

# --- Variety pools -----------------------------------------------------
# Chosen via a stable hash of (shot number, line), with a no-immediate-
# repeat rule, so results vary across a script but stay reproducible.

CAMERA_ANGLES = [
    "medium over-the-shoulder camera angle",
    "low-angle shot looking up at the character",
    "wide establishing shot with plenty of empty space around the character",
    "close-up framing on the character's hands and the object they're holding",
    "side-profile medium shot",
    "high-angle shot looking down at the character",
    "tight framing looking down over the character's shoulder at a screen or object",
    "medium-wide shot centered on the character",
]

LIGHTING = [
    "late-afternoon lighting",
    "soft early-morning light",
    "dim indoor lighting",
    "harsh midday sun",
    "cool blue night lighting",
    "warm golden-hour light",
]

# Short mood/background clauses that add texture and a touch of body
# language without touching the fixed character design.
ATMOSPHERE = [
    "Body language kept slightly tense with shoulders low, background rendered "
    "in a few flat color blocks with soft, uncluttered negative space",
    "Weight shifted onto one foot in a relaxed stance, background kept minimal "
    "with a plain gradient sky and no extra clutter",
    "Leaning forward slightly with a focused posture, simple flat background "
    "shapes framing the character without distracting detail",
    "Shoulders slumped in a tired, deflated posture, background reduced to "
    "soft muted color blocks for a clean composition",
    "Standing tall with a confident, relaxed posture, background composed of "
    "a few simple flat shapes and open negative space",
    "One hand resting loosely at their side in a calm posture, background "
    "kept sparse with soft flat color gradients",
]

# Generic single-player locations, used when the narration doesn't already
# name a specific one. Locations only (no actions) so they combine cleanly
# with the action taken from the narration line itself.
GENERIC_ENVIRONMENTS = [
    "in a quiet locker room, gear scattered on a bench",
    "in a stadium tunnel leading toward the court entrance",
    "in the stadium stands, empty seats around them",
    "in a small kitchen, a racket leaning against the wall",
    "in a parked car in a stadium lot",
    "on a hotel room balcony overlooking distant tennis courts",
    "at a practice wall on an empty court",
    "in a dim bedroom at night",
    "on a bench beside one public tennis court, tennis bag resting nearby",
    "in an empty gym",
]

# Narration keyword -> location description, checked before falling back
# to the generic pool above, so the scene still matches what's said.
KEYWORD_ENVIRONMENTS = {
    "phone": "seated on a bench beside one public tennis court, tennis bag resting nearby",
    "locker room": "in a locker room, gear scattered on a bench",
    "hotel": "in a hotel room, a suitcase open on the bed",
    "stands": "in the stadium stands, court visible below",
    "bench": "on a courtside bench, tennis bag resting nearby",
    "car": "in a parked car, racket bag on the passenger seat",
    "home": "at home in a small living room, racket propped by the door",
    "gym": "in a gym, weights and resistance bands nearby",
    "practice": "at a practice wall on an empty court",
    "training": "on a practice court during a solo training session",
    "coach": "at the edge of the court beside a coach",
    "morning": "on an empty court just after sunrise",
    "night": "on a court under stadium floodlights after dark",
}

# Multi-player rally/serve geometry, used only when a second player or a
# clear exchange is in the narration.
MULTI_PLAYER_GEOMETRY = [
    (
        "Main player behind the near baseline has just hit a strong shot "
        "cross-court. Opponent is behind the far baseline preparing to "
        "return it. One net separates them, one yellow ball travels "
        "logically toward the opponent. Camera positioned just behind the "
        "near baseline."
    ),
    (
        "Main player stands at the baseline mid-serve, ball tossed "
        "overhead, racket raised. Opponent waits in a ready stance on the "
        "far side of the net, inside the service box. Camera positioned "
        "from the side of the court so both baselines are visible."
    ),
    (
        "Both players are positioned at their respective baselines "
        "mid-rally, one yellow ball frozen mid-air over the net between "
        "them. Court lines, net, and service boxes are clearly and "
        "correctly drawn. Camera positioned high behind one baseline for "
        "a clear view of the full court."
    ),
    (
        "Main player has moved forward to the net for a volley while the "
        "opponent remains behind the far baseline. One yellow ball travels "
        "toward the net player. Camera positioned at net height, slightly "
        "off to one side."
    ),
]

# Tracks the last pool index used per category so consecutive shots don't
# land on the same choice. Reset naturally each time the process starts.
_LAST_PICK = {}


def _hash_index(salt: str, shot_number: int, line: str, pool_len: int) -> int:
    digest = hashlib.md5(f"{salt}:{shot_number}:{line}".encode("utf-8")).hexdigest()
    return int(digest, 16) % pool_len


def _pick_from_pool(category: str, pool: list, salt: str, shot_number: int, line: str) -> str:
    idx = _hash_index(salt, shot_number, line, len(pool))
    if len(pool) > 1 and _LAST_PICK.get(category) == idx:
        idx = (idx + 1) % len(pool)
    _LAST_PICK[category] = idx
    return pool[idx]


def is_multi_player(line: str) -> bool:
    lowered = f" {line.lower()} "
    return any(keyword in lowered for keyword in MULTI_PLAYER_KEYWORDS)


def _conjugate(verb: str) -> str:
    lower = verb.lower()
    if lower in IRREGULAR_VERBS:
        result = IRREGULAR_VERBS[lower]
    elif lower.endswith(("s", "x", "z", "ch", "sh", "o")):
        result = verb + "es"
    elif lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        result = verb[:-1] + "ies"
    else:
        result = verb + "s"
    return result[0].upper() + result[1:] if verb[0].isupper() else result


def _to_third_person(line: str) -> str:
    """Rewrite a second-person narration line into a faceless third-person
    scene description ("You open your phone." -> "The player opens their
    phone.")."""
    text = line.strip().rstrip(".")
    starts_with_you = bool(re.match(r"^you\b", text, flags=re.IGNORECASE))

    text = re.sub(r"\byour\b", "their", text, flags=re.IGNORECASE)
    text = re.sub(r"\byou\b", "the player", text, flags=re.IGNORECASE)
    text = re.sub(r"^(the player)\b", "The player", text)

    if starts_with_you:
        words = text.split(" ")
        if len(words) > 2:
            words[2] = _conjugate(words[2])
        text = " ".join(words)

    return text[0].upper() + text[1:] if text else text


def _pick_environment(shot_number: int, line: str) -> str:
    lowered = line.lower()
    for keyword, description in KEYWORD_ENVIRONMENTS.items():
        if keyword in lowered:
            return description
    return _pick_from_pool("environment", GENERIC_ENVIRONMENTS, "env", shot_number, line)


def _extra_props(line: str) -> list:
    lowered = line.lower()
    props = []
    if "phone" in lowered:
        props.append("one phone")
    if "racket" in lowered:
        props.append("one racket")
    if "ball" in lowered:
        props.append("one yellow ball")
    return props


def build_prompt(line: str, aspect: str = "16:9", shot_number: int = 0) -> str:
    """Build a concise (roughly 75-150 word), varied image prompt from a
    narration line while keeping the character and art direction consistent
    across every shot."""
    line = line.strip()
    action = _to_third_person(line)
    camera = _pick_from_pool("camera", CAMERA_ANGLES, "camera", shot_number, line)
    lighting = _pick_from_pool("lighting", LIGHTING, "light", shot_number, line)

    if is_multi_player(line):
        geometry = _pick_from_pool(
            "geometry", MULTI_PLAYER_GEOMETRY, "geometry", shot_number, line
        )
        prompt = (
            f"{CHARACTER_LINE_MULTI} {action}. {geometry} {camera.capitalize()}, "
            f"{lighting}. {CONSISTENCY_CLAUSE} No extra courts, no players in "
            f"stands, no duplicated people, no distorted court geometry, no "
            f"realism, logos, or watermark."
        )
    else:
        environment = _pick_environment(shot_number, line)
        atmosphere = _pick_from_pool("atmosphere", ATMOSPHERE, "atmo", shot_number, line)
        props = _extra_props(line)
        props_clause = f", {', '.join(props)}" if props else ""
        prompt = (
            f"{CHARACTER_LINE_SINGLE} {action}, {environment}. {atmosphere}. "
            f"{camera.capitalize()}, {lighting}. {CONSISTENCY_CLAUSE} "
            f"Exactly one person{props_clause}, no extra people, no realism, "
            f"no logos, no watermark."
        )

    if aspect and aspect != "16:9":
        prompt = prompt.replace("16:9.", f"{aspect} aspect ratio.")

    return prompt


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
