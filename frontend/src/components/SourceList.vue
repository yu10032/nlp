<script setup lang="ts">
import type { RetrievalEvidence } from '../types'
defineProps<{
  evidence: RetrievalEvidence[]
  selected?: string[]
  selectable?: boolean
  inlinePreview?: boolean
}>()
defineEmits<{ toggle: [id: string]; preview: [source: RetrievalEvidence] }>()
</script>
<template>
  <div class="source-list" :class="{ 'is-margin-notes': selectable }">
    <template v-if="selectable">
      <article
        v-for="(source, index) in evidence"
        :key="source.id"
        class="margin-note"
        :class="{
          'is-cited': selected?.includes(source.id),
          'is-uncited': selected && !selected.includes(source.id),
          'source-inactive': source.active === false,
        }"
      >
        <span class="note-num">{{ index + 1 }}</span>
        <div class="note-body">
          <div class="note-src">
            <strong>{{ source.material_title }}</strong>
            <span>
              <template v-if="source.section_path?.length"
                >§{{ source.section_path.join(' / ') }} ·
              </template>
              {{ source.locator }} · v{{ source.material_version
              }}<template v-if="source.active === false"> · 已失效</template>
            </span>
          </div>
          <blockquote class="note-quote">{{ source.text }}</blockquote>
          <div class="note-ops">
            <button
              v-if="inlinePreview"
              type="button"
              class="source-link text-button"
              @click="$emit('preview', source)"
            >
              查看原文
            </button>
            <RouterLink
              v-else
              class="source-link"
              :to="{
                path: '/materials',
                query: { document: source.material_id, chunk: source.id },
              }"
            >
              查看原文
            </RouterLink>
            <label class="cite-check">
              <input
                type="checkbox"
                :checked="selected?.includes(source.id)"
                :aria-label="`引用${source.material_title} ${source.locator}`"
                @change="$emit('toggle', source.id)"
              />
              <span>{{ selected?.includes(source.id) ? '已引用' : '重新引用' }}</span>
            </label>
          </div>
        </div>
      </article>
    </template>

    <template v-else>
      <article
        v-for="source in evidence"
        :key="source.id"
        class="source-quote-item"
        :class="{ 'source-inactive': source.active === false }"
      >
        <blockquote class="entry-quote">{{ source.text }}</blockquote>
        <footer class="entry-quote-foot">
          <span>
            {{ source.material_title }} · {{ source.locator }} · v{{ source.material_version
            }}<template v-if="source.active === false"> · 已失效</template>
          </span>
          <button
            v-if="inlinePreview"
            type="button"
            class="source-link text-button"
            @click="$emit('preview', source)"
          >
            查看原文
          </button>
          <RouterLink
            v-else
            class="source-link"
            :to="{ path: '/materials', query: { document: source.material_id, chunk: source.id } }"
          >
            查看原文
          </RouterLink>
        </footer>
      </article>
    </template>
  </div>
</template>
