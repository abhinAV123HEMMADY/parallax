/**
 * Caption extraction — the most fragile part of this extension, isolated on purpose.
 *
 * Everything here depends on YouTube internals that are undocumented and do change: the shape of
 * `ytInitialPlayerResponse`, the `timedtext` response format, and the caption DOM classes. That is
 * why it lives in one module behind one contract (`getCues`, `liveCaptionText`): when YouTube
 * changes something, exactly one file breaks and the rest of the extension keeps working.
 *
 * Two independent paths, because they fail in different situations:
 *
 *   1. The full cue list, from the player's caption track. Needs no captions visible on screen
 *      and gives the whole transcript, which is what the backend ingests for search and Q&A.
 *   2. The rendered caption line. Needs captions switched on and gives only the current moment,
 *      but survives any change to the player response shape.
 *
 * When both fail the note is still saved without an excerpt. A missing excerpt is a small loss;
 * refusing the capture would be a large one.
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
    if (!response.ok) return [];
    return parseTimedTextXml(await response.text());
  } catch (error) {
    console.warn("[parallax] caption fetch failed entirely", error);
    return [];
  }
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
