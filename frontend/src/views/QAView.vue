<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import { api } from '../api'
import AppIcon from '../components/AppIcon.vue'
import MatchMethod from '../components/MatchMethod.vue'
import SourceList from '../components/SourceList.vue'
import SourceReader from '../components/SourceReader.vue'
import type {
  Draft,
  DraftSummary,
  Graph,
  Health,
  QuestionResult,
  RetrievalEvidence,
} from '../types'

const props = defineProps<{ courseId: string }>()
const route = useRoute()
const graph = ref<Graph>()
const health = ref<Health>()
const history = ref<DraftSummary[]>([])
const historyMenu = ref<HTMLDetailsElement>()
const questionText = ref('')
const matchMethod = ref('auto')
const matchedMethod = ref('auto')
const question = ref<QuestionResult>()
const selectedNodes = ref<string[]>([])
const citationIds = ref<string[]>([])
const evidence = ref<RetrievalEvidence[]>([])
const sourcePreview = ref<RetrievalEvidence>()
const graphMode = ref(false)
const answer = ref('')
const draft = ref<Draft>()
const reviewer = ref('教师')
const busy = ref('')
const error = ref('')
const message = ref('')
const searched = ref(false)
const states: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审核',
  approved: '已审核',
  rejected: '已退回',
  stale_review: '待重新审核',
}
const questionChanged = computed(
  () =>
    question.value &&
    (question.value.text !== questionText.value.trim() ||
      matchedMethod.value !== matchMethod.value),
)
const dirty = computed(
  () =>
    !draft.value ||
    answer.value !== draft.value.answer ||
    JSON.stringify(selectedNodes.value) !== JSON.stringify(draft.value.node_ids) ||
    JSON.stringify(citationIds.value) !== JSON.stringify(draft.value.citation_ids),
)
const confirmedNodes = computed(
  () =>
    graph.value?.nodes.filter((node) => node.status === 'confirmed' && node.kind !== 'chapter') ??
    [],
)
const generationReady = computed(() => health.value?.generation.available === true)
const selectedNodeNames = computed(() =>
  confirmedNodes.value
    .filter((node) => selectedNodes.value.includes(node.id))
    .map((node) => node.name)
    .join('、'),
)
const generationBlockReason = computed(() => {
  if (!question.value) return '先查找依据'
  if (questionChanged.value) return '重新查找依据后可生成'
  if (!generationReady.value) return '生成服务未配置，可手动编写'
  if (!evidence.value.length) return '没有可用依据，可手动编写'
  return ''
})
const reviewBlockReason = computed(() => {
  if (!question.value || (draft.value?.status === 'approved' && !dirty.value)) return ''
  if (questionChanged.value) return '请重新查找依据'
  if (!answer.value.trim()) return '填写答复后可审核'
  if (!citationIds.value.length) return '至少引用一条课程依据'
  if (!reviewer.value.trim()) return '请填写审核人'
  return ''
})
onBeforeRouteLeave(() => {
  if (dirty.value && (draft.value || answer.value.trim()))
    return window.confirm('答疑有未保存的修改，仍要离开吗？')
})

function predictionScore(nodeId: string) {
  return question.value?.predictions.find((item) => item.node_id === nodeId)?.score
}

function toggle(ids: string[], id: string) {
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]
}

async function findEvidence() {
  sourcePreview.value = undefined
  busy.value = 'retrieval'
  error.value = ''
  message.value = ''
  try {
    if (!question.value || questionChanged.value) {
      question.value = await api.matchQuestion(
        props.courseId,
        questionText.value,
        matchMethod.value,
      )
      matchedMethod.value = matchMethod.value
      draft.value = undefined
      answer.value = ''
      if (!selectedNodes.value.length)
        selectedNodes.value = question.value.predictions.map((item) => item.node_id)
    }
    const result = await api.retrieve(
      props.courseId,
      questionText.value,
      selectedNodes.value,
      graphMode.value ? 'graph_augmented' : 'basic',
    )
    evidence.value = result.evidence
    citationIds.value = result.evidence.map((item) => item.id)
    searched.value = true
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = ''
  }
}

async function confirmNodes() {
  if (!question.value) return
  busy.value = 'links'
  error.value = ''
  try {
    question.value = await api.confirmLinks(props.courseId, question.value.id, selectedNodes.value)
    message.value = '知识点关联已确认'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = ''
  }
}

function applyDraft(value: Draft) {
  draft.value = value
  answer.value = value.answer
  selectedNodes.value = [...value.node_ids]
  citationIds.value = [...value.citation_ids]
  evidence.value = [
    ...new Map(
      [...evidence.value, ...value.citations].map((source) => [source.id, source]),
    ).values(),
  ]
}
async function save(generate = false) {
  const payload = {
    title: questionText.value.trim().slice(0, 200),
    answer: answer.value,
    node_ids: selectedNodes.value,
    citation_ids: citationIds.value,
  }
  const result =
    !draft.value || generate
      ? await api.createDraft(props.courseId, {
          ...payload,
          question_id: question.value!.id,
          generate,
          retrieval_mode: graphMode.value ? 'graph_augmented' : 'basic',
        })
      : await api.updateDraft(props.courseId, draft.value.id, {
          ...payload,
          expected_version: draft.value.version,
        })
  applyDraft(result)
  history.value = await api.drafts(props.courseId)
  return result
}
async function saveDraft(generate = false) {
  busy.value = generate ? 'generation' : 'saving'
  error.value = ''
  message.value = ''
  try {
    await save(generate)
    message.value = generate ? '答疑草稿已生成，请核查正文与引用' : '草稿已保存'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = ''
  }
}
async function review(result: string) {
  busy.value = 'review'
  error.value = ''
  message.value = ''
  try {
    const saved = dirty.value ? await save() : draft.value!
    applyDraft(
      await api.reviewDraft(props.courseId, saved.id, saved.version, result, reviewer.value),
    )
    history.value = await api.drafts(props.courseId)
    message.value = result === 'approved' ? '当前版本已审核，可导出' : '已退回修改'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = ''
  }
}
async function openDraft(id: string) {
  sourcePreview.value = undefined
  busy.value = 'opening'
  error.value = ''
  message.value = ''
  try {
    const value = await api.draft(props.courseId, id)
    question.value = await api.question(props.courseId, value.question_id)
    questionText.value = value.question_text
    evidence.value = value.citations
    searched.value = true
    applyDraft(value)
    historyMenu.value!.open = false
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = ''
  }
}
function fresh() {
  sourcePreview.value = undefined
  questionText.value = ''
  question.value = undefined
  draft.value = undefined
  answer.value = ''
  selectedNodes.value = []
  citationIds.value = []
  evidence.value = []
  searched.value = false
  message.value = ''
  error.value = ''
}
onMounted(async () => {
  try {
    const result = await Promise.all([
      api.graph(props.courseId),
      api.health(),
      api.drafts(props.courseId),
    ])
    graph.value = result[0]
    health.value = result[1]
    history.value = result[2]
    if (typeof route.query.node === 'string') selectedNodes.value = [route.query.node]
    if (typeof route.query.question === 'string') {
      question.value = await api.question(props.courseId, route.query.question)
      questionText.value = question.value.text
      selectedNodes.value = question.value.needs_review
        ? question.value.predictions.map((p) => p.node_id)
        : question.value.confirmed_node_ids
      await findEvidence()
    }
    if (typeof route.query.draft === 'string') await openDraft(route.query.draft)
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>课程答疑</h1>
      <span
        v-if="draft || answer.trim()"
        class="document-state"
        :class="{
          'is-approved': draft?.status === 'approved' && !dirty,
          'is-stale': draft?.status === 'stale_review' && !dirty,
        }"
        >{{ dirty ? '未保存' : states[draft!.status] }}</span
      >
    </div>
    <div class="heading-actions">
      <details ref="historyMenu" class="history-menu">
        <summary>历史 · {{ history.length }}</summary>
        <div class="history-options sheet">
          <button
            v-for="item in history"
            :key="item.id"
            type="button"
            :aria-label="`${item.title}，${states[item.status]}`"
            @click="openDraft(item.id)"
          >
            <strong>{{ item.title }}</strong>
            <small>{{ states[item.status] }} · 第 {{ item.version }} 版</small>
          </button>
          <p v-if="!history.length" class="muted">还没有保存的答疑</p>
        </div>
      </details>
      <button class="secondary" type="button" :disabled="!!busy" @click="fresh">
        <AppIcon name="plus" :size="15" />新答疑
      </button>
    </div>
  </div>

  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="message" class="success-message" role="status">{{ message }}</p>

  <div class="qa-layout">
    <article class="qa-main sheet">
      <form class="question-form qa-question" @submit.prevent="findEvidence">
        <h2>教学问题</h2>
        <label class="sr-only" for="teaching-question">教学问题</label>
        <div class="question-input-wrap">
          <textarea
            id="teaching-question"
            v-model="questionText"
            rows="2"
            maxlength="4000"
            required
            placeholder="输入想讨论的问题…"
          ></textarea>
        </div>
        <div class="question-actions">
          <details class="inline-settings">
            <summary>检索设置</summary>
            <div class="settings-body">
              <MatchMethod v-model="matchMethod" :course-id="courseId" :disabled="!!busy" />
              <label class="check-label">
                <input v-model="graphMode" type="checkbox" :disabled="!!busy" />
                图谱增强检索
              </label>
            </div>
          </details>
          <button
            :class="!question || questionChanged ? 'primary' : 'secondary'"
            :disabled="!!busy || !questionText.trim()"
          >
            <AppIcon name="search" :size="15" />
            {{ busy === 'retrieval' ? '检索中…' : '查找依据' }}
          </button>
        </div>
      </form>

      <details
        v-if="question"
        class="question-nodes knowledge-details task-section"
        :open="question.needs_review"
      >
        <summary>
          <span class="section-title">关联知识点</span>
          <span class="selection-summary">{{ selectedNodeNames || '无关联' }}</span>
          <span v-if="question.needs_review" class="tag predicted">待确认</span>
        </summary>
        <div class="knowledge-body">
          <div class="node-choices">
            <label
              v-for="node in confirmedNodes"
              :key="node.id"
              class="node-tag"
              :title="
                predictionScore(node.id) === undefined
                  ? undefined
                  : `模型建议 ${predictionScore(node.id)!.toFixed(2)}`
              "
              :class="{
                'is-selected': selectedNodes.includes(node.id),
                'is-predicted': question.needs_review && predictionScore(node.id) !== undefined,
              }"
            >
              <input
                type="checkbox"
                :checked="selectedNodes.includes(node.id)"
                :disabled="!!busy"
                @change="selectedNodes = toggle(selectedNodes, node.id)"
              />
              <span>{{ node.name }}</span>
            </label>
          </div>
          <div class="knowledge-actions">
            <details class="context-details">
              <summary>匹配详情</summary>
              <p>{{ question.model_version }} · 图谱 v{{ question.graph_version }}</p>
              <p v-for="prediction in question.predictions" :key="prediction.node_id">
                {{ graph?.nodes.find((node) => node.id === prediction.node_id)?.name }} ·
                {{ prediction.score.toFixed(2) }}
              </p>
            </details>
            <div class="section-actions">
              <RouterLink :to="{ path: '/graph', query: { question: question.id } }">
                图谱核查
              </RouterLink>
              <button
                class="text-button"
                type="button"
                :disabled="!!busy || !!questionChanged"
                @click="confirmNodes"
              >
                {{ question.needs_review ? '确认关联' : '更新关联' }}
              </button>
            </div>
          </div>
          <p v-if="!question.predictions.length && question.needs_review" class="section-hint">
            未匹配到知识点，可手动选择或确认无关联。
          </p>
        </div>
      </details>

      <section
        v-if="question"
        class="answer-workspace task-section"
        aria-labelledby="answer-heading"
      >
        <div class="task-heading">
          <h2 id="answer-heading">答复</h2>
          <button
            :class="!answer.trim() && !questionChanged ? 'primary' : 'text-button'"
            class="generate-answer"
            type="button"
            :disabled="
              !!busy || !question || !!questionChanged || !generationReady || !evidence.length
            "
            @click="saveDraft(true)"
          >
            {{ busy === 'generation' ? '正在生成…' : answer.trim() ? '重新生成' : '生成答复' }}
          </button>
        </div>
        <p v-if="generationBlockReason && !questionChanged" class="section-hint">
          {{ generationBlockReason }}
        </p>
        <p v-if="questionChanged" class="notice">问题已修改，请重新查找依据。</p>

        <label class="sr-only" for="answer">答疑正文</label>
        <textarea
          id="answer"
          v-model="answer"
          class="answer-editor"
          rows="8"
          placeholder="写下答复，或根据课程依据生成…"
        ></textarea>

        <div class="draft-foot">
          <span>{{ answer.length }} 字</span>
          <span>{{ citationIds.length }} 条引用</span>
        </div>
      </section>

      <details v-if="draft" class="revision-history">
        <summary>版本与审核记录</summary>
        <div
          v-for="record in draft.reviews"
          :key="`${record.revision}-${record.created_at}`"
          class="audit-line"
        >
          <span>v{{ record.revision }} · {{ record.reviewer }} · {{ states[record.result] }}</span>
          <time>{{ new Date(record.created_at).toLocaleString('zh-CN') }}</time>
        </div>
        <details v-for="revision in draft.revisions" :key="revision.version" class="revision-item">
          <summary>v{{ revision.version }} · {{ revision.snapshot.title }}</summary>
          <p class="revision-prose">{{ revision.snapshot.answer || '空草稿' }}</p>
        </details>
      </details>

      <section v-if="question" class="review-bar" aria-label="保存与审核">
        <div class="review-controls">
          <div class="reviewer-field">
            <label for="reviewer">审核人</label>
            <input id="reviewer" v-model="reviewer" class="line-input" maxlength="80" />
          </div>

          <div class="review-actions">
            <a
              v-if="draft?.status === 'approved' && !dirty"
              class="primary"
              :href="api.exportUrl(courseId, draft.id)"
            >
              <AppIcon name="download" :size="14" />导出
            </a>
            <details v-if="draft" class="review-more">
              <summary>更多</summary>
              <button
                class="text-button"
                type="button"
                :disabled="!!busy || !!questionChanged"
                @click="review('rejected')"
              >
                退回修改
              </button>
            </details>
            <button
              :class="dirty && answer.trim() ? 'primary' : 'secondary'"
              type="button"
              :disabled="!!busy || !!questionChanged || !dirty"
              @click="saveDraft()"
            >
              {{ busy === 'saving' ? '保存中…' : '保存草稿' }}
            </button>
            <button
              v-if="draft?.status !== 'approved' || dirty"
              class="review-btn"
              type="button"
              :disabled="
                !!busy ||
                !answer.trim() ||
                !citationIds.length ||
                !reviewer.trim() ||
                !!questionChanged ||
                (draft?.status === 'approved' && !dirty)
              "
              @click="review('approved')"
            >
              {{ busy === 'review' ? '审核中…' : '审核通过' }}
            </button>
          </div>
        </div>
        <p v-if="reviewBlockReason && !questionChanged" class="review-requirement" role="status">
          {{ reviewBlockReason }}
        </p>
      </section>
    </article>

    <aside class="qa-evidence">
      <SourceReader
        v-if="sourcePreview"
        :course-id="courseId"
        :source="sourcePreview"
        @close="sourcePreview = undefined"
      />
      <template v-else>
        <div class="margin-head">
          <h2>课程依据</h2>
          <span v-if="evidence.length"
            >{{ citationIds.length }} / {{ evidence.length }} 已引用</span
          >
        </div>
        <SourceList
          v-if="evidence.length"
          :evidence="evidence"
          :selected="citationIds"
          selectable
          inline-preview
          @toggle="(id) => (citationIds = toggle(citationIds, id))"
          @preview="(source) => (sourcePreview = source)"
        />
        <div v-else class="evidence-empty">
          <p>
            {{ searched ? '未找到依据，试试调整问题或补充资料。' : '查找后在这里核对课程原文。' }}
          </p>
          <RouterLink v-if="searched" to="/materials">前往补充资料</RouterLink>
        </div>
      </template>
    </aside>
  </div>
</template>
