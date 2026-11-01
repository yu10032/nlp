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
      <label class="section-label" for="retrieval-question">同一个问题，核查两组课程依据</label>
      <textarea
        id="retrieval-question"
        v-model="text"
        rows="2"
        maxlength="4000"
        required
        :disabled="busy"
        placeholder="输入问题，先选定图谱增强的目标知识点…"
      ></textarea>
      <div class="experiment-actions">
        <MatchMethod v-model="method" :course-id="courseId" :disabled="busy" />
        <button type="button" class="secondary" :disabled="busy || !text.trim()" @click="suggest">
          建议知识点
        </button>
      </div>
      <fieldset class="retrieval-targets">
        <legend>图谱增强的目标</legend>
        <div class="node-choices">
          <label v-for="node in options" :key="node.id" class="check-label"
            ><input v-model="selected" type="checkbox" :value="node.id" :disabled="busy" />{{
              node.name
            }}</label
          >
        </div>
        <p v-if="!selected.length" class="footnote">未选目标时，两组使用相同的普通检索。</p>
      </fieldset>
      <div class="experiment-actions">
        <label class="budget-control"
          >每组最多
          <input
            v-model.number="budget"
            aria-label="每组证据预算"
            type="number"
            min="1"
            max="10"
            required
          />
          段</label
        >
        <button class="primary" :disabled="busy || !text.trim() || selected.length > 10">
          {{ busy ? '处理中…' : '运行并保存对照' }}
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
      <a :href="api.evidenceExportUrl(courseId, record.id)" download>导出记录 JSON</a>
      <p class="muted">
        图谱 v{{ record.snapshot.graph_version }} · 每组最多
        {{ record.snapshot.evidence_budget }} 段 · {{ record.snapshot.basic.retrieval_version }}
      </p>
      <p class="muted">目标：{{ record.snapshot.nodes.map((n) => n.name).join('、') || '无' }}</p>
      <details class="snapshot-materials">
        <summary>{{ record.snapshot.materials.length }} 份资料快照</summary>
        <p v-for="m in record.snapshot.materials" :key="m.id">{{ m.title }} · v{{ m.version }}</p>
      </details>
      <p v-if="record.is_stale" class="experiment-notice">
        课程图谱或资料已更新。以下为当时的证据快照，重跑会建立新记录。
      </p>
    </header>
    <p class="comparison-diff">
      共有 {{ record.snapshot.difference.shared.length }} 段 · 增强补入
      {{ record.snapshot.difference.added.length }} 段 · 移出
      {{ record.snapshot.difference.removed.length }} 段
    </p>
    <p class="footnote">
      增强组先为每个目标保留一份直接依据，再按词面相关性及已确认的一跳关系补齐；片段按 ID
      去重。数量差异不代表质量改善，请核查补入与移出的证据。
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
          <div class="source-rank">
            <span>〔{{ index + 1 }}〕 {{ difference(source.id) }}</span
            ><small class="muted">词面分数 {{ source.score?.toFixed(3) }}</small>
          </div>
          <blockquote>{{ source.text }}</blockquote>
          <p class="source-locator">
            {{ source.material_title }} · v{{ source.material_version }} · {{ source.locator }}
          </p>
          <div v-if="source.graph_paths?.length" class="graph-paths">
            <p v-for="(path, i) in source.graph_paths" :key="i">
              <template v-if="path.kind === 'direct'">{{ path.node_name }} → 直接依据</template
              ><template v-else
                >{{ path.via_node_name }} {{ path.via_node_id === path.edge_source_id ? '—' : '←' }}
                {{ relations[path.relation!] ?? path.relation }}
                {{ path.via_node_id === path.edge_source_id ? '→' : '—' }} {{ path.node_name }} →
                课程依据</template
              >
            </p>
          </div>
          <p v-else-if="difference(source.id) === '增强补入'" class="footnote">
            目标依据优先后，在固定预算内顺延补入
          </p>
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
          >增强后的整体效果<select
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
      <label for="comparison-note">改善或噪声案例</label
      ><textarea
        id="comparison-note"
        v-model="assessment.note"
        rows="3"
        maxlength="4000"
        placeholder="记录哪段补充了必要依据，或哪条关系带入了无关材料…"
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
