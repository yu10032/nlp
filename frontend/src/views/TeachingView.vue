<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { api } from '../api'
import QuizEditor from '../components/QuizEditor.vue'
import LessonEditor from '../components/LessonEditor.vue'
import LessonPreview from '../components/LessonPreview.vue'
import SourceList from '../components/SourceList.vue'
import SourceReader from '../components/SourceReader.vue'
import type {
  DraftSummary,
  Graph,
  Health,
  LessonBody,
  LessonSegment,
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
const nodeEvidence = ref<{ node_id: string; citation_ids: string[]; has_active_source: boolean }[]>(
  [],
)
const preview = ref(false)
const stopRequested = ref(false)
const generationProgress = ref('')
const reviewer = ref('教师')
const historyMenu = ref<HTMLDetailsElement>()
const requestedCount = ref(3)
const requestedType = ref<QuizItem['type']>('single_choice')
const quizBody = ref<QuizBody>({ difficulty: 'basic', items: [], missing_info: [] })
const lessonBody = ref<LessonBody>({
  format_version: 2,
  plan_confirmed: false,
  duration: 45,
  objectives: '',
  key_questions: '',
  preparation: '',
  homework: '',
  student_homework: '',
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
const lessonChars = computed(() =>
  lessonBody.value.segments.reduce((sum, s) => sum + s.content.replace(/\s/g, '').length, 0),
)
function planSnapshot(value: LessonBody, ids: string[]) {
  return JSON.stringify({
    target_node_ids: ids,
    duration: value.duration,
    objectives: value.objectives,
    key_questions: value.key_questions,
    segments: value.segments.map(({ id, title, stage, minutes, node_ids, quiz_ids }) => ({
      id,
      title,
      stage,
      minutes,
      node_ids,
      quiz_ids,
    })),
  })
}
const planConfirmed = computed(
  () =>
    !!draft.value &&
    lessonBody.value.plan_confirmed &&
    planSnapshot(lessonBody.value, targets.value) ===
      planSnapshot(draft.value.body as LessonBody, draft.value.body.target_node_ids),
)
const completedSegments = computed(
  () => lessonBody.value.segments.filter((s) => s.content.trim()).length,
)
const pendingSegments = computed(() => lessonBody.value.segments.filter((s) => !s.content.trim()))
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
  nodeEvidence.value = []
  quizBody.value = { difficulty: 'basic', items: [blankItem()], missing_info: [] }
  lessonBody.value = {
    format_version: 2,
    plan_confirmed: false,
    duration: 45,
    objectives: '',
    key_questions: '',
    preparation: '',
    homework: '',
    student_homework: '',
    segments: (
      [
        ['opening', '导入与复习', 5],
        ['instruction', '知识讲解与例题演示', 25],
        ['practice', '课堂练习与讨论', 10],
        ['summary', '总结与出口检测', 5],
      ] as const
    ).map(([stage, title, minutes]) => ({
      id: crypto.randomUUID(),
      stage,
      title,
      minutes,
      content: '',
      activity: '',
      example: '',
      student_activity: '',
      expected_response: '',
      check_for_understanding: '',
      misconceptions: '',
      quiz_ids: [],
      node_ids: [],
      citation_ids: [],
    })),
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
  else {
    const saved = structuredClone(value.body as LessonBody)
    lessonBody.value = {
      ...saved,
      format_version: saved.format_version ?? 1,
      plan_confirmed: saved.plan_confirmed ?? false,
      preparation: saved.preparation ?? '',
      homework: saved.homework ?? '',
      student_homework: saved.student_homework ?? '',
      segments: saved.segments.map((segment) => ({
        ...segment,
        id: segment.id ?? crypto.randomUUID(),
        stage: segment.stage ?? 'instruction',
        student_activity: segment.student_activity ?? '',
        expected_response: segment.expected_response ?? '',
        check_for_understanding: segment.check_for_understanding ?? '',
        misconceptions: segment.misconceptions ?? '',
      })),
    }
  }
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
    nodeEvidence.value = result.node_evidence
    searched.value = true
    source.value = undefined
  })
}
async function generate() {
  if (!isQuiz.value) {
    await generatePendingSegments()
    return
  }
  if (
    dirty.value &&
    hasWork.value &&
    !window.confirm('生成会建立一份新草稿，当前未保存的修改将被替换。继续？')
  )
    return
  await run('generation', async () => {
    const spec = {
      difficulty: quizBody.value.difficulty,
      items: Array.from({ length: requestedCount.value }, blankItem),
      missing_info: [],
    }
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
async function confirmPlan() {
  await run('confirming-plan', async () => {
    lessonBody.value.format_version = 2
    for (const segment of lessonBody.value.segments)
      if (!segment.node_ids.length) segment.node_ids = [...targets.value]
    const saved = dirty.value || !draft.value ? await persist() : draft.value
    apply(await api.confirmLessonPlan(props.courseId, saved.id, saved.version))
    message.value = '课堂安排已确认，可以逐段生成；已有正文会保留。'
  })
}
async function generatePendingSegments() {
  stopRequested.value = false
  await run('lesson-generation', async () => {
    let saved = dirty.value || !draft.value ? await persist() : draft.value
    if (!(saved.body as LessonBody).plan_confirmed) throw new Error('请先确认课堂安排')
    const pending = (saved.body as LessonBody).segments.filter((s) => !s.content.trim())
    for (let index = 0; index < pending.length; index++) {
      if (stopRequested.value) break
      const segment = pending[index]!
      generationProgress.value = `正在生成 ${index + 1} / ${pending.length}：${segment.title}`
      saved = await api.generateLessonSegment(props.courseId, saved.id, segment.id, saved.version)
      apply(saved)
    }
    generationProgress.value = ''
    await reloadLibrary()
    message.value = stopRequested.value
      ? '已停止后续生成，完成的环节已保存。'
      : '环节已逐段保存，请核查正文、活动与依据。'
  })
}
async function rewriteSegment(segment: LessonSegment, instruction: string) {
  await run(`segment:${segment.id}`, async () => {
    const saved = dirty.value || !draft.value ? await persist() : draft.value
    apply(
      await api.generateLessonSegment(
        props.courseId,
        saved.id,
        segment.id,
        saved.version,
        instruction,
      ),
    )
    await reloadLibrary()
    message.value = `“${segment.title}”已单独保存为新版本，其他环节保留。`
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
      <h1>{{ isQuiz ? '辅助出题' : '课堂讲义' }}</h1>
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
  <div v-if="busy === 'lesson-generation'" class="lesson-progress" role="status">
    <span
      >{{ generationProgress }} · 已保存 {{ completedSegments }} /
      {{ lessonBody.segments.length }} 段</span
    >
    <button class="secondary" type="button" :disabled="stopRequested" @click="stopRequested = true">
      {{ stopRequested ? '当前环节完成后停止' : '停止后续生成' }}
    </button>
  </div>
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
            ><p class="section-hint">
              按整节课准备可直接讲授的正文、例题、师生互动、练习答案和反馈，活动用时计入课时。
            </p>
            <p v-if="lessonBody.format_version === 1" class="section-hint">
              当前为旧版提纲。可继续编辑，或按完整讲义要求补充后审核。
              <button class="text-button" type="button" @click="lessonBody.format_version = 2">
                补充为完整讲义
              </button>
            </p>
            <div class="lesson-goals">
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
            <label class="editor-field">
              课前准备与先备知识
              <textarea
                v-model="lessonBody.preparation"
                rows="3"
                maxlength="4000"
                placeholder="学生需掌握什么；教师与学生分别准备哪些材料或工具？"
              ></textarea>
            </label>
            <div class="duration-setting">
              <label
                >课堂时长
                <input v-model.number="lessonBody.duration" type="number" min="5" max="240" />
                分钟</label
              ><span :class="totalMinutes === lessonBody.duration ? 'muted' : 'time-mismatch'"
                >已安排 {{ totalMinutes }} / {{ lessonBody.duration }} 分钟</span
              >
            </div>
            <p v-if="lessonBody.format_version === 2" class="section-hint">
              讲解正文 {{ lessonChars }} 字，按当前课时至少需 {{ lessonBody.duration * 60 }} 字。
              篇幅用于避免内容过于简略，仍需核对知识覆盖、活动和答案是否完整。
            </p></template
          >
          <div class="teaching-start">
            <button class="secondary" type="button" :disabled="!targets.length" @click="retrieve">
              {{ busy === 'retrieval' ? '查找中…' : '查找课程依据' }}</button
            ><button
              v-if="!isQuiz"
              class="secondary"
              type="button"
              :disabled="!title.trim() || !targets.length || !lessonBody.objectives.trim()"
              @click="confirmPlan"
            >
              {{ planConfirmed ? '安排已确认' : '确认课堂安排' }}</button
            ><button
              class="primary"
              type="button"
              :disabled="
                !health?.generation.available ||
                !targets.length ||
                !title.trim() ||
                (!isQuiz && !lessonBody.objectives.trim()) ||
                (!isQuiz && (!planConfirmed || !pendingSegments.length)) ||
                (isQuiz &&
                  (!Number.isInteger(requestedCount) || requestedCount < 1 || requestedCount > 5))
              "
              @click="generate"
            >
              {{
                busy === 'generation'
                  ? '生成中…'
                  : isQuiz
                    ? '生成题目'
                    : `生成空白环节（${pendingSegments.length}）`
              }}
            </button>
          </div>
          <div v-if="!isQuiz" class="lesson-plan-summary">
            <p class="section-hint">
              先核对下方环节的标题、类型、用时与知识点，再确认安排。未单独关联的环节在确认时使用本课全部目标知识点。生成只填写空白正文；失败后可继续。
            </p>
            <ol class="lesson-timeline">
              <li v-for="segment in lessonBody.segments" :key="segment.id">
                <span>{{ segment.title || '未命名环节' }}</span
                ><small
                  >{{ segment.minutes }} 分钟 ·
                  {{ segment.content.trim() ? '已有正文' : '待编写' }}</small
                >
              </li>
            </ol>
          </div>
          <p v-if="!isQuiz && busy === 'generation'" class="section-hint" role="status">
            正在编写整节课的讲解、例题和互动，可能需要几分钟，请等待生成完成。
          </p>
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
          :can-generate="planConfirmed && !!health?.generation.available"
          @preview="source = $event"
          @generate="rewriteSegment"
        />
        <label v-if="!isQuiz" class="editor-field missing-info">
          课后巩固与参考要点
          <textarea
            v-model="lessonBody.homework"
            rows="5"
            maxlength="5000"
            placeholder="写出巩固题、具体要求和参考解答要点，作为教学建议。"
          ></textarea>
        </label>
        <label v-if="!isQuiz" class="editor-field missing-info">
          学生版课后任务（不含答案）
          <textarea
            v-model="lessonBody.student_homework"
            rows="3"
            maxlength="5000"
            placeholder="仅写题目、要求和提交物；教师参考答案写在上方课后巩固中。"
          ></textarea>
        </label>
        <p v-if="!isQuiz" class="section-hint">
          学生版隐藏教师提示与独立答案字段，保留讲解正文中的示范推导，请在预览里核对发放内容。
        </p>
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
          <button v-if="!isQuiz" class="secondary" type="button" @click="preview = true">
            阅读预览
          </button>
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
            <a
              v-if="!isQuiz && draft?.status === 'approved' && !dirty"
              class="secondary"
              :href="api.lessonWordUrl(courseId, draft.id)"
              download
              >导出 Word</a
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
      <div v-if="!isQuiz && nodeEvidence.length" class="node-evidence-report">
        <h3>目标依据检查</h3>
        <p
          v-for="item in nodeEvidence"
          :key="item.node_id"
          :class="item.has_active_source ? 'muted' : 'error'"
        >
          {{ allNodes.find((n) => n.id === item.node_id)?.name }}：{{
            !item.has_active_source
              ? '缺少有效原文，请补充资料'
              : item.citation_ids.length
                ? `已选 ${item.citation_ids.length} 段直接依据`
                : '有原文，当前检索额度未选入'
          }}
        </p>
      </div>
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
  <LessonPreview
    v-if="preview && !isQuiz"
    :title="title"
    :body="lessonBody"
    :nodes="selectedNodes"
    :evidence="evidence.filter((e) => usedCitationIds.includes(e.id))"
    :course-id="courseId"
    :approved="draft?.status === 'approved' && !dirty"
    :content-id="draft?.id"
    :version="draft?.version"
    @close="preview = false"
  />
</template>
