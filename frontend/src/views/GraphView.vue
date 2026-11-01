<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import AppIcon from '../components/AppIcon.vue'
import GraphCanvas from '../components/GraphCanvas.vue'
import MatchMethod from '../components/MatchMethod.vue'
import SourceList from '../components/SourceList.vue'
import type {
  DocumentChunk,
  Graph,
  NodeDetail,
  NodeWrite,
  RetrievalEvidence,
  QuestionResult,
  NodeQuestions,
} from '../types'

const props = defineProps<{ courseId: string }>()
const route = useRoute()
const router = useRouter()
const graph = ref<Graph>()
const selected = ref<NodeDetail>()
const search = ref('')
const error = ref('')
const saving = ref(false)
const editing = ref(false)
const newNode = ref(false)
const edgeFormOpen = ref(false)
const sourceOptions = ref<(DocumentChunk & { material_title: string })[]>([])
const questionText = ref('')
const questionMethod = ref('auto')
const question = ref<QuestionResult>()
const questionBusy = ref(false)
const adjustingLinks = ref(false)
const questionSelection = ref<string[]>([])
const relatedQuestions = ref<NodeQuestions>()
const predictedIds = computed(() => question.value?.predictions.map((p) => p.node_id) ?? [])
const confirmedIds = computed(() => question.value?.confirmed_node_ids ?? [])
const linkOptions = computed(
  () => graph.value?.nodes.filter((n) => n.status === 'confirmed' && n.kind !== 'chapter') ?? [],
)

function applyQuestion(value: QuestionResult) {
  question.value = value
  questionText.value = value.text
  questionSelection.value = value.needs_review
    ? value.predictions.map((p) => p.node_id)
    : [...value.confirmed_node_ids]
  adjustingLinks.value = false
}
async function loadQuestion(id: string) {
  questionBusy.value = true
  error.value = ''
  try {
    applyQuestion(await api.question(props.courseId, id))
    const node = confirmedIds.value[0] ?? predictedIds.value[0]
    if (node) await selectNode(node)
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    questionBusy.value = false
  }
}
async function matchQuestion() {
  questionBusy.value = true
  error.value = ''
  try {
    applyQuestion(await api.matchQuestion(props.courseId, questionText.value, questionMethod.value))
    await router.replace({ query: { question: question.value!.id } })
    if (predictedIds.value[0]) await selectNode(predictedIds.value[0])
    else if (selected.value)
      relatedQuestions.value = await api.nodeQuestions(props.courseId, selected.value.id)
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    questionBusy.value = false
  }
}
async function confirmQuestion() {
  questionBusy.value = true
  error.value = ''
  try {
    applyQuestion(
      await api.confirmLinks(props.courseId, question.value!.id, questionSelection.value),
    )
    if (selected.value)
      relatedQuestions.value = await api.nodeQuestions(props.courseId, selected.value.id)
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    questionBusy.value = false
  }
}
watch(
  () => route.query.question,
  (id) => {
    if (typeof id === 'string' && id !== question.value?.id && graph.value) void loadQuestion(id)
  },
)
watch(
  () => route.query.node,
  (id) => {
    if (typeof id === 'string' && graph.value && !editing.value) void selectNode(id)
  },
)
const form = reactive<NodeWrite>({
  name: '',
  aliases: [],
  description: '',
  kind: 'concept',
  status: 'candidate',
  evidence_chunk_ids: [],
})
const aliasText = ref('')
const edgeForm = reactive({ target_id: '', relation: 'uses', chunk_id: '' })
const kinds: Record<string, string> = {
  concept: '概念',
  method: '方法',
  algorithm: '方法',
  model: '模型',
  task: '任务',
  metric: '评测',
  chapter: '章节',
}
const edgeStates: Record<string, string> = {
  confirmed: '已确认',
  candidate: '待确认',
  rejected: '已驳回',
}
const relations: Record<string, string> = {
  contains: '包含',
  uses: '使用',
  applies_to: '适用于',
  contrasts_with: '对比',
  prerequisite_of: '先修',
}

const nodes = computed(
  () =>
    graph.value?.nodes.filter((node) =>
      [node.name, ...node.aliases].some((name) =>
        name.toLowerCase().includes(search.value.toLowerCase()),
      ),
    ) ?? [],
)
const searchHighlights = computed(() =>
  search.value.trim() ? nodes.value.map((node) => node.id) : [],
)
const candidateCount = computed(() => {
  if (!graph.value) return 0
  const pendingNodes = graph.value.nodes.filter((n) => n.status === 'candidate').length
  const pendingEdges = graph.value.edges.filter((e) => e.status === 'candidate').length
  return pendingNodes + pendingEdges
})
const relatedEdges = computed(
  () =>
    graph.value?.edges.filter(
      (edge) => edge.source_id === selected.value?.id || edge.target_id === selected.value?.id,
    ) ?? [],
)
const evidence = computed<RetrievalEvidence[]>(
  () => selected.value?.evidence.map((item) => ({ ...item, section_path: [] })) ?? [],
)
let selectionRequest = 0

async function selectNode(id: string) {
  const request = ++selectionRequest
  error.value = ''
  editing.value = false
  edgeFormOpen.value = false
  relatedQuestions.value = undefined
  try {
    const [detail, questions] = await Promise.all([
      api.node(props.courseId, id),
      api.nodeQuestions(props.courseId, id),
    ])
    if (request === selectionRequest) {
      selected.value = detail
      relatedQuestions.value = questions
    }
  } catch (cause) {
    error.value = (cause as Error).message
  }
}
async function loadSources() {
  if (sourceOptions.value.length) return
  const documents = (await api.documents(props.courseId)).filter((doc) => doc.active)
  const chunks = await Promise.all(
    documents.map(async (doc) =>
      (await api.chunks(props.courseId, doc.id)).map((chunk) => ({
        ...chunk,
        material_title: doc.title,
      })),
    ),
  )
  sourceOptions.value = chunks.flat()
}
async function editNode(create = false) {
  error.value = ''
  newNode.value = create
  Object.assign(
    form,
    create
      ? {
          name: '',
          aliases: [],
          description: '',
          kind: 'concept',
          status: 'candidate',
          evidence_chunk_ids: typeof route.query.source === 'string' ? [route.query.source] : [],
        }
      : {
          ...selected.value,
          evidence_chunk_ids: selected.value?.evidence.map((item) => item.id) ?? [],
        },
  )
  aliasText.value = form.aliases.join('，')
  editing.value = true
  try {
    await loadSources()
  } catch (cause) {
    error.value = (cause as Error).message
  }
}
async function saveNode() {
  saving.value = true
  error.value = ''
  try {
    form.aliases = aliasText.value
      .split(/[,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
    const result = newNode.value
      ? await api.createNode(props.courseId, form)
      : await api.updateNode(props.courseId, selected.value!.id, form)
    graph.value = await api.graph(props.courseId)
    await selectNode(result.id)
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    saving.value = false
  }
}
async function saveEdge() {
  saving.value = true
  error.value = ''
  try {
    await api.createEdge(props.courseId, { source_id: selected.value!.id, ...edgeForm })
    graph.value = await api.graph(props.courseId)
    edgeFormOpen.value = false
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    saving.value = false
  }
}
async function review(edgeId: string, result: string) {
  saving.value = true
  error.value = ''
  try {
    await api.reviewEdge(props.courseId, edgeId, result)
    graph.value = await api.graph(props.courseId)
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    saving.value = false
  }
}
function nodeName(id: string) {
  return graph.value?.nodes.find((node) => node.id === id)?.name
}
onMounted(async () => {
  try {
    graph.value = await api.graph(props.courseId)
    if (typeof route.query.question === 'string') await loadQuestion(route.query.question)
    const id =
      typeof route.query.node === 'string'
        ? route.query.node
        : !question.value
          ? graph.value.nodes[0]?.id
          : undefined
    if (id) await selectNode(id)
    if (route.query.source) await editNode(true)
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>知识图谱</h1>
      <span v-if="graph" class="page-meta">
        {{ graph.nodes.length }} 个知识点<template v-if="candidateCount">
          · {{ candidateCount }} 项待确认</template
        >
        · 图谱 v{{ graph.version }}
      </span>
    </div>
    <button class="primary" type="button" @click="editNode(true)">
      <AppIcon name="plus" :size="15" />添加知识点
    </button>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="!graph && !error" class="loading-block" role="status">正在展卷读取图谱…</div>
  <div v-if="graph" class="graph-workbench">
    <section class="graph-main">
      <section class="graph-question sheet" aria-label="问题与图谱关联">
        <form @submit.prevent="matchQuestion">
          <label class="section-label" for="graph-question">把课堂问题放进知识脉络</label>
          <textarea
            id="graph-question"
            v-model="questionText"
            rows="2"
            maxlength="4000"
            required
            placeholder="输入学生的问题，定位可能涉及的知识点…"
          ></textarea>
          <div class="experiment-actions">
            <MatchMethod
              v-model="questionMethod"
              :course-id="courseId"
              :disabled="questionBusy || editing"
            />
            <button class="primary" :disabled="questionBusy || editing || !questionText.trim()">
              {{ questionBusy ? '处理中…' : '匹配并定位' }}
            </button>
          </div>
        </form>
        <div v-if="question" class="question-context">
          <p class="question-original">{{ question.text }}</p>
          <div class="question-associations">
            <span class="muted">原始建议</span>
            <span v-for="p in question.predictions" :key="p.node_id" class="tag predicted"
              >{{ nodeName(p.node_id) }} {{ p.score.toFixed(3) }}</span
            >
            <span v-if="!question.predictions.length" class="muted">未达到匹配阈值</span>
          </div>
          <div class="question-associations">
            <span class="muted">人工确认</span>
            <span v-if="question.needs_review" class="muted">尚未核查</span>
            <template v-else
              ><span v-for="id in confirmedIds" :key="id" class="tag confirmed">{{
                nodeName(id)
              }}</span
              ><span v-if="!confirmedIds.length">已确认无关联</span></template
            >
            <button
              class="text-button"
              type="button"
              :disabled="questionBusy || editing"
              @click="adjustingLinks = !adjustingLinks"
            >
              {{ adjustingLinks ? '收起调整' : '调整关联' }}
            </button>
          </div>
          <form v-if="adjustingLinks" class="question-link-form" @submit.prevent="confirmQuestion">
            <div class="node-checks">
              <label v-for="node in linkOptions" :key="node.id" class="check-label"
                ><input v-model="questionSelection" type="checkbox" :value="node.id" />{{
                  node.name
                }}</label
              >
            </div>
            <div class="entry-actions">
              <button class="secondary" :disabled="questionBusy || questionSelection.length > 10">
                确认关联</button
              ><button class="text-button" type="button" @click="questionSelection = []">
                清空选择
              </button>
            </div>
          </form>
          <div class="question-context-footer">
            <small class="muted"
              >{{ question.model_version }} · 预测时图谱 v{{ question.graph_version
              }}<template v-if="question.graph_version !== graph.version"
                >（当前 v{{ graph.version }}，需重新核查）</template
              ></small
            >
            <RouterLink :to="{ path: '/qa', query: { question: question.id } }"
              >就此答疑</RouterLink
            >
            <RouterLink
              :to="{ path: '/experiments', query: { view: 'retrieval', question: question.id } }"
              >检索对照</RouterLink
            >
          </div>
        </div>
      </section>
      <div class="graph-toolbar">
        <div class="search-field">
          <label class="sr-only" for="node-search">查找知识点</label>
          <input
            id="node-search"
            v-model="search"
            class="line-input"
            type="search"
            placeholder="搜索知识点或别名"
          />
        </div>
      </div>
      <div class="graph-surface sheet">
        <GraphCanvas
          v-if="graph.nodes.length"
          :key="graph.version"
          :graph="graph"
          :selected-id="selected?.id"
          :highlight-ids="searchHighlights"
          :predicted-ids="predictedIds"
          :confirmed-ids="confirmedIds"
          @select="selectNode"
        />
        <div v-else class="empty-state graph-empty">
          <h2>建立课程的知识脉络</h2>
          <p class="muted">从已上传的讲义资料定位段落，提炼并确认核心知识点。</p>
          <RouterLink to="/materials">前往课程资料添加知识点</RouterLink>
        </div>
        <div v-if="graph.nodes.length" class="node-strip">
          <button
            v-for="node in nodes"
            :key="node.id"
            type="button"
            class="node-tab"
            :class="{
              selected: selected?.id === node.id,
              candidate: node.status === 'candidate',
              'question-predicted': predictedIds.includes(node.id),
              'question-confirmed': confirmedIds.includes(node.id),
            }"
            @click="selectNode(node.id)"
          >
            {{ node.name }}
          </button>
          <p v-if="search && !nodes.length" class="muted">没有匹配的知识点</p>
        </div>
      </div>
    </section>

    <aside class="node-inspector sheet">
      <form v-if="editing" class="node-form" @submit.prevent="saveNode">
        <div class="inspector-heading">
          <h2>{{ newNode ? '新知识点词条' : '编辑知识点词条' }}</h2>
          <button class="icon-button" type="button" aria-label="取消编辑" @click="editing = false">
            <AppIcon name="close" :size="16" />
          </button>
        </div>
        <div class="field-group">
          <label for="node-name">名称</label>
          <input id="node-name" v-model="form.name" class="line-input" required maxlength="120" />
        </div>
        <div class="field-group">
          <label for="node-kind">类型</label>
          <select id="node-kind" v-model="form.kind">
            <option v-for="(label, key) in kinds" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <div class="field-group">
          <label for="node-aliases">别名</label>
          <input
            id="node-aliases"
            v-model="aliasText"
            class="line-input"
            placeholder="多个别名用逗号分隔"
          />
        </div>
        <div class="field-group">
          <label for="node-description">简要解释</label>
          <textarea id="node-description" v-model="form.description" rows="3"></textarea>
        </div>
        <div class="field-group">
          <label for="node-evidence">课程依据</label>
          <select id="node-evidence" v-model="form.evidence_chunk_ids" multiple size="4">
            <option v-for="chunk in sourceOptions" :key="chunk.id" :value="chunk.id">
              {{ chunk.material_title }} · {{ chunk.locator }} · {{ chunk.text.slice(0, 30) }}
            </option>
          </select>
        </div>
        <label class="check-label">
          <input
            type="checkbox"
            :checked="form.status === 'confirmed'"
            @change="
              form.status = ($event.target as HTMLInputElement).checked ? 'confirmed' : 'candidate'
            "
          />
          已核对知识点与来源
        </label>
        <button class="primary full-width" :disabled="saving">
          {{ saving ? '保存中…' : '保存知识点' }}
        </button>
      </form>

      <template v-else-if="selected">
        <div class="entry-kicker">
          <span>{{ kinds[selected.kind] ?? selected.kind }}</span>
          <span class="tag" :class="selected.status === 'confirmed' ? 'confirmed' : 'predicted'">
            {{ selected.status === 'confirmed' ? '已确认' : '待确认' }}
          </span>
        </div>
        <h2 class="entry-title">{{ selected.name }}</h2>
        <p v-if="selected.aliases.length" class="entry-alias">
          又称 {{ selected.aliases.join('、') }}
        </p>
        <p class="entry-def">{{ selected.description || '尚未填写简要解释。' }}</p>

        <div class="entry-actions">
          <RouterLink class="secondary" :to="{ path: '/qa', query: { node: selected.id } }">
            就此答疑
          </RouterLink>
          <RouterLink
            v-if="selected.status === 'confirmed' && selected.kind !== 'chapter'"
            class="text-button"
            :to="{ path: '/quiz', query: { node: selected.id } }"
            >出题</RouterLink
          >
          <RouterLink
            v-if="selected.status === 'confirmed' && selected.kind !== 'chapter'"
            class="text-button"
            :to="{ path: '/lessons', query: { node: selected.id } }"
            >备课</RouterLink
          >
          <button class="text-button" type="button" aria-label="编辑知识点" @click="editNode()">
            编辑词条
          </button>
        </div>

        <div class="entry-section">
          <div class="ink-section-head">
            <h3>课程依据</h3>
            <span>{{ evidence.length }} 段</span>
          </div>
          <SourceList v-if="evidence.length" :evidence="evidence" />
          <p v-else class="muted section-empty">尚未关联有效资料</p>
        </div>

        <div class="entry-section">
          <div class="ink-section-head">
            <h3>相关提问</h3>
            <span v-if="relatedQuestions">{{ relatedQuestions.total }} 条</span>
          </div>
          <div v-for="item in relatedQuestions?.items" :key="item.id" class="related-question">
            <button
              class="text-button"
              type="button"
              :disabled="questionBusy"
              @click="router.replace({ query: { question: item.id } })"
            >
              {{ item.text }}
            </button>
            <small :class="item.node_relation === 'confirmed' ? 'confirmed' : 'muted'">{{
              {
                confirmed: '人工确认',
                predicted: '模型建议 · 待核查',
                not_selected: '原建议 · 人工已改选',
              }[item.node_relation]
            }}</small>
          </div>
          <p v-if="relatedQuestions && !relatedQuestions.total" class="muted section-empty">
            还没有关联到这里的提问
          </p>
          <p v-if="relatedQuestions && relatedQuestions.total > 50" class="footnote">
            显示最近 50 条相关提问
          </p>
        </div>

        <div class="entry-section">
          <div class="ink-section-head">
            <h3>知识关系</h3>
            <button
              class="text-button"
              type="button"
              aria-label="添加关系"
              @click="edgeFormOpen = !edgeFormOpen"
            >
              {{ edgeFormOpen ? '收起' : '＋ 添加' }}
            </button>
          </div>
          <form v-if="edgeFormOpen" class="edge-form" @submit.prevent="saveEdge">
            <div class="field-group">
              <label for="edge-target">目标知识点</label>
              <select id="edge-target" v-model="edgeForm.target_id" required>
                <option value="" disabled>选择知识点</option>
                <option
                  v-for="node in graph.nodes.filter((item) => item.id !== selected!.id)"
                  :key="node.id"
                  :value="node.id"
                >
                  {{ node.name }}
                </option>
              </select>
            </div>
            <div class="field-group">
              <label for="edge-relation">关系</label>
              <select id="edge-relation" v-model="edgeForm.relation">
                <option v-for="(label, key) in relations" :key="key" :value="key">
                  {{ label }}
                </option>
              </select>
            </div>
            <div class="field-group">
              <label for="edge-source">依据</label>
              <select id="edge-source" v-model="edgeForm.chunk_id" required>
                <option value="" disabled>选择来源片段</option>
                <option v-for="source in selected.evidence" :key="source.id" :value="source.id">
                  {{ source.material_title }} · {{ source.locator }}
                </option>
              </select>
            </div>
            <button class="primary" :disabled="saving">保存候选关系</button>
          </form>

          <div v-for="edge in relatedEdges" :key="edge.id" class="edge-row">
            <p class="edge-phrase">
              <span>{{ nodeName(edge.source_id) }}</span>
              <em>{{ relations[edge.relation] }}</em>
              <span>{{ nodeName(edge.target_id) }}</span>
            </p>
            <div class="edge-ops">
              <span
                class="tag"
                :class="
                  edge.status === 'confirmed'
                    ? 'confirmed'
                    : edge.status === 'rejected'
                      ? 'expired'
                      : 'predicted'
                "
              >
                {{ edgeStates[edge.status] }}
              </span>
              <template v-if="edge.status === 'candidate'">
                <button
                  class="text-button"
                  type="button"
                  :disabled="saving"
                  @click="review(edge.id, 'confirmed')"
                >
                  确认
                </button>
                <button
                  class="text-button"
                  type="button"
                  :disabled="saving"
                  @click="review(edge.id, 'rejected')"
                >
                  驳回
                </button>
              </template>
            </div>
          </div>
          <p v-if="!relatedEdges.length && !edgeFormOpen" class="muted section-empty">
            暂无关联关系
          </p>
        </div>
      </template>

      <div v-else class="empty-state">
        <h2>选择一个知识点</h2>
        <p class="muted">点击左侧图谱词条查看课程依据与关系。</p>
      </div>
    </aside>
  </div>
</template>
