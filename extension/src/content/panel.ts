/**
 * The injected panel. Plain DOM inside a shadow root — no framework.
 *
 * The shadow root is not a style preference, it is a requirement. YouTube ships aggressive global
 * CSS and its own custom elements; an open-DOM panel would both inherit YouTube's rules
 * unpredictably and leak its own into the page. A shadow root makes the boundary absolute, at the
 * cost of having to inline the styles here rather than shipping a stylesheet.
 *
 * The design is a white card with pastel accents, which is a deliberate reversal of what was here
 * before: the panel used to borrow YouTube's greys and its #065fd4 blue so it would disappear into
 * the rail. It now reads as the learner's own surface resting on the page instead. The risk that
 * trade accepts is looking like an ad, so the restraint moved elsewhere rather than going away —
 * one card instead of stacked ones, a single accent hue rather than a palette per control, no
 * brand mark, and no icon on anything that a word already explains.
 *
 * Colour carries meaning and nothing else: lavender for the one primary action and for timestamps
 * you can jump to, a rose tint only for errors, grey for everything that is merely text.
 *
 * Navigation is two tabs rather than three stacked sections. The previous layout put Notes below
 * Ask below Capture, which buried the notes — the thing a learner comes back to — under the thing
 * they use once. Capture stays pinned above the tabs because it is the only urgent action: the
 * moment worth keeping is on screen right now.
 *
 * Motion follows two rules. Only `transform` and `opacity` are animated, so nothing here triggers
 * layout. And anything the learner sees many times a session is either fast (under ~200ms) or not
 * animated at all — a capture happens dozens of times per lecture, and an animation on that path
 * would be felt as lag long before it was noticed as polish.
 */

import type { Citation, NoteOut, ProposedTopic, QueuedNote, TopicSuggestion } from "../lib/types";
import { formatTimestamp } from "./player";

const HOST_ID = "parallax-watch-note-host";

/**
 * The panel is a white card regardless of YouTube's theme — deliberately, so it reads as the
 * learner's own surface sitting on top of the page rather than a piece of YouTube's chrome.
 * It replaced a theme-following treatment that borrowed YouTube's greys and its #065fd4 blue.
 *
 * Contrast was the constraint on the palette, not taste: pastels are pale by definition, so
 * every one of these is used as a *tint behind* dark text or as a large shape, never as text on
 * white. The hues that do carry text were darkened until they cleared 4.5:1 against the palest
 * surface they ever sit on (--surface, not white — measured there because it is the worse case):
 * --accent 5.1, --fg-dim 5.7, --fg-faint 4.7, --danger 4.8 on --danger-tint. The first pass of
 * this palette shipped --fg-faint at 3.1 and a mint at 3.0, which is how secondary text ends up
 * unreadable while still looking tasteful in a screenshot.
 */
const PALETTE = `
    --bg: #ffffff;
    --surface: #f6f5fb;
    --surface-sunk: #f1eff9;
    --fg: #23222b;
    --fg-dim: #62606f;
    --fg-faint: #706d7b;
    --line: #ebe9f3;
    --line-strong: #ddd9ec;

    --accent: #6354d6;
    --accent-tint: #efecfd;
    --accent-ink: #ffffff;

    --mint: #2b7a5d;
    --mint-tint: #e6f6ef;
    --danger: #b3455e;
    --danger-tint: #fdeef2;

    --shadow: 0 1px 2px rgba(35,34,43,.04), 0 10px 28px -12px rgba(35,34,43,.16);
`;

const STYLES = `
  :host { all: initial; display: block; }

  * { box-sizing: border-box; font-family: "Roboto", "Segoe UI", system-ui, sans-serif; }

  :host {
    --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
    ${PALETTE}
  }

  .panel {
    color: var(--fg);
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 16px;
    box-shadow: var(--shadow);
    font-size: 13px;
    line-height: 1.55;
    margin-bottom: 16px;
    overflow: hidden;
    animation: panel-in 240ms var(--ease-out) both;
  }
  @keyframes panel-in { from { opacity: 0; transform: translateY(5px); } }

  .pad { padding: 14px 16px; }

  /* --- header ------------------------------------------------------------ */

  .head { display: flex; align-items: center; gap: 8px; }
  .title {
    font-size: 11px; font-weight: 600; letter-spacing: .07em;
    color: var(--fg-faint); text-transform: uppercase; flex: 1;
  }
  /* The matched topic is the one piece of state the learner did not type, so it gets the
     accent tint — a quiet pill rather than another line of grey text. */
  .topic {
    font-size: 11.5px; color: var(--fg-faint);
    max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    transition: color 200ms ease, background-color 200ms ease;
    padding: 2px 8px; border-radius: 999px;
  }
  .topic.is-set { color: var(--accent); background: var(--accent-tint); font-weight: 500; }

  /* --- buttons ----------------------------------------------------------- */

  button {
    font: inherit; font-size: 13px; font-weight: 550;
    cursor: pointer; border: 1px solid transparent;
    border-radius: 10px; padding: 10px 14px;
    background: var(--accent); color: var(--accent-ink);
    transition: transform 150ms var(--ease-out), background-color 150ms ease,
                box-shadow 150ms ease, opacity 150ms ease;
  }
  button:active:not(:disabled) { transform: scale(.98); }
  button:disabled { opacity: .4; cursor: default; }
  button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .capture { width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; }
  .capture .k {
    font-size: 10.5px; font-variant-numeric: tabular-nums; font-weight: 500;
    background: rgba(255,255,255,.18); padding: 2px 6px; border-radius: 6px;
  }

  button.quiet {
    background: transparent; color: var(--fg-dim);
    padding: 6px 9px; font-size: 12px; font-weight: 500;
  }
  button.outline {
    background: var(--bg); color: var(--fg);
    border-color: var(--line-strong); font-size: 12px; padding: 6px 11px; font-weight: 500;
  }

  @media (hover: hover) and (pointer: fine) {
    button:hover:not(:disabled) {
      background: #5446c4;
      box-shadow: 0 4px 12px -4px rgba(99,84,214,.5);
    }
    button.quiet:hover:not(:disabled) { background: var(--surface); color: var(--fg); }
    button.outline:hover:not(:disabled) { background: var(--surface); border-color: var(--accent); }
  }

  /* --- status ------------------------------------------------------------ */

  .status { font-size: 11.5px; color: var(--fg-faint); margin-top: 9px; }
  .status:empty { display: none; }
  .status.is-error {
    color: var(--danger); background: var(--danger-tint);
    padding: 6px 10px; border-radius: 8px;
  }

  /* --- composer ---------------------------------------------------------- */

  .composer { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
  .composer.hidden { display: none; }
  .composer:not(.hidden) { animation: fade-up 180ms var(--ease-out) both; }
  @keyframes fade-up { from { opacity: 0; transform: translateY(-4px); } }

  .composer-row { display: flex; align-items: center; gap: 8px; }
  .stamp {
    font-variant-numeric: tabular-nums; font-weight: 600;
    font-size: 12px; color: var(--accent); flex: 1;
  }

  .excerpt {
    font-size: 11.5px; color: var(--fg-dim); margin: 0;
    padding: 8px 10px; border-radius: 10px;
    background: var(--surface); border-left: 3px solid var(--line-strong);
    max-height: 64px; overflow: auto;
  }
  .excerpt.hidden { display: none; }

  textarea, input[type="text"] {
    width: 100%; font: inherit; font-size: 13px; color: var(--fg);
    background: var(--surface);
    border: 1px solid transparent;
    border-radius: 10px; padding: 10px 12px;
    transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease;
  }
  textarea { min-height: 70px; resize: vertical; }
  textarea::placeholder, input::placeholder { color: var(--fg-faint); }
  textarea:focus, input[type="text"]:focus {
    outline: none; background: var(--bg);
    border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-tint);
  }

  .share {
    display: flex; align-items: center; gap: 7px;
    font-size: 12px; color: var(--fg-dim); cursor: pointer;
  }
  .share input { accent-color: var(--accent); margin: 0; cursor: pointer; width: 14px; height: 14px; }

  /* --- tabs -------------------------------------------------------------- */

  /* A segmented control on a tinted strip, rather than an underline. The underline read as
     YouTube's own tab chrome, which is exactly the association the white card is trying to
     break. */
  .tabs {
    display: flex; align-items: center; gap: 4px;
    padding: 10px 16px; border-top: 1px solid var(--line);
    background: var(--surface);
  }
  .tab {
    background: transparent; border: 0;
    border-radius: 8px; color: var(--fg-dim);
    font-size: 12.5px; font-weight: 550; padding: 6px 12px;
    transition: color 150ms ease, background-color 150ms ease, box-shadow 150ms ease;
  }
  .tab[aria-selected="true"] {
    color: var(--accent); background: var(--bg);
    box-shadow: 0 1px 2px rgba(35,34,43,.06);
  }
  .tab:active:not(:disabled) { transform: none; }
  .tab .count { color: var(--fg-faint); font-weight: 500; font-variant-numeric: tabular-nums; }
  .tabs .spacer { flex: 1; }

  .view { padding: 14px 16px 16px; }
  .view[hidden] { display: none; }

  /* --- ask --------------------------------------------------------------- */

  .answer { margin-top: 10px; }
  .answer:empty { display: none; }
  .answer p { margin: 0; font-size: 12.5px; }

  .thinking { display: flex; gap: 4px; align-items: center; padding: 4px 0; }
  .thinking i {
    width: 4px; height: 4px; border-radius: 50%;
    background: var(--fg-faint); display: block;
    animation: bob 900ms ease-in-out infinite;
  }
  .thinking i:nth-child(2) { animation-delay: 120ms; }
  .thinking i:nth-child(3) { animation-delay: 240ms; }
  @keyframes bob { 30% { transform: translateY(-3px); opacity: 1; } 0%,60%,100% { opacity: .4; } }

  .cites { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
  .flag { font-size: 11px; color: var(--fg-faint); margin-top: 6px; display: block; }

  /* --- notes ------------------------------------------------------------- */

  /* overflow-x matters: .note uses a negative inline margin so its hover tint reaches past
     the view's padding, which makes the row wider than this box and raises a horizontal
     scrollbar if it is allowed to. */
  .notes { max-height: 320px; overflow-y: auto; overflow-x: hidden; }
  .notes::-webkit-scrollbar { width: 5px; }
  .notes::-webkit-scrollbar-thumb { background: var(--line); border-radius: 3px; }
  .notes::-webkit-scrollbar-track { background: transparent; }

  /* Rows are separated by space and a hover tint instead of rules. At ten-plus notes the
     ruled list read as a table; the card is small enough that whitespace alone groups them. */
  .note {
    padding: 9px 10px; margin: 0 -10px;
    border-radius: 10px;
    display: flex; gap: 10px; align-items: flex-start;
    transition: background-color 150ms ease;
  }
  @media (hover: hover) and (pointer: fine) {
    .note:hover { background: var(--surface); }
  }
  /* Only genuinely new rows animate — see renderNotes. Re-animating the whole list on every
     save would turn an ordinary action into a flicker. */
  .note.enter { animation: fade-up 200ms var(--ease-out) both; }

  .ts {
    background: var(--accent-tint); border: 0; padding: 1px 7px;
    border-radius: 6px;
    color: var(--accent); font-weight: 600; font-size: 11.5px;
    font-variant-numeric: tabular-nums; flex: none;
    text-align: center; line-height: 1.6;
  }
  @media (hover: hover) and (pointer: fine) {
    .ts:hover { background: var(--accent); color: var(--accent-ink); box-shadow: none; }
  }
  .note-main { flex: 1; min-width: 0; }
  .note-text { font-size: 12.5px; overflow-wrap: anywhere; }
  .note-quote {
    font-size: 11.5px; color: var(--fg-faint); margin: 3px 0 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  .del {
    flex: none; padding: 0 2px; border-radius: 4px; line-height: 1;
    background: transparent; border: 0; color: var(--fg-faint); font-size: 15px;
    opacity: 0; transition: opacity 150ms ease, color 150ms ease;
  }
  @media (hover: hover) and (pointer: fine) {
    .note:hover .del, .del:focus-visible { opacity: 1; }
    .del:hover { color: var(--danger); }
  }
  @media not all and (hover: hover) { .del { opacity: .5; } }

  .pending .note-text { color: var(--fg-dim); }
  .pending .ts { color: var(--fg-faint); }
  .failed .ts { color: var(--danger); background: var(--danger-tint); }
  .state { font-size: 11px; color: var(--fg-faint); }

  .empty { color: var(--fg-faint); font-size: 12px; padding: 22px 0; text-align: center; }

  .hidden { display: none; }

  /* Reduced motion means gentler, not none: opacity still aids comprehension, movement goes. */
  @media (prefers-reduced-motion: reduce) {
    .panel, .composer:not(.hidden), .note.enter {
      animation-name: fade-only; animation-duration: 140ms;
    }
    @keyframes fade-only { from { opacity: 0; } }
    button:active:not(:disabled) { transform: none; }
    .thinking i { animation: none; }
  }
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

type TabName = "notes" | "ask";

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
  private topicLabel!: HTMLElement;
  private askInput!: HTMLInputElement;
  private askAnswer!: HTMLElement;
  private notesTab!: HTMLButtonElement;
  private askTab!: HTMLButtonElement;
  private notesView!: HTMLElement;
  private askView!: HTMLElement;
  private noteCount!: HTMLElement;

  private pendingSeconds = 0;
  private pendingTopicId: string | null = null;
  /** Note ids already on screen, so a re-render only animates what is genuinely new. */
  private renderedIds = new Set<string>();

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

    // The manifest's "Alt+N" is Option on a Mac, so the hint has to match the keycap the learner
    // is actually looking at rather than the string the manifest happens to use.
    const altKey = navigator.platform.toLowerCase().includes("mac") ? "⌥N" : "Alt+N";

    const wrapper = document.createElement("div");
    wrapper.className = "panel";
    wrapper.innerHTML = `
      <div class="pad">
        <div class="head">
          <span class="title">Watch &amp; Note</span>
          <span class="topic" data-topic></span>
        </div>

        <div style="margin-top:10px">
          <button class="capture" data-capture>Capture moment <span class="k">${altKey}</span></button>
        </div>

        <div class="status" data-status></div>

        <div class="composer hidden" data-composer>
          <div class="composer-row">
            <span class="stamp" data-composer-meta></span>
            <button class="quiet" data-cancel>Cancel</button>
          </div>
          <p class="excerpt hidden" data-composer-excerpt></p>
          <textarea data-text placeholder="What did you notice here?"></textarea>
          <div class="composer-row">
            <label class="share"><input type="checkbox" data-share /> Share</label>
            <span style="flex:1"></span>
            <button data-save>Save</button>
          </div>
        </div>
      </div>

      <div class="tabs" role="tablist">
        <button class="tab" role="tab" data-tab="notes" aria-selected="true">
          Notes <span class="count" data-count></span>
        </button>
        <button class="tab" role="tab" data-tab="ask" aria-selected="false">Ask</button>
        <span class="spacer"></span>
        <button class="quiet" data-export>Export</button>
      </div>

      <div class="view" data-view="notes">
        <div class="notes" data-notes></div>
      </div>

      <div class="view" data-view="ask" hidden>
        <input type="text" data-ask placeholder="Ask anything about this video…" />
        <div class="answer" data-answer></div>
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
    this.topicLabel = q("[data-topic]");
    this.askInput = q<HTMLInputElement>("[data-ask]");
    this.askAnswer = q("[data-answer]");
    this.notesTab = q<HTMLButtonElement>('[data-tab="notes"]');
    this.askTab = q<HTMLButtonElement>('[data-tab="ask"]');
    this.notesView = q('[data-view="notes"]');
    this.askView = q('[data-view="ask"]');
    this.noteCount = q("[data-count]");

    q("[data-capture]").addEventListener("click", () => this.callbacks.onCapture());
    q("[data-export]").addEventListener("click", () => this.callbacks.onExport());
    q("[data-cancel]").addEventListener("click", () => {
      this.hideComposer();
      this.callbacks.onCancel();
    });
    this.notesTab.addEventListener("click", () => this.showTab("notes"));
    this.askTab.addEventListener("click", () => this.showTab("ask"));

    this.saveButton.addEventListener("click", () => this.submit());
    this.textarea.addEventListener("keydown", (event) => {
      // Cmd/Ctrl+Enter saves. Plain Enter must stay a newline — a note is prose, not a form field.
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") this.submit();
      if (event.key === "Escape") {
        this.hideComposer();
        this.callbacks.onCancel();
      }
    });

    this.askInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      const question = this.askInput.value.trim();
      if (question) this.callbacks.onAsk(question);
    });

    // YouTube binds single-key shortcuts (k, j, f, t…) on document. Without this, typing a note
    // also scrubs and pauses the video underneath.
    for (const type of ["keydown", "keyup", "keypress"] as const) {
      wrapper.addEventListener(type, (event) => event.stopPropagation());
    }
  }

  private showTab(tab: TabName): void {
    const onNotes = tab === "notes";
    this.notesTab.setAttribute("aria-selected", String(onNotes));
    this.askTab.setAttribute("aria-selected", String(!onNotes));
    this.notesView.hidden = !onNotes;
    this.askView.hidden = onNotes;
    if (!onNotes) this.askInput.focus({ preventScroll: true });
  }

  private submit(): void {
    const text = this.textarea.value.trim();
    if (!text) return;
    this.callbacks.onSave(text, this.shareBox.checked, this.pendingTopicId);
    this.hideComposer();
    // A saved note belongs to the list, so show the learner where it went.
    this.showTab("notes");
  }

  showComposer(seconds: number, excerpt: string | null, shareDefault: boolean): void {
    this.pendingSeconds = seconds;
    this.composer.classList.remove("hidden");
    this.composerMeta.textContent = formatTimestamp(seconds);
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
    this.statusLine.classList.toggle("is-error", isError);
  }

  setTopic(suggestion: TopicSuggestion | null, proposed?: ProposedTopic | null): void {
    this.pendingTopicId = suggestion?.topic_id ?? null;
    this.topicLabel.classList.remove("is-set");

    if (suggestion?.topic_id) {
      this.topicLabel.textContent = suggestion.topic_name ?? "";
      this.topicLabel.classList.add("is-set");
      this.topicLabel.title =
        `Matched to "${suggestion.topic_name}" by ${suggestion.strategy} ` +
        `(${suggestion.score.toFixed(2)}), so notes feed your mastery map.`;
    } else if (proposed) {
      // Nothing matched, but saving a note will mint this topic. Named rather than shown as
      // "unmapped" because the learner is about to file a note under it, and the trailing "new"
      // keeps the distinction from a match honest.
      this.topicLabel.textContent = `${proposed.name} · new`;
      this.topicLabel.title =
        `No existing topic matched, so saving a note creates "${proposed.name}" ` +
        `(${proposed.subject}) and files the note under it.`;
    } else {
      // Nothing to say yet. An "unmapped" badge is noise on a panel this small — the absence of
      // a topic is already legible from there being no topic.
      this.topicLabel.textContent = "";
      this.topicLabel.title = "";
    }
  }

  renderNotes(notes: NoteOut[], pending: QueuedNote[]): void {
    this.notesList.replaceChildren();
    const total = notes.length + pending.length;
    this.noteCount.textContent = total > 0 ? String(total) : "";

    if (total === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Nothing saved yet.";
      this.notesList.append(empty);
      this.renderedIds.clear();
      return;
    }

    const seen = new Set<string>();

    for (const note of notes) {
      seen.add(note.id);
      const row = document.createElement("div");
      row.className = this.renderedIds.has(note.id) ? "note" : "note enter";

      const timestamp = document.createElement("button");
      timestamp.className = "ts";
      timestamp.textContent = formatTimestamp(note.t_seconds);
      timestamp.title = "Jump to this moment";
      timestamp.addEventListener("click", () => this.callbacks.onSeek(note.t_seconds));

      const main = document.createElement("div");
      main.className = "note-main";
      const body = document.createElement("div");
      body.className = "note-text";
      body.textContent = note.learner_text;
      main.append(body);

      if (note.transcript_excerpt) {
        const excerpt = document.createElement("p");
        excerpt.className = "note-quote";
        excerpt.textContent = note.transcript_excerpt;
        excerpt.title = note.transcript_excerpt;
        main.append(excerpt);
      }

      const remove = document.createElement("button");
      remove.className = "del";
      remove.textContent = "×";
      remove.title = "Delete this note";
      remove.setAttribute("aria-label", "Delete this note");
      remove.addEventListener("click", () => this.callbacks.onDelete(note.id));

      row.append(timestamp, main, remove);
      this.notesList.append(row);
    }

    for (const queued of pending) {
      seen.add(queued.localId);
      const failed = queued.failedPermanently;
      const row = document.createElement("div");
      row.className = this.renderedIds.has(queued.localId) ? "note pending" : "note pending enter";
      if (failed) row.classList.add("failed");

      const stamp = document.createElement("span");
      stamp.className = "ts";
      stamp.textContent = formatTimestamp(queued.payload.t_seconds);

      const main = document.createElement("div");
      main.className = "note-main";
      const body = document.createElement("div");
      body.className = "note-text";
      body.textContent = queued.payload.learner_text;
      const state = document.createElement("span");
      state.className = "state";
      state.textContent = failed ? "not synced" : "syncing…";
      if (failed && queued.lastError) state.title = queued.lastError;
      main.append(body, state);

      row.append(stamp, main);
      this.notesList.append(row);
    }

    this.renderedIds = seen;
  }

  renderAnswer(answer: string, citations: Citation[], stubbed: boolean): void {
    this.askAnswer.replaceChildren();

    const text = document.createElement("p");
    text.textContent = answer;
    this.askAnswer.append(text);

    if (stubbed) {
      const flag = document.createElement("span");
      flag.className = "flag";
      flag.textContent = "Keyword match — no model configured.";
      this.askAnswer.append(flag);
    }

    if (citations.length > 0) {
      const row = document.createElement("div");
      row.className = "cites";
      for (const citation of citations) {
        const jump = document.createElement("button");
        jump.className = "outline";
        jump.textContent = formatTimestamp(citation.t_seconds);
        jump.title = citation.quote;
        jump.addEventListener("click", () => this.callbacks.onSeek(citation.t_seconds));

        const save = document.createElement("button");
        save.className = "quiet";
        save.textContent = "Note this";
        save.title = "Start a note at this timestamp";
        save.addEventListener("click", () => this.callbacks.onSaveCitation(citation));

        row.append(jump, save);
      }
      this.askAnswer.append(row);
    }
  }

  setAskBusy(busy: boolean): void {
    this.askInput.disabled = busy;
    if (busy) {
      this.askAnswer.replaceChildren();
      const dots = document.createElement("div");
      dots.className = "thinking";
      dots.append(
        document.createElement("i"),
        document.createElement("i"),
        document.createElement("i"),
      );
      this.askAnswer.append(dots);
    }
  }
}
