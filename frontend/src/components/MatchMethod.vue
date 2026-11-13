<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import type { MatcherState } from '../types'
const props = defineProps<{ courseId: string; disabled?: boolean }>()
const method = defineModel<string>({ default: 'auto' })
const state = ref<MatcherState>()
const error = ref('')
const labels: Record<string, string> = {
  name: '名称与别名',
  tfidf: 'TF-IDF',
  embedding: '句向量',
  mlp: '本地 MLP（开发）',
}
onMounted(async () => {
  try {
    state.value = await api.matcher(props.courseId)
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
</script>
<template>
  <div class="match-method">
    <label
      >匹配方式<select aria-label="匹配方式" v-model="method" :disabled="disabled || !state">
        <option value="auto">自动 · {{ labels[state?.active_method ?? 'tfidf'] }}</option>
        <option
          v-for="item in state?.methods"
          :key="item.id"
          :value="item.id"
          :disabled="!item.available"
        >
          {{ labels[item.id] }}{{ item.available ? '' : ' · 不可用' }}
        </option>
      </select></label
    >
    <span v-if="error" class="error">{{ error }}</span>
    <details v-else-if="state?.scope_reason" class="method-scope context-details">
      <summary>适用范围</summary>
      <p class="muted">{{ state.scope_reason }}</p>
    </details>
  </div>
</template>
