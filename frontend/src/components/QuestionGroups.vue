<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import type { QuestionBatch, QuestionGroup, QuestionResult } from '../types'
const props = defineProps<{ courseId: string; batch: QuestionBatch }>()
const emit = defineEmits<{ updated: [batch: QuestionBatch]; open: [question: QuestionResult] }>()
const busy = defineModel<boolean>('busy', { required: true })
const merging = ref<string[]>([])
const editing = ref<string | null>()
const chosen = ref<string[]>([])
const title = ref('')
const error = ref('')
const message = ref('')
const ungrouped = computed(() => props.batch.questions.filter((q) => !q.group_id))
const editOptions = computed(() =>
  props.batch.questions.filter((q) => !q.group_id || q.group_id === editing.value),
)
const question = (id: string) => props.batch.questions.find((q) => q.id === id)!
function edit(group?: QuestionGroup) {
  editing.value = group?.id ?? null
  title.value = group?.title ?? ''
  chosen.value = [...(group?.question_ids ?? [])]
}
async function change(action: () => Promise<QuestionBatch>, done: string) {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    emit('updated', await action())
    editing.value = undefined
    merging.value = []
    message.value = done
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}
function save() {
  const group = props.batch.groups.find((g) => g.id === editing.value)
  return change(
    () =>
      group
        ? api.updateQuestionGroup(
            props.courseId,
            group.id,
            chosen.value,
            title.value,
            group.version,
          )
        : api.createQuestionGroup(props.courseId, props.batch.id, chosen.value, title.value),
    '分组已保存并确认',
  )
}
function confirm(group: QuestionGroup) {
  return change(
    () =>
      api.updateQuestionGroup(
        props.courseId,
        group.id,
        group.question_ids,
        group.title,
        group.version,
      ),
    '分组已确认；知识点关联仍按每条问题单独核查',
  )
}
function remove(group: QuestionGroup, id: string) {
  return change(
    () =>
      group.question_ids.length === 2
        ? api.dissolveQuestionGroup(props.courseId, group.id, group.version)
        : api.updateQuestionGroup(
            props.courseId,
            group.id,
            group.question_ids.filter((qid) => qid !== id),
            group.title,
            group.version,
            false,
          ),
    group.question_ids.length === 2
      ? '分组不足两问，已解散；原问题均保留'
      : '问题已移出，剩余分组待重新确认',
  )
}
function merge() {
  return change(
    () =>
      api.mergeQuestionGroups(
        props.courseId,
        props.batch.groups.filter((g) => merging.value.includes(g.id)),
      ),
    '分组已合并，请核查成员并确认',
  )
}
function dissolve(group: QuestionGroup) {
  return change(
    () => api.dissolveQuestionGroup(props.courseId, group.id, group.version),
    '分组已解散，原问题均保留',
  )
}
</script>
<template>
  <section class="question-group-workspace" aria-label="相似问题整理">
    <div class="section-heading">
      <h2>相似问题</h2>
      <div class="entry-actions">
        <button
          class="text-button"
          type="button"
          :disabled="busy || ungrouped.length < 2"
          @click="edit()"
        >
          手动建组</button
        ><button
          class="secondary"
          type="button"
          :disabled="busy || merging.length < 2"
          @click="merge"
        >
          合并所选组
        </button>
      </div>
    </div>
    <p class="footnote">
      TF-IDF 词面候选，需人工确认是否为同一诉求；分组保留全部原问题，热点仍按不同问题 ID 计数。
    </p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="message" class="success-message" role="status">{{ message }}</p>
    <form v-if="editing !== undefined" class="group-editor sheet" @submit.prevent="save">
      <label for="group-title">分组标题</label
      ><input
        id="group-title"
        v-model="title"
        maxlength="200"
        placeholder="留空使用首问"
        :disabled="busy"
      />
      <fieldset>
        <legend>成员</legend>
        <label v-for="q in editOptions" :key="q.id" class="group-member-choice"
          ><input v-model="chosen" type="checkbox" :value="q.id" :disabled="busy" />{{
            q.text
          }}</label
        >
      </fieldset>
      <div class="entry-actions">
        <button class="primary" :disabled="busy || chosen.length < 2">保存并确认分组</button
        ><button class="text-button" type="button" :disabled="busy" @click="editing = undefined">
          取消
        </button>
      </div>
    </form>
    <div class="question-group-list">
      <article v-for="group in batch.groups" :key="group.id" class="question-group sheet">
        <div class="question-group-heading">
          <label class="check-label"
            ><input
              v-model="merging"
              type="checkbox"
              :value="group.id"
              :aria-label="`选择分组：${group.title}`"
              :disabled="busy"
            /><span class="tag" :class="group.status === 'confirmed' ? 'confirmed' : 'predicted'">{{
              group.status === 'confirmed' ? '人工确认' : '待确认'
            }}</span></label
          ><span class="muted">{{ group.question_ids.length }} 问</span>
        </div>
        <h3>{{ group.title }}</h3>
        <div v-for="id in group.question_ids" :key="id" class="group-member">
          <button
            class="text-button"
            type="button"
            :disabled="busy"
            @click="emit('open', question(id))"
          >
            {{ question(id).text }}</button
          ><button
            class="text-button group-remove"
            type="button"
            :aria-label="`移出：${question(id).text}`"
            :disabled="busy"
            @click="remove(group, id)"
          >
            移出
          </button>
        </div>
        <div class="group-footer">
          <button
            v-if="group.status === 'candidate'"
            class="secondary"
            type="button"
            :disabled="busy"
            @click="confirm(group)"
          >
            确认同一诉求</button
          ><button class="text-button" type="button" :disabled="busy" @click="edit(group)">
            整理成员</button
          ><button class="text-button" type="button" :disabled="busy" @click="dissolve(group)">
            解散
          </button>
        </div>
      </article>
    </div>
    <p v-if="!batch.groups.length && editing === undefined" class="muted group-empty">
      没有达到候选阈值的相似组，可手动选择同一诉求的问题建组。
    </p>
    <details v-if="ungrouped.length" class="ungrouped-questions">
      <summary>未归组 · {{ ungrouped.length }} 问</summary>
      <button
        v-for="q in ungrouped"
        :key="q.id"
        class="text-button"
        type="button"
        :disabled="busy"
        @click="emit('open', q)"
      >
        {{ q.text }}
      </button>
    </details>
  </section>
</template>
