<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { api } from '../api'
import QuizEditor from '../components/QuizEditor.vue'
import LessonEditor from '../components/LessonEditor.vue'
import SourceList from '../components/SourceList.vue'
import SourceReader from '../components/SourceReader.vue'
import type {
  DraftSummary,
  Graph,
  Health,
  LessonBody,
  QuizBody,
  QuizItem,
  RetrievalEvidence,
  TeachingContent,
  TeachingKind,
} from '../types'

const props = defineProps<{ courseId: string; kind: TeachingKind }>()
const route = useRoute()
const isQuiz = computed(() => props.kind === 'quiz')
const title = ref('')
const targets = ref<string[]>([])
const graph = ref<Graph>({ version: 0, nodes: [], edges: [] })
const health = ref<Health>()
const history = ref<DraftSummary[]>([])
const quizzes = ref<DraftSummary[]>([])
const draft = ref<TeachingContent>()
const evidence = ref<RetrievalEvidence[]>([])
const source = ref<RetrievalEvidence>()
const chapter = ref('')
const nodeSearch = ref('')
const busy = ref('loading')
const error = ref('')
const message = ref('')
const searched = ref(false)
const reviewer = ref('教师')
const historyMenu = ref<HTMLDetailsElement>()
const requestedCount = ref(3)
const requestedType = ref<QuizItem['type']>('single_choice')
const quizBody = ref<QuizBody>({ difficulty: 'basic', items: [], missing_info: [] })
const lessonBody = ref<LessonBody>({
  duration: 45,
  objectives: '',
  key_questions: '',
  segments: [],
  missing_info: [],
})
const body = computed(() => (isQuiz.value ? quizBody.value : lessonBody.value))
const serialized = () =>
  JSON.stringify({ title: title.value, target_node_ids: targets.value, body: body.value })
const baseline = ref('')
const dirty = computed(() => baseline.value !== serialized())
const hasWork = computed(
  () =>
    !!draft.value ||
    !!title.value.trim() ||
    quizBody.value.items.some((i) => i.stem.trim()) ||
    lessonBody.value.segments.some((s) => s.content.trim()),
)
const allNodes = computed(() =>
  graph.value.nodes.filter((n) => n.status === 'confirmed' && n.kind !== 'chapter'),
)
const chapters = computed(() =>
  graph.value.nodes.filter((n) => n.status === 'confirmed' && n.kind === 'chapter'),
)
const selectedNodes = computed(() => allNodes.value.filter((n) => targets.value.includes(n.id)))
const filteredNodes = computed(() => {
  const descendants = new Set<string>(chapter.value ? [chapter.value] : [])
  if (chapter.value) {
    for (let changed = true; changed;) {
      changed = false
      for (const edge of graph.value.edges)
        if (
          edge.relation === 'contains' &&
          edge.status === 'confirmed' &&
          descendants.has(edge.source_id) &&
          !descendants.has(edge.target_id)
        ) {
          descendants.add(edge.target_id)
          changed = true
        }
    }
  }
  return allNodes.value.filter(
    (n) =>
      (!chapter.value || descendants.has(n.id)) &&
      (n.name + n.aliases.join(' ')).toLowerCase().includes(nodeSearch.value.toLowerCase()),
  )
})
const totalMinutes = computed(() =>
  lessonBody.value.segments.reduce((sum, s) => sum + Number(s.minutes || 0), 0),
)
const usedCitationIds = computed(() => [
  ...new Set(
    (isQuiz.value ? quizBody.value.items : lessonBody.value.segments).flatMap(
      (p) => p.citation_ids,
    ),
  ),
])
const states: Record<string, string> = {
  draft: '草稿',
  approved: '已审核',
  rejected: '已退回',
  stale_review: '待重新审核',
}

watch(
  targets,
  (ids) => {
    for (const part of isQuiz.value ? quizBody.value.items : lessonBody.value.segments) {
      part.node_ids = part.node_ids.filter((id) => ids.includes(id))
    }
  },
  { deep: true, flush: 'sync' },
)

function blankItem(): QuizItem {
  return {
    type: requestedType.value,
    stem: '',
    options: requestedType.value === 'single_choice' ? ['', '', '', ''] : [],
    answer: '',
    explanation: '',
    node_ids: [],
    citation_ids: [],
  }
}
function reset() {
  title.value = ''
  targets.value = []
  draft.value = undefined
  evidence.value = []
  source.value = undefined
  searched.value = false
  quizBody.value = { difficulty: 'basic', items: [blankItem()], missing_info: [] }
  lessonBody.value = {
    duration: 45,
    objectives: '',
    key_questions: '',
    segments: [
      {
        title: '',
        minutes: 45,
        content: '',
        activity: '',
        example: '',
        quiz_ids: [],
        node_ids: [],
        citation_ids: [],
      },
    ],
    missing_info: [],
  }
  baseline.value = serialized()
  message.value = ''
  error.value = ''
}
function mayDiscard() {
  return !dirty.value || !hasWork.value || window.confirm('有未保存的修改，确定离开当前内容？')
}
onBeforeRouteLeave(() => mayDiscard())
function fresh() {
  if (mayDiscard()) reset()
}
async function run(label: string, action: () => Promise<void>) {
  busy.value = label
  error.value = ''
  message.value = ''
  try {
    await action()
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = ''
  }
}
async function reloadLibrary() {
  const [saved, quizList] = await Promise.all([
    api.teachingList(props.courseId, props.kind),
    api.teachingList(props.courseId, 'quiz'),
  ])
  history.value = saved
  quizzes.value = quizList.filter((q) => q.status === 'approved')
}
function apply(value: TeachingContent) {
  draft.value = value
  title.value = value.title
  targets.value = [...value.body.target_node_ids]
  if (isQuiz.value) quizBody.value = structuredClone(value.body as QuizBody)
  else lessonBody.value = structuredClone(value.body as LessonBody)
  evidence.value = [
    ...new Map([...evidence.value, ...value.citations].map((e) => [e.id, e])).values(),
  ]
  baseline.value = serialized()
}
function payload() {
  return { title: title.value.trim(), target_node_ids: targets.value, body: body.value }
}
async function persist() {
  const saved = draft.value
    ? await api.updateTeaching(props.courseId, props.kind, draft.value.id, {
        ...payload(),
        expected_version: draft.value.version,
      })
    : await api.createTeaching(props.courseId, props.kind, { ...payload(), generate: false })
  apply(saved)
  await reloadLibrary()
  return saved
}
async function save() {
  await run('saving', async () => {
    await persist()
    message.value = '草稿已保存'
  })
}
async function retrieve() {
  await run('retrieval', async () => {
    const result = await api.retrieve(
      props.courseId,
      selectedNodes.value.map((n) => n.name).join(' '),
      targets.value,
      'graph_augmented',
    )
    evidence.value = [
      ...new Map([...evidence.value, ...result.evidence].map((e) => [e.id, e])).values(),
    ]
    searched.value = true
    source.value = undefined
  })
}
async function generate() {
  if (
    dirty.value &&
    hasWork.value &&
    !window.confirm('生成会建立一份新草稿，当前未保存的修改将被替换。继续？')
  )
    return
  await run('generation', async () => {
    const spec = isQuiz.value
      ? {
          difficulty: quizBody.value.difficulty,
          items: Array.from({ length: requestedCount.value }, blankItem),
          missing_info: [],
        }
      : lessonBody.value
    apply(
      await api.createTeaching(props.courseId, props.kind, {
        ...payload(),
        body: spec,
        generate: true,
      }),
    )
    await reloadLibrary()
    message.value = '草稿已生成，请核查内容与依据'
    searched.value = true
  })
}
async function open(id: string) {
  if (!mayDiscard()) return
  await run('opening', async () => {
    const saved = await api.teaching(props.courseId, props.kind, id)
    evidence.value = []
    source.value = undefined
    apply(saved)
    searched.value = true
    if (historyMenu.value) historyMenu.value.open = false
  })
}
async function review(result: string) {
  await run('review', async () => {
    const saved = dirty.value || !draft.value ? await persist() : draft.value
    apply(
      await api.reviewTeaching(
        props.courseId,
        props.kind,
        saved.id,
        saved.version,
        result,
        reviewer.value.trim(),
      ),
    )
    await reloadLibrary()
    message.value = result === 'approved' ? '当前版本已审核，可导出' : '已退回修改'
  })
}
onMounted(async () => {
  reset()
  await run('loading', async () => {
    const [g, h] = await Promise.all([api.graph(props.courseId), api.health()])
    graph.value = g
    health.value = h
    await reloadLibrary()
    if (
      typeof route.query.node === 'string' &&
      allNodes.value.some((n) => n.id === route.query.node)
    )
      targets.value = [route.query.node]
    if (typeof route.query.content === 'string') {
      apply(await api.teaching(props.courseId, props.kind, route.query.content))
      searched.value = true
    }
    baseline.value = serialized()
  })
})
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>{{ isQuiz ? '辅助出题' : '备课提纲' }}</h1>
      <span v-if="draft" class="page-meta"
        >{{ states[draft.status] }} · 第 {{ draft.version }} 版</span
      >
    </div>
    <div class="heading-actions">
      <details ref="historyMenu" class="history-menu">
        <summary>{{ isQuiz ? '课程题库' : '已存备课' }} {{ history.length }} 份 ▾</summary>
        <div class="history-options sheet">
          <button
            v-for="item in history"
            :key="item.id"
            type="button"
            :disabled="!!busy"
            @click="open(item.id)"
          >
            <strong>{{ item.title }}</strong
            ><small>{{ states[item.status] }} · 第 {{ item.version }} 版</small>
          </button>
          <p v-if="!history.length" class="muted">还没有保存的内容</p>
        </div>
      </details>
      <button type="button" class="secondary" :disabled="!!busy" @click="fresh">
        ＋ {{ isQuiz ? '新题组' : '新备课' }}
      </button>
    </div>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="message" class="success-message" role="status">{{ message }}</p>
  <p v-if="busy === 'loading'" class="loading-block" role="status">正在打开课程工作台…</p>
  <div v-else class="teaching-layout">
    <article class="teaching-main sheet">
      <fieldset :disabled="!!busy" class="teaching-fields">
        <div class="teaching-setup">
          <label class="editor-field title-field"
            >{{ isQuiz ? '题组名称' : '课题'
            }}<input
              v-model="title"
              maxlength="200"
              :placeholder="
                isQuiz ? '例如：语言模型基础练习' : '例如：从 N 元模型到预训练语言模型'
              "
          /></label>
          <div class="scope-picker">
            <div class="section-heading">
              <span class="section-label">目标知识点 · {{ targets.length }} / 5</span
              ><RouterLink to="/graph">整理图谱 ↗</RouterLink>
            </div>
            <div class="scope-filters">
              <select v-model="chapter" aria-label="按章节筛选">
                <option value="">全部章节</option>
                <option v-for="n in chapters" :key="n.id" :value="n.id">
                  {{ n.name }}
                </option></select
              ><input v-model="nodeSearch" aria-label="搜索目标知识点" placeholder="搜索知识点" />
            </div>
            <div class="scope-node-list">
              <label
                v-for="node in filteredNodes"
                :key="node.id"
                class="node-tag"
                :class="{ 'is-selected': targets.includes(node.id) }"
                ><input
                  v-model="targets"
                  type="checkbox"
                  :value="node.id"
                  :disabled="targets.length >= 5 && !targets.includes(node.id)"
                />{{ node.name }}</label
              >
              <p v-if="!filteredNodes.length" class="muted">
                暂无可选知识点。请先在图谱中确认来源。
              </p>
            </div>
            <p v-if="chapter || nodeSearch" class="selected-scope">
              已选：{{ selectedNodes.map((n) => n.name).join('、') || '尚未选择'
              }}<button
                v-if="targets.length"
                class="text-button"
                type="button"
                @click="targets = []"
              >
                清空
              </button>
            </p>
          </div>
          <div v-if="isQuiz" class="generation-settings">
            <label
              >题型<select v-model="requestedType">
                <option value="single_choice">单选题</option>
                <option value="short_answer">简答题</option>
              </select></label
            ><label
              >生成数量<input
                v-model.number="requestedCount"
                type="number"
                min="1"
                max="5" /></label
            ><label
              >预设难度<select v-model="quizBody.difficulty">
                <option value="basic">基础</option>
                <option value="intermediate">进阶</option>
                <option value="advanced">挑战</option>
              </select></label
            >
          </div>
          <template v-else
            ><div class="lesson-goals">
              <label class="editor-field"
                >教学目标<textarea
                  v-model="lessonBody.objectives"
                  rows="2"
                  maxlength="3000"
                  placeholder="这节课希望学生能够理解或完成什么？"
                ></textarea></label
              ><label class="editor-field"
                >重点问题<textarea
                  v-model="lessonBody.key_questions"
                  rows="2"
                  maxlength="3000"
                ></textarea>
              </label>
            </div>
            <div class="duration-setting">
              <label
                >课堂时长
                <input v-model.number="lessonBody.duration" type="number" min="5" max="240" />
                分钟</label
              ><span :class="totalMinutes === lessonBody.duration ? 'muted' : 'time-mismatch'"
                >已安排 {{ totalMinutes }} / {{ lessonBody.duration }} 分钟</span
              >
            </div></template
          >
          <div class="teaching-start">
            <button class="secondary" type="button" :disabled="!targets.length" @click="retrieve">
              {{ busy === 'retrieval' ? '查找中…' : '查找课程依据' }}</button
            ><button
              class="primary"
              type="button"
              :disabled="
                !health?.generation.available ||
                !targets.length ||
                !title.trim() ||
                (!isQuiz && !lessonBody.objectives.trim()) ||
                (isQuiz &&
                  (!Number.isInteger(requestedCount) || requestedCount < 1 || requestedCount > 5))
              "
              @click="generate"
            >
              {{ busy === 'generation' ? '生成中…' : isQuiz ? '生成题目' : '生成课时提纲' }}
            </button>
          </div>
          <p v-if="!health?.generation.available" class="section-hint">
            生成服务未配置，可直接编写、保存和审核。
          </p>
        </div>
        <QuizEditor
          v-if="isQuiz"
          :body="quizBody"
          :nodes="selectedNodes"
          :evidence="evidence"
          @preview="source = $event"
        />
        <LessonEditor
          v-else
          :body="lessonBody"
          :nodes="selectedNodes"
          :evidence="evidence"
          :quizzes="quizzes"
          @preview="source = $event"
        />
        <label class="editor-field missing-info"
          >待补充事项<textarea
            :value="body.missing_info.join('\n')"
            rows="2"
            placeholder="每行一项"
            @input="
              body.missing_info = ($event.target as HTMLTextAreaElement).value
                .split('\n')
                .filter(Boolean)
            "
          ></textarea>
        </label>
        <div class="teaching-save">
          <span class="muted">{{ dirty ? '有未保存修改' : draft ? '已保存' : '尚未保存' }}</span
          ><button
            class="secondary"
            type="button"
            :disabled="!title.trim() || !targets.length"
            @click="save"
          >
            {{ busy === 'saving' ? '保存中…' : '保存草稿' }}
          </button>
        </div>
        <div class="teaching-review">
          <label class="editor-field reviewer-field"
            >审核人<input v-model="reviewer" maxlength="80"
          /></label>
          <div class="review-actions">
            <button v-if="draft" class="text-button" type="button" @click="review('rejected')">
              退回修改</button
            ><button
              class="review-btn"
              type="button"
              :disabled="!title.trim() || !targets.length || !reviewer.trim()"
              @click="review('approved')"
            >
              审核通过</button
            ><a
              v-if="draft?.status === 'approved' && !dirty"
              class="primary"
              :href="api.teachingExportUrl(courseId, kind, draft.id)"
              download
              >导出 Markdown</a
            >
          </div>
        </div>
      </fieldset>
      <details v-if="draft" class="revision-history">
        <summary>版本与审核记录</summary>
        <p v-for="(entry, index) in draft.reviews" :key="index" class="audit-line">
          v{{ entry.revision }} · {{ states[entry.result] }} · {{ entry.reviewer
          }}<time>{{ new Date(entry.created_at).toLocaleString('zh-CN') }}</time>
        </p>
        <details v-for="revision in draft.revisions" :key="revision.version" class="revision-item">
          <summary>
            第 {{ revision.version }} 版 ·
            {{ new Date(revision.created_at).toLocaleString('zh-CN') }}
          </summary>
          <pre class="revision-prose">{{ revision.snapshot.answer }}</pre>
        </details>
      </details>
    </article>
    <aside class="teaching-evidence">
      <SourceReader
        v-if="source"
        :key="source.id"
        :course-id="courseId"
        :source="source"
        @close="source = undefined"
      /><template v-else
        ><div class="section-heading">
          <h2>课程依据</h2>
          <span class="page-meta">{{ evidence.length }} 段</span>
        </div>
        <SourceList
          :evidence="evidence"
          :selected="usedCitationIds"
          inline-preview
          @preview="source = $event"
        />
        <div v-if="!evidence.length" class="evidence-empty">
          <h3>{{ searched ? '未找到可用依据' : '从知识点查找依据' }}</h3>
          <p>
            {{
              searched
                ? '请补充资料或调整目标知识点。'
                : '选择本次教学范围，引用编号会出现在具体题目或课堂环节下。'
            }}
          </p>
        </div>
        <RouterLink class="text-button" to="/materials">查看课程资料 ↗</RouterLink></template
      >
    </aside>
  </div>
</template>
