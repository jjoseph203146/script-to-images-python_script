"""Script -> shot segmentation for Beyond the Baseline.

The pipeline used to generate exactly one image per non-empty script line.
That undersells lines that pack in multiple distinct visual beats ("You
open your phone. There's a number beside your name." is two moments, not
one) and produces a video that isn't visual enough. This module runs one
LLM call over the whole script and returns an ordered list of shot texts,
deliberately biased toward MORE shots than raw lines -- splitting a line
into several shots when it covers several ideas, and only ever merging
adjacent fragments when they are truly a single inseparable moment.

The result is cached to output/shots_plan.json, keyed by a hash of the
script text, so repeated runs (and --start/--end partial runs) keep using
the same shot numbering instead of re-segmenting -- and possibly
re-numbering everything -- on every call.
"""

import hashlib
import json
from pathlib import Path

SEGMENTATION_SYSTEM_INSTRUCTION = """\
You break a narration script for a faceless YouTube video into a shot
list for an illustrator. The finished video should be highly visual --
default to MORE shots, not fewer.

Rules:
- Read the whole script first so you understand the story before you cut it.
- Prefer splitting: if a line or sentence contains more than one distinct
  visual beat, action, or emotional turn, split it into separate shots --
  even if that means a shot list longer than the number of input lines.
- Only merge adjacent fragments into one shot when they are truly a single
  inseparable visual moment (e.g. "3... 2... 1-" / "-liftoff!" said as one
  beat) or a fragment on its own has no visual content at all (e.g. a lone
  "But" or "And then").
- Preserve the original wording as much as possible in each shot's text --
  you are cutting the script into pieces, not rewriting it. Trim only what
  a beat doesn't need (e.g. a leading conjunction that belongs with the
  previous shot).
- Keep the original order. Every word of the input script should be
  accounted for in some shot.
- A typical narration line should become 1-3 shots; a short simple line can
  stay as 1.

Respond with only a JSON object of the exact shape:
{"shots": ["shot one text", "shot two text", ...]}
No other keys, no markdown, no commentary.
"""


def script_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def plan_path(output_dir) -> Path:
    return Path(output_dir) / "shots_plan.json"


def load_plan(output_dir):
    """Return the cached {"script_hash": ..., "shots": [...]} plan, or None."""
    path = plan_path(output_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_plan(output_dir, text: str, shots: list) -> dict:
    plan = {"script_hash": script_hash(text), "shots": shots}
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    plan_path(output_dir).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def segment_script(client, text_model: str, script_text: str) -> list:
    """Call the Gemini text model to split script_text into a shot list.
    Raises on failure -- callers decide the fallback (e.g. one shot per
    non-empty line)."""
    from google.genai import types

    response = client.models.generate_content(
        model=text_model,
        contents=f"SCRIPT:\n{script_text}",
        config=types.GenerateContentConfig(
            system_instruction=SEGMENTATION_SYSTEM_INSTRUCTION,
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )
    data = json.loads(response.text)
    shots = [s.strip() for s in data.get("shots", []) if s and s.strip()]
    if not shots:
        raise RuntimeError("Segmentation returned no shots.")
    return shots


def fallback_shots(script_text: str) -> list:
    """One shot per non-empty line -- used when no client is available."""
    return [line.strip() for line in script_text.splitlines() if line.strip()]


def build_shot_plan(
    script_text: str, output_dir, client=None, text_model=None,
    force_resegment=False,
):
    """Return an ordered list of shot texts for script_text, using the
    cached plan when it matches, otherwise (re-)segmenting with the LLM if
    a client is available, or falling back to one shot per line."""
    h = script_hash(script_text)
    if not force_resegment:
        cached = load_plan(output_dir)
        if cached and cached.get("script_hash") == h and cached.get("shots"):
            return cached["shots"]

    if client is None:
        return fallback_shots(script_text)

    shots = segment_script(client, text_model, script_text)
    save_plan(output_dir, script_text, shots)
    return shots
