/**
 * PDF documents for video notes.
 *
 * Every timestamp is a real PDF link annotation (`<Link src>`), not styled text. That is the whole
 * point of the export: a note in a PDF is only useful if it takes you back to the second of the
 * lecture it came from. Styled text that merely looks like a link would read identically on screen
 * and do nothing when clicked.
 *
 * Export lives in the web app rather than the extension because the packs it needs — notes grouped
 * by video, topics ordered by prerequisite depth — are already here, as is the renderer. The
 * extension deep-links to these routes instead of shipping a second copy of a PDF library.
 */

import { Document, Image, Link, Page, StyleSheet, Text, View } from "@react-pdf/renderer";
import type { TopicNotePack, VideoNotePack, VideoNoteWithImage } from "../types";

const palette = {
  ink: "#111418",
  muted: "#5d6672",
  rule: "#dfe3e8",
  link: "#0b62d0",
  quote: "#39424e",
};

const styles = StyleSheet.create({
  page: { paddingTop: 48, paddingBottom: 56, paddingHorizontal: 52, fontSize: 10.5, color: palette.ink },
  eyebrow: { fontSize: 8, letterSpacing: 1.4, color: palette.muted, marginBottom: 6 },
  title: { fontSize: 19, marginBottom: 4 },
  subtitle: { fontSize: 10, color: palette.muted, marginBottom: 22 },
  sectionTitle: { fontSize: 13, marginTop: 18, marginBottom: 2 },
  sectionMeta: { fontSize: 9, color: palette.muted, marginBottom: 10 },
  note: { borderTopWidth: 0.7, borderTopColor: palette.rule, paddingTop: 9, marginBottom: 11 },
  stamp: { fontSize: 10.5, color: palette.link, marginBottom: 4 },
  body: { lineHeight: 1.45, marginBottom: 4 },
  quote: {
    fontSize: 9.5,
    color: palette.quote,
    lineHeight: 1.4,
    paddingLeft: 8,
    borderLeftWidth: 1.6,
    borderLeftColor: palette.rule,
    marginTop: 3,
  },
  thumb: { width: 200, marginTop: 6, marginBottom: 2 },
  contentsRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 5 },
  footer: {
    position: "absolute",
    bottom: 28,
    left: 52,
    right: 52,
    fontSize: 8,
    color: palette.muted,
    flexDirection: "row",
    justifyContent: "space-between",
  },
});

function stamp(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`;
}

/** The deep link a timestamp resolves to. `&t=<n>s` is what makes YouTube open mid-video. */
function youtubeAt(videoId: string, seconds: number): string {
  return `https://www.youtube.com/watch?v=${videoId}&t=${Math.max(0, Math.floor(seconds))}s`;
}

function Footer({ label }: { label: string }) {
  return (
    <View style={styles.footer} fixed>
      <Text>{label}</Text>
      <Text render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`} />
    </View>
  );
}

function NoteBlock({ videoId, note }: { videoId: string; note: VideoNoteWithImage }) {
  return (
    <View style={styles.note} wrap={false}>
      <Link src={youtubeAt(videoId, note.t_seconds)} style={styles.stamp}>
        {stamp(note.t_seconds)} — open in YouTube
      </Link>
      <Text style={styles.body}>{note.learner_text}</Text>
      {note.screenshot ? <Image src={note.screenshot} style={styles.thumb} /> : null}
      {note.transcript_excerpt ? (
        <Text style={styles.quote}>“{note.transcript_excerpt}”</Text>
      ) : null}
    </View>
  );
}

export function VideoPackDocument({ pack }: { pack: VideoNotePack }) {
  return (
    <Document title={`Parallax notes — ${pack.video_title}`} author="Parallax">
      <Page size="A4" style={styles.page}>
        <Text style={styles.eyebrow}>PARALLAX · VIDEO NOTES</Text>
        <Text style={styles.title}>{pack.video_title}</Text>
        <Text style={styles.subtitle}>
          {pack.notes.length} note{pack.notes.length === 1 ? "" : "s"} · every timestamp below is a
          link back to that moment
        </Text>
        {pack.notes.map((note) => (
          <NoteBlock key={note.id} videoId={pack.video_id} note={note} />
        ))}
        <Footer label={pack.video_title} />
      </Page>
    </Document>
  );
}

export function CoursePackDocument({ pack }: { pack: TopicNotePack }) {
  const total = pack.videos.reduce((sum, video) => sum + video.notes.length, 0);

  return (
    <Document title={`Parallax course pack — ${pack.topic_name}`} author="Parallax">
      <Page size="A4" style={styles.page}>
        <Text style={styles.eyebrow}>PARALLAX · COURSE PACK</Text>
        <Text style={styles.title}>{pack.topic_name}</Text>
        <Text style={styles.subtitle}>
          {total} note{total === 1 ? "" : "s"} across {pack.videos.length} video
          {pack.videos.length === 1 ? "" : "s"}
        </Text>

        <Text style={styles.sectionTitle}>Contents</Text>
        <Text style={styles.sectionMeta}>Ordered so foundations come before what they unlock.</Text>
        {pack.videos.map((video) => (
          <View key={video.video_id} style={styles.contentsRow}>
            <Link src={youtubeAt(video.video_id, video.notes[0]?.t_seconds ?? 0)}>
              {video.video_title}
            </Link>
            <Text style={{ color: palette.muted }}>{video.notes.length}</Text>
          </View>
        ))}

        {pack.videos.map((video) => (
          <View key={video.video_id} break>
            <Text style={styles.sectionTitle}>{video.video_title}</Text>
            <Text style={styles.sectionMeta}>
              {video.notes.length} note{video.notes.length === 1 ? "" : "s"}
            </Text>
            {video.notes.map((note) => (
              <NoteBlock key={note.id} videoId={video.video_id} note={note} />
            ))}
          </View>
        ))}

        <Footer label={`${pack.topic_name} — course pack`} />
      </Page>
    </Document>
  );
}
