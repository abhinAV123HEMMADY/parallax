/**
 * Parallax API client. Runs in the service worker only.
 *
 * That restriction is deliberate rather than incidental. A fetch from the content script would
 * carry `Origin: https://www.youtube.com`, so making it work would mean allow-listing YouTube as
 * a trusted origin on the backend — handing every script on youtube.com the same access as the
 * extension. From the worker the origin is `chrome-extension://<id>`, which is the thing the
 * backend's CORS list should actually name.
 */

import { getSettings } from "./storage";
import type {
  Cue,
  NoteCreate,
  NoteOut,
  TopicSuggestionResponse,
  TranscriptIngestResult,
  VideoAskResponse,
  VideoNotePack,
} from "./types";

/** Thrown for a response the server will reject again no matter how often we retry. */
export class PermanentApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "PermanentApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { apiBase } = await getSettings();
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    const message = `${path}: ${response.status}${body ? ` ${body.slice(0, 200)}` : ""}`;
    // 4xx means the request itself is wrong — a bad learner id, an oversized screenshot. Retrying
    // it forever would keep a poison item at the head of the queue and block everything behind
    // it. 429 and 5xx are the opposite: the request is fine, the server isn't ready.
    if (response.status >= 400 && response.status < 500 && response.status !== 429) {
      throw new PermanentApiError(message, response.status);
    }
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function health() {
  return request<{ status: string; llm_configured: boolean; embed_backend: string }>("/health");
}

export function createNote(payload: NoteCreate) {
  return request<NoteOut>("/notes", { method: "POST", body: JSON.stringify(payload) });
}

export function listNotes(learnerId: string, videoId: string) {
  const query = new URLSearchParams({ learner_id: learnerId, video_id: videoId });
  return request<VideoNotePack>(`/notes?${query}`);
}

export function recentNotes(learnerId: string, limit = 10) {
  const query = new URLSearchParams({ learner_id: learnerId, limit: String(limit) });
  return request<NoteOut[]>(`/notes/recent?${query}`);
}

export function deleteNote(learnerId: string, noteId: string) {
  const query = new URLSearchParams({ learner_id: learnerId });
  return request<{ status: string }>(`/notes/${noteId}?${query}`, { method: "DELETE" });
}

export function ingestTranscript(videoId: string, videoTitle: string, cues: Cue[]) {
  return request<TranscriptIngestResult>(`/notes/videos/${videoId}/transcript`, {
    method: "POST",
    body: JSON.stringify({ video_title: videoTitle, cues }),
  });
}

export function topicSuggestion(videoId: string, videoTitle: string) {
  const query = new URLSearchParams({ video_title: videoTitle });
  return request<TopicSuggestionResponse>(`/notes/videos/${videoId}/topic-suggestion?${query}`);
}

export function askVideo(videoId: string, question: string, learnerId: string | null) {
  return request<VideoAskResponse>(`/notes/videos/${videoId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question, learner_id: learnerId }),
  });
}
