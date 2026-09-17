import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue') },
  { path: '/resume-upload', name: 'ResumeUpload', component: () => import('../views/ResumeUploadView.vue') },
  { path: '/job-matching', name: 'JobMatching', component: () => import('../views/JobMatchingView.vue') },
  { path: '/interview', name: 'Interview', component: () => import('../views/InterviewView.vue') },
  { path: '/choose-job', name: 'ChooseJob', component: () => import('../views/ChooseJobView.vue') },
  { path: '/interview-records', name: 'InterviewRecords', component: () => import('../views/InterviewRecordsView.vue') },
  { path: '/summary/:reportId', name: 'Summary', component: () => import('../views/SummaryView.vue') },
  // 个人知识库 (v0.7)
  { path: '/knowledge', name: 'Knowledge', component: () => import('../views/knowledge/KnowledgeView.vue') },
  { path: '/knowledge/graph', name: 'KnowledgeGraph', component: () => import('../views/knowledge/GraphView.vue') },
  { path: '/knowledge/chat', name: 'KbChat', component: () => import('../views/knowledge/KbChatView.vue') },
  { path: '/knowledge/note/:id', name: 'NoteEditor', component: () => import('../views/knowledge/NoteEditorView.vue') },
  { path: '/knowledge/new', name: 'NoteNew', component: () => import('../views/knowledge/NoteEditorView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const authenticated = isAuthenticated()
  if (to.name !== 'Login' && !authenticated) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'Login' && authenticated) {
    return { name: 'Home' }
  }
  return true
})

export default router
