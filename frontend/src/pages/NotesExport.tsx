/**
 * Export page for video notes — reached directly from the Chrome extension.
 *
 * Two routes land here: `#/notes/export/:videoId` for one video and
 * `#/notes/export/topic/:topicId` for a whole topic. It is not a tab, because nobody navigates to
 * it deliberately; the extension opens it in a new tab and the download starts from here.
 *
 * `@react-pdf/renderer` is imported dynamically. It is by far the largest dependency in this app,
 * and every other surface — the learning pipeline, the mastery map, the peer feed — would pay for
 * it on first load if it were imported statically.
 */

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getTopicNotePack, getVideoNotePack } from "../api/rest";
import { useLearner } from "../LearnerContext";
import type { TopicNotePack, VideoNotePack } from "../types";

type Status =
  | { phase: "loading" }
  | { phase: "empty" }
  | { phase: "error"; message: string }
  | { phase: "ready"; url: string; filename: string; label: string; count: number };

function safeFilename(input: string): string {
  return (
    input
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60)
      .toLowerCase() || "notes"
  );
}

export default function NotesExport() {
  const { videoId, topicId } = useParams<{ videoId?: string; topicId?: string }>();
  const { learnerId } = useLearner();
  const [status, setStatus] = useState<Status>({ phase: "loading" });

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;

    (async () => {
      try {
        // Both the renderer and the documents are pulled in only once an export is actually
        // requested, which is the point of this page being a separate route.
        const [{ pdf }, { CoursePackDocument, VideoPackDocument }] = await Promise.all([
          import("@react-pdf/renderer"),
          import("../lib/notesPdf"),
        ]);

        let element: React.ReactElement;
        let filename: string;
        let label: string;
        let count: number;

        if (topicId) {
          const pack: TopicNotePack = await getTopicNotePack(learnerId, topicId);
          count = pack.videos.reduce((sum, video) => sum + video.notes.length, 0);
          if (count === 0) {
            if (!cancelled) setStatus({ phase: "empty" });
            return;
          }
          element = <CoursePackDocument pack={pack} />;
          filename = `parallax-${safeFilename(pack.topic_name)}-course-pack.pdf`;
          label = `${pack.topic_name} — course pack`;
        } else if (videoId) {
          const pack: VideoNotePack = await getVideoNotePack(learnerId, videoId);
          count = pack.notes.length;
          if (count === 0) {
            if (!cancelled) setStatus({ phase: "empty" });
            return;
          }
          element = <VideoPackDocument pack={pack} />;
          filename = `parallax-${safeFilename(pack.video_title)}-notes.pdf`;
          label = pack.video_title;
        } else {
          if (!cancelled) setStatus({ phase: "error", message: "No video or topic in the URL." });
          return;
        }

        const blob = await pdf(element).toBlob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        revoked = url;
        setStatus({ phase: "ready", url, filename, label, count });
      } catch (error) {
        if (!cancelled) {
          setStatus({
            phase: "error",
            message: error instanceof Error ? error.message : String(error),
          });
        }
      }
    })();

    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [learnerId, topicId, videoId]);

  return (
    <div className="stack" style={{ maxWidth: 640, margin: "0 auto" }}>
      <div>
        <span className="eyebrow">Export</span>
        <h2 style={{ margin: "4px 0 0" }}>Notes as PDF</h2>
      </div>

      {status.phase === "loading" && <p className="muted">Building your PDF…</p>}

      {status.phase === "empty" && (
        <p className="muted">
          No notes here yet. Capture a moment with the Parallax extension on a YouTube lecture, then
          come back.
        </p>
      )}

      {status.phase === "error" && (
        <p className="faint">Couldn't build the PDF — {status.message}</p>
      )}

      {status.phase === "ready" && (
        <>
          <p className="muted" style={{ marginBottom: 0 }}>
            <strong>{status.label}</strong> · {status.count} note
            {status.count === 1 ? "" : "s"}. Every timestamp in the PDF is a link back to that
            second of the video.
          </p>
          <a href={status.url} download={status.filename}>
            <button>Download {status.filename}</button>
          </a>
          {/* An inline preview so a click can be verified without leaving the page — the links in
              here are the real annotations, so this is also how you check one works. */}
          <iframe
            title="PDF preview"
            src={status.url}
            style={{
              width: "100%",
              height: 520,
              border: "1px solid var(--rule, rgba(127,127,127,.3))",
              borderRadius: 12,
            }}
          />
        </>
      )}
    </div>
  );
}
