import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MatchMethod from './MatchMethod.vue'
import { api } from '../api'
import type { MatcherState } from '../types'

vi.mock('../api', () => ({
  api: { matcher: vi.fn() },
}))

const matcherMock = vi.mocked(api.matcher)

const state: MatcherState = {
  active_method: 'tfidf',
  scope_reason: '开发课程启用了本地 MLP 匹配器',
  run_id: null,
  data_status: null,
  methods: [
    { id: 'name', available: true },
    { id: 'mlp', available: false },
  ],
}

function mountView(props: { courseId: string; disabled?: boolean; modelValue?: string }) {
  return mount(MatchMethod, { props })
}

describe('MatchMethod', () => {
  beforeEach(() => {
    matcherMock.mockReset()
  })

  it('挂载时按课程请求匹配器状态', async () => {
    matcherMock.mockResolvedValueOnce(state)
    const wrapper = mountView({ courseId: 'c1' })
    await flushPromises()
    expect(matcherMock).toHaveBeenCalledWith('c1')
    wrapper.unmount()
  })

  it('渲染自动选项与方法列表，不可用项禁用并标注', async () => {
    matcherMock.mockResolvedValueOnce(state)
    const wrapper = mountView({ courseId: 'c1' })
    await flushPromises()
    const options = wrapper.findAll('option')
    expect(options).toHaveLength(3)
    expect(options[0].text()).toContain('自动 · TF-IDF')
    expect(options[1].text()).toBe('名称与别名')
    expect(options[2].text()).toContain('本地 MLP（开发） · 不可用')
    expect((options[2].element as HTMLOptionElement).disabled).toBe(true)
    expect((options[1].element as HTMLOptionElement).disabled).toBe(false)
    wrapper.unmount()
  })

  it('请求失败时展示错误信息', async () => {
    matcherMock.mockRejectedValueOnce(new Error('服务不可用'))
    const wrapper = mountView({ courseId: 'c1' })
    await flushPromises()
    expect(wrapper.get('.error').text()).toBe('服务不可用')
    wrapper.unmount()
  })

  it('加载成功且无失败时展示作用范围说明', async () => {
    matcherMock.mockResolvedValueOnce(state)
    const wrapper = mountView({ courseId: 'c1' })
    await flushPromises()
    expect(wrapper.get('.muted').text()).toBe(state.scope_reason)
    wrapper.unmount()
  })

  it('disabled 属性禁用下拉框', async () => {
    matcherMock.mockResolvedValueOnce(state)
    const wrapper = mountView({ courseId: 'c1', disabled: true })
    await flushPromises()
    expect(wrapper.get('select').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('选择方法后通过 update:modelValue 同步', async () => {
    matcherMock.mockResolvedValueOnce(state)
    const wrapper = mountView({ courseId: 'c1', modelValue: 'auto' })
    await flushPromises()
    await wrapper.get('select').setValue('name')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['name'])
    wrapper.unmount()
  })
})
