import { createRouter, createWebHistory } from 'vue-router'

export const sections = [
  { path: '/materials', label: '课程资料', shortLabel: '资料', group: 0, icon: 'document' },
  { path: '/graph', label: '知识图谱', shortLabel: '图谱', group: 0, icon: 'graph' },
  {
    path: '/questions',
    label: '提问热点',
    shortLabel: '提问',
    group: 1,
    icon: 'questions',
  },
  { path: '/qa', label: '课程答疑', shortLabel: '答疑', group: 1, icon: 'chat' },
  {
    path: '/quiz',
    label: '辅助出题',
    shortLabel: '出题',
    group: 1,
    icon: 'quiz',
  },
  {
    path: '/lessons',
    label: '备课提纲',
    shortLabel: '备课',
    group: 1,
    icon: 'lessons',
  },
  { path: '/coverage', label: '知识点覆盖', shortLabel: '覆盖', group: 2, icon: 'coverage' },
  { path: '/experiments', label: '模型实验', shortLabel: '实验', group: 2, icon: 'experiments' },
]

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', redirect: '/graph' },
    { path: '/materials', component: () => import('./views/MaterialsView.vue') },
    { path: '/graph', component: () => import('./views/GraphView.vue') },
    { path: '/questions', component: () => import('./views/QuestionsView.vue') },
    { path: '/qa', component: () => import('./views/QAView.vue') },
    { path: '/quiz', component: () => import('./views/TeachingView.vue'), props: { kind: 'quiz' } },
    {
      path: '/lessons',
      component: () => import('./views/TeachingView.vue'),
      props: { kind: 'lesson' },
    },
    { path: '/coverage', component: () => import('./views/CoverageView.vue') },
    { path: '/experiments', component: () => import('./views/ExperimentsView.vue') },
  ],
})
