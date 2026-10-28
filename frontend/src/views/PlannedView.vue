<script setup lang="ts">
defineProps<{ title: string; description: string; courseId: string }>()
</script>
<template>
  <div class="page-heading">
    <div class="heading-with-count">
      <h1>{{ title }}</h1>
      <span class="page-meta">待开放模块</span>
    </div>
  </div>
  <section class="planned sheet">
    <h2>后续阶段接入</h2>
    <p>{{ description }}</p>
    <div class="planned-links">
      <RouterLink class="secondary" to="/graph">查看知识图谱</RouterLink>
      <RouterLink class="text-button" to="/qa">前往课程答疑 →</RouterLink>
    </div>
  </section>
</template>
