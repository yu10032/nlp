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
  text: string
  graph_version: number
  model_version: string
  predictions: { node_id: string; score: number; rank: number; status: string }[]
  confirmed_node_ids: string[]
  needs_review: boolean
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
