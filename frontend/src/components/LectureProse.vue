<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { api } from '../api'

const props = defineProps<{ text: string; courseId?: string; materialId?: string }>()
const markdown = new MarkdownIt({ html: false, breaks: true })
markdown.inline.ruler.before('escape', 'lesson_math', (state, silent) => {
  const start = state.pos
  const opener = state.src.startsWith('\\(', start) ? '\\(' : state.src[start] === '$' ? '$' : ''
  if (!opener || state.src.startsWith('$$', start)) return false
  const closer = opener === '$' ? '$' : '\\)'
  let end = state.src.indexOf(closer, start + opener.length)
  while (end > 0 && state.src[end - 1] === '\\')
    end = state.src.indexOf(closer, end + closer.length)
  if (end < 0) return false
  if (!silent) {
    const token = state.push('lesson_math', 'math', 0)
    token.content = state.src.slice(start + opener.length, end)
  }
  state.pos = end + closer.length
  return true
})
markdown.block.ruler.before('fence', 'lesson_math_block', (state, start, end, silent) => {
  const first = state.src.slice(state.bMarks[start]! + state.tShift[start]!, state.eMarks[start])
  const opener = first.startsWith('$$') ? '$$' : first.startsWith('\\[') ? '\\[' : ''
  if (!opener) return false
  const closer = opener === '$$' ? '$$' : '\\]'
  let content = first.slice(opener.length)
  let next = start + 1
  while (!content.includes(closer) && next < end) {
    content += '\n' + state.src.slice(state.bMarks[next], state.eMarks[next])
    next++
  }
  if (!content.includes(closer)) return false
  // 同行闭合符之后有正文时，交给普通 Markdown，避免吞掉后文。
  if (content.slice(content.indexOf(closer) + closer.length).trim()) return false
  if (!silent) {
    const token = state.push('lesson_math_block', 'math', 0)
    token.content = content.slice(0, content.indexOf(closer))
    token.map = [start, next]
  }
  state.line = next
  return true
})
markdown.renderer.rules.lesson_math = (tokens, index) =>
  katex.renderToString(tokens[index]!.content, {
    throwOnError: false,
    trust: false,
    strict: 'ignore',
  })
markdown.renderer.rules.lesson_math_block = (tokens, index) =>
  '<div class="lecture-equation">' +
  katex.renderToString(tokens[index]!.content, {
    displayMode: true,
    throwOnError: false,
    trust: false,
    strict: 'ignore',
  }) +
  '</div>'
markdown.renderer.rules.image = (tokens, index) => {
  const token = tokens[index]!
  const source = String(token.attrGet('src') ?? '')
  if (!/^asset:rId\d+$/.test(source) || !props.courseId || !props.materialId)
    return '<span class="muted">[图片需回看原件]</span>'
  const url = api.documentImageUrl(props.courseId, props.materialId, source.slice(6))
  return `<img src="${markdown.utils.escapeHtml(url)}" alt="原文插图，图中内容需人工核查" loading="lazy" />`
}
const rendered = computed(() => markdown.render(props.text))
</script>

<template>
  <!-- 只渲染 Markdown 解析器与 KaTeX 输出；输入 HTML 被转义，外部图片不加载。 -->
  <div class="lecture-prose" v-html="rendered"></div>
</template>
