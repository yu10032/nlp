<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api'
import AppIcon from './components/AppIcon.vue'
import { sections } from './router'
import type { Course, Health } from './types'

const route = useRoute()
const courses = ref<Course[]>([])
const health = ref<Health>()
const courseId = ref('')
const loading = ref(true)
const error = ref('')
const adding = ref(false)
const saving = ref(false)
const title = ref('')
const menuOpen = ref(false)

const course = computed(() => courses.value.find((item) => item.id === courseId.value))
const generationLabel = computed(() => {
  if (!health.value) return '读取服务状态…'
  if (health.value.generation.available)
    return `生成：${health.value.generation.model ?? health.value.generation.provider}`
  return '生成服务未配置'
})
const matcherLabel = computed(() => {
  if (!health.value) return '匹配器待确认'
  return health.value.matcher.trained_model_loaded ? '匹配：自训模型' : '匹配：词面基线'
})

watch(courseId, (value) => {
  localStorage.setItem('ta-course', value)
  menuOpen.value = false
})
watch(
  () => route.path,
  () => {
    menuOpen.value = false
  },
)

onMounted(async () => {
  try {
    const [courseList, healthData] = await Promise.all([
      api.courses(),
      api.health().catch(() => undefined),
    ])
    courses.value = courseList
    health.value = healthData
    const saved = localStorage.getItem('ta-course')
    courseId.value =
      courses.value.find((item) => item.id === saved)?.id ?? courses.value[0]?.id ?? ''
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    loading.value = false
  }
})

async function addCourse() {
  saving.value = true
  error.value = ''
  try {
    const created = await api.createCourse(title.value)
    courses.value.push(created)
    courseId.value = created.id
    adding.value = false
    title.value = ''
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    saving.value = false
  }
}

function startCourse() {
  adding.value = true
}
</script>
<template>
  <div class="workspace">
    <header class="topbar">
      <RouterLink class="brand" to="/graph">
        <span class="brand-seal" aria-hidden="true">助</span>
        <span>课程智能助教</span>
      </RouterLink>

      <div class="course-switch">
        <label class="sr-only" for="course">当前课程</label>
        <select id="course" v-model="courseId" :disabled="loading || !courses.length">
          <option v-if="!courses.length" value="">{{ loading ? '读取课程…' : '暂无课程' }}</option>
          <option v-for="item in courses" :key="item.id" :value="item.id">
            {{ item.title }}
          </option>
        </select>
        <span v-if="course?.id === 'demo-nlp'" class="context-note">手工示例</span>
        <button
          class="icon-button"
          type="button"
          :aria-label="adding ? '取消新建课程' : '新建课程'"
          @click="adding = !adding"
        >
          <AppIcon :name="adding ? 'close' : 'plus'" :size="15" />
        </button>
      </div>

      <nav class="topnav" :class="{ 'is-open': menuOpen }" aria-label="主要功能">
        <template v-for="(section, index) in sections" :key="section.path">
          <span
            v-if="index > 0 && section.group !== sections[index - 1]!.group"
            class="nav-gap"
            aria-hidden="true"
          ></span>
          <RouterLink :to="section.path" :title="section.label">
            <span class="nav-short">{{ section.shortLabel }}</span>
            <span class="nav-full">{{ section.label }}</span>
          </RouterLink>
        </template>
        <div class="sys-status sys-mobile">
          <span :class="{ 'is-ok': health?.generation.available }">{{ generationLabel }}</span>
          <span :class="{ 'is-ok': !!health }">{{ matcherLabel }}</span>
        </div>
      </nav>

      <div class="sys-status sys-desktop" aria-label="系统能力状态">
        <span :class="{ 'is-ok': health?.generation.available }">{{ generationLabel }}</span>
        <span :class="{ 'is-ok': !!health }">{{ matcherLabel }}</span>
      </div>

      <button
        class="mobile-menu icon-button"
        type="button"
        aria-label="切换导航"
        :aria-expanded="menuOpen"
        @click="menuOpen = !menuOpen"
      >
        <AppIcon :name="menuOpen ? 'close' : 'menu'" />
      </button>
    </header>

    <div v-if="adding" class="course-drawer">
      <form class="course-form" @submit.prevent="addCourse">
        <label for="course-title">新课程名称</label>
        <input
          id="course-title"
          v-model="title"
          class="line-input"
          required
          maxlength="120"
          placeholder="例如：自然语言处理导论"
        />
        <button class="primary" :disabled="saving">{{ saving ? '保存中…' : '创建课程' }}</button>
        <button class="text-button" type="button" @click="adding = false">取消</button>
      </form>
    </div>

    <main class="main">
      <div class="page">
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div v-if="loading" class="loading-block" role="status">正在展卷读取课程…</div>
        <RouterView v-else-if="courseId" v-slot="{ Component }">
          <component :is="Component" :key="`${courseId}:${route.path}`" :course-id="courseId" />
        </RouterView>
        <div v-else-if="!error" class="empty-state sheet">
          <h2>创建第一门课程</h2>
          <p class="muted">建立独立的课程讲义空间，隔离资料、图谱与审核记录。</p>
          <button class="primary" @click="startCourse">新建课程</button>
        </div>
      </div>
    </main>
  </div>
</template>
