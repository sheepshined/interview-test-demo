import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue') },
  { path: '/resume-upload', name: 'ResumeUpload', component: () => import('../views/ResumeUploadView.vue') },
  { path: '/job-matching', name: 'JobMatching', component: () => import('../views/JobMatchingView.vue') },
  { path: '/interview', name: 'Interview', component: () => import('../views/InterviewView.vue') },
  { path: '/choose-job', name: 'ChooseJob', component: () => import('../views/ChooseJobView.vue') },
  { path: '/summary/:reportId', name: 'Summary', component: () => import('../views/SummaryView.vue') },
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
