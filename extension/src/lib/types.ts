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

export interface ProposedTopic {
  name: string;
  subject: string;
}

export interface TopicSuggestionResponse {
  chosen: TopicSuggestion;
  lexical: TopicSuggestion;
  semantic: TopicSuggestion;
  /** What saving a note would create. Null when `chosen` matched an existing topic. */
  proposed: ProposedTopic | null;
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

/**
 * Who notes belong to. The backend requires a learner (video_notes.learner_id is a NOT NULL FK
 * to users.id), so notes cannot be anonymous — but nothing about that has to be a setup step.
 * The extension uses the same seeded learner the web app defaults to in
 * frontend/src/LearnerContext.tsx, so a note captured on YouTube shows up in Parallax without
 * anyone choosing a profile in two places. Change both together.
 */
export const DEFAULT_LEARNER_ID = "u_amy";

export interface Settings {
  apiBase: string;
  /**
   * Where the Parallax web app lives. Separate from apiBase because they only share a host in
   * local dev: deployed, the API and the web app sit on different domains entirely, so the old
   * trick of rewriting apiBase's :8000 to :5173 produced a URL that did not exist.
   */
  webBase: string;
  shareByDefault: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  apiBase: "http://localhost:8000",
  webBase: "http://localhost:5173",
  shareByDefault: false,
};
