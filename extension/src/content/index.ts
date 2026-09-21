/**
 * Content script entry: owns the panel's lifecycle across YouTube's SPA navigation.
 *
 * The single most important thing here is that this file runs *once per page load*, and YouTube
 * almost never does a page load. Clicking from one video to the next rewrites the DOM in place,
 * so a script that sets up on `document_idle` and stops there works exactly once and then appears
 * broken. `yt-navigate-finish` is YouTube's own signal that a navigation settled, and re-running
 * setup on it is what makes the panel survive.
 *
 * All network access goes through the service worker (see lib/api.ts for why).
 */

import type {
  Citation,
  Cue,
  NoteCreate,
  QueuedNote,
  Settings,
  TopicSuggestionResponse,
  VideoAskResponse,
  VideoNotePack,
  WorkerRequest,
  WorkerResponse,
} from "../lib/types";
import { DEFAULT_LEARNER_ID } from "../lib/types";
import { cueAt, getCues, getCuesFromTranscriptPanel, liveCaptionText } from "./captions";
import { Panel } from "./panel";
import {
  currentSeconds,
  currentVideoId,
  currentVideoTitle,
  pause,
  playerRect,
  seekTo,
} from "./player";

async function send<T>(message: WorkerRequest): Promise<T> {
  const response = (await chrome.runtime.sendMessage(message)) as WorkerResponse<T> | undefined;
  if (!response) throw new Error("no response from the Parallax service worker");
  if (!response.ok) throw new Error(response.error);
  return response.data;
}

/** Per-video state. Reset on every navigation so nothing leaks between videos. */
interface VideoState {
  videoId: string;
  title: string;
  cues: Cue[];
  cuesLoaded: boolean;
}

let panel: Panel | null = null;
let state: VideoState | null = null;
let settings: Settings | null = null;

async function refreshNotes(): Promise<void> {
  if (!panel || !state) return;
  try {
    const [pack, pending] = await Promise.all([
      send<VideoNotePack>({ kind: "listNotes", videoId: state.videoId }),
      send<QueuedNote[]>({ kind: "pendingFor", videoId: state.videoId }),
    ]);
    panel.renderNotes(pack.notes, pending);
  } catch (error) {
    panel.setStatus(error instanceof Error ? error.message : String(error), true);
  }
}

/**
 * Loads the caption track and ships it to the backend for chunking and embedding.
 *
 * Runs once per video, in the background, and never blocks a capture: if it hasn't finished (or
 * fails outright) a note still saves, just without a server-resolved excerpt. The ingest is what
 * makes this video searchable by Parallax's existing timestamp search, so it is worth doing eagerly
 * rather than on first note.
 */
/**
 * How many times to ask for captions before believing a video has none, and how long to wait
 * between tries. The player populates its caption list slightly after the page becomes
 * interactive, so the first ask can legitimately come back empty on a video with 38 tracks.
 * Roughly three seconds total, which is well inside the time it takes to start watching.
 */
const CAPTION_ATTEMPTS = 4;
const CAPTION_RETRY_MS = 900;

/** Guards against two first-attempt runs overlapping; retries pass attempt > 0 and bypass it. */
let captionsInFlight = false;

async function loadCaptions(attempt = 0): Promise<void> {
  if (!state || !panel || state.cuesLoaded) return;
  if (captionsInFlight && attempt === 0) return;
  captionsInFlight = true;

  // Captured so a retry that lands after the learner has navigated away is discarded rather
  // than writing another video's transcript into this one's state.
  const videoId = state.videoId;

  try {
    panel.setStatus("Reading captions…");
    const { url } = await send<{ url: string | null }>({ kind: "captionTrackUrl" });

    // No track in the player response doesn't mean no transcript: the panel is populated by a
    // different call, so it is worth asking even here rather than giving up on the video.
    const cues = url ? await getCues(url) : await getCuesFromTranscriptPanel();
    if (cues.length === 0) {
      // Don't brand the video transcript-less on the first miss. cuesLoaded is deliberately
      // still false here: it used to be set before the attempt, which made one early empty
      // read permanent for the rest of the visit.
      if (attempt < CAPTION_ATTEMPTS - 1) {
        captionsInFlight = false;
        setTimeout(() => {
          if (state?.videoId === videoId) void loadCaptions(attempt + 1);
        }, CAPTION_RETRY_MS);
        return;
      }
      panel.setStatus("No transcript available — notes still save, without transcript context.");
      return;
    }
    state.cuesLoaded = true;
    state.cues = cues;

    const result = await send<{ chunks_written: number }>({
      kind: "ingestTranscript",
      videoId: state.videoId,
      videoTitle: state.title,
      cues,
    });
    panel.setStatus(`Transcript synced — ${cues.length} cues in ${result.chunks_written} searchable chunks.`);

    // Topic matching reads the ingested chunks, so it can only run after the ingest lands.
    const suggestion = await send<TopicSuggestionResponse>({
      kind: "topicSuggestion",
      videoId: state.videoId,
      videoTitle: state.title,
    });
    panel.setTopic(suggestion.chosen, suggestion.proposed);
  } catch (error) {
    panel.setStatus(
      `Transcript sync failed: ${error instanceof Error ? error.message : String(error)}`,
      true,
    );
  } finally {
    // Without this a thrown request would leave the flag set and block every later attempt,
    // including the one a fresh navigation would otherwise make.
    captionsInFlight = false;
  }
}

/** Best available excerpt for a timestamp: the full cue list, else the on-screen caption. */
function excerptFor(seconds: number): string | null {
  if (!state) return null;
  return cueAt(state.cues, seconds) ?? liveCaptionText();
}

async function beginCapture(): Promise<void> {
  if (!panel || !state || !settings) return;

  const seconds = currentSeconds();
  // Pause first. The learner is about to type, and a video that keeps playing means they lose the
  // next thirty seconds of the lecture to their own note-taking.
  pause();

  panel.showComposer(seconds, excerptFor(seconds), settings.shareByDefault);

  const rect = playerRect();
  if (!rect) return;
  try {
    const { screenshot } = await send<{ screenshot: string | null }>({
      kind: "captureFrame",
      rect: { ...rect, devicePixelRatio: window.devicePixelRatio || 1 },
    });
    pendingScreenshot = screenshot;
  } catch {
    pendingScreenshot = null;
  }
}

let pendingScreenshot: string | null = null;

async function saveNote(text: string, share: boolean, topicId: string | null): Promise<void> {
  if (!panel || !state) return;

  const payload: NoteCreate = {
    learner_id: DEFAULT_LEARNER_ID,
    video_id: state.videoId,
    video_title: state.title,
    t_seconds: panel.composerSeconds,
    learner_text: text,
    topic_id: topicId,
    share,
    screenshot: pendingScreenshot,
  };
  pendingScreenshot = null;

  try {
    const result = await send<{ sent: number; remaining: number }>({ kind: "createNote", payload });
    panel.setStatus(
      result.remaining > 0
        ? `Saved locally — ${result.remaining} note(s) waiting to sync.`
        : "Note saved.",
    );
  } catch (error) {
    panel.setStatus(error instanceof Error ? error.message : String(error), true);
  }
  await refreshNotes();
}

function buildPanel(): Panel {
  return new Panel({
    onCapture: () => void beginCapture(),
    onSave: (text, share, topicId) => void saveNote(text, share, topicId),
    onCancel: () => {
      pendingScreenshot = null;
    },
    onSeek: (seconds) => seekTo(seconds),
    onDelete: (noteId) => {
      void (async () => {
        try {
          await send({ kind: "deleteNote", noteId });
        } catch (error) {
          panel?.setStatus(error instanceof Error ? error.message : String(error), true);
        }
        await refreshNotes();
      })();
    },
    onAsk: (question) => {
      void (async () => {
        if (!panel || !state) return;
        panel.setAskBusy(true);
        try {
          const result = await send<VideoAskResponse>({
            kind: "ask",
            videoId: state.videoId,
            question,
          });
          panel.renderAnswer(result.answer, result.citations, result.stubbed);
        } catch (error) {
          panel.renderAnswer(
            error instanceof Error ? error.message : String(error),
            [],
            false,
          );
        } finally {
          panel.setAskBusy(false);
        }
      })();
    },
    onExport: () => {
      if (state) void send({ kind: "openExport", videoId: state.videoId });
    },
    onSaveCitation: (citation: Citation) => {
      if (!panel || !settings) return;
      seekTo(citation.t_seconds);
      pause();
      panel.showComposer(citation.t_seconds, citation.quote, settings.shareByDefault);
    },
  });
}

/**
 * Sets up for whatever video is now on screen. Idempotent — safe to call on every navigation.
 *
 * YouTube fires `yt-navigate-finish` before the new player and metadata are necessarily in the
 * DOM, so this retries briefly rather than assuming the title and video element are ready. Reading
 * too early is how notes end up filed under the previous video's title.
 */
async function setup(attempt = 0): Promise<void> {
  const videoId = currentVideoId();

  if (!videoId) {
    panel?.unmount();
    panel = null;
    state = null;
    return;
  }

  if (state?.videoId === videoId && panel?.isMounted) return;

  settings ??= await send<Settings>({ kind: "getSettings" });

  const title = currentVideoTitle();
  if ((!title || !playerRect()) && attempt < 10) {
    setTimeout(() => void setup(attempt + 1), 400);
    return;
  }

  state = { videoId, title, cues: [], cuesLoaded: false };
  pendingScreenshot = null;

  panel ??= buildPanel();
  panel.mount();
  if (!panel.isMounted && attempt < 10) {
    // The rail this mounts into can arrive after the player does.
    setTimeout(() => void setup(attempt + 1), 400);
    return;
  }

  panel.setTopic(null);
  panel.setStatus("Reading captions…");

  await refreshNotes();
  void loadCaptions();
}

document.addEventListener("yt-navigate-finish", () => void setup());

// The keyboard command is routed through here rather than handled in the worker so both paths
// share one capture implementation.
chrome.runtime.onMessage.addListener((message: { kind?: string }) => {
  if (message?.kind === "captureNoteFromCommand") void beginCapture();
});

// Settings can change while a tab is open (learner switched in options); pick that up rather than
// making the learner reload YouTube.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "sync" && changes.settings) {
    settings = changes.settings.newValue as Settings;
    void refreshNotes();
  }
});

void setup();
