/**
 * chrome.storage access. Every read tolerates missing keys, because a fresh install has none and
 * the service worker can be woken for a keyboard command before the options page has ever run.
 */

import { DEFAULT_SETTINGS, type QueuedNote, type Settings } from "./types";

const SETTINGS_KEY = "settings";
const QUEUE_KEY = "noteQueue";

export async function getSettings(): Promise<Settings> {
  const stored = await chrome.storage.sync.get(SETTINGS_KEY);
  return { ...DEFAULT_SETTINGS, ...(stored[SETTINGS_KEY] ?? {}) };
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const next = { ...(await getSettings()), ...patch };
  await chrome.storage.sync.set({ [SETTINGS_KEY]: next });
  return next;
}

/**
 * The queue lives in storage.local, not sync: it can hold screenshots, and sync has an ~8KB
 * per-item quota that a single frame would blow instantly.
 */
export async function getQueue(): Promise<QueuedNote[]> {
  const stored = await chrome.storage.local.get(QUEUE_KEY);
  const queue = stored[QUEUE_KEY];
  return Array.isArray(queue) ? (queue as QueuedNote[]) : [];
}

export async function setQueue(queue: QueuedNote[]): Promise<void> {
  await chrome.storage.local.set({ [QUEUE_KEY]: queue });
}

export async function pushQueue(note: QueuedNote): Promise<void> {
  await setQueue([...(await getQueue()), note]);
}
