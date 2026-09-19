import type {
  ExamPlan,
  MasteryGraph,
  MentraUser,
  ProtegeTurnResult,
  SquadProposal,
  StruggleFeedItem,
  TopicNotePack,
  VideoNote,
  VideoNotePack,
  VideoNoteWithImage,
} from "../types";

// Production builds default to the hosted backend so a static deploy works without any
// dashboard env config; VITE_API_BASE_URL still overrides when set.
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.PROD ? "https://mentra-backend-mats.onrender.com" : "http://localhost:8000");

// Every endpoint reflects real backend state or fails loudly. No client-side simulation of
// lessons, quizzes, mastery, or Protégé Mode: if the backend is unreachable, callers see a
// real error and the UI shows an honest "couldn't load" state.

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export function startLearning(learnerId: string, topicInput: string, inputMode: "text" | "photo") {
  return postJson<{ session_id: string; status: string }>("/learn", {
    learner_id: learnerId,
    topic_input: topicInput,
    input_mode: inputMode,
  });
}

export function submitConfidence(cardId: string, learnerId: string, rating: number, recalled: boolean) {
  return postJson<{ status: string; next_due_days: number; mastery_score: number | null; topic_id: string | null }>(
    "/learn/confidence",
    {
      card_id: cardId,
      learner_id: learnerId,
      rating,
      recalled,
    },
  );
}

export function submitQuizAnswer(lessonId: string, question: string, correct: boolean, modalityUsed?: string) {
  return postJson<{ status: string; mastery_score: number | null; topic_id: string }>("/learn/quiz-answer", {
    lesson_id: lessonId,
    question,
    correct,
    modality_used: modalityUsed ?? null,
  });
}

export function listUsers() {
  return getJson<MentraUser[]>("/users");
}

export function createUser(name: string, gradeLevel?: string) {
  return postJson<MentraUser>("/users", { name, grade_level: gradeLevel ?? null });
}

export function getExamPlan(learnerId: string, daysUntilExam: number): Promise<ExamPlan> {
  return postJson<ExamPlan>("/exam/plan", {
    learner_id: learnerId,
    days_until_exam: daysUntilExam,
  });
}

export function getStruggleFeed(userId: string): Promise<StruggleFeedItem[]> {
  return getJson<StruggleFeedItem[]>(`/peer/feed/${userId}`);
}

export function getSquadProposals(topicId: string): Promise<SquadProposal[]> {
  return getJson<SquadProposal[]>(`/peer/squads/${topicId}`);
}

export function getMasteryGraph(userId: string): Promise<MasteryGraph> {
  return getJson<MasteryGraph>(`/mastery/graph/${userId}`);
}

export function postQna(topicId: string, authorId: string, body: string) {
  return postJson<{ id: string; moderation_status: string }>("/peer/qna", {
    topic_id: topicId,
    author_id: authorId,
    body,
  });
}

export function startProtege(topicName: string, learnerId: string): Promise<ProtegeTurnResult> {
  return postJson<ProtegeTurnResult>("/protege/start", { topic_name: topicName, learner_id: learnerId });
}

export function sendProtegeTurn(sessionId: string, learnerExplanation: string): Promise<ProtegeTurnResult> {
  return postJson<ProtegeTurnResult>("/protege/turn", {
    session_id: sessionId,
    learner_explanation: learnerExplanation,
  });
}

export function publishProtegeExplanation(sessionId: string) {
  return postJson<{ id: string; moderation_status: string }>("/protege/publish", { session_id: sessionId });
}

// --- Video notes ---

export function getVideoNotes(learnerId: string, videoId: string) {
  const query = new URLSearchParams({ learner_id: learnerId, video_id: videoId });
  return getJson<{ video_id: string; video_title: string; notes: VideoNote[] }>(`/notes?${query}`);
}

export function getTopicNotes(learnerId: string, topicId: string) {
  const query = new URLSearchParams({ learner_id: learnerId });
  return getJson<{ topic_id: string; topic_name: string; videos: { video_id: string; video_title: string; notes: VideoNote[] }[] }>(
    `/notes/topic/${topicId}?${query}`,
  );
}

export function getNoteDetail(learnerId: string, noteId: string) {
  const query = new URLSearchParams({ learner_id: learnerId });
  return getJson<VideoNoteWithImage>(`/notes/${noteId}?${query}`);
}

/** Screenshots are omitted from list responses because they are large, so a pack destined for PDF
 * has to fetch each note's detail. Done with a bounded concurrency rather than one big
 * Promise.all: a topic pack can hold dozens of notes and each carries an image. */
async function withImages(notes: VideoNote[], learnerId: string): Promise<VideoNoteWithImage[]> {
  const out: VideoNoteWithImage[] = [];
  const batchSize = 4;
  for (let i = 0; i < notes.length; i += batchSize) {
    const batch = notes.slice(i, i + batchSize);
    const resolved = await Promise.all(
      batch.map(async (note) => {
        if (!note.has_screenshot) return { ...note, screenshot: null };
        try {
          return await getNoteDetail(learnerId, note.id);
        } catch {
          // A missing image must not lose the note it belongs to.
          return { ...note, screenshot: null };
        }
      }),
    );
    out.push(...resolved);
  }
  return out;
}

export async function getVideoNotePack(learnerId: string, videoId: string): Promise<VideoNotePack> {
  const pack = await getVideoNotes(learnerId, videoId);
  return { ...pack, notes: await withImages(pack.notes, learnerId) };
}

export async function getTopicNotePack(learnerId: string, topicId: string): Promise<TopicNotePack> {
  const pack = await getTopicNotes(learnerId, topicId);
  const videos = [];
  for (const video of pack.videos) {
    videos.push({ ...video, notes: await withImages(video.notes, learnerId) });
  }
  return { topic_id: pack.topic_id, topic_name: pack.topic_name, videos };
}

export function generateCardsFromNotes(learnerId: string, topicId: string) {
  const query = new URLSearchParams({ learner_id: learnerId });
  return postJson<{ lesson_id: string; topic_id: string; cards_created: number; notes_used: number }>(
    `/notes/topic/${topicId}/flashcards?${query}`,
    {},
  );
}
