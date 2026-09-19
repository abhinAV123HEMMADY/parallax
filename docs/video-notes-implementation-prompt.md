# Implementation prompt — Watch & Note as a Chrome extension

Timestamped notes with real frame captures on any YouTube video, feeding Mentra's backend.

Paste everything below the line into a fresh Claude Code session at the repo root.

---

## Context

You are adding a **Chrome extension** client to Mentra, an existing topic-driven tutoring
platform in this repo. The repo currently has `backend/` (FastAPI), `frontend/` (React/Vite
SPA), and `mcp_servers/`. You are adding `extension/` as a second frontend against the same
backend, plus the backend surface it needs.

Read `README.md` first, then these files before writing anything:

- `backend/app/database.py` — `Base`, `get_db`, and why the engine uses `NullPool`
- `backend/app/models/video.py` and `backend/app/models/peer.py` — model conventions
- `backend/app/models/__init__.py` — every model must be registered here
- `backend/app/api/routes_learning.py` — route conventions (transaction ownership, errors)
- `backend/app/api/routes_users.py` — the existing learner endpoints
- `backend/app/schemas/learning.py` — schema conventions
- `backend/app/mastery/service.py` — how interaction signals become mastery and struggle events
- `backend/app/orchestrator/nodes/lesson_generator.py` — the LLM-node pattern (tool schema,
  `_SYSTEM`, `_stub_*`, graceful degradation)
- `backend/app/llm.py` — the single LLM entry point
- `backend/app/config.py` — settings, including `cors_origins`
- `backend/app/orchestrator/nodes/video_curator.py`, `mcp_servers/video_transcript/server.py`,
  and `backend/scripts/seed.py` (the `video_seed` list) — the existing video path
- `frontend/src/api/rest.ts` and `frontend/src/types.ts` — client conventions to mirror

Do not start coding until you have read those. Report a one-paragraph summary of the
conventions you found, then proceed.

## What this is, and why an extension

Mentra already finds the *exact timestamp* in a lecture that explains a topic
(`video_curator` → the Video Transcript MCP server). Today that's a dead-end `?t=123s` link,
and the transcript data behind it is four hand-seeded rows in `video_transcript_chunks`.

The extension turns YouTube itself into the workspace:

1. On any YouTube watch page, an injected panel lets the learner capture a note at the
   current playback second — **with a real cropped screenshot of the video frame**.
2. Notes render as a timeline; clicking one seeks the video.
3. Notes export to a PDF where every entry is a clickable link back to that exact second.
4. The learner can ask questions scoped to the video; answers cite timestamps.
5. Notes flow into Mentra's existing loop — they become FSRS flashcards, and repeated notes
   on one topic (opt-in) surface on the peer feed.

**Two capabilities exist only in an extension, and they are the justification for building
one.** Be aware of both, because they shape the design:

- **Frame capture.** A web page cannot screenshot a YouTube iframe — cross-origin means a
  tainted canvas and `toDataURL()` throws. `chrome.tabs.captureVisibleTab` is not page
  JavaScript, so it can.
- **Real transcripts.** Server-side transcript fetching is the flakiest part of any YouTube
  integration: `youtube-transcript-api` gets IP-blocked from cloud hosts. A content script
  runs *on* youtube.com, so fetching the caption track is same-origin and just works. This
  means the extension can populate `video_transcript_chunks` with real captions for arbitrary
  videos, replacing the four seeded rows. **This is the most valuable thing in the build** —
  it upgrades the existing pgvector timestamp search from a demo to something real. It only
  pays off once Step 0 replaces the placeholder embedding function, which is why Step 0 is
  first and not optional.

## Division of labour — do not port the app into the extension

The extension is a capture client, not a second Mentra. Keep it thin and deep-link out.

| Surface | Extension | Web app (`frontend/`) |
|---|---|---|
| Capture note at timestamp | ✅ | — |
| Frame screenshot | ✅ only here | impossible |
| Seek to a note | ✅ | — |
| Ask about this video | ✅ | — |
| Caption ingest | ✅ only here | impossible |
| PDF export | deep-links to web app | ✅ implemented here |
| Mastery Map, exam planner, peer feed, tutor hub, Protégé Mode, lesson/quiz/flashcards | ✗ | ✅ unchanged |

Any extension button for something heavy opens the web app in a new tab. Do not reimplement.

## Hard constraints

- **Do not change the mastery weights** in `backend/app/mastery/service.py`
  (`QUIZ_WEIGHT`, `FLASHCARD_WEIGHT`, `PROTEGE_WEIGHT`) and do not add notes as a fourth
  mastery signal. Taking a note is an *attention* signal, not a demonstration of
  understanding — folding it in would mean a diligent note-taker scores as struggling, and
  the README defines that score as demonstrated understanding. Notes emit a `StruggleEvent`
  instead (Step 5).
- **Every LLM call must degrade to a deterministic stub** with the identical output shape,
  exactly like the existing nodes. The whole system must still run with no API key. Never let
  an LLM failure raise into a route.
- **No fabricated data anywhere.** If caption extraction fails for a video, the panel says so
  and notes still save without an excerpt. Do not invent transcript text.
- **Match the existing comment style.** This codebase explains *why*, names tradeoffs, and
  documents non-obvious decisions (see the `NullPool` comment in `database.py`). Do not write
  comments that restate the code. The extension has an unusual number of
  non-obvious constraints — document them where they bite.
- Do not use `any` in TypeScript. Do not add a CSS or component library to the extension.

## MV3 constraints you must design around, not discover

Read these before Step 6. Each one will otherwise cost you an hour.

1. **YouTube is an SPA.** Navigating between videos does not reload the page, so a content
   script that runs once at `document_idle` never runs again. Listen for the
   `yt-navigate-finish` event on `document` and re-initialise. Test by clicking from one
   video to another.
2. **Service workers die.** The MV3 background worker is terminated after ~30 seconds idle.
   Keep no in-memory state, hold no WebSocket (leave the existing `api/ws.py` streaming to the
   web app), and persist anything that must survive in `chrome.storage`.
3. **No DOM in the service worker.** `Image` and `document.createElement('canvas')` do not
   exist there. Cropping a screenshot requires `createImageBitmap()` + `OffscreenCanvas` +
   `convertToBlob()`.
4. **Content scripts run in an isolated world.** They cannot read page globals like
   `ytInitialPlayerResponse`. To reach them you must inject into the MAIN world
   (`chrome.scripting.executeScript({ world: 'MAIN' })`) and `postMessage` the result back.
5. **YouTube's CSS will destroy your panel and vice versa.** Mount the injected UI inside a
   **shadow root**. This is not optional.
6. **The extension ID changes** on every unpacked reload unless you pin it. Either add a `key`
   to the manifest or make the dev CORS origin permissive — decide, and document which.
7. **Cross-origin fetch from the extension** needs the backend origin in `host_permissions`.
   Do that *and* add the extension origin to the backend's CORS list.
8. **DRM content captures black.** Ordinary YouTube videos capture fine; protected content
   (rented movies) will not. Note it in the README rather than trying to fix it.

## Verified facts about this codebase — do not re-derive, and do not contradict

These were checked against the code. Trust them over your assumptions.

- `backend/scripts/init_db.py` does `from app.models import *` then
  `Base.metadata.create_all`. Registering a new model in `backend/app/models/__init__.py` is
  therefore enough for its table to be created. **But `create_all` never ALTERs an existing
  table** — any change to an existing model needs a hand-written migration. Prefer designs
  that add tables over designs that change them.
- `GET /users` and `POST /users` already exist in `backend/app/api/routes_users.py`.
- `Lesson` and `Flashcard` rows are created in
  `backend/app/orchestrator/nodes/stream_result.py`. Read it: it documents why the parent
  `Lesson` must be flushed before child `Flashcard` inserts (no `relationship()` is declared,
  so SQLAlchemy will not order the cross-table inserts and the FK can be violated).
- **`Flashcard.lesson_id` is a non-nullable FK to `lessons.id`.** There is no such thing as a
  lesson-less flashcard. This constrains Step 10 — see it.
- **`backend/app/fsrs/scheduler.py` has no card-initialisation function.** `fsrs_update`
  updates an existing card only. Initial values come from
  `backend/app/orchestrator/nodes/flashcard_fsrs.py`: `initial_stability = 2.0`,
  `DEFAULT_DIFFICULTY`, `elapsed_days = 0`, `due_date = now + next_interval(2.0)` days.
- `backend/app/orchestrator/nodes/prerequisite_graph.py` has only a **private, one-hop**
  `_upstream_of(db, topic_id)`. There is no depth or topological-order function anywhere.
- `backend/app/peer/engine.py` filters on two thresholds you must respect:
  `get_struggle_feed` returns only events with `visibility != "private"`, and
  `propose_squads_for_topic` requires `severity >= STRUGGLE_SEVERITY_CUTOFF` (0.5) within
  `SQUAD_WINDOW_DAYS` (14).
- **`pseudo_embed` is not a semantic embedding and pgvector similarity over it is noise.**
  It hashes the string, seeds an RNG, and emits a random unit vector, so any two distinct
  strings are near-orthogonal. Measured on the real function: `"limits"` vs
  `"Introduction to limits | Khan Academy"` scores **−0.043**, and `"derivatives"` vs
  `"derivative"` scores **+0.043**. Nothing that depends on embedding similarity can work
  until Step 0 replaces it.

## Build it in this order. Stop after each step and report.

### Step 0 — Real embeddings — ✅ ALREADY DONE, SKIP

**This step is complete. Do not redo it.** It shipped as `shared/mentra_embed` (an editable
package installed with `make install-shared`), backed by `BAAI/bge-small-en-v1.5` via
`fastembed`, 384-dim so no migration was needed. All five former `pseudo_embed` call sites in
`backend/scripts/seed.py` and the two vector-search MCP servers now use it. `embed_query`
applies bge's instruction prefix; `embed_document` does not — respect that asymmetry.
`MENTRA_EMBED=hash` still selects the old placeholder, `/health` reports the active backend,
and `make reembed` rewrites stored vectors after a model change (needed because vectors from
different embedders are not comparable). `backend/tests/test_embedding.py` covers it.

Verified end to end: `search_transcripts("how do I find the slope of a curve")` returns the
instantaneous-rate-of-change lecture first, over MCP, despite zero word overlap with its title.

The original spec is kept below for context only.

#### Original spec (for reference)

Two things in this build depend on semantic similarity: ranking ingested caption chunks
(Step 3's whole value) and mapping a video to a Mentra topic. Both are currently backed by
`pseudo_embed`, which — per the measurement above — ranks by noise. Ingesting real captions
behind a hash-based embedding produces a bigger table that searches no better.

Replace it:

- Add `fastembed` to `backend/requirements.txt`. Use `BAAI/bge-small-en-v1.5`, which outputs
  **384 dimensions** — exactly `EMBEDDING_DIM` in `backend/app/models/topic.py`, so **no
  schema change and no migration**. `fastembed` is ONNX-based and does not pull in PyTorch.
- Create one embedding module and route every caller through it. `pseudo_embed` is currently
  duplicated in `backend/scripts/seed.py`, `mcp_servers/video_transcript/server.py`, and
  `mcp_servers/tutor_match/server.py`. Read the comment at
  `mcp_servers/video_transcript/server.py:24` — the duplication is deliberate, to keep MCP
  servers dependency-free. That tradeoff was free for a hash function and is not free for a
  130 MB model loaded per process. Resolve it deliberately: extract a small shared package the
  MCP servers depend on, and say in your report that you broke the no-shared-dependency rule
  on purpose and why.
- **Load the model once at module import**, never per call. Note in a comment that each Celery
  prefork worker loads its own copy.
- Keep a `MENTRA_EMBED=hash|bge` setting in `config.py` defaulting to `bge`, so the project
  still runs where the model can't be downloaded.
- Re-run `make seed` so existing topic/tutor/transcript embeddings are regenerated. Stale
  384-dim hash vectors mixed with real ones would silently poison every ranking.

Acceptance: print cosine similarity for `"limits"` vs `"Introduction to limits | Khan Academy"`
and `"derivatives"` vs `"chain rule"` under the new embedder. The first must be clearly higher
than the second. Paste the real numbers.

### Step 1 — Shared API types and CORS

Two clients now consume the same API, so stop hand-writing types.

- Add a script that generates TypeScript from the backend's own OpenAPI schema
  (`openapi-typescript` against `http://localhost:8000/openapi.json`) into
  `shared/api-types.ts`, and a `make types` target for it. Both `frontend/` and `extension/`
  import from there. Do not retrofit all of `frontend/src/types.ts` — use generated types for
  the *new* endpoints only, and note the migration path in a comment.
- In `backend/app/config.py`, `cors_origins` is a comma-separated string. Add the extension
  origin. Document in `.env.example` how to find the unpacked extension's ID and that it
  changes on reload unless pinned.

Acceptance: `make types` produces a file containing the new note types once Step 2 lands;
`/health` responds to a `fetch` from the extension's service worker.

### Step 2 — `VideoNote` model

Create `backend/app/models/note.py`:

```python
class VideoNote(Base):
    __tablename__ = "video_notes"
    id: str                        # PK, uuid4 default, same pattern as StruggleEvent
    learner_id: str                # FK users.id
    video_id: str                  # YouTube video id
    video_title: str
    topic_id: str | None           # FK topics.id, nullable — resolved in Step 4
    t_seconds: int                 # playback position the note was captured at
    learner_text: str
    transcript_excerpt: str | None # caption text at t_seconds, supplied by the extension
    screenshot: str | None         # data URL of the cropped, downscaled frame
    created_at: datetime
```

Composite indexes on `(learner_id, video_id)` and `(learner_id, topic_id)`.
Register in `backend/app/models/__init__.py` (import **and** `__all__`).

On `screenshot`: storing a data URL in a text column is the wrong long-term answer — the right
one is object storage with a signed URL. Cap accepted payloads at **200 KB** (rejecting larger
with a 413), keep frames downscaled in Step 7, and write a comment stating the tradeoff and
what would replace it. Do not silently accept unbounded blobs.

Add `"note_marked"` to the `signal_type` comment enumeration on `StruggleEvent` in
`backend/app/models/peer.py`.

Acceptance: `python backend/scripts/init_db.py` creates the table with both indexes.

### Step 3 — Notes routes

`backend/app/schemas/notes.py`: `NoteCreate`, `NoteOut`, `VideoNotePack`, `TopicNotePack`.

`backend/app/api/routes_notes.py`, `APIRouter(prefix="/notes", tags=["notes"])`:

- `POST /notes` — create. Validate `screenshot` size. Resolve `topic_id` (Step 4). Emit the
  attention signal (Step 5). Return `NoteOut`.
- `GET /notes?learner_id=&video_id=` — notes for one video, ordered by `t_seconds`.
- `GET /notes/topic/{topic_id}?learner_id=` — `TopicNotePack`: notes across every video for a
  topic, grouped by video, notes ordered by `t_seconds` within each video.

  Videos are ordered by prerequisite depth. **There is no existing function for this** —
  `prerequisite_graph.py` only has a private one-hop `_upstream_of`. Write a real one: a new
  `backend/app/topics/graph.py` with `async def topic_depth(db, topic_id) -> int` doing a BFS
  over `PrerequisiteEdge`. `PrerequisiteEdge` has no cycle constraint, so **carry a visited
  set** or a cyclic seed will hang the request. Refactor
  `prerequisite_graph_node` to use the new module for its upstream lookup so there is one
  implementation, and keep its existing behaviour identical — it is covered by the demo
  walkthrough in the README, so verify the `u_amy` → `derivatives` → `limits` redirect still
  works after the refactor.
- `DELETE /notes/{note_id}?learner_id=` — 404 if missing, 403 if it belongs to another learner.
- `GET /notes/recent?learner_id=&limit=` — for the extension popup.

Register the router in `backend/app/main.py`. Routes own their transaction (`await db.commit()`),
matching `routes_learning.py`. Error details are lowercase strings.

Acceptance: `curl` each endpoint against a seeded DB and paste real responses in your report.

### Step 4 — Caption ingest and video→topic mapping

This is the step that makes the extension worth building. Two backend endpoints:

**`POST /notes/videos/{video_id}/transcript`** — accepts a caption track scraped by the
content script: `{ video_title, cues: [{ t_seconds, text }] }`. It:

- Groups cues into ~30–60 second chunks (YouTube cues are a few words each; one row per cue
  would make similarity search useless).
- Writes them as `VideoTranscriptChunk` rows embedded with the Step 0 embedder. This only has
  value because Step 0 landed first — ingesting captions behind `pseudo_embed` would build a
  bigger table that ranks by noise.
- Is idempotent: re-ingesting a video replaces its chunks rather than duplicating them.
- Caps how much it will accept per video (cue count and total characters) and rejects
  oversize payloads rather than embedding a three-hour lecture synchronously inside a request.

This means the existing `search_transcripts` MCP tool starts returning genuinely relevant
timestamps from videos the learner actually watched. Verify end to end and paste the real
relevance scores.

**Topic resolution** — a note on an arbitrary YouTube video has no Mentra topic. Implement
`GET /notes/videos/{video_id}/topic-suggestion` with **two** strategies and report which wins
on the seeded topics:

1. *Lexical:* normalised token overlap between `video_title` (plus ingested caption text) and
   each `Topic.name`. Deterministic, testable, and works with no model.
2. *Semantic:* nearest `Topic.content_embedding` by pgvector cosine distance.

Return `None` when the best score is below a threshold defined in `config.py` alongside
`gap_threshold`. Note that `Topic.content_embedding` is seeded from the topic **name only**
(see `seed.py`), so the semantic path is comparing a video title against an embedding of a
short label — expect it to be weaker than you assume, and let the measurement decide the
default. The panel shows the suggestion; the learner confirms or overrides; `POST /notes`
accepts an explicit `topic_id` that always wins. Never silently attach a note to a wrong
topic — an unmatched note is fine.

Acceptance: ingest captions for one real non-seeded video, show `search_transcripts` returning
a timestamp from it with its relevance score, and show both topic-suggestion strategies' scores
for that video.

### Step 5 — Notes as an attention signal

In `backend/app/mastery/service.py`, add a **new** function — do not modify `recompute_mastery`:

```python
async def record_note_signal(db, learner_id, topic_id, share: bool) -> None:
```

It inserts a `StruggleEvent` with `signal_type="note_marked"`. No-op when `topic_id` is None.
Does not commit — the route owns the transaction, same contract as `recompute_mastery`.

Write a docstring explaining why notes are deliberately *not* a mastery input. This is the most
important design decision in the feature; make it legible to the next reader.

**Severity must be derived, not fixed.** `backend/app/peer/engine.py` gates on
`severity >= STRUGGLE_SEVERITY_CUTOFF` (0.5) within `SQUAD_WINDOW_DAYS` (14), and
`get_struggle_feed` drops anything with `visibility == "private"`. A fixed low severity plus a
private default would make note signals completely inert — they would reach neither the feed
nor squad formation. Do not write a spec that claims otherwise.

Instead: **one note is not a struggle, but repeated notes on one topic are.** Count the
learner's `note_marked` events on this topic inside `SQUAD_WINDOW_DAYS` and scale severity so it
crosses 0.5 at the third note. Import the window and cutoff constants from `peer.engine` rather
than duplicating the numbers. `visibility` is `"connections"` when `share` is true and
`"private"` otherwise, defaulting to private — `POST /notes` takes the flag, and the panel has a
per-note share toggle that remembers the last choice in `chrome.storage.sync`.

Read `peer/engine.py` before writing this and confirm the two thresholds are still what this
says. Then prove the behaviour: a test asserting that notes one and two stay below the cutoff
and note three reaches it.

### Step 6 — Extension scaffold

Create `extension/` as its own Vite build (`@crxjs/vite-plugin` is the standard choice; if the
version you get fights the MV3 manifest, fall back to a manual build and say so). Manifest V3:

- `permissions`: `storage`, `scripting`, `activeTab`
- `host_permissions`: `*://*.youtube.com/*` and the backend origin
- `content_scripts`: matches `*://www.youtube.com/*`, `run_at: document_idle`
- `background.service_worker`
- `action` (popup), `options_page`
- `commands`: a keyboard shortcut for capture (e.g. `Alt+N`)

Files: `manifest.config.ts`, `src/background.ts`, `src/content/index.ts`, `src/popup/`,
`src/options/`, `src/lib/api.ts`, `src/lib/storage.ts`.

**Identity.** The backend has no auth — `frontend/src/LearnerContext.tsx` is a learner
*selector*. For now the options page lists learners from `GET /users` and stores the chosen
`learner_id` in `chrome.storage.sync`. State plainly in the README that this is not
authentication and that the production answer is a token issued by a `/link-extension` page in
the web app. Do not build a fake auth layer that implies more security than exists.

All backend calls go through the **service worker**, not the content script, so the request
origin is `chrome-extension://…` rather than `https://www.youtube.com`. The content script
talks to the worker via `chrome.runtime.sendMessage`. Write down why in a comment.

Acceptance: extension loads unpacked with no console errors; options page saves a learner;
popup shows `GET /notes/recent`.

### Step 7 — Content script: panel, player access, capture

**Player access.** Do not use the YouTube IFrame API — you are on the page itself. The
`<video>` element is directly accessible: `document.querySelector('video.html5-main-video')`
gives you `.currentTime` to read and to assign for seeking. Simpler and more robust than any
API wrapper.

**Panel.** Inject a panel below the player (`#secondary` or under `#below`). Mount it in a
**shadow root** with its own styles. Re-initialise on `yt-navigate-finish`. Handle
theater/fullscreen mode changing the layout without throwing.

**Capture flow**, triggered by the panel button or the `Alt+N` command:

1. Read `video.currentTime`, round to an int. Pause the video — it must not run away while the
   learner types.
2. Grab the caption text at that moment (Step 7b).
3. Ask the service worker for a screenshot (Step 7c).
4. Show a composer prefilled with the excerpt and the frame thumbnail; the learner types and
   saves; the worker POSTs to `/notes` and the timeline updates.

**7b — caption text.** Implement two paths and fall back cleanly:

- *Primary:* MAIN-world injection to read `ytInitialPlayerResponse` →
  `captions.playerCaptionsTracklistRenderer.captionTracks[0].baseUrl`, `postMessage` it back,
  then fetch that URL with `&fmt=json3` from the content script (same-origin, so it works).
  Cache the parsed cue list per video in `chrome.storage.session`. Pick the cue whose window
  contains `t_seconds`. This full cue list is also what Step 4 ingests.
- *Fallback:* read the rendered `.ytp-caption-segment` text, which only works when captions
  are switched on and only gives the current moment.
- *Neither available:* save the note with `transcript_excerpt: null` and show an honest
  "no captions on this video" line in the panel.

Caption extraction is the most fragile part of this build and YouTube changes these internals.
Isolate it in one module with a documented contract so it is the only thing that breaks, and
say clearly in your report which path actually worked when you tested.

**7c — screenshot.** In the service worker: `chrome.tabs.captureVisibleTab` (whole viewport),
then crop to the player using the `getBoundingClientRect()` and `devicePixelRatio` the content
script sent. Cropping requires `createImageBitmap()` + `OffscreenCanvas` + `convertToBlob()` —
there is no `Image` or `canvas` element in a service worker. Downscale to ~480px wide, encode
JPEG at ~0.7 quality, and assert the result is under the 200 KB cap from Step 2 before
sending. Handle the black-frame DRM case by not special-casing it — just note it.

Acceptance: a note captured at 1:23 on a real YouTube video saves with a correctly cropped
frame and the caption text spoken at that moment. Paste the stored `t_seconds`, the excerpt,
and the screenshot byte size.

### Step 8 — Offline queue

Wrap the worker's note POST in a queue persisted to `chrome.storage.local`: a failed send is
retried with backoff, and the panel shows pending state. The worker may be killed mid-flight,
so the queue must be durable and drained on startup and on `chrome.alarms`, never held in a
module-level variable.

This is the honest version of the "offline mode" in the original YouTube Study Kit: capture
always works, sync catches up. Say that in the README rather than claiming offline AI.

Acceptance: stop the backend, capture two notes, restart the backend, show both arriving.

### Step 9 — Video Q&A with timestamp citations

New LLM node `backend/app/orchestrator/nodes/video_qa.py`, following
`lesson_generator.py` exactly: a tool schema dict, a `_SYSTEM` prompt, a `_stub_*` fallback,
one `forced_tool_call`.

- Input: the question plus the video's `VideoTranscriptChunk` rows, each labelled with its
  `chunk_start_seconds`.
- Output schema: `{ "answer": str, "citations": [{ "t_seconds": int, "quote": str }] }`.
- Constrain `t_seconds` in the prompt to seconds present in the supplied chunks, **and
  validate it server-side after the call** — drop any citation whose timestamp is not a real
  chunk start. A hallucinated timestamp must never become a seek button.
- Stub fallback: highest keyword-overlap chunk plus a templated answer.

Expose `POST /notes/videos/{video_id}/ask`. This is a single node, not a graph — call it
directly, do not add it to `orchestrator/graph.py`.

In the panel: a question box, the answer, and citation chips that set `video.currentTime` on
click and offer "save as note" (prefilling the composer at that timestamp).

### Step 10 — PDF export in the web app

Implement export **once**, in `frontend/`, and deep-link to it from the extension. Do not
bundle a PDF library into the extension.

Add `@react-pdf/renderer` to `frontend/package.json` and create `frontend/src/lib/notesPdf.tsx`
plus a route (e.g. `#/notes/export/:videoId` and `#/notes/export/topic/:topicId`) that fetches
the pack and renders it. Lazy-load the library with `React.lazy` / dynamic `import()` — it is
large enough to notice in the initial bundle.

Two documents:

- **Video pack** — one video's notes: title, note count, then one block per note with `mm:ss`,
  the screenshot, the learner text, and the transcript excerpt.
- **Course pack** — a topic's notes across videos, sectioned per video in prerequisite order,
  with a contents page.

Every timestamp must be a real clickable annotation:
`<Link src={`https://www.youtube.com/watch?v=${videoId}&t=${t}s`}>`, not styled text. Open the
generated PDF, click an entry, and confirm it lands at the right second — and say in your
report that you actually checked.

The extension's popup gets an "Export notes" button that opens that route in a new tab.

### Step 11 — Notes → flashcards

`POST /notes/topic/{topic_id}/flashcards` — turn a learner's notes on a topic into FSRS cards.

New node `backend/app/orchestrator/nodes/notes_to_flashcards.py`, same pattern. Input: the
notes' `learner_text` + `transcript_excerpt`. Output `{"cards": [{"front", "back"}]}`.

**Two constraints make the naive implementation impossible. Read both before writing code.**

*1. `Flashcard.lesson_id` is a non-nullable FK to `lessons.id`.* Notes have no lesson, so you
cannot insert a card directly. Do **not** make the column nullable: that requires a migration
`Base.metadata.create_all` will not perform, and it would silently hide note-derived cards from
`recompute_mastery`, which reaches flashcards by joining through `Lesson.learner_id` and
`Lesson.topic_id`.

Instead, create a **synthetic `Lesson` row** for the generated set — correct `topic_id` and
`learner_id`, with `content_json` recording the provenance (that it was generated from N notes,
and their ids). Reviews of these cards then flow into the flashcard component of mastery
automatically, which is right: reviewing a card *is* a demonstration, even when the card came
from a note. Mirror `backend/app/orchestrator/nodes/stream_result.py` exactly, including its
`await db.flush()` between the parent `Lesson` and the child `Flashcard` inserts — read the
comment there explaining why the FK fails without it.

*2. There is no card-initialisation function in `backend/app/fsrs/scheduler.py`.* `fsrs_update`
updates an existing card only. Copy the initialisation from
`backend/app/orchestrator/nodes/flashcard_fsrs.py`: `initial_stability = 2.0`,
`DEFAULT_DIFFICULTY`, `elapsed_days = 0`, and `due_date = utcnow() + next_interval(2.0)` days.
Note that `stream_result.py` currently omits `due_date` on insert and so falls back to the
column default of "due now", losing the computed interval — do not copy that; set `due_date`
explicitly and mention the existing inconsistency in your report rather than fixing it here.

This is what makes notes part of Mentra's loop rather than a separate notebook: a moment the
learner flagged while watching becomes a scheduled review.

### Step 12 — Tests

There is currently **no test suite**. Add `pytest` + `pytest-asyncio` + `httpx` to
`backend/requirements.txt` and create `backend/tests/`:

- `test_caption_chunking.py` — cue grouping produces 30–60s chunks; re-ingest replaces rather
  than duplicates; an empty cue list is handled.
- `test_notes_routes.py` — create/list/delete round-trip; 403 on another learner's note; 404
  on a missing note; 413 on an oversized screenshot.
- `test_note_signal.py` — a note writes exactly one `StruggleEvent` with
  `signal_type="note_marked"`, and **mastery score is unchanged**. This is the regression test
  protecting the Step 5 decision. Plus the severity ramp: notes one and two fall below
  `STRUGGLE_SEVERITY_CUTOFF`, note three reaches it.
- `test_topic_suggestion.py` — a below-threshold match returns `None` rather than a wrong topic.
- `test_notes_to_flashcards.py` — a synthetic `Lesson` row is created with the right
  `learner_id`/`topic_id`, cards carry its `lesson_id`, and `recompute_mastery` can still see
  a confidence rating on one of those cards (this is what the synthetic lesson buys).
- `test_topic_depth.py` — BFS depth on the seeded graph, and **a cyclic edge pair terminates**
  rather than hanging.
- `test_embedding.py` — the Step 0 embedder scores a topic name against its matching video
  title higher than against an unrelated topic. Guards the regression back to hash embeddings.
- `test_video_qa_validation.py` — a fabricated citation timestamp is dropped; the stub path
  returns the documented shape with no API key set.

Use a transactional fixture that rolls back, or a dedicated test database — do not mutate the
seeded dev DB.

For the extension, add `vitest` and unit-test the pure logic only: cue→chunk grouping, cue
lookup at a timestamp, crop-rectangle math, and the offline queue's state machine. Do not
attempt to test Chrome APIs or YouTube's DOM.

### Step 13 — Documentation

Update `README.md`:

- Add `extension/` to the architecture diagram as a second client on the same backend, and
  state the two things that exist only there (frame capture, caption access).
- Add a "Load the extension" section: `npm run build` in `extension/`, load unpacked, find the
  extension ID, add it to `CORS_ORIGINS`, pick a learner in options.
- Extend the demo walkthrough with a numbered Watch & Note flow on a real YouTube video.
- State the limitations honestly: learner selection is not authentication; screenshots are
  data URLs in Postgres and object storage is the real answer; DRM content captures black;
  caption extraction depends on YouTube internals that can change.

While you are in there, fix two existing inaccuracies you will be able to verify: the README
references `frontend/src/api/demo.ts` and `frontend/src/api/examPlan.ts`, which do not exist,
and it says the agent nodes call "the Claude API" while `backend/app/llm.py` calls OpenAI.
Correct both to match the code.

## Definition of done

- Extension loads unpacked; on a real YouTube video the panel appears, survives navigating to
  a second video, and works in theater mode.
- A note captured at 1:23 stores `t_seconds=83`, the caption text at that moment, and a cropped
  frame under 200 KB; clicking it in the timeline seeks the video back to 1:23.
- Captions for a non-seeded video are ingested, and `search_transcripts` returns a timestamp
  from that video.
- Notes export to a PDF whose entries open YouTube at the right second.
- Backend still runs with no API key (Q&A falls back to its stub).
- `pytest` passes from `backend/`; `npm run build` passes in both `frontend/` and `extension/`.
- No mastery weight changed; `test_note_signal.py` proves it.
- Embedding similarity is real: the Step 0 acceptance numbers are in your report.
- Note-derived flashcards exist with a synthetic parent lesson and are visible to
  `recompute_mastery`.
- The `u_amy` → `derivatives` → `limits` prerequisite redirect from the README walkthrough
  still works after the Step 3 graph refactor.

## Reporting

After each step, report: what you changed (file paths), what you actually ran to verify, real
output, and anything you could not verify. Extension work in particular cannot be fully
verified from a terminal — when a step needs me to click something in Chrome, say exactly what
to click and what I should expect to see, and wait.

If you hit a constraint that makes a step a bad idea, stop and say so rather than working
around it. A flagged blocker is more useful than a silent workaround.
