<script setup lang="ts">
import PartLinks from './PartLinks.vue'
import type { DraftSummary, KnowledgeNode, LessonBody, RetrievalEvidence } from '../types'
const props = defineProps<{
  body: LessonBody
  nodes: KnowledgeNode[]
  evidence: RetrievalEvidence[]
  quizzes: DraftSummary[]
}>()
defineEmits<{ preview: [source: RetrievalEvidence] }>()
function move(index: number, delta: number) {
  const segments = props.body.segments
  ;[segments[index], segments[index + delta]] = [segments[index + delta]!, segments[index]!]
}
</script>
<template>
  <section v-for="(segment, index) in body.segments" :key="index" class="teaching-part lesson-part">
    <header class="part-heading">
      <span class="part-number">{{ String(index + 1).padStart(2, '0') }}</span>
      <label class="segment-time"
        ><input
          v-model.number="segment.minutes"
          type="number"
          min="1"
          max="240"
          :aria-label="`第${index + 1}段时长`"
        />
        分钟</label
      >
      <div class="part-remove part-order">
        <button
          class="text-button"
          type="button"
          :disabled="index === 0"
          :aria-label="`上移第${index + 1}段`"
          @click="move(index, -1)"
        >
          ↑</button
        ><button
          class="text-button"
          type="button"
          :disabled="index === body.segments.length - 1"
          :aria-label="`下移第${index + 1}段`"
          @click="move(index, 1)"
        >
          ↓</button
        ><button
          class="text-button"
          type="button"
          :disabled="body.segments.length === 1"
          :aria-label="`删除第${index + 1}段`"
          @click="body.segments.splice(index, 1)"
        >
          删除
        </button>
      </div>
    </header>
    <label class="editor-field"
      >课堂环节<input
        v-model="segment.title"
        maxlength="200"
        placeholder="例如：从相邻词预测引入 N 元语言模型"
    /></label>
    <label class="editor-field"
      >讲解内容<textarea v-model="segment.content" rows="4" maxlength="6000"></textarea>
    </label>
    <div class="paired-fields">
      <label class="editor-field"
        >课堂活动<textarea
          v-model="segment.activity"
          rows="2"
          maxlength="2000"
          placeholder="提问、讨论或随堂练习"
        ></textarea></label
      ><label class="editor-field"
        >例子建议<textarea v-model="segment.example" rows="2" maxlength="3000"></textarea>
      </label>
    </div>
    <details class="example-picker">
      <summary>
        关联题库例题<span v-if="segment.quiz_ids.length"> · {{ segment.quiz_ids.length }} 组</span>
      </summary>
      <label v-for="quiz in quizzes" :key="quiz.id" class="check-label"
        ><input v-model="segment.quiz_ids" type="checkbox" :value="quiz.id" />{{ quiz.title }} · v{{
          quiz.version
        }}</label
      >
      <p v-if="!quizzes.length" class="muted">题目审核通过后，可在这里选择。</p>
      <p v-if="segment.quiz_ids.some((id) => !quizzes.some((q) => q.id === id))" class="error">
        已关联例题失效，请移除后重新选择。<button
          class="text-button"
          type="button"
          @click="
            segment.quiz_ids = segment.quiz_ids.filter((id) => quizzes.some((q) => q.id === id))
          "
        >
          移除失效例题
        </button>
      </p>
    </details>
    <PartLinks
      :part="segment"
      :nodes="nodes"
      :evidence="evidence"
      :index="index"
      @preview="$emit('preview', $event)"
    />
  </section>
  <button
    class="secondary add-part"
    type="button"
    :disabled="body.segments.length >= 12"
    @click="
      body.segments.push({
        title: '',
        minutes: 5,
        content: '',
        activity: '',
        example: '',
        quiz_ids: [],
        node_ids: [],
        citation_ids: [],
      })
    "
  >
    ＋ 添加课堂环节
  </button>
</template>
