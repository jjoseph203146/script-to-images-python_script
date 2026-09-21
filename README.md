# script_to_images

Generate one image per narration line for faceless YouTube videos, using
Google Gemini image generation. Built for the **Beyond the Baseline** tennis
channel's full style guide (`style_preset.py`'s `CHANNEL_STYLE_GUIDE`), but
works for any script.

## What it does

- Reads `script.txt`, one narration line per line (blank lines are skipped).
- **Segments the script into shots** with one LLM call over the whole
  script (`segmentation.py`), biased toward *more* shots than lines: a line
  that covers several distinct visual beats gets split into several shots,
  and adjacent fragments are only merged when they're truly one moment.
  This is what actually drives the shot count -- it's not 1 image per line.
  The result is cached to `output/shots_plan.json` (keyed by a hash of the
  script text) so re-runs and `--start`/`--end` partial runs keep the same
  shot numbering instead of re-cutting the script every time. Pass
  `--resegment` to force a fresh cut.
- For each shot, a Gemini **text** model (`gemini-3.6-flash` by default)
  reads the full channel style guide plus the whole script, the shot's
  text, and the last few prompts already generated, and writes a single
  ~75-150 word image prompt for that shot: it picks the strongest visual
  idea, the character count, the location, the camera angle, and the
  progression stage (beginner/competitive/elite), and avoids repeating
  recent camera angles or environments — instead of illustrating every line
  literally on the same bench or baseline.
- If that text-model call fails (or `--rule-based` is passed), an offline
  heuristic prompt builder in `style_preset.py` is used instead, so the
  pipeline never breaks and there's a free, no-API-key way to preview shot
  structure.
- Optionally feeds in reference images from a `reference_photos/` folder so
  Gemini's image model stays consistent with your character design.
- Generates one image per line with Google Gemini's **image** model
  (`gemini-2.5-flash-image` by default) and saves them as numbered PNGs in
  `output/`, e.g. `001_you_open_your_phone.png`.
- Writes `output/shots.csv` with shot number, narration line, generated
  prompt, output filename, and status (`success` / `failed` / `dry-run`).
- Retries a failed image generation automatically (up to 2 retries) with a
  short backoff, and logs every failure (including prompt-generation
  failures) to `output/errors.log`.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Get a Gemini API key from https://aistudio.google.com/apikey.

3. Copy `.env.example` to `.env` and fill in your key:

   ```bash
   cp .env.example .env
   ```

   Or just export it in your shell:

   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

4. (Optional) Drop reference images (character sheets, style boards, etc.)
   into `reference_photos/`. Any image files there are attached to every
   generation call.

## Usage

```bash
python generate_images.py --script script.txt --output output
```

### Flags

| Flag           | Description                                                          | Default      |
|----------------|-----------------------------------------------------------------------|--------------|
| `--script`     | Path to the narration script (required)                               | -            |
| `--output`     | Output folder for images + `shots.csv`                                | `output`     |
| `--references` | Folder with reference images                                          | `reference_photos` |
| `--start`      | First shot number to generate (1-indexed)                             | first line   |
| `--end`        | Last shot number to generate (inclusive)                              | last line    |
| `--model`      | `flash`, `pro`, or a raw Gemini image model id                        | `flash`      |
| `--text-model` | Gemini text model used to write prompts (defaults to match `--model`) | `gemini-2.5-flash` |
| `--aspect`     | Aspect ratio hint passed to the prompt writer                         | `16:9`       |
| `--dry-run`    | Skip image generation; still writes real prompts to `shots.csv`       | off          |
| `--rule-based` | Skip AI segmentation and the LLM prompt writer; one shot per line, offline heuristic prompts | off |
| `--resegment`  | Ignore any cached `output/shots_plan.json` and re-cut the script into shots (shot numbers may change) | off |

`--dry-run` still calls the (cheap) text model by default, since the point
is to preview the *real* prompts before spending image-generation credits.
Combine it with `--rule-based` for a fully offline, no-API-key preview of
shot count and filenames.

### Examples

Preview the real LLM-written prompts without generating any images:

```bash
python generate_images.py --script script.txt --dry-run
```

Preview shot structure completely offline (no API key needed):

```bash
python generate_images.py --script script.txt --dry-run --rule-based
```

Only regenerate shots 5 through 10:

```bash
python generate_images.py --script script.txt --start 5 --end 10
```

Use the higher-quality model for both prompt writing and image generation:

```bash
python generate_images.py --script script.txt --model pro
```

## Style guide

The full **Beyond the Baseline** creative direction — character design and
continuity across beginner/competitive/elite stages, camera and scene
variety rules, court geometry rules, negative rules, prompt length targets,
etc. — lives in `style_preset.CHANNEL_STYLE_GUIDE` and is sent to the text
model as its system instruction for every shot. Edit that constant to
retune the channel's visual identity; edit `prompt_llm.py` to change how
much script/history context each shot gets.

`style_preset.py` also holds the offline fallback builder
(`build_prompt_fallback`) and its variety pools (locations, camera angles,
lighting) — useful for tuning the safety-net path or for `--rule-based`
runs, but it doesn't implement the full guide's judgment calls the way the
LLM path does.

## Notes

- Shot numbers are assigned sequentially over the segmented shot list (see
  above), not raw script lines, so `--start`/`--end` reference the same
  numbering as a full run as long as `output/shots_plan.json` is still
  cached for that script; re-running a partial range only updates those
  rows in `shots.csv`.
- Filenames are sanitized (lowercased, alphanumeric + underscores only,
  truncated) so they're always safe to use.
- Re-running a shot whose previous status was `failed` tells the prompt
  writer to lean on the guide's "scenes that previously failed" exception
  (a longer, more explicit prompt) automatically.
