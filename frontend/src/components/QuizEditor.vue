<script setup lang="ts">
import PartLinks from './PartLinks.vue'
import type { KnowledgeNode, QuizBody, RetrievalEvidence } from '../types'
const props = defineProps<{
  body: QuizBody
  nodes: KnowledgeNode[]
  evidence: RetrievalEvidence[]
}>()
defineEmits<{ preview: [source: RetrievalEvidence] }>()
function changeType(index: number) {
  const item = props.body.items[index]!
  item.options = item.type === 'single_choice' ? ['', '', '', ''] : []
  item.answer = ''
}
</script>
<template>
  <section v-for="(item, index) in body.items" :key="index" class="teaching-part">
    <header class="part-heading">
      <span class="part-number">{{ String(index + 1).padStart(2, '0') }}</span>
      <label class="sr-only" :for="`type-${index}`">第{{ index + 1 }}题题型</label>
      <select :id="`type-${index}`" v-model="item.type" @change="changeType(index)">
        <option value="single_choice">单选题</option>
        <option value="short_answer">简答题</option>
      </select>
      <button
        class="text-button part-remove"
        type="button"
        :disabled="body.items.length === 1"
        :aria-label="`删除第${index + 1}题`"
        @click="body.items.splice(index, 1)"
      >
        删除
      </button>
    </header>
    <label class="editor-field"
      >题干<textarea
        v-model="item.stem"
        rows="3"
        maxlength="3000"
        placeholder="写下需要学生思考的问题"
      ></textarea>
    </label>
    <div v-if="item.type === 'single_choice'" class="quiz-options">
      <label v-for="(_, i) in item.options" :key="i" class="option-field"
        ><span>{{ 'ABCD'[i] }}</span
        ><input
          v-model="item.options[i]"
          :aria-label="`第${index + 1}题选项${'ABCD'[i]}`"
          maxlength="2000"
      /></label>
    </div>
    <label v-if="item.type === 'single_choice'" class="editor-field choice-answer"
      >正确答案<select v-model="item.answer">
        <option value="">请选择</option>
        <option v-for="letter in 'ABCD'" :key="letter">{{ letter }}</option>
      </select></label
    >
    <label v-else class="editor-field"
      >参考答案<textarea v-model="item.answer" rows="3" maxlength="4000"></textarea>
    </label>
    <label class="editor-field"
      >答案解析<textarea
        v-model="item.explanation"
        rows="2"
        maxlength="5000"
        placeholder="说明解题依据与关键步骤"
      ></textarea>
    </label>
    <PartLinks
      :part="item"
      :nodes="nodes"
      :evidence="evidence"
      :index="index"
      @preview="$emit('preview', $event)"
    />
  </section>
  <button
    class="secondary add-part"
    type="button"
    :disabled="body.items.length >= 5"
    @click="
      body.items.push({
        type: 'short_answer',
        stem: '',
        options: [],
        answer: '',
        explanation: '',
        node_ids: [],
        citation_ids: [],
      })
    "
  >
    ＋ 添加一题 <span class="muted">{{ body.items.length }} / 5</span>
  </button>
</template>
