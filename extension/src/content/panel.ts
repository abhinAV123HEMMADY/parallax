/**
 * The injected panel. Plain DOM inside a shadow root — no framework.
 *
 * The shadow root is not a style preference, it is a requirement. YouTube ships aggressive global
 * CSS and its own custom elements; an open-DOM panel would both inherit YouTube's rules
 * unpredictably and leak its own into the page. A shadow root makes the boundary absolute, at the
 * cost of having to inline the styles here rather than shipping a stylesheet.
 */

import type { Citation, NoteOut, QueuedNote, TopicSuggestion } from "../lib/types";
import { formatTimestamp } from "./player";

const HOST_ID = "parallax-watch-note-host";

const STYLES = `
  :host { all: initial; }
  * { box-sizing: border-box; font-family: "Roboto", "Segoe UI", system-ui, sans-serif; }
  .card {
    background: var(--bg, #0f0f0f); color: var(--fg, #f1f1f1);
    border: 1px solid rgba(255,255,255,.14); border-radius: 12px;
    padding: 14px; margin-bottom: 16px; font-size: 13px; line-height: 1.5;
  }
  @media (prefers-color-scheme: light) {
    .card { --bg: #fff; --fg: #0f0f0f; border-color: rgba(0,0,0,.12); }
  }
  .row { display: flex; align-items: center; gap: 8px; }
  .between { justify-content: space-between; }
  h2 { font-size: 14px; font-weight: 600; margin: 0; letter-spacing: .01em; }
  .muted { opacity: .62; font-size: 12px; }
  .chip {
    font-size: 11px; padding: 2px 8px; border-radius: 999px;
    background: rgba(127,127,127,.18); white-space: nowrap;
  }
  button {
    font: inherit; font-size: 12px; font-weight: 500; cursor: pointer;
    border-radius: 8px; border: 1px solid transparent; padding: 7px 12px;
    background: #3ea6ff; color: #04121f;
  }
  button:hover { filter: brightness(1.08); }
  button:disabled { opacity: .5; cursor: default; filter: none; }
  button.ghost { background: transparent; color: inherit; border-color: rgba(127,127,127,.35); }
  button.tiny { padding: 3px 8px; font-size: 11px; }
  textarea, input[type="text"] {
    width: 100%; font: inherit; font-size: 13px; color: inherit;
    background: rgba(127,127,127,.12); border: 1px solid rgba(127,127,127,.3);
    border-radius: 8px; padding: 8px; resize: vertical;
  }
  textarea { min-height: 68px; }
  .stack { display: flex; flex-direction: column; gap: 8px; }
  .excerpt {
    font-size: 12px; opacity: .78; border-left: 2px solid rgba(62,166,255,.55);
    padding-left: 8px; margin: 6px 0 0;
  }
  .note { border-top: 1px solid rgba(127,127,127,.2); padding: 10px 0; }
  .note:last-child { border-bottom: 0; }
  .ts {
    background: none; border: 0; padding: 0; color: #3ea6ff; font-weight: 600;
    font-variant-numeric: tabular-nums; cursor: pointer; font-size: 12px;
  }
  .thumb { width: 100%; border-radius: 6px; margin-top: 6px; display: block; }
  .pending { opacity: .6; font-style: italic; }
  .error { color: #ff8080; font-size: 12px; }
  .hidden { display: none; }
`;

export interface PanelCallbacks {
  onCapture: () => void;
  onSave: (text: string, share: boolean, topicId: string | null) => void;
  onCancel: () => void;
  onSeek: (seconds: number) => void;
  onDelete: (noteId: string) => void;
  onAsk: (question: string) => void;
  onExport: () => void;
  onSaveCitation: (citation: Citation) => void;
}

export class Panel {
  private host: HTMLElement;
  private root: ShadowRoot;
  private callbacks: PanelCallbacks;

  private composer!: HTMLElement;
  private composerMeta!: HTMLElement;
  private composerExcerpt!: HTMLElement;
  private textarea!: HTMLTextAreaElement;
  private shareBox!: HTMLInputElement;
  private saveButton!: HTMLButtonElement;
  private notesList!: HTMLElement;
  private statusLine!: HTMLElement;
  private topicChip!: HTMLElement;
  private askInput!: HTMLInputElement;
  private askAnswer!: HTMLElement;

  private pendingSeconds = 0;
  private pendingTopicId: string | null = null;

  constructor(callbacks: PanelCallbacks) {
    this.callbacks = callbacks;
    this.host = document.createElement("div");
    this.host.id = HOST_ID;
    this.root = this.host.attachShadow({ mode: "open" });
    this.render();
  }

  /** Inserts the panel above the related-videos rail, falling back to under the player. */
  mount(): void {
    if (document.getElementById(HOST_ID)) return;
    const target =
      document.querySelector("#secondary-inner") ??
      document.querySelector("#secondary") ??
      document.querySelector("#below");
    if (!target) return;
    target.prepend(this.host);
  }

  unmount(): void {
    this.host.remove();
  }

  get isMounted(): boolean {
    return this.host.isConnected;
  }

  private render(): void {
    const style = document.createElement("style");
    style.textContent = STYLES;

    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <div class="card">
        <div class="row between">
          <h2>Parallax — Watch &amp; Note</h2>
          <span class="chip" data-topic>unmapped</span>
        </div>
        <div class="stack" style="margin-top:10px">
          <div class="row" style="gap:6px">
            <button data-capture>Capture this moment</button>
            <button class="ghost" data-export>Export PDF</button>
          </div>
          <div class="muted" data-status></div>
        </div>

        <div class="stack hidden" data-composer style="margin-top:12px">
          <div class="row between">
            <strong data-composer-meta></strong>
            <button class="ghost tiny" data-cancel>Cancel</button>
          </div>
          <p class="excerpt hidden" data-composer-excerpt></p>
          <textarea data-text placeholder="What did you notice here?"></textarea>
          <label class="row muted" style="gap:6px">
            <input type="checkbox" data-share /> Share with my connections
          </label>
          <button data-save>Save note</button>
        </div>
      </div>

      <div class="card">
        <h2>Ask about this video</h2>
        <div class="stack" style="margin-top:10px">
          <input type="text" data-ask placeholder="e.g. how does this relate to derivatives?" />
          <div data-answer></div>
        </div>
      </div>

      <div class="card">
        <h2>Notes</h2>
        <div data-notes style="margin-top:4px"></div>
      </div>
    `;

    this.root.append(style, wrapper);

    const q = <T extends HTMLElement>(selector: string): T => {
      const element = wrapper.querySelector<T>(selector);
      if (!element) throw new Error(`panel markup missing ${selector}`);
      return element;
    };

    this.composer = q("[data-composer]");
    this.composerMeta = q("[data-composer-meta]");
    this.composerExcerpt = q("[data-composer-excerpt]");
    this.textarea = q<HTMLTextAreaElement>("[data-text]");
    this.shareBox = q<HTMLInputElement>("[data-share]");
    this.saveButton = q<HTMLButtonElement>("[data-save]");
    this.notesList = q("[data-notes]");
    this.statusLine = q("[data-status]");
    this.topicChip = q("[data-topic]");
    this.askInput = q<HTMLInputElement>("[data-ask]");
    this.askAnswer = q("[data-answer]");

    q("[data-capture]").addEventListener("click", () => this.callbacks.onCapture());
    q("[data-export]").addEventListener("click", () => this.callbacks.onExport());
    q("[data-cancel]").addEventListener("click", () => {
      this.hideComposer();
      this.callbacks.onCancel();
    });
    this.saveButton.addEventListener("click", () => this.submit());
    this.textarea.addEventListener("keydown", (event) => {
      // Cmd/Ctrl+Enter saves. Plain Enter must stay a newline — a note is prose, not a form field.
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") this.submit();
    });
    this.askInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && this.askInput.value.trim()) {
        this.callbacks.onAsk(this.askInput.value.trim());
      }
    });
  }

  private submit(): void {
    const text = this.textarea.value.trim();
    if (!text) return;
    this.callbacks.onSave(text, this.shareBox.checked, this.pendingTopicId);
    this.hideComposer();
  }

  showComposer(seconds: number, excerpt: string | null, shareDefault: boolean): void {
    this.pendingSeconds = seconds;
    this.composer.classList.remove("hidden");
    this.composerMeta.textContent = `Note at ${formatTimestamp(seconds)}`;
    this.shareBox.checked = shareDefault;

    if (excerpt) {
      this.composerExcerpt.textContent = `“${excerpt}”`;
      this.composerExcerpt.classList.remove("hidden");
    } else {
      this.composerExcerpt.classList.add("hidden");
    }

    this.textarea.value = "";
    this.textarea.focus({ preventScroll: true });
  }

  prefill(text: string): void {
    this.textarea.value = text;
    this.textarea.focus({ preventScroll: true });
  }

  hideComposer(): void {
    this.composer.classList.add("hidden");
  }

  get composerSeconds(): number {
    return this.pendingSeconds;
  }

  setStatus(text: string, isError = false): void {
    this.statusLine.textContent = text;
    this.statusLine.classList.toggle("error", isError);
  }

  setTopic(suggestion: TopicSuggestion | null): void {
    this.pendingTopicId = suggestion?.topic_id ?? null;
    if (suggestion?.topic_id) {
      this.topicChip.textContent = `${suggestion.topic_name} · ${suggestion.strategy} ${suggestion.score.toFixed(2)}`;
      this.topicChip.title = "Parallax matched this video to a topic, so notes feed your mastery map.";
    } else {
      this.topicChip.textContent = "unmapped";
      this.topicChip.title =
        "No topic matched confidently. Notes still save and export; they just don't feed the peer layer.";
    }
  }

  renderNotes(notes: NoteOut[], pending: QueuedNote[]): void {
    this.notesList.replaceChildren();

    if (notes.length === 0 && pending.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No notes on this video yet.";
      this.notesList.append(empty);
      return;
    }

    for (const note of notes) {
      const row = document.createElement("div");
      row.className = "note";

      const header = document.createElement("div");
      header.className = "row between";

      const timestamp = document.createElement("button");
      timestamp.className = "ts";
      timestamp.textContent = formatTimestamp(note.t_seconds);
      timestamp.title = "Jump to this moment";
      timestamp.addEventListener("click", () => this.callbacks.onSeek(note.t_seconds));

      const remove = document.createElement("button");
      remove.className = "ghost tiny";
      remove.textContent = "Delete";
      remove.addEventListener("click", () => this.callbacks.onDelete(note.id));

      header.append(timestamp, remove);

      const body = document.createElement("div");
      body.textContent = note.learner_text;

      row.append(header, body);

      if (note.transcript_excerpt) {
        const excerpt = document.createElement("p");
        excerpt.className = "excerpt";
        excerpt.textContent = `“${note.transcript_excerpt}”`;
        row.append(excerpt);
      }

      this.notesList.append(row);
    }

    for (const queued of pending) {
      const row = document.createElement("div");
      row.className = "note pending";
      const label = queued.failedPermanently
        ? `${formatTimestamp(queued.payload.t_seconds)} — not synced: ${queued.lastError ?? "rejected"}`
        : `${formatTimestamp(queued.payload.t_seconds)} — syncing…`;
      row.textContent = `${label}\n${queued.payload.learner_text}`;
      row.style.whiteSpace = "pre-line";
      if (queued.failedPermanently) row.classList.add("error");
      this.notesList.append(row);
    }
  }

  renderAnswer(answer: string, citations: Citation[], stubbed: boolean): void {
    this.askAnswer.replaceChildren();

    const text = document.createElement("p");
    text.style.margin = "0";
    text.textContent = answer;
    this.askAnswer.append(text);

    if (stubbed) {
      const badge = document.createElement("p");
      badge.className = "muted";
      badge.style.margin = "6px 0 0";
      badge.textContent = "Keyword match — no language model configured.";
      this.askAnswer.append(badge);
    }

    if (citations.length > 0) {
      const row = document.createElement("div");
      row.className = "row";
      row.style.cssText = "flex-wrap:wrap;gap:6px;margin-top:8px";
      for (const citation of citations) {
        const jump = document.createElement("button");
        jump.className = "ghost tiny";
        jump.textContent = formatTimestamp(citation.t_seconds);
        jump.title = citation.quote;
        jump.addEventListener("click", () => this.callbacks.onSeek(citation.t_seconds));

        const save = document.createElement("button");
        save.className = "ghost tiny";
        save.textContent = "+ note";
        save.title = "Start a note at this timestamp";
        save.addEventListener("click", () => this.callbacks.onSaveCitation(citation));

        row.append(jump, save);
      }
      this.askAnswer.append(row);
    }
  }

  setAskBusy(busy: boolean): void {
    this.askInput.disabled = busy;
    if (busy) this.askAnswer.textContent = "Thinking…";
  }
}
