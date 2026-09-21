#!/usr/bin/env python3
"""script_to_images: generate one image per narration line for faceless
YouTube videos using Google Gemini image generation.

Usage:
    python generate_images.py --script script.txt --output output
"""

import argparse
import csv
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from style_preset import build_prompt_fallback, sanitize_filename
from prompt_llm import build_prompt_llm

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


def log_error(log_path: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


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


def build_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "ERROR: GEMINI_API_KEY environment variable is not set.\n"
            "Set it in your shell or in a .env file (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    from google import genai
    return genai.Client(api_key=api_key)


def build_prompt_with_retries(
    client, text_model, line, shot_number, total_shots, all_shots, recent_prompts,
    aspect, retry_hint, log_path,
):
    """Try the LLM-based, style-guide-aware prompt generator; fall back to
    the offline rule-based builder if it fails after retries."""
    attempt = 0
    while attempt <= PROMPT_MAX_RETRIES:
        try:
            return build_prompt_llm(
                client, text_model, line, shot_number, total_shots, all_shots,
                recent_prompts, aspect=aspect, retry_hint=retry_hint,
            )
        except Exception as exc:
            attempt += 1
            log_error(log_path, f"shot {shot_number:03d} prompt generation attempt {attempt} failed: {exc}")
            if attempt > PROMPT_MAX_RETRIES:
                break
            time.sleep(RETRY_BACKOFF_SECONDS)

    log_error(log_path, f"shot {shot_number:03d}: falling back to rule-based prompt")
    return build_prompt_fallback(line, aspect=aspect, shot_number=shot_number)


def generate_image(client, model_name, prompt, reference_images, out_path: Path):
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
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    if not response.candidates:
        raise RuntimeError("No candidates returned by the model.")

    for part in response.candidates[0].content.parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data and inline_data.data:
            out_path.write_bytes(inline_data.data)
            return True

    raise RuntimeError("No image data found in the model response.")


def generate_with_retries(client, model_name, prompt, reference_images, out_path, log_path):
    attempt = 0
    while True:
        try:
            generate_image(client, model_name, prompt, reference_images, out_path)
            return True
        except Exception as exc:
            attempt += 1
            log_error(log_path, f"{out_path.name}: attempt {attempt} failed: {exc}")
            if attempt > MAX_RETRIES:
                return False
            backoff = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate one image per narration line using Google Gemini."
    )
    parser.add_argument("--script", required=True, help="Path to script.txt")
    parser.add_argument("--output", default="output", help="Output folder for images and shots.csv")
    parser.add_argument("--references", default="references", help="Folder with reference images")
    parser.add_argument("--start", type=int, default=None, help="First shot number to generate (1-indexed)")
    parser.add_argument("--end", type=int, default=None, help="Last shot number to generate (inclusive)")
    parser.add_argument("--model", default="flash", help="'flash', 'pro', or a raw Gemini image model id")
    parser.add_argument("--text-model", default=None, help="Gemini text model for prompt writing (defaults to a match for --model)")
    parser.add_argument("--aspect", default="16:9", help="Aspect ratio hint, e.g. 16:9")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without generating images")
    parser.add_argument(
        "--rule-based", action="store_true",
        help="Skip the LLM prompt writer and use the offline heuristic prompt builder "
             "(no API calls at all in combination with --dry-run)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    script_path = Path(args.script)
    if not script_path.is_file():
        print(f"ERROR: script file not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / "errors.log"
    csv_path = output_dir / "shots.csv"

    model_name = MODEL_MAP.get(args.model, args.model)
    text_model_name = args.text_model or TEXT_MODEL_MAP.get(args.model, "gemini-2.5-flash")

    all_shots = read_script_lines(script_path)
    if not all_shots:
        print("No non-empty lines found in script. Nothing to do.")
        return

    start = args.start or 1
    end = args.end or all_shots[-1][0]
    selected_shots = [(n, line) for n, line in all_shots if start <= n <= end]

    if not selected_shots:
        print(f"No shots found in range [{start}, {end}].")
        return

    reference_images = load_reference_images(Path(args.references))
    if reference_images:
        print(f"Using {len(reference_images)} reference image(s) from {args.references}/")

    # A client is needed for image generation (unless --dry-run) and for the
    # LLM prompt writer (unless --rule-based), even during a dry run.
    need_client = (not args.dry_run) or (not args.rule_based)
    client = build_client() if need_client else None

    existing_rows = load_existing_shots(csv_path)

    total = len(selected_shots)
    mode_note = " (dry run)" if args.dry_run else ""
    mode_note += " (rule-based prompts)" if args.rule_based else " (LLM-guided prompts)"
    print(f"Generating {total} shot(s) [{start}-{end}] with model '{model_name}'{mode_note}")

    recent_prompts = []

    for i, (shot_number, line) in enumerate(selected_shots, start=1):
        retry_hint = existing_rows.get(shot_number, {}).get("status") == "failed"

        if args.rule_based:
            prompt = build_prompt_fallback(line, aspect=args.aspect, shot_number=shot_number)
        else:
            prompt = build_prompt_with_retries(
                client, text_model_name, line, shot_number, len(all_shots), all_shots,
                recent_prompts, args.aspect, retry_hint, log_path,
            )
        recent_prompts.append(prompt)

        filename = f"{shot_number:03d}_{sanitize_filename(line)}.png"
        out_path = output_dir / filename

        print(f"[{i}/{total}] shot {shot_number:03d}: {line}")

        if args.dry_run:
            print(f"  prompt ({len(prompt.split())} words): {prompt}")
            status = "dry-run"
        else:
            success = generate_with_retries(
                client, model_name, prompt, reference_images, out_path, log_path
            )
            if success:
                status = "success"
                print(f"  saved -> {out_path}")
            else:
                status = "failed"
                print(f"  FAILED (see {log_path})")

        existing_rows[shot_number] = {
            "shot_number": shot_number,
            "narration_line": line,
            "prompt": prompt,
            "filename": filename,
            "status": status,
        }

    write_shots_csv(csv_path, existing_rows)
    print(f"\nDone. Shot list written to {csv_path}")


if __name__ == "__main__":
    main()
