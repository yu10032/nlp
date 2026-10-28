<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { api } from '../api'
import AppIcon from './AppIcon.vue'
import type { DocumentChunk, RetrievalEvidence } from '../types'

const props = defineProps<{ courseId: string; source: RetrievalEvidence }>()
defineEmits<{ close: [] }>()
const chunks = ref<DocumentChunk[]>([])
const loading = ref(true)
const error = ref('')
const body = ref<HTMLDivElement>()
onMounted(async () => {
  try {
    chunks.value = await api.chunks(props.courseId, props.source.material_id)
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    loading.value = false
  }
  await nextTick()
  const target = document.getElementById(`preview-${props.source.id}`)
  if (target && body.value) body.value.scrollTop = Math.max(0, target.offsetTop - 16)
})
</script>
<template>
  <section class="source-reader sheet" aria-label="原文预览">
    <button class="text-button source-back" type="button" @click="$emit('close')">
      <AppIcon name="back" :size="14" />返回课程依据
    </button>
    <div class="source-reader-head">
      <h2>{{ source.material_title }}</h2>
      <p class="source-locator">
        v{{ source.material_version }}<span v-if="source.active === false"> · 历史引用已失效</span>
      </p>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="loading" class="loading-block" role="status">正在展开原文…</div>
    <div v-else ref="body" class="source-reader-body">
      <article
        v-for="chunk in chunks"
        :id="`preview-${chunk.id}`"
        :key="chunk.id"
        class="preview-chunk"
        :class="{ highlighted: chunk.id === source.id }"
      >
        <p class="source-locator">{{ chunk.section_path.join(' / ') || chunk.locator }}</p>
        <p class="chunk-prose">
          <mark v-if="chunk.id === source.id">{{ chunk.text }}</mark>
          <template v-else>{{ chunk.text }}</template>
        </p>
        <small v-if="chunk.section_path.length">{{ chunk.locator }}</small>
      </article>
    </div>
  </section>
</template>
