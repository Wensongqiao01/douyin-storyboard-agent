import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'landing', component: () => import('../views/LandingPage.vue') },
  { path: '/login', name: 'login', component: () => import('../views/LoginPage.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/DashboardPage.vue'), meta: { auth: true } },
  { path: '/result/:id', name: 'result', component: () => import('../views/ResultPage.vue'), meta: { auth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.auth && !token) {
    next('/login')
  } else if ((to.path === '/login' || to.path === '/') && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
