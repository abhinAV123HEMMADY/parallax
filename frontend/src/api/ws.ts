import type { PipelineUpdate } from "../types";

// Mirrors rest.ts: production builds default to the hosted backend over wss.
const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ??
  (import.meta.env.PROD ? "wss://mentra-backend-mats.onrender.com" : "ws://localhost:8000");

/** Subscribes to a learning session's live pipeline updates (Section 10). Returns a cleanup fn. */
export function subscribeToSession(sessionId: string, onUpdate: (msg: PipelineUpdate) => void): () => void {
  const socket = new WebSocket(`${WS_BASE}/ws/${sessionId}`);

  socket.onmessage = (event) => {
    const parsed = JSON.parse(event.data) as PipelineUpdate;
    onUpdate(parsed);
  };

  return () => socket.close();
}
