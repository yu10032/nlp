<script setup lang="ts">
import cytoscape from 'cytoscape'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Graph } from '../types'

const props = withDefaults(
  defineProps<{ graph: Graph; selectedId?: string; highlightIds?: string[] }>(),
  { highlightIds: () => [] },
)
const emit = defineEmits<{ select: [nodeId: string] }>()
const container = ref<HTMLDivElement>()
let graph: cytoscape.Core
let observer: ResizeObserver
let compact = false

const kindLabels: Record<string, string> = {
  concept: '概念',
  method: '方法',
  algorithm: '方法',
  model: '模型',
  task: '任务',
  metric: '评测',
  chapter: '章节',
}

function fit() {
  graph.resize()
  const nextCompact = container.value!.clientWidth < 450
  if (nextCompact !== compact) {
    compact = nextCompact
    graph
      .layout(
        compact
          ? { name: 'grid', cols: 2, padding: 20, animate: false }
          : { name: 'cose', padding: 52, animate: false, componentSpacing: 110 },
      )
      .run()
  }
  graph.fit(undefined, compact ? 20 : 52)
}

function zoomBy(factor: number) {
  const next = Math.min(2.2, Math.max(0.15, graph.zoom() * factor))
  graph.zoom({
    level: next,
    renderedPosition: {
      x: container.value!.clientWidth / 2,
      y: container.value!.clientHeight / 2,
    },
  })
}

function syncSelection() {
  graph.nodes().unselect().removeClass('highlighted')
  props.highlightIds.forEach((id) => graph.getElementById(id).addClass('highlighted'))
  if (props.selectedId) graph.getElementById(props.selectedId).select()
}

onMounted(() => {
  graph = cytoscape({
    container: container.value,
    elements: [
      ...props.graph.nodes.map((node) => ({
        data: {
          id: node.id,
          label: `${kindLabels[node.kind] ?? node.kind}\n${node.name}`,
          rawName: node.name,
          kind: node.kind,
          status: node.status,
        },
      })),
      ...props.graph.edges
        .filter((edge) => edge.status !== 'rejected')
        .map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source_id,
            target: edge.target_id,
            status: edge.status,
            label: (
              {
                contains: '包含',
                uses: '使用',
                applies_to: '适用于',
                contrasts_with: '对比',
                prerequisite_of: '先修',
              } as Record<string, string>
            )[edge.relation],
          },
        })),
    ],
    style: [
      {
        selector: 'node',
        style: {
          label: 'data(rawName)',
          shape: 'round-rectangle',
          'background-color': '#fffdf8',
          color: '#1f1c17',
          'font-size': 14,
          'font-family': '"Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", serif',
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': '116px',
          width: 136,
          height: 52,
          'border-width': 1.4,
          'border-color': '#1f1c17',
        },
      },
      {
        selector: 'node[kind="chapter"], node[kind="model"]',
        style: {
          'font-weight': 600,
          'border-width': 1.8,
        },
      },
      {
        selector: 'node[status="candidate"]',
        style: {
          'border-style': 'dashed',
          'border-color': '#9a9283',
          'background-color': '#fcf9f2',
          color: '#6e675b',
        },
      },
      {
        selector: 'node.highlighted',
        style: {
          'background-color': '#fbf2c8',
          'border-color': '#1f1c17',
          'border-width': 2,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'background-color': '#1f1c17',
          'border-color': '#1f1c17',
          color: '#fffdf8',
        },
      },
      {
        selector: 'edge',
        style: {
          label: 'data(label)',
          width: 1.15,
          'line-color': '#7c7467',
          'target-arrow-color': '#7c7467',
          'target-arrow-shape': 'vee',
          'curve-style': 'bezier',
          'font-size': 12,
          'font-family': '"Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", serif',
          'font-style': 'italic',
          color: '#6e675b',
          'text-background-color': '#fffdf8',
          'text-background-opacity': 1,
          'text-background-padding': '3px',
        },
      },
      {
        selector: 'edge[status="candidate"]',
        style: {
          'line-style': 'dashed',
          'line-color': '#9a9283',
          'target-arrow-color': '#9a9283',
        },
      },
    ],
    layout: {
      name: 'cose',
      animate: false,
      padding: 52,
      componentSpacing: 110,
      nodeRepulsion: () => 8500,
    },
    minZoom: 0.15,
    maxZoom: 2.2,
  })
  graph.on('tap', 'node', (event) => emit('select', event.target.id()))
  observer = new ResizeObserver(fit)
  observer.observe(container.value!)
  syncSelection()
})
watch(() => [props.selectedId, props.highlightIds], syncSelection)
onBeforeUnmount(() => {
  observer.disconnect()
  graph.destroy()
})
</script>
<template>
  <div class="graph-stage">
    <div
      ref="container"
      class="graph-canvas"
      role="img"
      aria-label="课程知识图谱，也可通过知识点列表选择节点"
    ></div>
    <div class="graph-controls">
      <div class="graph-legend">
        <span><i class="legend-node"></i>已确认</span>
        <span><i class="legend-candidate"></i>待确认</span>
      </div>
      <div class="graph-zoom-group">
        <button type="button" class="icon-button" aria-label="放大图谱" @click="zoomBy(1.2)">
          ＋
        </button>
        <button type="button" class="icon-button" aria-label="缩小图谱" @click="zoomBy(0.84)">
          －
        </button>
        <button type="button" class="icon-button graph-fit" aria-label="适配图谱" @click="fit">
          <AppIcon name="fit" :size="15" />
        </button>
      </div>
    </div>
  </div>
</template>
