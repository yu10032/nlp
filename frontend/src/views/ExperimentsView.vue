<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import LossChart from '../components/LossChart.vue'
import RetrievalComparison from '../components/RetrievalComparison.vue'
import type { ExperimentReport, Graph, Ranking } from '../types'
const props = defineProps<{ courseId: string }>()
const route = useRoute()
const tab = ref(route.query.view === 'retrieval' ? 'retrieval' : 'matching')
const retrievalOpened = ref(tab.value === 'retrieval')
function openRetrieval() {
  tab.value = 'retrieval'
  retrievalOpened.value = true
}
const question = ref('没出现过的词组合为什么也要分配概率？')
const report = ref<ExperimentReport>()
const graph = ref<Graph>()
const results = ref<Ranking[]>([])
const loading = ref(false)
const error = ref('')
const errorMethod = ref('mlp')
const labels: Record<string, string> = {
  name: '名称与别名',
  tfidf: 'TF-IDF',
  embedding: '固定句向量',
  mlp: '自训 MLP',
}
const count = computed(() =>
  Object.values(report.value?.split ?? {}).reduce((sum, s) => sum + s.questions, 0),
)
const errors = computed(
  () => report.value?.evaluation?.errors.filter((e) => e.method === errorMethod.value) ?? [],
)
const percent = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)
const nodeName = (id: string) => graph.value?.nodes.find((n) => n.id === id)?.name ?? id
const nodeNames = (ids: string[]) => ids.map(nodeName).join('、') || '无关联'
async function run() {
  loading.value = true
  error.value = ''
  try {
    results.value = (await api.compareMatches(props.courseId, question.value)).results
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    loading.value = false
  }
}
onMounted(async () => {
  try {
    const [g, r] = await Promise.all([api.graph(props.courseId), api.experiment(props.courseId)])
    graph.value = g
    report.value = r
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>实验核查</h1>
      <span v-if="tab === 'matching' && report?.run" class="page-meta">{{
        report.run.run_id
      }}</span>
    </div>
    <span v-if="tab === 'matching' && report?.run" class="page-meta"
      >自动策略：{{ labels[report.state.active_method] }} · 按验证集选择</span
    >
  </div>
  <div class="experiment-tabs" role="tablist" aria-label="实验类型">
    <button
      id="matching-tab"
      role="tab"
      :aria-selected="tab === 'matching'"
      aria-controls="matching-panel"
      @click="tab = 'matching'"
    >
      模型匹配
    </button>
    <button
      id="retrieval-tab"
      role="tab"
      :aria-selected="tab === 'retrieval'"
      aria-controls="retrieval-panel"
      @click="openRetrieval"
    >
      证据检索
    </button>
  </div>
  <div
    id="retrieval-panel"
    v-show="tab === 'retrieval'"
    role="tabpanel"
    aria-labelledby="retrieval-tab"
  >
    <RetrievalComparison v-if="retrievalOpened" :course-id="courseId" />
  </div>
  <div
    id="matching-panel"
    v-show="tab === 'matching'"
    role="tabpanel"
    aria-labelledby="matching-tab"
  >
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="report?.run?.data_status === 'development'" class="experiment-notice">
      开发数据
      {{ count }} 条，标签由开发阶段手工拟定，尚未独立复核。下列结果用于检查训练和接入流程。
    </p>
    <p v-else-if="report?.state.scope_reason" class="experiment-notice">
      {{ report.state.scope_reason }}。可继续比较当前课程的词面基线。
    </p>
    <section class="experiment-input sheet">
      <form class="experiment-form" @submit.prevent="run">
        <label class="section-label" for="experiment-question">同一个问题，比较各模型</label
        ><textarea
          id="experiment-question"
          v-model="question"
          rows="2"
          maxlength="4000"
          required
          class="experiment-textarea"
        ></textarea>
        <div class="experiment-actions">
          <span class="muted">实时本地推理；实验输入不写入课堂提问</span
          ><button class="primary" :disabled="loading || !question.trim()">
            {{ loading ? '匹配中…' : '运行对照' }}
          </button>
        </div>
      </form>
      <div v-if="results.length" class="ranking-grid">
        <section v-for="result in results" :key="result.method" class="ranking-result">
          <div class="section-heading">
            <h2>{{ labels[result.method] }}</h2>
            <small class="muted">阈值 {{ result.threshold.toFixed(2) }}</small>
          </div>
          <p v-if="!result.matches.length" class="muted">没有达到阈值的关联</p>
          <div v-for="match in result.matches" :key="match.node_id" class="match-row">
            <RouterLink :to="{ path: '/graph', query: { node: match.node_id } }">{{
              match.name
            }}</RouterLink
            ><span>{{ match.score.toFixed(3) }}</span>
          </div>
          <p class="ranking-version">{{ result.version }}</p>
        </section>
      </div>
    </section>
    <template v-if="report?.run && report.evaluation">
      <div class="experiment-record">
        <section class="training-sheet sheet">
          <LossChart
            v-if="report.history"
            :history="report.history"
            :selected="report.run.selected_epoch"
          />
        </section>
        <aside class="run-record">
          <h2>实验范围</h2>
          <dl>
            <dt>编码器</dt>
            <dd>{{ report.run.encoder_id }} · 冻结</dd>
            <dt>数据版本</dt>
            <dd>{{ report.run.dataset_version }}</dd>
            <dt>课程图谱</dt>
            <dd>第 {{ report.run.graph_version }} 版</dd>
            <dt>划分</dt>
            <dd v-for="(split, key) in report.split" :key="key">
              {{ key }}：{{ split.questions }} 题 / {{ split.families.length }} 个家族
            </dd>
            <dt>候选召回</dt>
            <dd>
              Recall@{{ report.run.candidate_k }} =
              {{ percent(report.evaluation.candidate_recall.ratio) }}
            </dd>
            <dt>随机种子</dt>
            <dd>{{ report.run.seed }}</dd>
          </dl>
        </aside>
      </div>
      <div class="table-wrap sheet model-metrics">
        <table class="ledger-table">
          <caption>
            固定保留问题 · 多标签关联结果
          </caption>
          <thead>
            <tr>
              <th>方法</th>
              <th>精确率</th>
              <th>召回率</th>
              <th>Micro F1</th>
              <th>完全匹配</th>
              <th>无关联误挂率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(metric, method) in report.evaluation.methods" :key="method">
              <th>{{ labels[method] }}</th>
              <td>{{ percent(metric.micro_precision) }}</td>
              <td>{{ percent(metric.micro_recall) }}</td>
              <td>{{ percent(metric.micro_f1) }}</td>
              <td>{{ percent(metric.exact_match) }}</td>
              <td>{{ percent(metric.no_match_false_link_rate) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="footnote">
          每种方法最多返回 3 个知识点；MLP 在同一个句向量 Top
          {{ report.run.candidate_k }}
          候选集内重排。阈值由验证集确定。无关联误挂率仅统计测试集中无关联问题，数量为
          {{ report.evaluation.methods.mlp?.no_match_questions }} 条。
        </p>
      </div>
      <section class="error-cases sheet">
        <div class="section-heading">
          <h2>错误案例</h2>
          <label
            >方法<select v-model="errorMethod" aria-label="错误案例方法">
              <option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option>
            </select></label
          >
        </div>
        <p v-if="!errors.length" class="muted">当前保留问题中没有该方法的错误记录。</p>
        <article v-for="(item, index) in errors.slice(0, 12)" :key="index" class="error-case">
          <p>{{ item.question }}</p>
          <div><span>开发参考标签</span>{{ nodeNames(item.expected) }}</div>
          <div><span>模型关联</span>{{ nodeNames(item.predicted) }}</div>
        </article>
        <p v-if="errors.length > 12" class="footnote">
          展示前 12 / {{ errors.length }} 条，完整记录保存在该实验目录的 evaluation.json。
        </p>
      </section>
    </template>
  </div>
</template>
