/**
 * Caption extraction — the most fragile part of this extension, isolated on purpose.
 *
 * Everything here depends on YouTube internals that are undocumented and do change: the shape of
 * `ytInitialPlayerResponse`, the `timedtext` response format, and the caption DOM classes. That is
 * why it lives in one module behind one contract (`getCues`, `liveCaptionText`): when YouTube
 * changes something, exactly one file breaks and the rest of the extension keeps working.
 *
 * Three independent paths, because they fail in different situations:
 *
 *   1. The full cue list, from the player's caption track. Needs no captions visible on screen
 *      and gives the whole transcript, which is what the backend ingests for search and Q&A.
 *   2. YouTube's own transcript panel, scraped from the DOM. Slower and it has to touch the
 *      page, but it is the only path that still works when (1) is refused.
 *   3. The rendered caption line. Needs captions switched on and gives only the current moment,
 *      but survives any change to the player response shape.
 *
 * Path (2) exists because YouTube now gates `timedtext` behind a proof-of-origin token. Without
 * one the request still returns **HTTP 200 with a zero-length body** rather than an error, so
 * every format negotiation "succeeds" and yields nothing — which is why this presented as
 * "captions could not be read" rather than as a failed fetch. The transcript panel is served
 * through the player's own authenticated path, so it is unaffected.
 *
 * When all three fail the note is still saved without an excerpt. A missing excerpt is a small
 * loss; refusing the capture would be a large one.
 */

import type { Cue } from "../lib/types";

interface Json3Event {
  tStartMs?: number;
  segs?: Array<{ utf8?: string }>;
}

/** Parses YouTube's `fmt=json3` timedtext payload into cues. */
export function parseJson3(payload: unknown): Cue[] {
  const events = (payload as { events?: Json3Event[] })?.events;
  if (!Array.isArray(events)) return [];

  const cues: Cue[] = [];
  for (const event of events) {
    const text = (event.segs ?? [])
      .map((seg) => seg.utf8 ?? "")
      .join("")
      .replace(/\s+/g, " ")
      .trim();
    // json3 includes zero-length spacer events with no segs; they carry no text and would
    // otherwise become empty cues that the backend then has to filter.
    if (!text || text === "\n") continue;
    cues.push({ t_seconds: Math.floor((event.tStartMs ?? 0) / 1000), text });
  }
  return cues;
}

/** Parses the older XML timedtext format, used when a track has no json3 variant. */
export function parseTimedTextXml(xml: string): Cue[] {
  const doc = new DOMParser().parseFromString(xml, "text/xml");
  const nodes = Array.from(doc.getElementsByTagName("text"));
  const cues: Cue[] = [];
  for (const node of nodes) {
    const start = Number(node.getAttribute("start") ?? "0");
    // The payload is HTML-escaped inside XML text nodes, so &amp;#39; style entities need a
    // second decode pass to come back as apostrophes rather than literal entity text.
    const decoded = new DOMParser().parseFromString(
      node.textContent ?? "",
      "text/html",
    ).documentElement.textContent;
    const text = (decoded ?? "").replace(/\s+/g, " ").trim();
    if (text) cues.push({ t_seconds: Math.floor(start), text });
  }
  return cues;
}

/** "1:23" → 83, "1:02:03" → 3723. Returns null for anything that isn't a timestamp. */
export function parseTimestamp(stamp: string): number | null {
  const parts = stamp.trim().split(":");
  if (parts.length < 2 || parts.length > 3) return null;
  const numbers = parts.map((p) => Number(p));
  if (numbers.some((n) => !Number.isFinite(n) || n < 0)) return null;
  return parts.length === 3
    ? numbers[0]! * 3600 + numbers[1]! * 60 + numbers[2]!
    : numbers[0]! * 60 + numbers[1]!;
}

/**
 * Turns the transcript panel's rows into cues.
 *
 * Split out from the DOM walk so the parsing is testable without a browser: the panel's markup
 * is YouTube's to change, but the shape of what comes out of it is this extension's contract.
 * Rows whose timestamp doesn't parse are dropped rather than defaulted to zero — a cue at the
 * wrong second sends the learner to the wrong moment, which is worse than a missing cue.
 */
export function parseTranscriptRows(rows: Array<{ stamp: string; text: string }>): Cue[] {
  const cues: Cue[] = [];
  for (const row of rows) {
    const seconds = parseTimestamp(row.stamp);
    if (seconds === null) continue;
    // Panel rows wrap mid-sentence, so the newlines are layout rather than meaning.
    const text = row.text.replace(/\s+/g, " ").trim();
    if (text) cues.push({ t_seconds: seconds, text });
  }
  return cues;
}

/**
 * Reads the full transcript out of YouTube's own transcript panel.
 *
 * This is the only path that survives the proof-of-origin gate on `timedtext`, but it costs a
 * visible side effect: the panel has to be open to be read. So the panel's prior state is
 * captured and restored — a learner who never opened it doesn't get it left open, and one who
 * did keeps it. Returns [] rather than throwing on any missing element, because a caption
 * failure must never cost the note.
 */
export async function getCuesFromTranscriptPanel(): Promise<Cue[]> {
  const readRows = () =>
    Array.from(document.querySelectorAll("ytd-transcript-segment-renderer")).map((node) => ({
      stamp: node.querySelector(".segment-timestamp")?.textContent ?? "",
      text: node.querySelector(".segment-text")?.textContent ?? "",
    }));

  // Already open — read it and leave it exactly as found.
  if (document.querySelector("ytd-transcript-segment-renderer")) {
    return parseTranscriptRows(readRows());
  }

  const open = Array.from(document.querySelectorAll("button")).find((button) =>
    /show transcript/i.test(button.getAttribute("aria-label") ?? button.textContent ?? ""),
  );
  if (!open) return [];
  open.click();

  // The panel renders asynchronously. Poll rather than guess a delay: the wait is the whole
  // cost of this path, so finishing as soon as rows appear matters.
  let rows: Array<{ stamp: string; text: string }> = [];
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    rows = readRows();
    if (rows.length > 0) break;
  }

  // Put it back. The learner didn't ask for this panel; reading it is our business, not theirs.
  const close = document.querySelector<HTMLButtonElement>(
    "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-searchable-transcript'] #visibility-button button",
  );
  close?.click();

  return parseTranscriptRows(rows);
}

/**
 * Fetches and parses the full cue list for the current video.
 *
 * The fetch happens here, in the content script, rather than in the service worker: the request is
 * same-origin to youtube.com from this context, which is precisely why an extension can read
 * captions reliably when a backend cannot.
 */
export async function getCues(trackUrl: string): Promise<Cue[]> {
  const jsonUrl = trackUrl.includes("fmt=") ? trackUrl : `${trackUrl}&fmt=json3`;

  try {
    const response = await fetch(jsonUrl, { credentials: "include" });
    if (response.ok) {
      const body = await response.text();
      if (body.trim().startsWith("{")) {
        const cues = parseJson3(JSON.parse(body));
        if (cues.length > 0) return cues;
      } else if (body.includes("<text")) {
        return parseTimedTextXml(body);
      }
    }
  } catch (error) {
    console.warn("[parallax] json3 caption fetch failed, trying xml", error);
  }

  try {
    const response = await fetch(trackUrl, { credentials: "include" });
    if (response.ok) {
      const cues = parseTimedTextXml(await response.text());
      if (cues.length > 0) return cues;
    }
  } catch (error) {
    console.warn("[parallax] caption fetch failed, falling back to the transcript panel", error);
  }

  // Both direct fetches came back empty — the proof-of-origin gate. Read the panel instead.
  return getCuesFromTranscriptPanel();
}

/** The caption line currently rendered on the player, if the learner has captions on. */
export function liveCaptionText(): string | null {
  const segments = document.querySelectorAll<HTMLElement>(".ytp-caption-segment");
  if (segments.length === 0) return null;
  const text = Array.from(segments)
    .map((segment) => segment.textContent ?? "")
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  return text || null;
}

/** The cue covering `seconds` — the latest one starting at or before it. */
export function cueAt(cues: Cue[], seconds: number): string | null {
  if (cues.length === 0) return null;
  let found: Cue | null = null;
  for (const cue of cues) {
    if (cue.t_seconds <= seconds) found = cue;
    else break;
  }
  return (found ?? cues[0])?.text ?? null;
}
