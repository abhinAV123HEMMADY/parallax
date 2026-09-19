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

export interface StruggleFeedItem {
  user_id: string;
  topic_id: string;
  topic_name: string;
  relative_signal: "struggling" | "on_track";
}

export interface SquadProposal {
  id: string;
  topic_id: string;
  member_ids: string[];
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
