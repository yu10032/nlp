<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import AppIcon from '../components/AppIcon.vue'
import type { CourseDocument, DocumentChunk } from '../types'

const props = defineProps<{ courseId: string }>()
const route = useRoute()
const documents = ref<CourseDocument[]>([])
const selected = ref<CourseDocument>()
const chunks = ref<DocumentChunk[]>([])
const loading = ref(true)
const reading = ref(false)
const uploading = ref(false)
const error = ref('')
const search = ref('')
const input = ref<HTMLInputElement>()
const replaceTarget = ref<string>()
const showHistory = ref(false)
const statuses: Record<string, string> = {
  ready: '已就绪',
  partial: '部分提取',
  failed: '解析失败',
  ingesting: '解析中',
}
const visibleDocuments = computed(() =>
  documents.value.filter(
    (doc) =>
      (showHistory.value || doc.active || ['failed', 'ingesting'].includes(doc.status)) &&
      doc.title.includes(search.value),
  ),
)
let timer: number | undefined
let selectionRequest = 0

async function selectDocument(document: CourseDocument) {
  const request = ++selectionRequest
  selected.value = document
  reading.value = true
  chunks.value = []
  try {
    const result = await api.chunks(props.courseId, document.id)
    if (request !== selectionRequest) return
    chunks.value = result
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    if (request === selectionRequest) reading.value = false
  }
}
function locateChunk() {
  if (typeof route.query.chunk === 'string')
    documentElement(route.query.chunk)?.scrollIntoView({ block: 'center' })
}
function documentElement(id: string) {
  return document.getElementById(`chunk-${id}`)
}

async function loadDocuments(preferred?: string) {
  documents.value = await api.documents(props.courseId)
  const id =
    preferred ??
    (typeof route.query.document === 'string' ? route.query.document : selected.value?.id)
  const next =
    documents.value.find((doc) => doc.id === id) ??
    documents.value.find((doc) => doc.active) ??
    documents.value[0]
  if (next) await selectDocument(next)
}

async function poll(jobId: string, materialId: string) {
  try {
    const job = await api.job(props.courseId, jobId)
    if (job.status === 'done' || job.status === 'failed') {
      uploading.value = false
      if (job.error) error.value = job.error
      await loadDocuments(materialId)
    } else timer = window.setTimeout(() => poll(jobId, materialId), 800)
  } catch (cause) {
    error.value = (cause as Error).message
    uploading.value = false
  }
}

async function upload(file?: File) {
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const result = await api.upload(props.courseId, file, replaceTarget.value)
    await loadDocuments(result.material_id)
    await poll(result.job_id, result.material_id)
  } catch (cause) {
    error.value = (cause as Error).message
    uploading.value = false
  } finally {
    if (input.value) input.value.value = ''
  }
}
function pick(replace?: string) {
  replaceTarget.value = replace
  input.value?.click()
}
function fileChanged(event: Event) {
  upload((event.target as HTMLInputElement).files?.[0])
}
function drop(event: DragEvent) {
  if (!uploading.value) {
    replaceTarget.value = undefined
    upload(event.dataTransfer?.files[0])
  }
}
onMounted(async () => {
  try {
    await loadDocuments()
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    loading.value = false
  }
})
watch(
  () => route.query.document,
  async (id) => {
    const document = documents.value.find((item) => item.id === id)
    if (document && document.id !== selected.value?.id) await selectDocument(document)
  },
)
watch([loading, reading, () => route.query.chunk], async ([isLoading, isReading]) => {
  if (isLoading || isReading) return
  await nextTick()
  locateChunk()
})
onBeforeUnmount(() => window.clearTimeout(timer))
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>课程资料</h1>
      <span v-if="!loading" class="page-meta">{{ visibleDocuments.length }} 份资料</span>
    </div>
    <button class="primary" type="button" :disabled="uploading" @click="pick()">
      <AppIcon name="upload" :size="15" />{{ uploading ? '正在解析…' : '上传资料' }}
    </button>
  </div>
  <input
    ref="input"
    class="hidden-file"
    type="file"
    accept=".docx,.pdf,.txt,.md"
    aria-label="上传课程资料"
    @change="fileChanged"
  />
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="loading" class="loading-block" role="status">正在读取资料目录…</div>
  <div v-else class="materials-layout" @dragover.prevent @drop.prevent="drop">
    <section class="document-library">
      <div class="library-search">
        <label class="sr-only" for="document-search">查找资料</label>
        <input
          id="document-search"
          v-model="search"
          class="line-input"
          type="search"
          placeholder="筛选讲义或资料名称"
        />
      </div>
      <div class="library-options">
        <span>目录</span>
        <label class="check-label"><input v-model="showHistory" type="checkbox" />历史版本</label>
      </div>
      <div class="document-list">
        <button
          v-for="doc in visibleDocuments"
          :key="doc.id"
          type="button"
          class="document-row"
          :class="{ selected: selected?.id === doc.id }"
          @click="selectDocument(doc)"
        >
          <span class="document-summary">
            <strong>{{ doc.title }}</strong>
            <small>
              {{ doc.chunk_count }} 个片段 · v{{ doc.version
              }}<template v-if="!doc.active && doc.status !== 'ingesting'"> · 历史</template>
            </small>
          </span>
          <span class="status-dot" :class="doc.status" :title="statuses[doc.status]"></span>
          <span class="sr-only">{{ statuses[doc.status] }}</span>
        </button>
      </div>
      <div v-if="!visibleDocuments.length" class="library-empty">
        {{ search ? '没有找到匹配的资料' : '还没有上传课程资料' }}
      </div>
      <button class="upload-drop" type="button" :disabled="uploading" @click="pick()">
        <AppIcon name="plus" :size="20" />
        <span>上传或拖入讲义资料</span>
        <small>DOCX / PDF / TXT / MD · 20 MB</small>
      </button>
    </section>

    <section class="document-reader sheet">
      <template v-if="selected">
        <header class="reader-heading">
          <div>
            <h2>{{ selected.title }}</h2>
            <p class="reader-meta">
              {{ statuses[selected.status] }} · {{ selected.chunk_count }} 个片段 · v{{
                selected.version
              }}<span v-if="!selected.active && selected.status !== 'ingesting'"> · 历史版本</span>
            </p>
          </div>
          <div class="reader-actions">
            <a
              v-if="selected.filename"
              class="icon-button"
              :href="api.fileUrl(courseId, selected.id)"
              aria-label="下载原文件"
            >
              <AppIcon name="download" :size="16" />
            </a>
            <button
              class="secondary"
              type="button"
              :disabled="uploading"
              @click="pick(selected.id)"
            >
              更新版本
            </button>
          </div>
        </header>
        <div v-if="selected.warnings.length" class="notice">
          <p v-for="warning in selected.warnings" :key="warning">{{ warning }}</p>
        </div>
        <div v-if="reading" class="loading-block" role="status">正在展开原文…</div>
        <div v-else class="document-chunks">
          <article
            v-for="chunk in chunks"
            :id="`chunk-${chunk.id}`"
            :key="chunk.id"
            class="chunk-block"
            :class="{ highlighted: route.query.chunk === chunk.id }"
          >
            <div class="chunk-meta">
              <span>{{ chunk.section_path.join(' / ') || chunk.locator }}</span>
              <RouterLink
                v-if="selected.active"
                :to="{ path: '/graph', query: { source: chunk.id, document: selected.id } }"
              >
                建立知识点 →
              </RouterLink>
            </div>
            <p class="chunk-prose">
              <mark v-if="route.query.chunk === chunk.id">{{ chunk.text }}</mark>
              <template v-else>{{ chunk.text }}</template>
            </p>
            <small v-if="chunk.section_path.length" class="chunk-foot">{{ chunk.locator }}</small>
          </article>
          <div v-if="!chunks.length" class="empty-state">
            <p class="muted">
              {{
                selected.status === 'ingesting'
                  ? '正在解析文档，请稍候…'
                  : '没有可用片段，请检查文档或上传文本版本。'
              }}
            </p>
          </div>
        </div>
      </template>
      <div v-else class="empty-state reader-empty">
        <h2>课程依据，从这里开始</h2>
        <p class="muted">上传讲义资料，保留原文段落与章节出处，供图谱与答疑核查。</p>
        <button class="primary" type="button" @click="pick()">上传第一份资料</button>
      </div>
    </section>
  </div>
</template>
