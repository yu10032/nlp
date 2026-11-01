<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../api'
import MatchMethod from '../components/MatchMethod.vue'
import QuestionGroups from '../components/QuestionGroups.vue'
import { useRoute, useRouter } from 'vue-router'
import type { Graph, QuestionResult, QuestionBatch, QuestionBatchSummary } from '../types'
const props = defineProps<{ courseId: string }>()
const graph = ref<Graph>()
const route = useRoute()
const router = useRouter()
const batches = ref<QuestionBatchSummary[]>([])
const batch = ref<QuestionBatch>()
const batchTitle = ref('')
const questions = ref<QuestionResult[]>([])
const selected = ref<QuestionResult>()
const inspector = ref<HTMLElement>()
const selectedNodes = ref<string[]>([])
const input = ref('')
const matchMethod = ref('auto')
const filter = ref('')
const busy = ref(true)
const error = ref('')
const message = ref('')
const lines = computed(() =>
  input.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean),
)
const nodes = computed(
  () => graph.value?.nodes.filter((n) => n.status === 'confirmed' && n.kind !== 'chapter') ?? [],
)
const associations = (q: QuestionResult) =>
  q.needs_review ? q.predictions.map((p) => p.node_id) : q.confirmed_node_ids
const visibleQuestions = computed(() =>
  questions.value.filter((q) => !filter.value || associations(q).includes(filter.value)),
)
const hotspots = computed(() =>
  nodes.value
    .map((node) => ({
      ...node,
      confirmed: questions.value.filter(
        (q) => !q.needs_review && q.confirmed_node_ids.includes(node.id),
      ).length,
      predicted: questions.value.filter(
        (q) => q.needs_review && q.predictions.some((p) => p.node_id === node.id),
      ).length,
    }))
    .filter((n) => n.confirmed + n.predicted > 0)
    .sort((a, b) => b.confirmed - a.confirmed || b.predicted - a.predicted),
)
function open(q: QuestionResult) {
  selected.value = q
  selectedNodes.value = [...associations(q)]
}
async function openFromGroup(q: QuestionResult) {
  open(q)
  await nextTick()
  inspector.value?.scrollIntoView({ block: 'start' })
}
async function importBatch() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api.createQuestionBatch(
      props.courseId,
      lines.value,
      matchMethod.value,
      batchTitle.value,
    )
    applyBatch(result)
    batches.value = await api.questionBatches(props.courseId)
    await router.replace({ query: { batch: result.id } })
    input.value = ''
    batchTitle.value = ''
    filter.value = ''
    if (result.questions[0]) open(result.questions[0])
    message.value = `已导入 ${result.questions.length} 条提问，知识点与相似分组待核查`
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
function applyBatch(value: QuestionBatch) {
  batch.value = value
  questions.value = value.questions
  if (selected.value) selected.value = value.questions.find((q) => q.id === selected.value!.id)
}
async function loadScope(id: string) {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    if (id) applyBatch(await api.questionBatch(props.courseId, id))
    else {
      batch.value = undefined
      questions.value = await api.questions(props.courseId)
    }
    filter.value = ''
    selected.value = undefined
    if (questions.value[0]) open(questions.value[0])
    await router.replace({ query: id ? { batch: id } : {} })
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
async function confirm() {
  if (!selected.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api.confirmLinks(props.courseId, selected.value.id, selectedNodes.value)
    questions.value = questions.value.map((q) => (q.id === result.id ? result : q))
    if (batch.value) batch.value.questions = questions.value
    open(result)
    message.value = '知识点关联已确认'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    const [g, q, b] = await Promise.all([
      api.graph(props.courseId),
      api.questions(props.courseId),
      api.questionBatches(props.courseId),
    ])
    graph.value = g
    questions.value = q
    batches.value = b
    if (typeof route.query.batch === 'string') await loadScope(route.query.batch)
    else if (q[0]) open(q[0])
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
})
</script>
<template>
  <div class="page-heading">
    <h1>提问热点</h1>
    <span class="page-meta"
      >{{ batch ? '本批次' : '最近' }} {{ questions.length }} 条<template v-if="!batch">
        · 最多显示 100 条</template
      ></span
    >
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="message" class="success-message" role="status">{{ message }}</p>
  <form class="question-import sheet" @submit.prevent="importBatch">
    <label class="sr-only" for="question-batch-title">批次名称</label
    ><input
      id="question-batch-title"
      v-model="batchTitle"
      maxlength="120"
      placeholder="批次名称（可选，如：第三周语言模型课）"
      :disabled="busy"
    />
    <label class="editor-field"
      >导入课堂提问<textarea
        v-model="input"
        rows="3"
        placeholder="每行一条，最多 50 条。保留学生原始表述。"
      ></textarea>
    </label>
    <MatchMethod v-model="matchMethod" :course-id="courseId" :disabled="busy" />
    <div class="question-actions">
      <span class="muted">{{ lines.length }} / 50 条</span
      ><button
        class="primary"
        :disabled="busy || !lines.length || lines.length > 50 || lines.some((s) => s.length > 4000)"
      >
        {{ busy ? '处理中…' : '导入并匹配' }}
      </button>
    </div>
  </form>
  <div class="question-batch-scope">
    <label for="question-batch-scope">查看范围</label
    ><select
      id="question-batch-scope"
      :value="batch?.id ?? ''"
      :disabled="busy"
      @change="loadScope(($event.target as HTMLSelectElement).value)"
    >
      <option value="">最近 100 条（含历史提问）</option>
      <option v-for="item in batches" :key="item.id" :value="item.id">
        {{ item.title }} · {{ new Date(item.created_at).toLocaleString('zh-CN') }} ·
        {{ item.question_count }} 问
      </option>
    </select>
  </div>
  <QuestionGroups
    v-if="batch"
    :key="batch.id"
    :course-id="courseId"
    :batch="batch"
    v-model:busy="busy"
    @updated="applyBatch"
    @open="openFromGroup"
  />
  <div class="hotspot-strip">
    <button type="button" class="node-tab" :class="{ selected: !filter }" @click="filter = ''">
      全部提问</button
    ><button
      v-for="node in hotspots"
      :key="node.id"
      class="node-tab"
      :class="{ selected: filter === node.id }"
      type="button"
      @click="filter = node.id"
    >
      {{ node.name
      }}<span
        >{{ node.confirmed }} 已确认<template v-if="node.predicted">
          / {{ node.predicted }} 待确认</template
        ></span
      >
    </button>
  </div>
  <div class="questions-layout">
    <div class="question-register sheet">
      <button
        v-for="q in visibleQuestions"
        :key="q.id"
        class="question-row"
        :class="{ selected: selected?.id === q.id }"
        type="button"
        :disabled="busy"
        @click="open(q)"
      >
        <span>{{ q.text }}</span
        ><small>{{
          q.needs_review ? '待确认' : q.confirmed_node_ids.length ? '已确认关联' : '已确认无关联'
        }}</small>
      </button>
      <p v-if="!visibleQuestions.length" class="muted">
        {{
          questions.length
            ? '当前知识点下没有提问。'
            : '导入一组提问后，按知识点查看热点与核查关联。'
        }}
      </p>
    </div>
    <article v-if="selected" ref="inspector" class="question-inspector sheet">
      <h2>{{ selected.text }}</h2>
      <p class="section-hint">
        {{ selected.needs_review ? selected.model_version + ' · 建议待核查' : '教师已确认关联' }}
      </p>
      <div class="node-choices">
        <label
          v-for="node in nodes"
          :key="node.id"
          class="node-tag"
          :class="{ 'is-selected': selectedNodes.includes(node.id) }"
          ><input v-model="selectedNodes" type="checkbox" :value="node.id" :disabled="busy" />{{
            node.name
          }}</label
        >
      </div>
      <div class="entry-actions">
        <RouterLink :to="{ path: '/graph', query: { question: selected.id } }">图谱核查</RouterLink>
        <button class="secondary" type="button" :disabled="busy" @click="confirm">确认关联</button
        ><RouterLink class="primary" :to="{ path: '/qa', query: { question: selected.id } }"
          >就此答疑 ↗</RouterLink
        >
      </div>
      <p v-if="!selectedNodes.length" class="section-hint">可确认无关联，保留原始提问。</p>
      <div class="question-task-links">
        <template v-for="nodeId in selected.confirmed_node_ids" :key="nodeId"
          ><span>{{ nodes.find((n) => n.id === nodeId)?.name }}</span
          ><RouterLink :to="{ path: '/quiz', query: { node: nodeId } }">出题 ↗</RouterLink
          ><RouterLink :to="{ path: '/lessons', query: { node: nodeId } }"
            >备课 ↗</RouterLink
          ></template
        >
      </div>
    </article>
  </div>
</template>
