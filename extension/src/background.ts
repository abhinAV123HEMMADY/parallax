/**
 * Service worker: the extension's only network caller, and the only place that can screenshot.
 *
 * Holds no state between messages. MV3 terminates this worker after ~30 seconds idle, so any
 * module-level variable is gone by the next message and anything durable lives in
 * chrome.storage (see lib/queue.ts).
 */

import * as api from "./lib/api";
import { FLUSH_ALARM, enqueue, flush, pendingFor } from "./lib/queue";
import { getSettings } from "./lib/storage";
import type { CaptureRect, WorkerRequest, WorkerResponse } from "./lib/types";

/** Downscale target. Keeps a frame far inside the backend's 200KB cap on the stored data URL. */
const MAX_FRAME_WIDTH = 480;
const JPEG_QUALITY = 0.7;

/**
 * Crops the visible-tab capture down to the video element and downscales it.
 *
 * `Image` and `document.createElement("canvas")` do not exist in a service worker, so this uses
 * createImageBitmap + OffscreenCanvas. captureVisibleTab returns the whole viewport in CSS
 * pixels scaled by devicePixelRatio, which is why the content script has to send both its rect
 * and its DPR — on a Retina display the capture is 2x the rect's coordinates.
 */
async function cropFrame(dataUrl: string, rect: CaptureRect): Promise<string> {
  const response = await fetch(dataUrl);
  const bitmap = await createImageBitmap(await response.blob());

  const dpr = rect.devicePixelRatio || 1;
  // Clamp to the bitmap: a rect can run past the capture when the player is partly scrolled out.
  const sx = Math.max(0, Math.round(rect.x * dpr));
  const sy = Math.max(0, Math.round(rect.y * dpr));
  const sw = Math.max(1, Math.min(Math.round(rect.width * dpr), bitmap.width - sx));
  const sh = Math.max(1, Math.min(Math.round(rect.height * dpr), bitmap.height - sy));

  const scale = Math.min(1, MAX_FRAME_WIDTH / sw);
  const dw = Math.max(1, Math.round(sw * scale));
  const dh = Math.max(1, Math.round(sh * scale));

  const canvas = new OffscreenCanvas(dw, dh);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no 2d context in worker");
  ctx.drawImage(bitmap, sx, sy, sw, sh, 0, 0, dw, dh);
  bitmap.close();

  const blob = await canvas.convertToBlob({ type: "image/jpeg", quality: JPEG_QUALITY });
  const buffer = await blob.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]!);
  return `data:image/jpeg;base64,${btoa(binary)}`;
}

async function captureFrame(rect: CaptureRect): Promise<string | null> {
  try {
    // windowId omitted: capture the focused window, which is the one the learner is watching in.
    const shot = await chrome.tabs.captureVisibleTab({ format: "png" });
    return await cropFrame(shot, rect);
  } catch (error) {
    // A screenshot is a bonus, never a reason to lose the note — DRM playback captures black and
    // captureVisibleTab can be refused outright depending on how the capture was triggered.
    console.warn("[parallax] frame capture failed; saving note without an image", error);
    return null;
  }
}

/**
 * Reads the caption track URL out of the page's own `ytInitialPlayerResponse`.
 *
 * A content script runs in an isolated world and cannot see page globals, so the only way to this
 * value is executing in the MAIN world. The returned URL is then fetched by the content script,
 * where the request is same-origin to youtube.com — which is the whole reason caption access is
 * reliable from an extension and unreliable from a server.
 */
async function captionTrackUrl(tabId: number): Promise<string | null> {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    world: "MAIN",
    func: () => {
      const response = (window as unknown as { ytInitialPlayerResponse?: unknown })
        .ytInitialPlayerResponse as
        | { captions?: { playerCaptionsTracklistRenderer?: { captionTracks?: unknown[] } } }
        | undefined;
      const tracks = response?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
      if (!Array.isArray(tracks) || tracks.length === 0) return null;
      // Prefer a manually authored English track over an auto-generated one: auto captions have
      // no punctuation, which materially hurts both chunk readability and embedding quality.
      const typed = tracks as Array<{ baseUrl?: string; languageCode?: string; kind?: string }>;
      const english = typed.filter((t) => (t.languageCode ?? "").startsWith("en"));
      const pool = english.length > 0 ? english : typed;
      const manual = pool.find((t) => t.kind !== "asr");
      return (manual ?? pool[0])?.baseUrl ?? null;
    },
  });
  return (result?.result as string | null) ?? null;
}

async function handle(message: WorkerRequest, sender: chrome.runtime.MessageSender): Promise<unknown> {
  const settings = await getSettings();

  switch (message.kind) {
    case "getSettings":
      return settings;

    case "listUsers":
      return api.listUsers();

    case "listNotes": {
      if (!settings.learnerId) throw new Error("no learner selected — open the extension options");
      return api.listNotes(settings.learnerId, message.videoId);
    }

    case "createNote": {
      // Queued, never sent inline: the capture has already happened from the learner's point of
      // view, and the panel should not block on the network to confirm it.
      const queued = await enqueue(message.payload);
      const result = await flush();
      return { localId: queued.localId, ...result };
    }

    case "deleteNote": {
      if (!settings.learnerId) throw new Error("no learner selected");
      return api.deleteNote(settings.learnerId, message.noteId);
    }

    case "ingestTranscript":
      return api.ingestTranscript(message.videoId, message.videoTitle, message.cues);

    case "topicSuggestion":
      return api.topicSuggestion(message.videoId, message.videoTitle);

    case "ask":
      return api.askVideo(message.videoId, message.question, settings.learnerId);

    case "captureFrame":
      return { screenshot: await captureFrame(message.rect) };

    case "captionTrackUrl": {
      const tabId = sender.tab?.id;
      if (tabId === undefined) throw new Error("no tab to read captions from");
      return { url: await captionTrackUrl(tabId) };
    }

    case "pendingFor":
      return pendingFor(message.videoId);

    case "flushQueue":
      return flush();

    case "openExport": {
      // PDF export lives in the web app, which already has the note packs, the prerequisite
      // ordering and a PDF renderer. Duplicating it here would mean a second copy of both.
      const base = settings.apiBase.replace(/:8000$/, ":5173");
      await chrome.tabs.create({ url: `${base}/#/notes/export/${message.videoId}` });
      return { opened: true };
    }
  }
}

chrome.runtime.onMessage.addListener(
  (message: WorkerRequest, sender, sendResponse: (r: WorkerResponse<unknown>) => void) => {
    handle(message, sender)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error: unknown) =>
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }),
      );
    // Keeps the message channel open for the async reply above.
    return true;
  },
);

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === FLUSH_ALARM) void flush();
});

// Drain anything stranded by a previous shutdown. Both events fire on a worker that was dead.
chrome.runtime.onStartup.addListener(() => void flush());
chrome.runtime.onInstalled.addListener(() => void flush());

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-note") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined) return;
  // The content script owns the capture flow; the command only nudges it, so the keyboard path
  // and the button path cannot drift apart.
  try {
    await chrome.tabs.sendMessage(tab.id, { kind: "captureNoteFromCommand" });
  } catch {
    // No content script on this tab (not a YouTube page) — nothing to do.
  }
});
