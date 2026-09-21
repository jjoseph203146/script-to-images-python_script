# Backend contract — what Claude Code needs to build

The front end (`index.html`) is complete and calls only the endpoints below.
Nothing in `style_preset.py` (especially `CHANNEL_STYLE_GUIDE`) or
`prompt_llm.py` changes. `generate_images.py` is **refactored, not rewritten**.

Target repo: `jjoseph203146/script-to-images-python_script`
branch `claude/script-to-images-tool-lcfxjg`

---

## 1. File layout to add

```
app.py                     # Flask app + SSE + zip           (new)
templates/index.html       # copy of design_handoff_web_ui/index.html  (new)
requirements.txt           # += flask
generate_images.py         # refactored: main() -> run_pipeline()   (edit)
```

Run with `python app.py`, serving `http://127.0.0.1:5000`. Single user,
no auth, no database. All mutable state lives in module-level globals.

---

## 2. Refactor `generate_images.py`

Extract everything inside `main()` after `parse_args()` into one importable
function. `main()` becomes a thin adapter so the CLI keeps working byte-for-byte.

```python
def run_pipeline(
    script_path,            # Path
    output_dir="output",
    references_dir="reference_photos",
    start=None, end=None,
    model="flash", text_model=None, aspect="16:9",
    dry_run=False, rule_based=False,
    api_key=None,           # NEW: passed in, not read from env at call time
    keep_versions=True,     # NEW: see §5
    on_event=None,          # NEW: callable(event_name: str, payload: dict)
    should_stop=None,       # NEW: callable() -> bool, checked between shots
):
    ...
    return {"success": n, "failed": n, "stopped": bool}
```

Rules for the refactor:

- **Keep every existing behaviour.** `read_script_lines` numbering over the
  whole script, `start`/`end` selecting a sub-range of that same numbering,
  `load_reference_images` sorted by name, `MODEL_MAP` / `TEXT_MODEL_MAP`,
  `MAX_RETRIES = 2` with `RETRY_BACKOFF_SECONDS` doubling (2s, 4s),
  `PROMPT_MAX_RETRIES = 1` then fall back to `build_prompt_fallback`,
  `load_existing_shots` + `write_shots_csv` with fieldnames
  `["shot_number","narration_line","prompt","filename","status"]`,
  `retry_hint = existing_rows.get(n, {}).get("status") == "failed"`,
  and `log_error` appending `[YYYY-MM-DD HH:MM:SS] message` to
  `output/errors.log`.
- **`build_client(api_key)`** takes the key as an argument. Fall back to
  `os.environ["GEMINI_API_KEY"]` when it's `None` so the CLI is unchanged.
  Never print or log the key.
- `should_stop()` is checked at the top of each shot loop iteration; when it
  returns `True`, break, write `shots.csv`, and return `stopped=True`.
- `write_shots_csv` is also called after **every** shot (not only at the end)
  so a crash or stop still leaves an accurate CSV. Keep the final write too.
- `on_event` is called at the points listed in §4. Make it defensive
  (`if on_event: on_event(...)`) so the CLI path passes `None`.

`main()` after the refactor:

```python
def main():
    args = parse_args()
    run_pipeline(
        Path(args.script), args.output, args.references,
        args.start, args.end, args.model, args.text_model, args.aspect,
        args.dry_run, args.rule_based,
    )
```

---

## 3. Endpoints

All JSON unless noted. Errors: non-2xx with a plain-text body — the UI
surfaces `await r.text()` in a toast.

| Method | Path | Body / query | Returns |
| --- | --- | --- | --- |
| GET | `/` | — | `templates/index.html` |
| GET | `/api/state` | — | see below |
| POST | `/api/script` | `{text, name}` | `{lines: int}` — writes `script.txt` (or the working script path) |
| GET | `/api/references` | — | `{references: [{name, size}]}` |
| POST | `/api/references` | multipart `files[]` | `{references: [...]}` — saves into `reference_photos/` |
| DELETE | `/api/references/<name>` | — | `{references: [...]}` |
| GET | `/api/references/<name>` | — | the image bytes |
| POST | `/api/session/key` | `{key}` | `204` — stores in a module global only |
| POST | `/api/run` | settings object (§6) | `{ok: true}` — starts a worker thread |
| POST | `/api/stop` | — | `{ok: true}` — sets the stop flag |
| POST | `/api/reroll/<n>` | settings object | `{ok: true}` — see §5 |
| GET | `/api/stream` | — | `text/event-stream`, see §4 |
| GET | `/api/output/<filename>` | `?download=1` optional | the PNG (`as_attachment` when `download=1`) |
| GET | `/api/errors` | — | `{text: str}` — contents of `output/errors.log`, `""` if absent |
| GET | `/api/shots.csv` | — | `output/shots.csv` as a download |
| GET | `/api/download.zip` | `?errors=0` optional | streamed zip, `as_attachment=True` |

### `GET /api/state`

Everything the UI needs to rehydrate after a refresh. `shots` comes straight
from `shots.csv` — it is the source of truth for status.

```json
{
  "running": false,
  "key_set": false,
  "settings": {"model":"flash","aspect":"16:9","output":"output","references":"reference_photos"},
  "script": {"name": "script.txt", "text": "You open your phone.\n..."},
  "references": [{"name":"Gemini_Generated_Image_4e2sw24e2sw24e2s.jpg","size":474977}],
  "shots": [
    {"shot_number":1,"narration_line":"You open your phone.",
     "prompt":"Same Beyond the Baseline white circular-head character…",
     "filename":"001_you_open_your_phone.png","status":"success",
     "versions":1,"bytes":1402331}
  ]
}
```

`versions` and `bytes` are derived server-side (count `NNN_slug.v*.png`
siblings; `os.path.getsize` on the PNG) — they are **not** new CSV columns.
Keep `shots.csv` exactly five columns.

### `GET /api/download.zip`

Stream a zip containing every `*.png` in `output/` **with their original
`NNN_slug.png` names** (do not flatten or renumber), plus `shots.csv`, plus
`errors.log` unless `?errors=0`. Use `zipfile.ZipFile` over a
`tempfile.SpooledTemporaryFile` and `send_file(..., as_attachment=True,
download_name="output.zip")`. The browser's own save dialog then picks the
destination — the UI deliberately triggers this with a plain
`window.location.href`, not `fetch`, so no blob is held in memory.

---

## 4. SSE events

One broadcast channel; a `queue.Queue` per connected client is enough (there
is only ever one browser). Each event is `event: <name>\ndata: <json>\n\n`.
Send a `: ping\n\n` comment every 15s so the connection survives idle gaps.

| Event | Emitted | Payload |
| --- | --- | --- |
| `run_start` | once, before the loop | `{total, start, end, model, text_model, aspect, dry_run, rule_based}` |
| `shot_start` | top of each iteration | `{shot_number, narration_line}` |
| `shot_prompt` | after the prompt is built | `{shot_number, prompt, source}` — `source` is `"llm"` or `"rule-based"` |
| `shot_retry` | inside `generate_with_retries` on each failure | `{shot_number, attempt, max, error, backoff}` |
| `shot_done` | after the status is decided | `{shot_number, filename, status, versions, bytes}` — `status` is `success` / `failed` / `dry-run` |
| `run_done` | after the final CSV write | `{success, failed, dry_run, stopped}` |
| `log` | every `log_error` call | `{line}` — the exact line appended to errors.log |

`shot_retry` needs a small hook in `generate_with_retries`; pass `on_event`
and `shot_number` down into it. `log` is easiest as a wrapper around
`log_error`.

---

## 5. Reroll — the one new behaviour

`POST /api/reroll/<n>` is the same pipeline over a single shot:
`run_pipeline(start=n, end=n, ...)`. Two things make it a reroll rather than
a retry:

1. **A fresh prompt.** The LLM path already runs at `temperature=0.9`, so
   calling it again produces a genuinely different prompt. Do not cache or
   reuse the stored prompt. (`retry_hint` stays keyed off
   `status == "failed"` exactly as today — a reroll of a `success` row does
   not set it.)
2. **Version preservation.** Before writing, if `out_path` exists and
   `keep_versions` is true, rename it to `NNN_slug.vK.png` where `K` is the
   lowest free integer starting at 1. The live file always keeps the plain
   `NNN_slug.png` name, so nothing downstream breaks and `shots.csv` needs no
   new column. `versions` reported over the API is
   `1 + len(glob("NNN_slug.v*.png"))`.

Without (2) a single stray click destroys a frame the user liked — that is
why it's in scope. Exclude `*.v*.png` from `download.zip` unless you want the
history in the archive (the UI assumes they're excluded).

Reroll must work **while a run is in progress**: queue it behind the current
shot rather than starting a second `genai` client in parallel.

---

## 6. Settings object

Sent by `POST /api/run` and `POST /api/reroll/<n>`. Maps 1:1 to the CLI flags.

```json
{
  "model": "flash",            // flash | pro  -> MODEL_MAP / TEXT_MODEL_MAP
  "text_model": null,          // null = derive from model
  "aspect": "16:9",
  "start": null,               // null = 1
  "end": null,                 // null = last shot
  "dry_run": false,
  "rule_based": false,
  "output": "output",
  "references": "reference_photos"
}
```

Validation: `start`/`end` clamped to `[1, len(shots)]`; reject a run when
`(not dry_run or not rule_based)` and no key is set — matching
`need_client` in the current `main()`.

---

## 7. API key handling

- Stored in one module-level variable, e.g. `_SESSION_KEY: str | None`.
- Never written to `.env`, never logged, never returned by `/api/state`
  (only `key_set: true|false`).
- Passed into `run_pipeline(api_key=...)` per run.
- Cleared on process exit — that's the whole lifetime. The UI labels this
  "Held in server memory for this session only".

---

## 8. Things to deliberately not do

- No auth, no sessions, no database, no user accounts.
- No new columns in `shots.csv` — five columns, as today.
- No edits to `CHANNEL_STYLE_GUIDE` or the prompt-composition logic in
  `prompt_llm.py`.
- No shelling out to `generate_images.py` — import `run_pipeline` and call it.
- No parallel generation. One shot at a time, as the CLI does, so retry
  behaviour and rate-limit backoff stay identical.
