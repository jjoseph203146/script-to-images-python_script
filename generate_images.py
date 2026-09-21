#!/usr/bin/env python3
"""script_to_images: generate one image per narration line for faceless
YouTube videos using Google Gemini image generation.

Usage:
    python generate_images.py --script script.txt --output output

The pipeline itself lives in run_pipeline(), which is also imported by
app.py (the local web UI) -- main() is a thin CLI adapter over it.
"""

import argparse
import csv
import mimetypes
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from style_preset import build_prompt_fallback, sanitize_filename
from prompt_llm import build_prompt_llm
from segmentation import build_shot_plan

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MODEL_MAP = {
    "flash": "gemini-2.5-flash-image",
    "pro": "gemini-3-pro-image-preview",
}
TEXT_MODEL_MAP = {
    "flash": "gemini-3.6-flash",
    "pro": "gemini-3.1-pro-preview",
}

MAX_RETRIES = 2  # additional attempts after the first try, for image generation
PROMPT_MAX_RETRIES = 1  # additional attempts after the first try, for LLM prompt generation
RETRY_BACKOFF_SECONDS = 2  # doubles each retry: 2s, 4s

VERSION_RE = re.compile(r"\.v(\d+)\.png$")


class MissingAPIKeyError(RuntimeError):
    """Raised when a Gemini client is needed but no API key is available."""


def log_error(log_path: Path, message: str, on_event=None) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if on_event:
        on_event("log", {"line": line})


def read_script_lines(script_path: Path):
    """Return a list of (shot_number, line) for every non-empty line,
    numbered sequentially starting at 1."""
    shots = []
    shot_number = 0
    with open(script_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            shot_number += 1
            shots.append((shot_number, line))
    return shots


def load_reference_images(references_dir: Path):
    """Load reference images (if any) as raw bytes + mime type, sorted by name."""
    if not references_dir or not references_dir.is_dir():
        return []

    refs = []
    for path in sorted(references_dir.iterdir()):
        if not path.is_file():
            continue
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type or not mime_type.startswith("image/"):
            continue
        refs.append((path, mime_type))
    return refs


def build_client(api_key=None):
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "GEMINI_API_KEY is not set. Set it in your shell, in a .env file "
            "(see .env.example), or pass api_key= to run_pipeline()."
        )

    from google import genai
    return genai.Client(api_key=api_key)


def build_prompt_with_retries(
    client, text_model, line, shot_number, total_shots, all_shots, recent_prompts,
    aspect, retry_hint, log_path, on_event=None,
):
    """Try the LLM-based, style-guide-aware prompt generator; fall back to
    the offline rule-based builder if it fails after retries.

    Returns (prompt, source) where source is "llm" or "rule-based".
    """
    attempt = 0
    while attempt <= PROMPT_MAX_RETRIES:
        try:
            prompt = build_prompt_llm(
                client, text_model, line, shot_number, total_shots, all_shots,
                recent_prompts, aspect=aspect, retry_hint=retry_hint,
            )
            return prompt, "llm"
        except Exception as exc:
            attempt += 1
            log_error(log_path, f"shot {shot_number:03d} prompt generation attempt {attempt} failed: {exc}", on_event)
            if attempt > PROMPT_MAX_RETRIES:
                break
            time.sleep(RETRY_BACKOFF_SECONDS)

    log_error(log_path, f"shot {shot_number:03d}: falling back to rule-based prompt", on_event)
    return build_prompt_fallback(line, aspect=aspect, shot_number=shot_number), "rule-based"


def generate_image(client, model_name, prompt, reference_images, out_path: Path, aspect: str = "16:9"):
    """Attempt one image generation call. Returns True on success."""
    from google.genai import types

    contents = []
    for ref_path, mime_type in reference_images:
        contents.append(
            types.Part.from_bytes(data=ref_path.read_bytes(), mime_type=mime_type)
        )
    contents.append(prompt)

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect),
        ),
    )

    if not response.candidates:
        raise RuntimeError("No candidates returned by the model.")

    for part in response.candidates[0].content.parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data and inline_data.data:
            out_path.write_bytes(inline_data.data)
            return True

    raise RuntimeError("No image data found in the model response.")


def generate_with_retries(
    client, model_name, prompt, reference_images, out_path, log_path,
    aspect="16:9", on_event=None, shot_number=None,
):
    attempt = 0
    while True:
        try:
            generate_image(client, model_name, prompt, reference_images, out_path, aspect=aspect)
            return True
        except Exception as exc:
            attempt += 1
            log_error(log_path, f"{out_path.name}: attempt {attempt} failed: {exc}", on_event)
            if attempt > MAX_RETRIES:
                return False
            backoff = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            if on_event:
                on_event("shot_retry", {
                    "shot_number": shot_number, "attempt": attempt, "max": MAX_RETRIES,
                    "error": str(exc), "backoff": backoff,
                })
            print(f"  retrying ({attempt}/{MAX_RETRIES}) after {backoff}s...")
            time.sleep(backoff)


def load_existing_shots(csv_path: Path):
    rows = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows[int(row["shot_number"])] = row
    return rows


def write_shots_csv(csv_path: Path, rows: dict):
    fieldnames = ["shot_number", "narration_line", "prompt", "filename", "status"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for shot_number in sorted(rows):
            writer.writerow(rows[shot_number])


def compute_versions_bytes(out_path: Path):
    """versions = 1 + number of NNN_slug.vK.png siblings; bytes = current
    file size, or None if the live file doesn't exist yet."""
    if not out_path.exists():
        return 1, None
    stem = out_path.stem
    siblings = list(out_path.parent.glob(f"{stem}.v*.png"))
    return 1 + len(siblings), out_path.stat().st_size


def preserve_version(out_path: Path):
    """If out_path already exists, rename it to the next free
    NNN_slug.vK.png so a fresh generation doesn't destroy the previous
    frame. The live file always keeps the plain NNN_slug.png name."""
    if not out_path.exists():
        return
    stem = out_path.stem
    parent = out_path.parent
    used = set()
    for p in parent.glob(f"{stem}.v*.png"):
        m = VERSION_RE.search(p.name)
        if m:
            used.add(int(m.group(1)))
    k = 1
    while k in used:
        k += 1
    out_path.rename(parent / f"{stem}.v{k}.png")


def select_version(out_path: Path, version: int):
    """Swap out_path's live content with its NNN_slug.vK.png sibling, so
    an earlier reroll can be picked as the final frame without losing any
    version. The version count and every other version's number stay the
    same -- only the live file and slot K trade places."""
    if not out_path.exists():
        raise FileNotFoundError(f"{out_path.name} does not exist")
    stem = out_path.stem
    parent = out_path.parent
    v_path = parent / f"{stem}.v{version}.png"
    if not v_path.exists():
        raise FileNotFoundError(f"{v_path.name} does not exist")

    temp_path = parent / f"{stem}.__swap__.png"
    out_path.rename(temp_path)
    v_path.rename(out_path)
    temp_path.rename(v_path)
    return compute_versions_bytes(out_path)


def run_pipeline(
    script_path,
    output_dir="output",
    references_dir="reference_photos",
    start=None, end=None,
    model="flash", text_model=None, aspect="16:9",
    dry_run=False, rule_based=False,
    api_key=None,
    keep_versions=True,
    on_event=None,
    should_stop=None,
    force_resegment=False,
):
    """Run the full script_to_images pipeline. Used by both the CLI
    (main()) and the web UI (app.py), so every behavior here is shared."""

    def emit(name, payload):
        if on_event:
            on_event(name, payload)

    script_path = Path(script_path)
    if not script_path.is_file():
        raise FileNotFoundError(f"script file not found: {script_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    references_path = Path(references_dir)

    log_path = output_dir / "errors.log"
    csv_path = output_dir / "shots.csv"

    model_name = MODEL_MAP.get(model, model)
    text_model_name = text_model or TEXT_MODEL_MAP.get(model, "gemini-3.6-flash")

    # A client is needed for image generation (unless dry_run), for the
    # LLM prompt writer (unless rule_based), and for shot segmentation
    # (unless rule_based) -- even during a dry run, since dry-run previews
    # the real segmentation and prompts.
    need_client = (not dry_run) or (not rule_based)
    client = build_client(api_key) if need_client else None

    script_text = script_path.read_text(encoding="utf-8")
    if script_text.strip():
        shot_texts = build_shot_plan(
            script_text, output_dir,
            client=None if rule_based else client,
            text_model=text_model_name,
            force_resegment=force_resegment,
        )
    else:
        shot_texts = []
    all_shots = list(enumerate(shot_texts, start=1))

    start_resolved = start or 1
    end_resolved = end or (all_shots[-1][0] if all_shots else 0)
    selected_shots = [(n, line) for n, line in all_shots if start_resolved <= n <= end_resolved]

    if not all_shots or not selected_shots:
        print("No shots to generate." if not all_shots else f"No shots found in range [{start_resolved}, {end_resolved}].")
        emit("run_start", {
            "total": 0, "start": start_resolved, "end": end_resolved, "model": model_name,
            "text_model": text_model_name, "aspect": aspect, "dry_run": dry_run, "rule_based": rule_based,
        })
        emit("run_done", {"success": 0, "failed": 0, "dry_run": 0, "stopped": False})
        return {"success": 0, "failed": 0, "stopped": False}

    reference_images = load_reference_images(references_path)
    if reference_images:
        print(f"Using {len(reference_images)} reference image(s) from {references_path}/")

    existing_rows = load_existing_shots(csv_path)

    total = len(selected_shots)
    mode_note = " (dry run)" if dry_run else ""
    mode_note += " (rule-based prompts)" if rule_based else " (LLM-guided prompts)"
    print(f"Generating {total} shot(s) [{start_resolved}-{end_resolved}] with model '{model_name}'{mode_note}")

    emit("run_start", {
        "total": total, "start": start_resolved, "end": end_resolved, "model": model_name,
        "text_model": text_model_name, "aspect": aspect, "dry_run": dry_run, "rule_based": rule_based,
    })

    recent_prompts = []
    success_count = 0
    failed_count = 0
    dry_run_count = 0
    stopped = False

    for i, (shot_number, line) in enumerate(selected_shots, start=1):
        if should_stop and should_stop():
            stopped = True
            break

        emit("shot_start", {"shot_number": shot_number, "narration_line": line})

        retry_hint = existing_rows.get(shot_number, {}).get("status") == "failed"

        if rule_based:
            prompt, prompt_source = build_prompt_fallback(line, aspect=aspect, shot_number=shot_number), "rule-based"
        else:
            prompt, prompt_source = build_prompt_with_retries(
                client, text_model_name, line, shot_number, len(all_shots), all_shots,
                recent_prompts, aspect, retry_hint, log_path, on_event,
            )
        recent_prompts.append(prompt)
        emit("shot_prompt", {"shot_number": shot_number, "prompt": prompt, "source": prompt_source})

        filename = f"{shot_number:03d}_{sanitize_filename(line)}.png"
        out_path = output_dir / filename

        print(f"[{i}/{total}] shot {shot_number:03d}: {line}")

        if dry_run:
            print(f"  prompt ({len(prompt.split())} words): {prompt}")
            status = "dry-run"
            dry_run_count += 1
        else:
            if keep_versions:
                preserve_version(out_path)
            success = generate_with_retries(
                client, model_name, prompt, reference_images, out_path, log_path,
                aspect=aspect, on_event=on_event, shot_number=shot_number,
            )
            if success:
                status = "success"
                success_count += 1
                print(f"  saved -> {out_path}")
            else:
                status = "failed"
                failed_count += 1
                print(f"  FAILED (see {log_path})")

        existing_rows[shot_number] = {
            "shot_number": shot_number,
            "narration_line": line,
            "prompt": prompt,
            "filename": filename,
            "status": status,
        }
        write_shots_csv(csv_path, existing_rows)

        versions, size_bytes = compute_versions_bytes(out_path)
        emit("shot_done", {
            "shot_number": shot_number, "filename": filename, "status": status,
            "versions": versions, "bytes": size_bytes,
        })

    write_shots_csv(csv_path, existing_rows)
    print(f"\nDone. Shot list written to {csv_path}")

    emit("run_done", {
        "success": success_count, "failed": failed_count, "dry_run": dry_run_count, "stopped": stopped,
    })
    return {"success": success_count, "failed": failed_count, "stopped": stopped}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate one image per narration line using Google Gemini."
    )
    parser.add_argument("--script", required=True, help="Path to script.txt")
    parser.add_argument("--output", default="output", help="Output folder for images and shots.csv")
    parser.add_argument("--references", default="reference_photos", help="Folder with reference images")
    parser.add_argument("--start", type=int, default=None, help="First shot number to generate (1-indexed)")
    parser.add_argument("--end", type=int, default=None, help="Last shot number to generate (inclusive)")
    parser.add_argument("--model", default="flash", help="'flash', 'pro', or a raw Gemini image model id")
    parser.add_argument("--text-model", default=None, help="Gemini text model for prompt writing (defaults to a match for --model)")
    parser.add_argument("--aspect", default="16:9", help="Aspect ratio hint, e.g. 16:9")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without generating images")
    parser.add_argument(
        "--rule-based", action="store_true",
        help="Skip the LLM prompt writer and shot segmentation, using one shot per "
             "non-empty line and the offline heuristic prompt builder "
             "(no API calls at all in combination with --dry-run)",
    )
    parser.add_argument(
        "--resegment", action="store_true",
        help="Ignore any cached output/shots_plan.json and re-run shot segmentation "
             "(shot numbers may change)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        run_pipeline(
            Path(args.script), args.output, args.references,
            args.start, args.end, args.model, args.text_model, args.aspect,
            args.dry_run, args.rule_based,
            force_resegment=args.resegment,
        )
    except (FileNotFoundError, MissingAPIKeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
