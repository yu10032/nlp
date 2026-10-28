<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import AppIcon from '../components/AppIcon.vue'
import type { Coverage, CoverageKind } from '../types'
const props = defineProps<{ courseId: string }>()
const coverage = ref<Coverage>()
const error = ref('')
const kinds: { key: CoverageKind; label: string }[] = [
  { key: 'material', label: '课程资料' },
  { key: 'quiz', label: '已审核题目' },
  { key: 'lesson', label: '已审核备课' },
]
onMounted(async () => {
  try {
    coverage.value = await api.coverage(props.courseId)
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>知识点覆盖</h1>
      <span v-if="coverage" class="page-meta">已确认知识点 {{ coverage.items.length }} 项</span>
    </div>
    <RouterLink class="secondary" to="/graph">
      查看图谱<AppIcon name="arrow" :size="15" />
    </RouterLink>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="!coverage && !error" class="loading-block" role="status">正在核算覆盖台账…</div>
  <template v-if="coverage">
    <div class="coverage-summary sheet">
      <section v-for="kind in kinds" :key="kind.key" class="coverage-stat">
        <div>
          <h2>{{ kind.label }}</h2>
          <p class="stat-figure">
            {{ coverage.metrics[kind.key].covered
            }}<small>/ {{ coverage.metrics[kind.key].total }}</small>
          </p>
        </div>
        <span class="stat-ratio">{{
          coverage.metrics[kind.key].ratio === null
            ? '暂无范围'
            : `${Math.round(coverage.metrics[kind.key].ratio! * 100)}%`
        }}</span>
      </section>
    </div>

    <div class="table-wrap sheet">
      <table class="ledger-table">
        <caption>
          已确认知识点覆盖明细
        </caption>
        <thead>
          <tr>
            <th scope="col">知识点</th>
            <th v-for="kind in kinds" :key="kind.key" scope="col">{{ kind.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in coverage.items" :key="item.node_id">
            <th scope="row">
              <RouterLink
                class="ledger-node-link"
                :to="{ path: '/graph', query: { node: item.node_id } }"
              >
                {{ item.name }}
              </RouterLink>
            </th>
            <td v-for="kind in kinds" :key="kind.key">
              <span v-if="item[kind.key]" class="tag confirmed">已覆盖</span>
              <span v-else class="gap-mark">待补充</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!coverage.items.length" class="muted empty-row">暂无可统计的已确认知识点。</p>
    </div>

    <p class="footnote">
      注：统计范围限于当前课程已确认知识点，排除章节节点、草稿、过期审核与失效引用。覆盖率仅反映内容关联情况，不代表学生掌握程度。
    </p>
  </template>
</template>
