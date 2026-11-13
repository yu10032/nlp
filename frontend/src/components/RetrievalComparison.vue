<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { api } from '../api'
import MatchMethod from './MatchMethod.vue'
import SourceReader from './SourceReader.vue'
import type {
  ComparisonSummary,
  Graph,
  RetrievalAssessment,
  RetrievalComparison,
  RetrievalEvidence,
} from '../types'

const props = defineProps<{ courseId: string }>()
const route = useRoute()
const graph = ref<Graph>()
const text = ref('')
const context = ref<{ id: string; text: string }>()
const method = ref('auto')
const selected = ref<string[]>([])
const budget = ref(5)
const record = ref<RetrievalComparison>()
const history = ref<ComparisonSummary[]>([])
const preview = ref<RetrievalEvidence>()
const busy = ref(true)
const error = ref('')
const message = ref('')
const assessment = reactive<RetrievalAssessment>({
  reviewer: '教师',
  relevance: {},
  outcome: 'uncertain',
  note: '',
})
const savedAssessment = ref('')
const dirty = computed(() => !!record.value && JSON.stringify(assessment) !== savedAssessment.value)
const options = computed(
  () => graph.value?.nodes.filter((n) => n.status === 'confirmed' && n.kind !== 'chapter') ?? [],
)
const plans = computed(() =>
  record.value
    ? [
        { key: 'basic', title: '普通检索', result: record.value.snapshot.basic },
        {
          key: 'graph_augmented',
          title: '图谱增强',
          result: record.value.snapshot.graph_augmented,
        },
      ]
    : [],
)
const relations: Record<string, string> = {
  contains: '包含',
  uses: '使用',
  applies_to: '适用于',
  contrasts_with: '对比',
  prerequisite_of: '先修',
}
function mayDiscard() {
  return !dirty.value || window.confirm('评价有未保存的修改，仍要切换吗？')
}
onBeforeRouteLeave(() => !busy.value && mayDiscard())
function apply(value: RetrievalComparison) {
  record.value = value
  preview.value = undefined
  Object.assign(assessment, {
    reviewer: value.assessment.reviewer ?? '教师',
    relevance: { ...value.assessment.relevance },
    outcome: value.assessment.outcome ?? 'uncertain',
    note: value.assessment.note ?? '',
  })
  savedAssessment.value = JSON.stringify(assessment)
}
async function suggest() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    selected.value = (await api.match(props.courseId, text.value, method.value)).matches.map(
      (m) => m.node_id,
    )
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
async function run() {
  if (!mayDiscard()) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    apply(
      await api.compareEvidence(props.courseId, {
        question_text: text.value,
        node_ids: selected.value,
        evidence_budget: budget.value,
        question_id: context.value?.text === text.value.trim() ? context.value.id : undefined,
      }),
    )
    history.value = await api.evidenceComparisons(props.courseId)
    message.value = '对照已保存，可逐段核查相关性'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
async function load(event: Event) {
  const input = event.target as HTMLSelectElement
  const id = input.value
  if (!id || !mayDiscard()) {
    input.value = record.value?.id ?? ''
    return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    apply(await api.evidenceComparison(props.courseId, id))
    text.value = record.value!.question_text
    selected.value = record
      .value!.snapshot.nodes.map((n) => n.id)
      .filter((id) => options.value.some((n) => n.id === id))
    budget.value = record.value!.snapshot.evidence_budget
    const q = record.value!.snapshot.question_context
    context.value = q ? { id: q.id, text: text.value } : undefined
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
async function save() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api.assessEvidence(props.courseId, record.value!.id, assessment)
    record.value = result
    savedAssessment.value = JSON.stringify(assessment)
    message.value = '人工评价已保存'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
function difference(id: string) {
  const d = record.value!.snapshot.difference
  return d.added.includes(id) ? '增强补入' : d.removed.includes(id) ? '增强移出' : '两组共有'
}
onMounted(async () => {
  try {
    const [g, h] = await Promise.all([
      api.graph(props.courseId),
      api.evidenceComparisons(props.courseId),
    ])
    graph.value = g
    history.value = h
    if (typeof route.query.question === 'string') {
      const q = await api.question(props.courseId, route.query.question)
      text.value = q.text
      context.value = { id: q.id, text: q.text }
      selected.value = (
        q.needs_review ? q.predictions.map((p) => p.node_id) : q.confirmed_node_ids
      ).filter((id) => options.value.some((n) => n.id === id))
    }
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
})
</script>
<template>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="message" class="status-message" role="status">{{ message }}</p>
  <section class="experiment-input sheet">
    <form class="retrieval-form" @submit.prevent="run">
      <label class="section-label" for="retrieval-question">测试问题</label>
      <textarea
        id="retrieval-question"
        v-model="text"
        rows="2"
        maxlength="4000"
        required
        :disabled="busy"
        placeholder="输入想比较的问题…"
      ></textarea>
      <div class="experiment-actions">
        <details class="inline-settings">
          <summary>检索设置</summary>
          <div class="settings-body">
            <MatchMethod v-model="method" :course-id="courseId" :disabled="busy" />
            <label class="budget-control"
              >每组依据<input
                v-model.number="budget"
                aria-label="每组证据预算"
                type="number"
                min="1"
                max="10"
                required
              />段</label
            >
          </div>
        </details>
        <button type="button" class="secondary" :disabled="busy || !text.trim()" @click="suggest">
          建议知识点
        </button>
      </div>
      <fieldset class="retrieval-targets">
        <legend>关联知识点</legend>
        <div class="node-choices">
          <label v-for="node in options" :key="node.id" class="check-label"
            ><input v-model="selected" type="checkbox" :value="node.id" :disabled="busy" />{{
              node.name
            }}</label
          >
        </div>
        <p v-if="!selected.length" class="section-hint">未选知识点，两组将使用相同检索。</p>
      </fieldset>
      <div class="experiment-actions">
        <button class="primary" :disabled="busy || !text.trim() || selected.length > 10">
          {{ busy ? '处理中…' : '运行对照' }}
        </button>
      </div>
    </form>
  </section>
  <div class="comparison-history">
    <label for="comparison-history">历史对照</label
    ><select id="comparison-history" :value="record?.id ?? ''" :disabled="busy" @change="load">
      <option value="" disabled>选择已保存的记录</option>
      <option v-for="item in history" :key="item.id" :value="item.id">
        {{ new Date(item.created_at).toLocaleString('zh-CN') }} ·
        {{ item.question_text.slice(0, 48) }}
      </option>
    </select>
  </div>
  <section v-if="record" class="comparison-record" aria-label="检索对照结果">
    <header class="comparison-head">
      <h2>{{ record.question_text }}</h2>
      <a :href="api.evidenceExportUrl(courseId, record.id)" download>导出记录</a>
      <details class="context-details comparison-context">
        <summary>对照信息</summary>
        <p>
          图谱 v{{ record.snapshot.graph_version }} · 每组最多
          {{ record.snapshot.evidence_budget }} 段 · {{ record.snapshot.basic.retrieval_version }}
        </p>
        <p>知识点：{{ record.snapshot.nodes.map((n) => n.name).join('、') || '无' }}</p>
        <div class="snapshot-materials">
          <p v-for="m in record.snapshot.materials" :key="m.id">{{ m.title }} · v{{ m.version }}</p>
        </div>
        <p>
          增强检索优先保留目标知识点的直接依据，再补充已确认的一跳关系；数量变化不代表质量改善。
        </p>
      </details>
      <p v-if="record.is_stale" class="experiment-notice">资料或图谱已更新，当前显示历史快照。</p>
    </header>
    <p class="comparison-diff">
      共有 {{ record.snapshot.difference.shared.length }} 段 · 增强补入
      {{ record.snapshot.difference.added.length }} 段 · 移出
      {{ record.snapshot.difference.removed.length }} 段
    </p>
    <div class="evidence-columns">
      <section
        v-for="plan in plans"
        :key="plan.key"
        class="evidence-plan sheet"
        :aria-label="plan.title"
      >
        <div class="section-heading">
          <h3>{{ plan.title }}</h3>
          <span class="muted">{{ plan.result.evidence.length }} 段</span>
        </div>
        <p v-if="!plan.result.evidence.length" class="muted section-empty">没有检索到课程依据</p>
        <article
          v-for="(source, index) in plan.result.evidence"
          :key="source.id"
          class="comparison-source"
        >
          <div class="source-rank" :title="`词面分数 ${source.score?.toFixed(3)}`">
            <span
              >〔{{ index + 1 }}〕<template v-if="difference(source.id) !== '两组共有'">
                {{ difference(source.id) }}</template
              ></span
            >
          </div>
          <blockquote>{{ source.text }}</blockquote>
          <p class="source-locator">
            {{ source.material_title }} · v{{ source.material_version }} · {{ source.locator }}
          </p>
          <details v-if="source.graph_paths?.length" class="context-details graph-paths">
            <summary>增强路径</summary>
            <p v-for="(path, i) in source.graph_paths" :key="i">
              <template v-if="path.kind === 'direct'">{{ path.node_name }} → 直接依据</template
              ><template v-else
                >{{ path.via_node_name }} {{ path.via_node_id === path.edge_source_id ? '—' : '←' }}
                {{ relations[path.relation!] ?? path.relation }}
                {{ path.via_node_id === path.edge_source_id ? '→' : '—' }} {{ path.node_name }} →
                课程依据</template
              >
            </p>
          </details>
          <div class="source-assessment">
            <button class="text-button" type="button" @click="preview = source">查看原文</button
            ><label
              >相关性<select
                v-model="assessment.relevance[source.id]"
                :aria-label="`${plan.title}第${index + 1}段相关性`"
                :disabled="busy"
              >
                <option :value="undefined">待评价</option>
                <option value="relevant">相关</option>
                <option value="irrelevant">无关</option>
                <option value="uncertain">待判断</option>
              </select></label
            >
          </div>
        </article>
      </section>
    </div>
    <SourceReader
      v-if="preview"
      :key="preview.id"
      :course-id="courseId"
      :source="preview"
      @close="preview = undefined"
    />
    <form class="comparison-review sheet" @submit.prevent="save">
      <h3>人工核查</h3>
      <div class="comparison-review-controls">
        <label
          >评价人<input
            v-model="assessment.reviewer"
            required
            maxlength="80"
            :disabled="busy" /></label
        ><label
          >整体效果<select
            v-model="assessment.outcome"
            aria-label="增强后的整体效果"
            :disabled="busy"
          >
            <option value="uncertain">待判断</option>
            <option value="better">更好</option>
            <option value="worse">更差</option>
            <option value="mixed">有改善也有噪声</option>
            <option value="same">无明显变化</option>
          </select></label
        >
      </div>
      <label for="comparison-note">评价备注</label
      ><textarea
        id="comparison-note"
        v-model="assessment.note"
        rows="3"
        maxlength="4000"
        placeholder="哪些依据有帮助，哪些带来了噪声？"
        :disabled="busy"
      ></textarea>
      <div class="experiment-actions">
        <span class="muted">{{
          dirty ? '评价尚未保存' : record.assessment.updated_at ? '人工评价已保存' : '尚未人工评价'
        }}</span
        ><button class="secondary" :disabled="busy || !dirty">保存人工评价</button>
      </div>
    </form>
  </section>
</template>
