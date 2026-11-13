<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{
  history: { epoch: number; train_loss: number; validation_loss: number }[]
  selected: number
}>()
const maximum = computed(() =>
  Math.max(...props.history.flatMap((p) => [p.train_loss, p.validation_loss]), 0.1),
)
const x = (epoch: number) => 42 + ((epoch - 1) / Math.max(1, props.history.length - 1)) * 598
const y = (loss: number) => 188 - (loss / maximum.value) * 158
function path(key: 'train_loss' | 'validation_loss') {
  return props.history.map((p, i) => `${i ? 'L' : 'M'}${x(p.epoch)},${y(p[key])}`).join(' ')
}
</script>
<template>
  <figure class="loss-chart">
    <figcaption>
      <h2>匹配头训练曲线</h2>
      <span><i class="train-key"></i>训练损失 <i class="validation-key"></i>验证损失</span>
    </figcaption>
    <svg
      viewBox="0 0 660 220"
      role="img"
      :aria-label="`训练与验证损失曲线，共${history.length}轮，验证损失选择第${selected}轮权重`"
    >
      <path d="M42,20 V188 H640" class="chart-axis" />
      <text x="4" y="33">{{ maximum.toFixed(2) }}</text>
      <text x="22" y="192">0</text>
      <text x="39" y="211">1</text>
      <text x="606" y="211">{{ history.length }} 轮</text>
      <path :d="path('train_loss')" class="train-line" />
      <path :d="path('validation_loss')" class="validation-line" />
      <line :x1="x(selected)" y1="20" :x2="x(selected)" y2="188" class="selected-epoch" />
    </svg>
    <p class="section-hint">最佳权重 · 第 {{ selected }} 轮</p>
  </figure>
</template>
