<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import AppIcon from '../components/AppIcon.vue'
import type { Graph, MatchResult, QuestionResult } from '../types'
const props = defineProps<{ courseId: string }>()
const question = ref('Transformer 为什么使用 attention？')
const graph = ref<Graph>()
const names = ref<MatchResult>()
const lexical = ref<QuestionResult>()
const loading = ref(false)
const error = ref('')
onMounted(async () => {
  try {
    graph.value = await api.graph(props.courseId)
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
async function run() {
  loading.value = true
  error.value = ''
  try {
    const result = await Promise.all([
      api.match(props.courseId, question.value),
      api.matchQuestion(props.courseId, question.value),
    ])
    names.value = result[0]
    lexical.value = result[1]
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    loading.value = false
  }
}
function nodeName(id: string) {
  return graph.value?.nodes.find((node) => node.id === id)?.name ?? id
}
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>模型实验</h1>
      <span class="page-meta">同输入词面基线对照</span>
    </div>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="experiment-layout">
    <section class="experiment-main sheet">
      <form class="experiment-form" @submit.prevent="run">
        <label class="section-label" for="experiment-question">实验输入问题</label>
        <textarea
          id="experiment-question"
          v-model="question"
          class="experiment-textarea"
          rows="3"
          required
          maxlength="4000"
        ></textarea>
        <div class="experiment-actions">
          <span class="why-note">在当前课程已确认知识点集合上执行同步推理</span>
          <button class="primary" :disabled="loading">
            {{ loading ? '匹配中…' : '运行对照' }}<AppIcon name="arrow" :size="15" />
          </button>
        </div>
      </form>

      <div v-if="names && lexical" class="result-columns">
        <div class="result-group">
          <div class="ink-section-head">
            <h2>名称与别名匹配</h2>
            <span>{{ names.method }}</span>
          </div>
          <p v-if="!names.matches.length" class="muted section-empty">没有名称或别名直接命中</p>
          <div v-for="match in names.matches" :key="match.node_id" class="match-row">
            <RouterLink :to="{ path: '/graph', query: { node: match.node_id } }">
              {{ match.name }}
            </RouterLink>
            <span>词面命中 {{ match.score.toFixed(1) }}</span>
          </div>
        </div>

        <div class="result-group">
          <div class="ink-section-head">
            <h2>TF-IDF 候选排序</h2>
            <span>{{ lexical.model_version }}</span>
          </div>
          <p v-if="!lexical.predictions.length" class="muted section-empty">
            没有达到开发阈值的候选节点
          </p>
          <div
            v-for="prediction in lexical.predictions"
            :key="prediction.node_id"
            class="match-row"
          >
            <RouterLink :to="{ path: '/graph', query: { node: prediction.node_id } }">
              {{ nodeName(prediction.node_id) }}
            </RouterLink>
            <span>得分 {{ prediction.score.toFixed(3) }}</span>
          </div>
        </div>
      </div>

      <p v-if="names && lexical" class="footnote">
        注：分数仅用于候选关联排序，不代表答案正确概率。当前对照为开发阶段基线，尚未接入正式评测结论。
      </p>
    </section>

    <aside class="experiment-status">
      <div class="margin-head">
        <h2>模型与权重状态</h2>
      </div>
      <div class="model-state is-ready">
        <strong>名称 / 别名基线</strong>
        <p>已接入 · name-baseline-v1</p>
      </div>
      <div class="model-state is-ready">
        <strong>TF-IDF 词面基线</strong>
        <p>已接入 · tfidf-bigram-v1</p>
      </div>
      <div class="model-state">
        <strong>固定句编码器</strong>
        <p>待配置与验证</p>
      </div>
      <div class="model-state">
        <strong>自训 MLP 匹配头</strong>
        <p>训练代码已就绪，正式权重尚未接入</p>
      </div>
    </aside>
  </div>
</template>
