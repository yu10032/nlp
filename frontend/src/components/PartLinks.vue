<script setup lang="ts">
import type { KnowledgeNode, PartLinks, RetrievalEvidence } from '../types'
defineProps<{
  part: PartLinks
  nodes: KnowledgeNode[]
  evidence: RetrievalEvidence[]
  index: number
}>()
defineEmits<{ preview: [source: RetrievalEvidence] }>()
</script>
<template>
  <div class="part-links">
    <div class="node-choices">
      <span class="section-label">知识点</span>
      <label
        v-for="node in nodes"
        :key="node.id"
        class="node-tag"
        :class="{ 'is-selected': part.node_ids.includes(node.id) }"
      >
        <input
          v-model="part.node_ids"
          type="checkbox"
          :value="node.id"
          :aria-label="`第${index + 1}项关联${node.name}`"
        />{{ node.name }}
      </label>
    </div>
    <div class="part-citations">
      <span class="section-label">依据</span>
      <span
        v-for="(source, i) in evidence"
        :key="source.id"
        :title="`${source.material_title} · ${source.locator}`"
        class="cite-check"
      >
        <input
          v-model="part.citation_ids"
          type="checkbox"
          :value="source.id"
          :aria-label="`第${index + 1}项引用依据${i + 1}`"
        />
        <button class="text-button" type="button" @click="$emit('preview', source)">
          [{{ i + 1 }}]<span v-if="source.active === false">已失效</span>
        </button>
      </span>
      <span v-if="!evidence.length" class="muted">先查找课程依据</span>
    </div>
  </div>
</template>
