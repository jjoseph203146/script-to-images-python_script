"""Beyond the Baseline channel style guide + prompt-building helpers.

CHANNEL_STYLE_GUIDE is the full creative direction doc for the channel. It
is used as the system instruction for the LLM-based prompt generator in
prompt_llm.py, which is what actually implements the "think like a
storyboard artist" logic (strongest visual idea, character count, camera
variety, progression stage, etc.) for each narration line.

This module also keeps a rule-based, fully offline fallback (used when the
LLM call fails, or when --rule-based is passed) so the pipeline never
breaks and there's a free/no-API-key way to preview shot structure.
"""

import hashlib
import re

CHANNEL_NAME = "Beyond the Baseline"

CHANNEL_STYLE_GUIDE = """\
CHANNEL STYLE PRESET: BEYOND THE BASELINE

Purpose:
Create consistent 16:9 illustrated stills for a faceless tennis storytelling YouTube channel called Beyond the Baseline.

CORE VISUAL IDENTITY

Use a soft, cel-shaded illustrated style: cartoon character design with
gentle gradient shading and volume, set against detailed, atmospheric,
semi-realistic environments (textured pavement, individual fence links,
layered tree foliage, moody lighting). Not flat vector, not painterly in
the fine-art sense, not photorealistic.

The recurring main character must always use this design:
- large perfectly white circular head
- two small black oval eyes
- tiny simple mouth
- thin dark limbs
- simplified athletic cartoon body
- no realistic facial features
- no realistic skin texture
- no realistic hair
- no detailed nose, ears, eyebrows, or facial anatomy
- no photorealism
- no semi-realistic human rendering
- no anime style
- no 3D render

The character should feel simple, recognizable, clean, and visually consistent across every image.

CHARACTER CONTINUITY

The main protagonist should visually evolve as tennis level rises, while remaining obviously the same character.

Beginner stage:
- slightly smaller or less athletic body
- basic athletic clothes
- inexpensive/simple racquet
- awkward posture
- public-court environments
- simple tennis bag or backpack

Competitive stage:
- more athletic proportions
- proper tennis clothing
- better racquet
- more confident posture
- tournament or academy environments
- larger tennis bag

Elite/pro stage:
- highly athletic simplified body
- premium unbranded tennis clothing
- professional racquet
- confident, efficient body language
- professional facilities, travel environments, stadiums
- multiple racquets or advanced equipment when appropriate

Do not change the white circular head design between levels.

IMAGE FORMAT

Every generated image must be:
- exactly one single image
- 16:9 widescreen
- suitable for YouTube video editing
- no collage
- no split screen
- no multiple panels
- no alternate versions in one image
- no watermark

STYLE

Visual style:
- cartoon character (simple head/eyes/limbs, per CORE VISUAL IDENTITY) rendered with soft cel-shading and gentle gradients, not flat color fills
- backgrounds and environments are illustrated with real texture and detail: cracked or worn pavement, individual chain-link fence links, layered tree foliage, crowd-filled stands, atmospheric depth
- soft depth of field / gentle background blur is welcome to separate the character from the environment
- warm, cinematic, often golden-hour or dusk lighting with visible glow from light sources (stadium floodlights, sunset) when the scene calls for it
- professional storybook/editorial illustration quality
- not glossy or plastic-looking
- not painterly in the fine-art sense (no visible brushstrokes, no canvas texture)
- not photorealistic
- not obviously AI-generated

Lighting:
- natural or cinematic depending on the scene, with soft directional light and visible atmosphere (haze, glow, gradient skies) rather than flat even lighting
- clear subject separation
- avoid excessive particles, dramatic fantasy effects, or neon unless specifically requested

Color:
- realistic tennis environments
- courts may use muted green, blue, hardcourt, or clay tones depending on scene
- bright yellow tennis balls should remain visually clear
- avoid random overly saturated color palettes

CAMERA VARIETY

Do not use the same camera angle repeatedly.

Vary naturally between:
- wide establishing shot
- medium shot
- medium close-up
- close-up
- over-the-shoulder
- behind-the-baseline
- courtside sideline angle
- low courtside angle
- bird's-eye / overhead
- rear three-quarter
- front three-quarter

The camera angle should serve the narration.

Avoid repeatedly placing the protagonist in the exact same position on the same court.

SCENE VARIETY

Use a wide range of tennis-related environments when appropriate:
- worn public courts
- neighborhood courts
- tennis clubs
- academies
- junior tournaments
- school courts
- college facilities
- locker rooms
- benches
- parking lots
- cars
- airports
- hotel rooms
- tournament hallways
- practice facilities
- small professional events
- Challenger-type venues
- large professional stadiums

Do not force every narration line into an on-court scene.

TENNIS COURT GEOMETRY RULES

When a court is visible, make the geometry believable.

For one-on-one tennis scenes:
- use exactly one main tennis court unless multiple courts are explicitly requested
- show exactly one net across the middle
- near-side player belongs on the near half
- far-side player belongs on the far half
- players should usually be behind or near their respective baselines unless the action requires net play
- do not place players in walkways between courts
- do not place players in stands unless explicitly requested
- do not show players randomly outside the court while actively rallying
- do not create multiple overlapping nets
- do not create impossible court lines
- do not place both opponents on the same side of the net

When describing a rally, clearly define:
- near player position
- far player position
- ball direction
- camera position

TENNIS ACTION RULES

Tennis actions should be physically believable.

Forehands:
- ball should be near the racquet strings at contact
- racquet and body orientation should make sense
- ball trajectory should travel toward the opponent's side

Serves:
- player should be behind the baseline
- ball toss should be above or slightly in front of the player
- racquet should be moving upward toward contact

Returns:
- player should face the server
- stance should be balanced and athletic

Rallies:
- one player on each side of the net
- ball should travel logically between them
- avoid impossible body positions

BEGINNER BODY LANGUAGE

Beginner scenes should look inexperienced but not ridiculous.

Use:
- slightly upright stance
- stiff swing
- poor spacing
- uncertain grip
- simple concentration

Do not make beginners look terrified, incompetent, or cartoonishly clumsy unless narration specifically calls for comedy.

ADVANCED BODY LANGUAGE

Advanced players should show:
- balanced athletic stance
- strong rotation
- efficient footwork
- good spacing
- controlled posture
- confident preparation

Do not turn advanced characters into exaggerated superheroes.

FACIAL EXPRESSION RULES

Use subtle expressions.

Allowed:
- neutral
- focused
- mildly curious
- mildly disappointed
- satisfied
- tired
- thoughtful
- determined

Avoid:
- terrified
- horrified
- exaggerated crying
- huge open-mouth shock
- extreme cartoon panic
unless explicitly requested.

TEXT AND NUMBERS

Do not add text unless the narration or shot explicitly requires it.

When text is required:
- keep it minimal
- spell exactly as requested
- use clean bold sans-serif typography
- avoid fake logos
- avoid unreadable filler text
- avoid multiple random numbers

For rating shots:
- emphasize only the required number
- do not add real UTR branding
- use a fictional generic rating interface

PHONE / UI SCENES

Phone interfaces should be:
- clean
- simple
- fictional
- readable
- generic
- not copied from a real app

Do not use real UTR app branding or logos.

For close-ups:
- phone should be upright and readable
- avoid mirrored text
- avoid distorted hands
- keep UI secondary unless the narration specifically focuses on the number

MULTI-CHARACTER RULES

When multiple characters are required:
- explicitly define the exact character count
- assign each person a clear role
- place them deliberately
- avoid random extra people
- avoid duplicate versions of the main character unless progression is intentionally being shown

Spectators:
- use simplified background shapes
- do not make spectators visually compete with the main subject

PROGRESSION SCENES

For beginner-to-pro progression visuals:
- environment should evolve naturally
- equipment should become more advanced
- body language should become more confident
- venue scale may increase
- lighting may become more dramatic
- avoid hard split-screen unless specifically requested
- prefer one continuous visual journey

VISUAL PACING

Every image should function as a clear storyboard frame.

Prioritize:
- one main idea
- one readable action
- one clear focal point

Do not overload a single image with multiple narrative events.

If a narration line contains several actions, choose the strongest visual moment rather than trying to show everything at once.

NEGATIVE RULES

Never generate:
- realistic humans
- photorealistic people
- extra limbs
- duplicate heads
- distorted hands
- impossible racquet shapes
- extra tennis balls unless requested
- extra courts unless requested
- extra nets
- random background players
- fake sponsor logos
- real tournament branding
- real professional player likenesses
- watermarks
- collages
- split screens
- unrelated text
- random UI clutter

PROMPT LENGTH

Most scene prompts should be concise:
approximately 75-150 words.

Only use longer prompts for:
- two-player matches
- complex court geometry
- progression scenes
- stadium scenes
- important typography
- scenes that previously failed

PROMPT GENERATION LOGIC

For every narration line:
1. Identify the single strongest visual idea.
2. Decide exact character count.
3. Decide location.
4. Decide camera angle.
5. Decide physical placement of characters.
6. Decide one primary action.
7. Add only the tennis geometry rules needed for that shot.
8. Preserve the Beyond the Baseline character and art style.
9. Avoid repeating recent camera angles and environments.
10. Generate exactly one 16:9 image prompt.

IMPORTANT:
Do not merely illustrate the narration literally every time.

Think like a YouTube editor and storyboard artist.

Choose a visual that helps maintain attention, communicates the emotion or idea quickly, and creates variety across the finished video.
"""

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

# --- Variety pools (rule-based fallback only) --------------------------
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
    phone.", "Then you start checking it." -> "Then the player starts
    checking it.")."""
    text = line.strip().rstrip(".")

    text = re.sub(r"\byour\b", "their", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\byou\b",
        lambda m: "The player" if m.group(0)[0].isupper() else "the player",
        text,
        flags=re.IGNORECASE,
    )

    # Conjugate the verb right after the first "the player" (the one that
    # used to be "you <verb>") to third-person singular.
    match = re.search(r"\bthe player\b\s+(\w+)", text, flags=re.IGNORECASE)
    if match:
        start, end = match.span(1)
        text = text[:start] + _conjugate(match.group(1)) + text[end:]

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


def build_prompt_fallback(line: str, aspect: str = "16:9", shot_number: int = 0) -> str:
    """Offline, rule-based prompt builder. Used automatically if the LLM
    prompt call fails, or directly when --rule-based is passed. Doesn't
    implement the full style guide's judgment calls (progression stage,
    strongest visual idea, etc.) -- it's a safety net, not the primary path."""
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
