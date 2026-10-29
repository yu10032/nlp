<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../api'
import type { KnowledgeNode, LessonBody, RetrievalEvidence } from '../types'
import LectureProse from './LectureProse.vue'

const props = defineProps<{
  title: string
  body: LessonBody
  nodes: KnowledgeNode[]
  evidence: RetrievalEvidence[]
  courseId: string
  approved: boolean
  contentId?: string
  version?: number
}>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const printing = ref(false)
const audience = ref<'teacher' | 'student'>('teacher')
const teacher = computed(() => audience.value === 'teacher')
const error = ref('')
const stageNames = {
  opening: '导入与复习',
  instruction: '讲解与示范',
  practice: '练习与应用',
  summary: '总结与检测',
}
const timeline = computed(() => {
  let elapsed = 0
  return props.body.segments.map((segment) => {
    const start = elapsed
    elapsed += segment.minutes
    return { ...segment, start, end: elapsed }
  })
})
function jump(id: string) {
  document.getElementById(`lesson-preview-${id}`)?.scrollIntoView({ block: 'start' })
}
async function print() {
  printing.value = true
  error.value = ''
  try {
    await api.validateLessonPrint(props.courseId, props.contentId!, props.version!, audience.value)
    await nextTick()
    for (const image of dialog.value!.querySelectorAll('img')) image.loading = 'eager'
    await Promise.all([...dialog.value!.querySelectorAll('img')].map((image) => image.decode()))
    await document.fonts.ready
    window.print()
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    printing.value = false
  }
}
onMounted(() => dialog.value!.showModal())
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="lesson-preview"
      aria-label="课堂讲义阅读预览"
      @cancel.prevent="emit('close')"
    >
      <div class="preview-toolbar">
        <span>{{ approved ? '当前版本已审核' : '草稿预览' }}</span>
        <div>
          <select v-model="audience" aria-label="讲义版本">
            <option value="teacher">教师版</option>
            <option value="student">学生版</option>
          </select>
          <a
            v-if="approved"
            class="secondary"
            :href="api.lessonWordUrl(courseId, contentId!, audience)"
            download
            >Word</a
          >
          <button class="secondary" type="button" :disabled="!approved || printing" @click="print">
            {{ printing ? '准备打印…' : '打印 / 保存 PDF' }}
          </button>
          <button class="text-button" type="button" @click="emit('close')">返回编辑</button>
        </div>
      </div>
      <p v-if="error" class="error preview-print-note" role="alert">{{ error }}</p>
      <p v-if="!approved" class="section-hint preview-print-note">
        可预览当前未保存内容；正式打印与导出需先保存并通过审核。
      </p>
      <article class="lecture-document">
        <header class="lecture-title">
          <p class="lecture-kicker">
            {{ teacher ? '教师版' : '学生版' }}课堂讲义 · {{ body.duration }} 分钟
          </p>
          <h1>{{ title || '未命名讲义' }}</h1>
          <p>{{ nodes.map((node) => node.name).join(' / ') }}</p>
        </header>
        <section>
          <h2>教学目标</h2>
          <LectureProse :text="body.objectives" />
        </section>
        <section v-if="body.key_questions">
          <h2>重点问题</h2>
          <LectureProse :text="body.key_questions" />
        </section>
        <section v-if="teacher && body.preparation">
          <h2>课前准备</h2>
          <LectureProse :text="body.preparation" />
        </section>
        <nav class="lecture-contents" aria-label="讲义目录">
          <h2>课堂安排</h2>
          <ol>
            <li v-for="part in timeline" :key="part.id">
              <button type="button" class="text-button" @click="jump(part.id)">
                {{ part.title }}
              </button>
              <span>{{ part.start }}–{{ part.end }} 分钟</span>
            </li>
          </ol>
        </nav>
        <section
          v-for="(part, index) in body.segments"
          :id="`lesson-preview-${part.id}`"
          :key="part.id"
          class="lecture-section"
        >
          <p class="lecture-kicker">{{ stageNames[part.stage] }} · {{ part.minutes }} 分钟</p>
          <h2>{{ String(index + 1).padStart(2, '0') }}　{{ part.title }}</h2>
          <LectureProse :text="part.content" />
          <template
            v-for="field in [
              ['activity', '教师引导与课堂活动'],
              ['example', '例题与演示'],
              ['student_activity', '学生任务'],
              ['expected_response', '预期回答与参考答案'],
              ['check_for_understanding', '检查与反馈'],
              ['misconceptions', '易错点与纠正'],
            ] as const"
            :key="field[0]"
          >
            <div
              v-if="part[field[0]] && (teacher || field[0] === 'student_activity')"
              class="lecture-subsection"
            >
              <h3>{{ field[1] }}</h3>
              <LectureProse :text="part[field[0]]" />
            </div>
          </template>
          <template v-for="quizId in part.quiz_ids" :key="quizId">
            <p
              v-if="!teacher && body.examples?.[quizId] && !body.examples[quizId].student_content"
              class="error"
            >
              旧版题组尚无学生版题干，请返回保存并重新审核。
            </p>
            <div
              v-if="body.examples?.[quizId] && (teacher || body.examples[quizId].student_content)"
              class="lecture-subsection"
            >
              <h3>关联题组：{{ body.examples[quizId].title }}</h3>
              <LectureProse
                :text="
                  teacher ? body.examples[quizId].answer : body.examples[quizId].student_content!
                "
              />
            </div>
          </template>
          <p class="lecture-reference">
            知识点：{{
              nodes
                .filter((n) => part.node_ids.includes(n.id))
                .map((n) => n.name)
                .join('、')
            }}<br />依据：{{
              part.citation_ids
                .map((id) => `[${evidence.findIndex((e) => e.id === id) + 1}]`)
                .join('、')
            }}
          </p>
        </section>
        <section v-if="teacher && body.student_homework">
          <h2>学生版课后任务</h2>
          <LectureProse :text="body.student_homework" />
        </section>
        <section v-if="teacher ? body.homework : body.student_homework">
          <h2>{{ teacher ? '课后巩固与参考要点' : '课后任务' }}</h2>
          <LectureProse :text="teacher ? body.homework : body.student_homework" />
        </section>
        <section v-if="teacher && body.missing_info.length">
          <h2>待补充事项</h2>
          <ul>
            <li v-for="(item, index) in body.missing_info" :key="index">{{ item }}</li>
          </ul>
        </section>
        <section v-if="evidence.length" class="lecture-sources">
          <h2>课程依据</h2>
          <div v-for="(source, index) in evidence" :key="source.id">
            <h3>
              [{{ index + 1 }}] {{ source.material_title }} · v{{ source.material_version }} ·
              {{ source.locator }}
            </h3>
            <LectureProse
              :text="source.text"
              :course-id="courseId"
              :material-id="source.material_id"
            />
          </div>
        </section>
      </article>
    </dialog>
  </Teleport>
</template>
