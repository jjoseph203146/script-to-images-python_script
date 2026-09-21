# Prompt for Claude Code

Copy everything below the line into Claude Code, run from the root of the
`script-to-images-python_script` repo with `design_handoff_web_ui/` committed
(or unzipped) at the repo root.

---

Read `design_handoff_web_ui/BACKEND.md` and `design_handoff_web_ui/README.md`
in full before writing any code. `BACKEND.md` is the contract — follow it
exactly; do not redesign the API, the event names, or the payload shapes.

Build the local web UI for this tool. `design_handoff_web_ui/index.html` is a
complete, finished front end — vanilla HTML/CSS/JS, no build step. Do **not**
rewrite it, restyle it, reformat it, or port it to a framework. Copy it to
`templates/index.html` verbatim. Your job is the Python side it talks to.

## What to build

1. **Refactor `generate_images.py`** per `BACKEND.md` §2. Extract everything in
   `main()` after `parse_args()` into an importable
   `run_pipeline(...)` with the exact signature given there, including the new
   `api_key`, `keep_versions`, `on_event`, and `should_stop` parameters.
   `main()` becomes a thin adapter that calls it, so
   `python generate_images.py --script script.txt` keeps behaving identically.

2. **Add `app.py`** — a Flask app serving `templates/index.html` at `/` and
   implementing every endpoint in `BACKEND.md` §3, the SSE stream in §4, the
   reroll behavior in §5, the settings object in §6, and the API-key handling
   in §7. Add `flask` to `requirements.txt`.

3. **Verify against the real pipeline.** Start the server, load `script.txt`,
   and run with `--dry-run --rule-based` (no API key, no spend) end to end.
   Confirm: the ribbon and grid fill in over SSE, `shots.csv` gets 13 rows with
   `status=dry-run`, the errors.log panel opens, and `Download all (.zip)`
   produces a zip with the PNG names intact. Then reroll one shot and confirm
   the version file appears.

## Non-negotiables

- **Do not touch `CHANNEL_STYLE_GUIDE` in `style_preset.py`** or the
  prompt-composition logic in `prompt_llm.py`. Not one character. The web UI is
  a front end over the existing pipeline.
- **Do not shell out** to `generate_images.py`. Import `run_pipeline` and call
  it in a worker thread.
- **Preserve every current behavior**: shot numbering over the whole script
  (so `--start`/`--end` reference the same numbers as a full run),
  `MAX_RETRIES = 2` with the 2s/4s doubling backoff, `PROMPT_MAX_RETRIES = 1`
  then fall back to `build_prompt_fallback`, `retry_hint` set when the previous
  `shots.csv` status was `failed`, reference images loaded sorted by name and
  attached to every call, `image_config.aspect_ratio` forced to `--aspect`, and
  `log_error` appending `[YYYY-MM-DD HH:MM:SS] message` to `output/errors.log`.
- **`shots.csv` keeps exactly five columns**:
  `shot_number, narration_line, prompt, filename, status`. It is the source of
  truth for status. `versions` and `bytes` in the API are derived server-side
  (glob for `NNN_slug.v*.png`, `os.path.getsize`) — never new columns.
- **One shot at a time.** No parallel generation, so retry and rate-limit
  behavior stay identical to the CLI. A reroll requested mid-run queues behind
  the current shot.
- **The API key lives in one module-level variable.** Never written to disk,
  never logged, never returned by `/api/state` (only `key_set: true|false`).
- Single-user local tool: no auth, no sessions, no database, no login.

## Definition of done

- `python app.py` serves a working UI at `http://127.0.0.1:5000`.
- `python generate_images.py --script script.txt --dry-run` still works exactly
  as before the refactor.
- `templates/index.html` is byte-identical to
  `design_handoff_web_ui/index.html`.
- A dry run, a real run, a stop mid-run, a reroll, a zip download, and a
  browser refresh mid-run all behave as described in `README.md` under
  "Interactions & behavior".

When you're done, tell me which files you changed and paste the diff of
`generate_images.py` so I can check the refactor didn't change any pipeline
behavior.
