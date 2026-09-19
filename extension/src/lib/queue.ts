/**
 * Durable send queue for notes.
 *
 * Capturing a note must never fail because the backend is down or the laptop is offline — the
 * learner is mid-lecture and the moment doesn't wait. So a capture always succeeds locally and
 * the send is a separate, retried concern. This is the honest version of the "offline mode" in
 * the original YouTube Study Kit: capture works offline, sync catches up. It is not offline AI.
 *
 * Everything is read from and written back to chrome.storage on each step rather than held in a
 * module variable. An MV3 service worker is terminated after ~30 seconds idle and can die
 * mid-flush, so in-memory queue state would silently lose notes. The cost is re-reading storage;
 * the benefit is that being killed at any instant loses nothing.
 */

import { PermanentApiError, createNote } from "./api";
import { getQueue, pushQueue, setQueue } from "./storage";
import type { NoteCreate, QueuedNote } from "./types";

const MAX_ATTEMPTS = 8;
const BASE_BACKOFF_MS = 5_000;
const ALARM = "mentra-flush-queue";

/** Exponential backoff, capped. Exported so the retry curve is unit-testable without chrome. */
export function backoffMs(attempts: number): number {
  return Math.min(BASE_BACKOFF_MS * 2 ** Math.max(0, attempts - 1), 5 * 60_000);
}

export function isDue(note: QueuedNote, now: number): boolean {
  if (note.failedPermanently) return false;
  if (note.attempts === 0) return true;
  return now - note.queuedAt >= backoffMs(note.attempts);
}

export async function enqueue(payload: NoteCreate): Promise<QueuedNote> {
  const note: QueuedNote = {
    localId: crypto.randomUUID(),
    payload,
    queuedAt: Date.now(),
    attempts: 0,
  };
  await pushQueue(note);
  await scheduleFlush();
  return note;
}

/**
 * Attempts one pass over the queue. Returns how many notes were accepted.
 *
 * Sends sequentially, not in parallel: a burst of note POSTs each carrying a screenshot is the
 * one thing most likely to trip a rate limit or a body-size guard, and losing the queue's order
 * would scramble a learner's timeline on replay.
 */
export async function flush(): Promise<{ sent: number; remaining: number }> {
  const now = Date.now();
  let queue = await getQueue();
  let sent = 0;

  for (const note of [...queue]) {
    if (!isDue(note, now)) continue;

    try {
      await createNote(note.payload);
      // Re-read: the worker may have been woken and mutated the queue while this awaited.
      queue = (await getQueue()).filter((q) => q.localId !== note.localId);
      await setQueue(queue);
      sent += 1;
    } catch (error) {
      const permanent = error instanceof PermanentApiError;
      const message = error instanceof Error ? error.message : String(error);
      queue = (await getQueue()).map((q) =>
        q.localId === note.localId
          ? {
              ...q,
              attempts: q.attempts + 1,
              queuedAt: Date.now(),
              lastError: message,
              // Give up on a request the server keeps rejecting, or one that has failed so often
              // it is almost certainly malformed. Kept in the queue and flagged rather than
              // deleted, so the learner's text is never thrown away silently.
              failedPermanently: permanent || q.attempts + 1 >= MAX_ATTEMPTS,
            }
          : q,
      );
      await setQueue(queue);
    }
  }

  const remaining = (await getQueue()).filter((q) => !q.failedPermanently).length;
  if (remaining > 0) await scheduleFlush();
  return { sent, remaining };
}

/**
 * Wakes the worker to retry. An alarm rather than setTimeout: a timer dies with the worker, and
 * the worker will be dead long before a multi-minute backoff elapses.
 */
export async function scheduleFlush(): Promise<void> {
  await chrome.alarms.create(ALARM, { delayInMinutes: 1, periodInMinutes: 1 });
}

export async function stopFlushing(): Promise<void> {
  await chrome.alarms.clear(ALARM);
}

export const FLUSH_ALARM = ALARM;

export async function pendingFor(videoId: string): Promise<QueuedNote[]> {
  return (await getQueue()).filter((q) => q.payload.video_id === videoId);
}
