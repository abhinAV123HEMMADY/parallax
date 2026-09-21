/**
 * Wire types and the content-script <-> service-worker message protocol.
 *
 * The API shapes mirror backend/app/schemas/notes.py. They are hand-written here rather than
 * generated because the extension needs only a handful of them; the web app's path to generated
 * types from the backend's OpenAPI schema is the right answer once both clients need the full
 * surface.
 */

export interface NoteOut {
  id: string;
  video_id: string;
  video_title: string;
  topic_id: string | null;
  topic_name: string | null;
  t_seconds: number;
  learner_text: string;
  transcript_excerpt: string | null;
  has_screenshot: boolean;
  created_at: string;
}

export interface VideoNotePack {
  video_id: string;
  video_title: string;
  notes: NoteOut[];
}

export interface NoteCreate {
  learner_id: string;
  video_id: string;
  video_title: string;
  t_seconds: number;
  learner_text: string;
  topic_id?: string | null;
  share?: boolean;
  screenshot?: string | null;
}

export interface Cue {
  t_seconds: number;
  text: string;
}

export interface TranscriptIngestResult {
  video_id: string;
  cues_received: number;
  chunks_written: number;
  replaced_existing: boolean;
}

export interface TopicSuggestion {
  topic_id: string | null;
  topic_name: string | null;
  score: number;
  strategy: string;
}

export interface TopicSuggestionResponse {
  chosen: TopicSuggestion;
  lexical: TopicSuggestion;
  semantic: TopicSuggestion;
}

export interface Citation {
  t_seconds: number;
  quote: string;
}

export interface VideoAskResponse {
  answer: string;
  citations: Citation[];
  stubbed: boolean;
}

export interface ParallaxUser {
  id: string;
  name: string;
  grade_level: string | null;
}

/** A note waiting to reach the backend. Persisted, so it survives the worker being killed. */
export interface QueuedNote {
  /** Client-side id, so the panel can show a pending row and reconcile it after the send. */
  localId: string;
  payload: NoteCreate;
  queuedAt: number;
  attempts: number;
  /** Set when the server rejected it in a way retrying cannot fix (4xx other than 429). */
  failedPermanently?: boolean;
  lastError?: string;
}

export type WorkerRequest =
  | { kind: "getSettings" }
  | { kind: "listUsers" }
  | { kind: "listNotes"; videoId: string }
  | { kind: "createNote"; payload: NoteCreate }
  | { kind: "deleteNote"; noteId: string }
  | { kind: "ingestTranscript"; videoId: string; videoTitle: string; cues: Cue[] }
  | { kind: "topicSuggestion"; videoId: string; videoTitle: string }
  | { kind: "ask"; videoId: string; question: string }
  | { kind: "captureFrame"; rect: CaptureRect }
  | { kind: "captionTrackUrl" }
  | { kind: "pendingFor"; videoId: string }
  | { kind: "flushQueue" }
  | { kind: "openExport"; videoId: string };

export interface CaptureRect {
  x: number;
  y: number;
  width: number;
  height: number;
  devicePixelRatio: number;
}

export type WorkerResponse<T> = { ok: true; data: T } | { ok: false; error: string };

export interface Settings {
  apiBase: string;
  learnerId: string | null;
  shareByDefault: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  apiBase: "http://localhost:8000",
  learnerId: null,
  shareByDefault: false,
};
