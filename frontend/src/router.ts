import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/profile' },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { title: '个人档案', icon: 'User' } },
  { path: '/jobs', name: 'jobs', component: () => import('@/views/JobsView.vue'), meta: { title: '岗位库', icon: 'Briefcase' } },
  { path: '/analysis', name: 'analysis', component: () => import('@/views/AnalysisView.vue'), meta: { title: '匹配分析', icon: 'DataAnalysis' } },
  { path: '/resume', name: 'resume', component: () => import('@/views/ResumeView.vue'), meta: { title: '简历定制', icon: 'Document' } },
  { path: '/applications', name: 'applications', component: () => import('@/views/ApplicationsView.vue'), meta: { title: '投递记录', icon: 'Promotion' } },
  { path: '/library', name: 'library', component: () => import('@/views/LibraryView.vue'), meta: { title: '参考资料库', icon: 'Collection' } },
  { path: '/agent', name: 'agent', component: () => import('@/views/AgentView.vue'), meta: { title: '智能助手', icon: 'ChatDotRound' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || '智能求职'} - 智能选岗及简历定制 Agent`
})

export default router
