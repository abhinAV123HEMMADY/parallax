export interface LessonContent {
  topic_name: string;
  overview: string;
  worked_examples: { difficulty: string; prompt: string; solution: string }[];
  common_mistakes: string[];
  lesson_id?: string;
}

export interface QuizQuestion {
  question: string;
  answer: string;
  // Escalation ladder shown only after the learner misses: analogy → diagram → video.
  reexplanations: { analogy?: string; diagram?: string; video?: VideoResult };
}

export interface MentraUser {
  id: string;
  name: string;
  grade_level: string | null;
}

export interface Flashcard {
  id?: string;
  front: string;
  back: string;
  stability: number;
  difficulty: number;
  elapsed_days: number;
  due_date: string;
}

export interface VideoResult {
  video_id: string;
  title: string;
  start_seconds: number;
  url: string;
  relevance: number;
}

export interface TutorResult {
  id: string;
  name: string;
  subjects: string[];
  verification_tier: string;
  rating: number;
  response_time_percentile: number;
  price_per_hour: number;
  session_format: string;
  relevance: number;
}

export interface ErrorStep {
  text: string;
  correct: boolean;
  note?: string;
}

export interface ErrorAnalysis {
  problem_statement: string;
  steps: ErrorStep[];
  first_error_step: number;
  error_explanation: string;
  tested_concept: string;
  prerequisite_concept: string;
  prerequisite_topic_id: string | null;
}

export interface ExamPlan {
  days_until_exam: number;
  curve_baseline: number[];
  curve_exam_aware: number[];
  exam_day: {
    baseline: number;
    exam_aware: number;
    cards_at_risk_baseline: number;
    cards_at_risk_exam_aware: number;
  };
  plan: { front: string; review_days: number[]; projected_exam_retrievability: number }[];
  daily_load: number[];
  demo_deck?: boolean;
  card_count?: number;
}

export interface PipelineUpdate {
  node: string;
  update: Record<string, unknown>;
}

export interface LearningSessionData {
  lesson?: LessonContent;
  quiz?: QuizQuestion[];
  flashcards?: Flashcard[];
  videos?: VideoResult[];
  tutor_matches?: TutorResult[];
  prerequisite_gap?: string | null;
  error_analysis?: ErrorAnalysis | null;
  done: boolean;
}

export interface ChecklistItem {
  id: string;
  sub_concept: string;
  covered: boolean;
}

export interface ProtegeTurnResult {
  session_id: string;
  topic_name: string;
  persona_message: string;
  understanding_score: number;
  checklist: ChecklistItem[];
  resolved_misconceptions: string[];
  status: "active" | "completed" | "published";
}

export interface ProtegeRecap {
  session_id: string;
  topic_id: string;
  topic_name: string;
  summary: string;
  taught_well: string[];
  still_shaky: string[];
  understanding_score: number;
  turn_count: number;
  created_at: string;
}

export interface ChatMessage {
  role: "persona" | "learner";
  content: string;
}

export type MasteryStatus = "mastered" | "decaying" | "gap" | "weak" | "untouched";

export interface MasteryNode {
  id: string;
  name: string;
  subject: string;
  mastery: number;
  retrievability: number | null;
  effective_mastery: number;
  status: MasteryStatus;
  cards_tracked: number;
}

export interface MasteryEdge {
  from: string;
  to: string;
}

export interface MasteryGraph {
  nodes: MasteryNode[];
  edges: MasteryEdge[];
  summary: {
    mastered: number;
    decaying: number;
    gaps: number;
    untouched: number;
    overall: number;
  };
}

// --- Video notes (Watch & Note) ---

export interface VideoNote {
  id: string;
  video_id: string;
  video_title: string;
  topic_id: string | null;
  topic_name: string | null;
  t_seconds: number;
  learner_text: string;
  transcript_excerpt: string | null;
  has_screenshot: boolean;
  created_at: string;
}

/** A note with its image resolved. List endpoints omit screenshots (they're large), so the PDF
 * routes fetch each note's detail before rendering. */
export interface VideoNoteWithImage extends VideoNote {
  screenshot: string | null;
}

export interface VideoNotePack {
  video_id: string;
  video_title: string;
  notes: VideoNoteWithImage[];
}

export interface TopicNotePack {
  topic_id: string;
  topic_name: string;
  videos: VideoNotePack[];
}
