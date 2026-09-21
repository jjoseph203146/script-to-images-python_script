# Handoff: script_to_images local web UI

## Overview

A single-user local web front end for the existing `script_to_images` CLI —
paste a narration script, manage reference photos, set the CLI flags, run the
pipeline with live per-shot progress, review the generated frames in a grid,
reroll any frame you don't like, and zip the whole `output/` folder.

The pipeline itself is **not** reimplemented. The web app imports and calls it.

Target repo: `jjoseph203146/script-to-images-python_script`
(branch `claude/script-to-images-tool-lcfxjg`)

## About the design files

`index.html` in this bundle is a **working, production-shaped front end**, not a
throwaway mock — the brief called for "a single HTML/JS page, no build step",
and that is exactly what it is: vanilla HTML + CSS + JS, no framework, no
bundler, no dependencies beyond two Google Fonts. It is intended to be dropped
into the repo as `templates/index.html` and served by Flask.

That said: it is a front end against a backend that **does not exist yet**.
Boot it today and it shows the empty first-run state and a
"Backend not reachable" toast. `BACKEND.md` is the contract it expects —
implement that, and the page works as-is.

`Script to Images Web UI.dc.html` is the design exploration it came from
(five earlier layout studies plus the chosen direction). Reference only; it
needs the Omelette runtime to render and should not be shipped.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, radii, states, and copy.
`index.html` carries all of it as real CSS — there is no separate spec to
translate. Recreate nothing; wire up the backend.

## Files in this bundle

| File | What it is |
| --- | --- |
| `index.html` | The complete front end. Copy to `templates/index.html`. |
| `BACKEND.md` | **Start here.** Endpoint contract, SSE event list, the `generate_images.py` refactor, reroll semantics. |
| `Script to Images Web UI.dc.html` | Design exploration (turn 1 = five layout studies, turn 2 = the chosen direction). Reference only. |
| `reference_photos/` | The 14 real reference JPEGs from the repo, used in the design. Already in the repo — do not re-add. |

## Screens / views

There is **one screen** plus three overlays.

### Main screen — two-pane console

- Full-viewport, `overflow:hidden` on `body`. Column flex: 54px top bar, then a
  row-flex `main` that fills the rest.
- **Top bar** — 54px, `#0D1B2E`, white. Left: `script_to_images` (IBM Plex Mono
  600/13), a `LOCAL · <host>` pill (1px `rgba(255,255,255,.22)` border, 999px
  radius, mono 500/9, `.12em` tracking), and the channel name in 11.5px sans at
  55% white. Right: two status dots (6px) with mono 11.5px labels — SSE state
  and key state. The live dot is `#F0EBE1` with a 1.4s opacity pulse.
- **Left rail** — fixed 372px, white, 20px padding, 18px gap, `overflow:auto`,
  1px right border `rgba(13,27,46,.10)`. Sections, each with a mono 10px
  `.14em`-tracked uppercase eyebrow in `#8C9AB0`:
  - **SCRIPT** — a 12px-radius box with a 3-line mono peek (11.5px/1.85,
    `#5B6B82`) that swaps to a textarea when *Paste / edit* is pressed; footer
    row with `Paste / edit` / `Upload .txt` pills and the filename in mono 11px.
  - **REFERENCE PHOTOS** — 8-column grid of 1:1 `object-fit:cover` thumbnails
    at 6px radius, plus a dashed `+` tile. Drag-and-drop anywhere on the grid.
    Each thumb's `title` is its real filename + size.
  - **SETTINGS** — one control per CLI flag, labelled with the flag itself in
    mono 10.5px: `--model` and `--aspect` selects (custom chevron, native arrow
    suppressed), `--text-model` text input placeholdered `auto — gemini-3.6-flash`,
    `--start`/`--end`, `--output`/`--references` (tinted `#F6F9FC` — rarely
    changed), `--dry-run` and `--rule-based` toggles, then the masked
    `GEMINI_API_KEY` field with its session-only note.
  - **Footer** (pushed down with `margin-top:auto`) — the primary
    `Generate N shots (start–end)` pill, which swaps to a red
    `Stop after current shot` while running.
- **Right pane** — fills remaining width, `#F6F9FC`:
  - **Run header** (white, bottom border): title `Shot 047 of 200` (600/21,
    `-.015em`), a mono subline naming the resolved image model, aspect, ref
    count, prompt model, and `2 retries (2s, 4s backoff)`; three right-aligned
    counts (SUCCESS green, FAILED red, QUEUED dim).
  - **Status ribbon** — a flex strip of **one 12px-tall segment per shot**,
    1px gaps, colored `#0D1B2E` success / `#D6584A` failed / `#F0EBE1` active /
    `#DCE5EF` queued. Clicking a segment scrolls the grid to that shot. This is
    what replaces a scrolling per-shot log: 200 shots stay legible in 12px of
    vertical space.
  - **Ticker** — one row, `#F6F9FC` 10px radius: shot number, narration line
    (single-line ellipsis), filename, and a status badge.
  - **Grid header** — `OUTPUT/` eyebrow, the click hint, and
    All / Done / Failed / Queued filter pills.
  - **Grid** — the scroll region (`flex:1`, `overflow:auto`, 18px/22px padding).
    `repeat(auto-fill, minmax(112px, 1fr))`, 14px row / 12px column gap. Each
    tile is a 16:9 frame at 7px radius with a mono shot-number chip top-left and
    an 8px mono filename caption beneath.
  - **Footer** (white, top border) — the `output/errors.log · N` button (turns
    red-tinted when non-empty), a disk summary, and the `Download all (.zip)`
    navy pill.

### Overlay: zip confirmation

620px modal, 16px radius, `rgba(13,27,46,.5)` scrim, 200ms fade + 4px rise.
Names the archive contents in a bordered manifest (PNG count + size,
`shots.csv` row count, an `errors.log` checkbox), and when a run is still in
flight adds a cream callout stating how many shots are left and that the zip is
a snapshot. Primary action `Save output.zip — 66.2 MB`.

### Overlay: errors.log

900px navy panel; the raw log in mono 11px/1.9, pre-wrapped, with the failing
lines tinted `#F2A69C`. Copy button. Replaces "go read the file".

### Overlay: full-size viewer

1040px navy panel. Filename + status badge + metadata, arrow-key navigation,
the frame at 16:9 `object-fit:contain`, a version strip when the shot has been
rerolled, the narration line, the full prompt in mono, and side actions
(Reroll / Copy prompt / Download frame) plus a facts block naming the ref count,
image model, and prompt source.

## Interactions & behavior

- **Click a finished frame** → opens the viewer. **Shift-click** → rerolls it
  immediately. A failed frame click → retries directly. Queued and in-flight
  tiles ignore clicks. The hover state on a finished tile reveals a `reroll`
  strip along the bottom (`::after`, `rgba(13,27,46,.86)`).
- **Reroll** → tile goes navy + pulses (`REROLLING`), then swaps to the new
  frame with a cream `vN` chip, and a toast reports the new version.
  See `BACKEND.md` §5 — the previous PNG is preserved as `NNN_slug.vK.png`.
- **Live progress** arrives over SSE (`/api/stream`), never polling. Tiles are
  patched individually (`patchShot`) rather than re-rendering the grid, so a
  200-shot grid stays smooth.
- **Ribbon click** → scrolls the grid to that shot.
- **Filters** re-render the grid in place; a filter with no matches shows the
  empty state with adjusted copy.
- **Download all** → a plain `window.location.href` navigation (not `fetch`),
  so the browser's native save dialog picks the destination and nothing is held
  in a blob.
- **Keyboard**: `Esc` closes any overlay; `←`/`→` step shots in the viewer;
  `r` rerolls the shot in the viewer.
- **Transitions**: 150ms `cubic-bezier(.16,1,.3,1)` on color/border/background;
  200ms on overlays; 1.1–1.4s opacity pulse on live indicators. No movement on
  hover; `scale(.98)` on button press.
- **Refresh-safe**: on boot the UI reads `/api/state` and overlays
  `shots.csv` onto the parsed script, so a reload mid-run restores the grid and
  reattaches the stream.

## State management

Single `state` object in `index.html`:

| Key | Meaning |
| --- | --- |
| `shots[]` | `{n, nnn, line, file, prompt, promptSource, status, versions, bytes, retry, stamp}` |
| `refs[]` | `{name, size}` from `/api/references` |
| `scriptText`, `scriptName` | current script |
| `running`, `activeN` | run state, driven entirely by SSE |
| `filter` | `all` / `success` / `failed` / `queued` |
| `errors` | raw `errors.log` text |
| `keySet` | whether the server holds a key |
| `viewerN` | shot open in the viewer |

`status` values match `shots.csv` exactly — `success`, `failed`, `dry-run` —
plus two client-only transient states, `queued` and `running`/`rerolling`.
**`shots.csv` is the source of truth**; the client never invents a status.

`slug()` in the JS is a faithful port of `style_preset.sanitize_filename`
(6 words, 40 chars, trailing underscore stripped) used only for optimistic
filenames before the backend confirms. Keep the two in sync.

## Design tokens

All declared as CSS custom properties at the top of `index.html`.

**Color** — `--navy #0D1B2E`, `--navy2 #16294A`, `--dim #5B6B82`,
`--dim2 #8C9AB0`, `--faint #B9C4D2`, `--bg #F6F9FC`, `--bg2 #EAF0F7`,
`--card #FFFFFF`, `--cream #F0EBE1`, `--creamline #E4DCCB`,
`--green #2F9969` (bg `#EFF8F3`, ink `#24784F`), `--red #D6584A`
(bg `#FBF1F0`, ink `#B8453A`), `--line rgba(13,27,46,.10)`,
`--line2 rgba(13,27,46,.18)`.

**Type** — Instrument Sans (400/500/600) for UI, IBM Plex Mono (400/500) for
every filename, flag, shot number, log line, and prompt. Display 600/21–24px at
`-.015em`/`-.02em`; body 12.5–14px; labels 10–11.5px; eyebrows mono 10px at
`.14em` uppercase. Frame captions 8px mono — the one sub-10px size, used only
for filenames under thumbnails.

**Radius** — pill `999px`, panel `16px`, card `12px`, input `10px`,
frame `7px`, chip `6px`.

**Shadow** — `0 16px 48px rgba(13,27,46,.22)` on overlays and the toast. None
elsewhere; separation is hairline borders.

**Motion** — `150ms`/`200ms` `cubic-bezier(.16,1,.3,1)`; `pulse` keyframe
1.1s (tiles) / 1.4s (status dots).

Derived from the Luminate design system (light-first navy/cream, Instrument
Sans + IBM Plex Mono, pill actions, hairline separation). If the repo later
adopts a different system, the token block at the top of `index.html` is the
only thing to swap.

## Assets

- `reference_photos/*.jpg` — the 14 real reference images, already in the repo.
  The UI serves them through `/api/references/<name>`.
- No icons library. The handful of glyphs (chevron, close, arrows, checkmark)
  are inline SVG paths in the markup.
- No logo — the wordmark is set in type.
- Fonts load from Google Fonts. For a fully offline tool, vendor the two
  families into `static/fonts/` and swap the `<link>` for `@font-face`.

## Open questions for the user

1. **Reroll history.** The design keeps the previous frame as
   `NNN_slug.vK.png`. If disk growth matters more than undo, drop it — but then
   a stray click is destructive.
2. **`script.txt` overwrite.** `POST /api/script` currently writes the working
   script file. Should pasting a new script overwrite the repo's `script.txt`,
   or write to a scratch file like `output/script.current.txt`?
3. **Range reroll.** Rerolling 40–60 in one action isn't in this build; the
   ribbon could support drag-select if it's wanted.
