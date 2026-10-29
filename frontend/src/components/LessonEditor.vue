<script setup lang="ts">
import PartLinks from './PartLinks.vue'
import { ref } from 'vue'
import type {
  DraftSummary,
  KnowledgeNode,
  LessonBody,
  LessonSegment,
  RetrievalEvidence,
} from '../types'
const props = defineProps<{
  body: LessonBody
  nodes: KnowledgeNode[]
  evidence: RetrievalEvidence[]
  quizzes: DraftSummary[]
  canGenerate: boolean
}>()
defineEmits<{
  preview: [source: RetrievalEvidence]
  generate: [segment: LessonSegment, instruction: string]
}>()
const instructions = ref<Record<string, string>>({})
const newId = () => crypto.randomUUID()
function move(index: number, delta: number) {
  const segments = props.body.segments
  ;[segments[index], segments[index + delta]] = [segments[index + delta]!, segments[index]!]
}
</script>
<template>
  <section
    v-for="(segment, index) in body.segments"
    :key="segment.id"
    class="teaching-part lesson-part"
  >
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
    <details class="segment-rewrite">
      <summary>{{ segment.content.trim() ? '只重写本环节' : '单独生成本环节' }}</summary>
      <label class="editor-field"
        >本环节修订要求<textarea
          v-model="instructions[segment.id]"
          rows="2"
          maxlength="2000"
          placeholder="例如：保留核心结论，补充一道逐步演算的例题。"
        ></textarea>
      </label>
      <p class="section-hint">
        将替换本环节正文与互动内容，其他环节保留。调整课堂安排后需重新确认。
      </p>
      <button
        class="secondary"
        type="button"
        :disabled="!canGenerate"
        @click="$emit('generate', segment, instructions[segment.id] ?? '')"
      >
        {{ segment.content.trim() ? '重写并保存本环节' : '生成并保存本环节' }}
      </button>
    </details>
    <label class="editor-field">
      环节类型
      <select v-model="segment.stage">
        <option value="opening">导入与复习</option>
        <option value="instruction">讲解与示范</option>
        <option value="practice">练习与应用</option>
        <option value="summary">总结与检测</option>
      </select>
    </label>
    <label class="editor-field"
      >课堂环节<input
        v-model="segment.title"
        maxlength="200"
        placeholder="例如：从相邻词预测引入 N 元语言模型"
    /></label>
    <label class="editor-field"
      >讲解正文<textarea
        v-model="segment.content"
        rows="10"
        maxlength="16000"
        placeholder="写出教师实际要讲的内容：概念、直观解释、公式与推导（适用时）、具体例子、过渡语。不要只写“介绍概念”或“组织讨论”。"
      ></textarea>
    </label>
    <div class="paired-fields">
      <label class="editor-field"
        >教师引导与活动步骤<textarea
          v-model="segment.activity"
          rows="4"
          maxlength="2000"
          placeholder="具体引导语、提问、组织方式和时间安排；计入本环节时长。"
        ></textarea></label
      ><label class="editor-field"
        >例题与演示<textarea
          v-model="segment.example"
          rows="4"
          maxlength="3000"
          placeholder="完整题目、已知条件、逐步解答和结论；教学假设应明确标注。"
        ></textarea>
      </label>
    </div>
    <div class="paired-fields">
      <label class="editor-field">
        学生任务<textarea
          v-model="segment.student_activity"
          rows="4"
          maxlength="3000"
          placeholder="写出具体问题或练习、参与方式和应提交的结果。"
        ></textarea>
      </label>
      <label class="editor-field">
        预期回答与参考答案<textarea
          v-model="segment.expected_response"
          rows="4"
          maxlength="4000"
          placeholder="写出参考答案、解题步骤和关键理由，便于现场讲评。"
        ></textarea>
      </label>
      <label class="editor-field">
        检查与反馈<textarea
          v-model="segment.check_for_understanding"
          rows="3"
          maxlength="3000"
          placeholder="怎样判断理解正确？回答错误时怎样追问或重新演示？"
        ></textarea>
      </label>
      <label class="editor-field">
        易错点与纠正<textarea
          v-model="segment.misconceptions"
          rows="3"
          maxlength="3000"
          placeholder="常见误解、错误原因和纠正方法。"
        ></textarea>
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
    :disabled="body.segments.length >= 24"
    @click="
      body.segments.push({
        id: newId(),
        stage: 'instruction',
        title: '',
        minutes: 5,
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
      })
    "
  >
    ＋ 添加课堂环节
  </button>
</template>
