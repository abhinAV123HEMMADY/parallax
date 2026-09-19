/**
 * Caption parsing and queue logic — the pure parts.
 *
 * Deliberately does not touch Chrome APIs or YouTube's DOM. Those are the parts that can only be
 * verified by loading the extension in a real browser, and a mock of them would assert that the
 * mock behaves like the mock.
 */

import { describe, expect, it } from "vitest";
import { cueAt, parseJson3, parseTimedTextXml } from "../src/content/captions";
import { backoffMs, isDue } from "../src/lib/queue";
import type { QueuedNote } from "../src/lib/types";

describe("parseJson3", () => {
  it("joins segments and converts ms to whole seconds", () => {
    const cues = parseJson3({
      events: [{ tStartMs: 1500, segs: [{ utf8: "A limit " }, { utf8: "describes" }] }],
    });
    expect(cues).toEqual([{ t_seconds: 1, text: "A limit describes" }]);
  });

  it("drops the spacer events YouTube interleaves", () => {
    // json3 includes zero-length events with no segs; they would otherwise become empty cues.
    const cues = parseJson3({
      events: [
        { tStartMs: 0, segs: [{ utf8: "\n" }] },
        { tStartMs: 1000 },
        { tStartMs: 2000, segs: [{ utf8: "real text" }] },
      ],
    });
    expect(cues).toEqual([{ t_seconds: 2, text: "real text" }]);
  });

  it("returns empty for a shape it does not recognise", () => {
    expect(parseJson3({})).toEqual([]);
    expect(parseJson3(null)).toEqual([]);
    expect(parseJson3({ events: "nope" })).toEqual([]);
  });
});

describe("parseTimedTextXml", () => {
  it("reads start times and decodes doubly-escaped entities", () => {
    const xml =
      '<?xml version="1.0"?><transcript>' +
      '<text start="12.34" dur="2">it&amp;#39;s the slope</text>' +
      '<text start="20" dur="2">of a curve</text>' +
      "</transcript>";
    expect(parseTimedTextXml(xml)).toEqual([
      { t_seconds: 12, text: "it's the slope" },
      { t_seconds: 20, text: "of a curve" },
    ]);
  });

  it("returns empty for markup with no text nodes", () => {
    expect(parseTimedTextXml("<transcript></transcript>")).toEqual([]);
  });
});

describe("cueAt", () => {
  const cues = [
    { t_seconds: 0, text: "first" },
    { t_seconds: 30, text: "second" },
    { t_seconds: 60, text: "third" },
  ];

  it("picks the latest cue at or before the timestamp", () => {
    expect(cueAt(cues, 45)).toBe("second");
    expect(cueAt(cues, 30)).toBe("second");
    expect(cueAt(cues, 999)).toBe("third");
  });

  it("falls back to the first cue before the track starts", () => {
    expect(cueAt([{ t_seconds: 10, text: "late start" }], 2)).toBe("late start");
  });

  it("is null with no cues", () => {
    expect(cueAt([], 10)).toBeNull();
  });
});

describe("queue retry policy", () => {
  const note = (over: Partial<QueuedNote> = {}): QueuedNote => ({
    localId: "x",
    payload: {
      learner_id: "u",
      video_id: "v",
      video_title: "t",
      t_seconds: 1,
      learner_text: "text",
    },
    queuedAt: 0,
    attempts: 0,
    ...over,
  });

  it("backs off exponentially and caps", () => {
    expect(backoffMs(1)).toBe(5_000);
    expect(backoffMs(2)).toBe(10_000);
    expect(backoffMs(3)).toBe(20_000);
    expect(backoffMs(30)).toBe(5 * 60_000);
  });

  it("sends a fresh note immediately", () => {
    expect(isDue(note(), 0)).toBe(true);
  });

  it("waits out the backoff after a failure", () => {
    const failed = note({ attempts: 1, queuedAt: 1_000 });
    expect(isDue(failed, 2_000)).toBe(false);
    expect(isDue(failed, 1_000 + 5_000)).toBe(true);
  });

  it("never retries a permanently failed note", () => {
    // A 4xx would otherwise sit at the head of the queue forever, blocking everything behind it.
    expect(isDue(note({ failedPermanently: true }), Number.MAX_SAFE_INTEGER)).toBe(false);
  });
});
