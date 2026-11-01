import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

const fetchMock = vi.fn()

function jsonResponse(body: unknown, init?: { ok?: boolean; status?: number }): Response {
  const { ok = true, status = 200 } = init ?? {}
  return { ok, status, json: async () => body } as unknown as Response
}

function lastCall(): [string, RequestInit | undefined] {
  return fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit | undefined]
}

function lastJsonBody(): Record<string, unknown> {
  const raw = lastCall()[1]?.body
  return JSON.parse(typeof raw === 'string' ? raw : '{}')
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('request 错误处理', () => {
  it('失败响应抛出后端统一错误体中的 message', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: { message: '课程不存在' } }, { ok: false, status: 404 }),
    )
    await expect(api.health()).rejects.toThrow('课程不存在')
  })

  it('错误体缺失 message 时回退为状态码占位消息', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'boom' }, { ok: false, status: 502 }))
    await expect(api.health()).rejects.toThrow('请求失败（502）')
  })
})

describe('URL 与查询参数构造', () => {
  it('纯链接方法返回完整地址并应用默认参数', () => {
    expect(api.fileUrl('c1', 'd1')).toBe('/api/v1/courses/c1/documents/d1/file')
    expect(api.documentImageUrl('c1', 'd1', 'cover')).toBe(
      '/api/v1/courses/c1/documents/d1/images/cover',
    )
    expect(api.evidenceExportUrl('c1', 'r1')).toBe(
      '/api/v1/courses/c1/evidence/comparisons/r1/export',
    )
    expect(api.exportUrl('c1', 'dr1')).toBe('/api/v1/courses/c1/drafts/dr1/export')
    expect(api.teachingExportUrl('c1', 'quiz', 't1')).toBe(
      '/api/v1/courses/c1/teaching/quiz/t1/export',
    )
    expect(api.lessonWordUrl('c1', 't1', 'student')).toBe(
      '/api/v1/courses/c1/teaching/lesson/t1/word?audience=student',
    )
    expect(api.lessonWordUrl('c1', 't1')).toBe(
      '/api/v1/courses/c1/teaching/lesson/t1/word?audience=teacher',
    )
  })

  it('GET 类请求不附带请求体', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([]))
    await api.graph('c1')
    const [url, init] = lastCall()
    expect(url).toBe('/api/v1/courses/c1/graph')
    expect(init).toBeUndefined()
  })

  it('dissolveQuestionGroup 以查询串携带版本号并使用 DELETE', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    await api.dissolveQuestionGroup('c1', 'g1', 3)
    const [url, init] = lastCall()
    expect(url).toBe('/api/v1/courses/c1/question-groups/g1?expected_version=3')
    expect(init?.method).toBe('DELETE')
  })

  it('validateLessonPrint 拼接版本与受众参数', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ version: 2 }))
    await api.validateLessonPrint('c1', 't1', 2)
    expect(lastCall()[0]).toBe(
      '/api/v1/courses/c1/teaching/lesson/t1/print?expected_version=2&audience=teacher',
    )
  })

  it('upload 替换文档时附加 replaces_id 查询参数', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ job_id: 'j1', material_id: 'm1', status: 'queued' }),
    )
    const file = new File(['x'], 'a.pdf')
    await api.upload('c1', file, 'd-old')
    const [url, init] = lastCall()
    expect(url).toBe('/api/v1/courses/c1/documents?replaces_id=d-old')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
    expect((init?.body as FormData).get('file')).toBe(file)
  })
})

describe('请求体构造', () => {
  it('importQuestions 将文本数组映射为逐条对象', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([]))
    await api.importQuestions('c1', ['问题一', '问题二'], 'tfidf')
    expect(lastJsonBody()).toEqual({
      questions: [
        { question_text: '问题一', method: 'tfidf' },
        { question_text: '问题二', method: 'tfidf' },
      ],
    })
  })

  it('mergeQuestionGroups 生成 expected_versions 映射', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    await api.mergeQuestionGroups('c1', [
      { id: 'a', version: 1 },
      { id: 'b', version: 2 },
    ])
    expect(lastJsonBody()).toEqual({
      group_ids: ['a', 'b'],
      expected_versions: { a: 1, b: 2 },
    })
  })

  it('match 默认使用 name 方法', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    await api.match('c1', '什么是分词')
    expect(lastJsonBody()).toEqual({ question: '什么是分词', method: 'name' })
  })

  it('matchQuestion 默认使用 auto 方法', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    await api.matchQuestion('c1', '什么是分词')
    expect(lastJsonBody()).toEqual({ question_text: '什么是分词', method: 'auto' })
  })

  it('updateQuestionGroup 携带版本号且默认确认', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    await api.updateQuestionGroup('c1', 'g1', ['q1', 'q2'], '标题', 4)
    expect(lastJsonBody()).toEqual({
      question_ids: ['q1', 'q2'],
      title: '标题',
      expected_version: 4,
      confirm: true,
    })
  })
})
