export interface Course {
  id: string
  title: string
  description: string
}
export interface KnowledgeNode {
  id: string
  name: string
  aliases: string[]
  description: string
  kind: string
  status: string
}
export interface KnowledgeEdge {
  id: string
  source_id: string
  target_id: string
  relation: string
  chunk_id: string
  status: string
  version: number
}
export interface Graph {
  version: number
  nodes: KnowledgeNode[]
  edges: KnowledgeEdge[]
}
export interface Evidence {
  id: string
  material_id: string
  material_title: string
  material_version: number
  locator: string
  text: string
}

export interface CourseDocument {
  id: string
  document_id: string
  title: string
  filename: string
  version: number
  active: boolean
  status: string
  parser_version: string
  warnings: string[]
  created_at: string
  chunk_count: number
}
export interface DocumentChunk {
  id: string
  material_id: string
  text: string
  locator: string
  section_path: string[]
  page_from: number | null
  page_to: number | null
  paragraph_locator: string | null
  extraction_status: string
  position: number
}
export interface NodeWrite {
  name: string
  aliases: string[]
  description: string
  kind: string
  status: string
  evidence_chunk_ids: string[]
}
export interface RetrievalEvidence extends Evidence {
  section_path: string[]
  score?: number
  origin?: string
  active?: boolean
  graph_paths?: {
    kind: 'direct' | 'one_hop'
    node_id: string
    node_name: string
    via_node_id?: string
    via_node_name?: string
    edge_id?: string
    edge_source_id?: string
    edge_target_id?: string
    relation?: string
  }[]
}
export interface RetrievalResult {
  retrieval_version: string
  mode: string
  evidence: RetrievalEvidence[]
  missing_evidence: boolean
  node_evidence: { node_id: string; citation_ids: string[]; has_active_source: boolean }[]
}
export interface QuestionResult {
  id: string
  batch_id: string | null
  group_id: string | null
  text: string
  graph_version: number
  model_version: string
  predictions: { node_id: string; score: number; rank: number; status: string }[]
  confirmed_node_ids: string[]
  needs_review: boolean
}
export interface QuestionBatchSummary {
  id: string
  title: string
  created_at: string
  question_count: number
}
export interface QuestionGroup {
  id: string
  title: string
  status: 'candidate' | 'confirmed'
  version: number
  question_ids: string[]
  proposal: { method: string; minimum_score?: number; suggested_member_ids?: string[] }
}
export interface QuestionBatch extends QuestionBatchSummary {
  grouping_version: string
  similarity_threshold: number
  questions: QuestionResult[]
  groups: QuestionGroup[]
}
export interface NodeQuestions {
  total: number
  items: (QuestionResult & { node_relation: 'confirmed' | 'predicted' | 'not_selected' })[]
}
export interface ComparisonSummary {
  id: string
  question_text: string
  created_at: string
}
export type Relevance = 'relevant' | 'irrelevant' | 'uncertain'
export interface RetrievalAssessment {
  reviewer: string
  relevance: Record<string, Relevance>
  outcome: 'better' | 'worse' | 'mixed' | 'same' | 'uncertain'
  note: string
  updated_at?: string
}
export interface RetrievalComparison extends ComparisonSummary {
  is_stale: boolean
  assessment: Partial<RetrievalAssessment>
  snapshot: {
    graph_version: number
    materials: { id: string; title: string; version: number }[]
    nodes: { id: string; name: string }[]
    question_context: { id: string; model_version: string; graph_version: number } | null
    evidence_budget: number
    basic: RetrievalResult
    graph_augmented: RetrievalResult
    difference: { shared: string[]; added: string[]; removed: string[] }
  }
}
export interface DraftSummary {
  id: string
  title: string
  status: string
  version: number
  updated_at: string
}
export interface Draft extends DraftSummary {
  answer: string
  question_id: string
  question_text: string
  node_ids: string[]
  citation_ids: string[]
  citations: RetrievalEvidence[]
  generation_info: Record<string, unknown>
  reviews: {
    revision: number
    result: string
    reviewer: string
    note: string
    created_at: string
  }[]
  revisions: { version: number; snapshot: { title: string; answer: string }; created_at: string }[]
}
export interface DraftWrite {
  title: string
  answer: string
  node_ids: string[]
  citation_ids: string[]
}
export interface Health {
  status: string
  generation: { provider: string; available: boolean; model: string | null }
  matcher: { active: string; trained_model_loaded: boolean }
}
export interface NodeDetail extends KnowledgeNode {
  evidence: Evidence[]
}
export interface Metric {
  covered: number
  total: number
  ratio: number | null
}
export type CoverageKind = 'material' | 'quiz' | 'lesson'
export interface Coverage {
  course_id: string
  metrics: Record<CoverageKind, Metric>
  items: { node_id: string; name: string; material: boolean; quiz: boolean; lesson: boolean }[]
}
export interface MatchResult {
  method: string
  matches: { node_id: string; name: string; score: number }[]
}

export type TeachingKind = 'quiz' | 'lesson'
export interface PartLinks {
  node_ids: string[]
  citation_ids: string[]
}
export interface QuizItem extends PartLinks {
  type: 'single_choice' | 'short_answer'
  stem: string
  options: string[]
  answer: string
  explanation: string
}
export interface QuizBody {
  difficulty: string
  items: QuizItem[]
  missing_info: string[]
}
export interface LessonSegment extends PartLinks {
  id: string
  stage: 'opening' | 'instruction' | 'practice' | 'summary'
  title: string
  minutes: number
  content: string
  activity: string
  example: string
  student_activity: string
  expected_response: string
  check_for_understanding: string
  misconceptions: string
  quiz_ids: string[]
}
export interface LessonBody {
  format_version: 1 | 2
  plan_confirmed: boolean
  examples?: Record<
    string,
    { title: string; version: number; answer: string; student_content?: string }
  >
  duration: number
  objectives: string
  key_questions: string
  preparation: string
  homework: string
  student_homework: string
  segments: LessonSegment[]
  missing_info: string[]
}
export interface TeachingContent extends Draft {
  kind: TeachingKind
  body: (QuizBody | LessonBody) & { target_node_ids: string[] }
}
export interface TeachingWrite {
  title: string
  target_node_ids: string[]
  body: QuizBody | LessonBody
}
export interface MatcherState {
  active_method: string
  scope_reason: string
  run_id: string | null
  data_status: string | null
  methods: { id: string; available: boolean }[]
}
export interface Ranking {
  method: string
  version: string
  threshold: number
  matches: { node_id: string; name: string; score: number }[]
}
export interface EvaluationMetric {
  questions: number
  micro_precision: number
  micro_recall: number
  micro_f1: number
  exact_match: number | null
  no_match_questions: number
  no_match_false_link_rate: number | null
  threshold: number
}
export interface ExperimentReport {
  state: MatcherState
  run: null | {
    run_id: string
    encoder_id: string
    dataset_version: string
    data_status: string
    graph_version: number
    selected_epoch: number
    candidate_k: number
    seed: number
    train_seconds: number
  }
  history?: { epoch: number; train_loss: number; validation_loss: number }[]
  split?: Record<string, { questions: number; families: string[] }>
  evaluation?: {
    methods: Record<string, EvaluationMetric>
    candidate_recall: { k: number; ratio: number | null }
    errors: { method: string; question: string; expected: string[]; predicted: string[] }[]
  }
}
