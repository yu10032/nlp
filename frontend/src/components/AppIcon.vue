<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 18 })
const paths: Record<string, string> = {
  graph: 'M7 7l4 8M16 7l-3 8M8 6h7',
  document: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5',
  chat: 'M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z',
  questions: 'M9 8a3 3 0 0 1 6 0c0 2-3 2-3 5M12 17h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  quiz: 'M9 5h11M9 12h11M9 19h11M3 5l1 1 2-2M3 12l1 1 2-2M3 19l1 1 2-2',
  lessons:
    'M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H3V4h1M20 4h-4a3 3 0 0 0-3 3M13 21a4 4 0 0 1 4-2h4V4h-1',
  experiments: 'M9 3h6M10 3v7l-6 9a1.3 1.3 0 0 0 1 2h14a1.3 1.3 0 0 0 1-2l-6-9V3M8 15h8',
  coverage: 'M4 4h16v16H4zM8 9l2 2 5-5M8 15h8',
  plus: 'M12 5v14M5 12h14',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  upload: 'M12 16V3M7 8l5-5 5 5M4 16v5h16v-5',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  back: 'M19 12H5M11 18l-6-6 6-6',
  check: 'M5 12l4 4L19 6',
  close: 'M6 6l12 12M6 18L18 6',
  edit: 'M4 20l4-1 12-12-3-3L5 16zM14 7l3 3',
  menu: 'M4 6h16M4 12h16M4 18h16',
  download: 'M12 3v13M7 11l5 5 5-5M4 17v4h16v-4',
  fit: 'M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5',
}
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'graph'">
      <circle cx="5" cy="6" r="3" />
      <circle cx="18" cy="5" r="3" />
      <circle cx="12" cy="18" r="3" />
    </template>
    <path :d="paths[name]" />
  </svg>
</template>
