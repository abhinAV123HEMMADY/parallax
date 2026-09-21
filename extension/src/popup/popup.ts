/**
 * Popup: identity, backend reachability, and recent notes.
 *
 * Intentionally read-only. The popup cannot see the video the learner is watching, so capture
 * belongs in the injected panel; anything heavier than a glance belongs in the web app.
 */

import { recentNotes, health } from "../lib/api";
import { getSettings } from "../lib/storage";
import { DEFAULT_LEARNER_ID } from "../lib/types";
import type { NoteOut } from "../lib/types";

const statusLine = document.getElementById("status") as HTMLParagraphElement;
const notesList = document.getElementById("notes") as HTMLDivElement;

document.getElementById("options")?.addEventListener("click", () => {
  void chrome.runtime.openOptionsPage();
});

function timestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function renderNotes(notes: NoteOut[]): void {
  notesList.replaceChildren();
  if (notes.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No notes yet. Open a YouTube lecture and capture a moment.";
    notesList.append(empty);
    return;
  }

  for (const note of notes) {
    const row = document.createElement("div");
    row.className = "note";

    const link = document.createElement("a");
    link.href = `https://www.youtube.com/watch?v=${note.video_id}&t=${note.t_seconds}s`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.className = "ts";
    link.textContent = timestamp(note.t_seconds);

    const title = document.createElement("span");
    title.className = "muted";
    title.textContent = ` · ${note.video_title.slice(0, 40)}`;

    const body = document.createElement("div");
    body.textContent = note.learner_text;

    row.append(link, title, body);
    notesList.append(row);
  }
}

async function main(): Promise<void> {
  const settings = await getSettings();

  try {
    const info = await health();
    statusLine.textContent = `Connected · embeddings: ${info.embed_backend} · model: ${
      info.llm_configured ? "live" : "stub"
    }`;
    renderNotes(await recentNotes(DEFAULT_LEARNER_ID, 8));
  } catch (error) {
    statusLine.textContent = `Can't reach ${settings.apiBase} — ${
      error instanceof Error ? error.message : String(error)
    }`;
    statusLine.classList.add("error");
  }
}

void main();
