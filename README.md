# script_to_images

Generate one image per narration line for faceless YouTube videos, using
Google Gemini image generation. Built for the **Beyond the Baseline** tennis
channel's recurring visual identity, but works for any script.

## What it does

- Reads `script.txt`, one narration line per line (blank lines are skipped).
- Builds a short image prompt per line: narration + the channel's style preset
  (extra tennis-court geometry is only added when a line mentions the court,
  serving, rallies, etc.).
- Optionally feeds in reference images from a `references/` folder so Gemini
  stays consistent with your character design.
- Generates one image per line with Google Gemini and saves them as
  numbered PNGs in `output/`, e.g. `001_you_open_your_phone.png`.
- Writes `output/shots.csv` with shot number, narration line, generated
  prompt, output filename, and status (`success` / `failed` / `dry-run`).
- Retries a failed generation automatically (up to 2 retries) with a short
  backoff, and logs every failure to `output/errors.log`.

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
   into `references/`. Any image files there are attached to every
   generation call.

## Usage

```bash
python generate_images.py --script script.txt --output output
```

### Flags

| Flag         | Description                                                        | Default      |
|--------------|---------------------------------------------------------------------|--------------|
| `--script`   | Path to the narration script (required)                             | -            |
| `--output`   | Output folder for images + `shots.csv`                              | `output`     |
| `--references` | Folder with reference images                                      | `references` |
| `--start`    | First shot number to generate (1-indexed)                           | first line   |
| `--end`      | Last shot number to generate (inclusive)                            | last line    |
| `--model`    | `flash`, `pro`, or a raw Gemini model id                             | `flash`      |
| `--aspect`   | Aspect ratio hint baked into the prompt                              | `16:9`       |
| `--dry-run`  | Print prompts without calling the API or generating images          | off          |

### Examples

Preview prompts for the whole script without spending API calls:

```bash
python generate_images.py --script script.txt --dry-run
```

Only regenerate shots 5 through 10:

```bash
python generate_images.py --script script.txt --start 5 --end 10
```

Use the higher-quality model:

```bash
python generate_images.py --script script.txt --model pro
```

## Style preset

Every image uses this recurring visual identity unless the line clearly
calls for something else:

- minimalist flat 2D cartoon illustration
- 16:9 widescreen
- faceless fictional tennis character
- large white circular head
- two small black oval eyes
- tiny simple mouth
- thin dark limbs
- simplified athletic body
- not realistic, no logos, no watermark

See `style_preset.py` to tune the preset or the keyword list that triggers
extra court-geometry detail.

## Notes

- Shot numbers are assigned sequentially over non-empty lines in the whole
  script, so `--start`/`--end` reference the same numbering as a full run,
  and re-running a partial range only updates those rows in `shots.csv`.
- Filenames are sanitized (lowercased, alphanumeric + underscores only,
  truncated) so they're always safe to use.
