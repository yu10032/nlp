import type {
  Course,
  CourseDocument,
  Coverage,
  DocumentChunk,
  Draft,
  DraftSummary,
  DraftWrite,
  Graph,
  Health,
  KnowledgeEdge,
  MatchResult,
  NodeDetail,
  NodeWrite,
  QuestionResult,
  RetrievalResult,
} from './types'

const base = '/api/v1'
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, options)
  const body = await response.json()
  if (!response.ok) throw new Error(body.error?.message ?? `请求失败（${response.status}）`)
  return body as T
}
function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}
const course = (id: string) => `/courses/${id}`

export const api = {
  health: () => request<Health>('/health'),
  courses: () => request<Course[]>('/courses'),
  createCourse: (title: string) => request<Course>('/courses', json('POST', { title })),
  graph: (id: string) => request<Graph>(`${course(id)}/graph`),
  node: (id: string, node: string) => request<NodeDetail>(`${course(id)}/nodes/${node}`),
  createNode: (id: string, body: NodeWrite) =>
    request<NodeDetail>(`${course(id)}/nodes`, json('POST', body)),
  updateNode: (id: string, node: string, body: NodeWrite) =>
    request<NodeDetail>(`${course(id)}/nodes/${node}`, json('PATCH', body)),
  createEdge: (
    id: string,
    body: { source_id: string; target_id: string; relation: string; chunk_id: string },
  ) => request<KnowledgeEdge>(`${course(id)}/edges`, json('POST', body)),
  reviewEdge: (id: string, edge: string, result: string) =>
    request<KnowledgeEdge>(`${course(id)}/edges/${edge}/review`, json('POST', { result })),
  coverage: (id: string) => request<Coverage>(`${course(id)}/coverage`),
  match: (id: string, question: string) =>
    request<MatchResult>(`${course(id)}/matches`, json('POST', { question })),
  documents: (id: string) => request<CourseDocument[]>(`${course(id)}/documents`),
  chunks: (id: string, document: string) =>
    request<DocumentChunk[]>(`${course(id)}/documents/${document}/chunks`),
  fileUrl: (id: string, document: string) => `${base}${course(id)}/documents/${document}/file`,
  upload: (id: string, file: File, replaces?: string) => {
    const body = new FormData()
    body.append('file', file)
    return request<{ job_id: string; material_id: string; status: string }>(
      `${course(id)}/documents${replaces ? `?replaces_id=${replaces}` : ''}`,
      { method: 'POST', body },
    )
  },
  job: (id: string, job: string) =>
    request<{ id: string; status: string; error: string | null }>(`${course(id)}/jobs/${job}`),
  matchQuestion: (id: string, question_text: string, method = 'tfidf') =>
    request<QuestionResult>(
      `${course(id)}/questions/match`,
      json('POST', { question_text, method }),
    ),
  questions: (id: string) => request<QuestionResult[]>(`${course(id)}/questions`),
  question: (id: string, question: string) =>
    request<QuestionResult>(`${course(id)}/questions/${question}`),
  confirmLinks: (id: string, question: string, node_ids: string[]) =>
    request<QuestionResult>(
      `${course(id)}/questions/${question}/links`,
      json('POST', { node_ids }),
    ),
  retrieve: (id: string, question_text: string, node_ids: string[], mode: string) =>
    request<RetrievalResult>(
      `${course(id)}/evidence/retrieve`,
      json('POST', { question_text, node_ids, mode }),
    ),
  drafts: (id: string) => request<DraftSummary[]>(`${course(id)}/drafts`),
  draft: (id: string, draft: string) => request<Draft>(`${course(id)}/drafts/${draft}`),
  createDraft: (
    id: string,
    body: DraftWrite & { question_id: string; generate: boolean; retrieval_mode: string },
  ) => request<Draft>(`${course(id)}/drafts`, json('POST', body)),
  updateDraft: (id: string, draft: string, body: DraftWrite & { expected_version: number }) =>
    request<Draft>(`${course(id)}/drafts/${draft}`, json('PATCH', body)),
  reviewDraft: (
    id: string,
    draft: string,
    expected_version: number,
    result: string,
    reviewer: string,
  ) =>
    request<Draft>(
      `${course(id)}/drafts/${draft}/review`,
      json('POST', { expected_version, result, reviewer }),
    ),
  exportUrl: (id: string, draft: string) => `${base}${course(id)}/drafts/${draft}/export`,
}
