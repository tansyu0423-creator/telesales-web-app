import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import UploadView from '../views/UploadView.vue'
import DetailView from '../views/DetailView.vue'
import LoginView from '../views/LoginView.vue'
import SettingsView from '../views/SettingsView.vue'
import { useAuthStore } from '../stores/authStore'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/upload',
      name: 'upload',
      component: UploadView
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    },
    {
      path: '/records/:id',
      name: 'detail',
      component: DetailView
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/'
    }
  ]
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.name !== 'login' && !authStore.isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.name === 'login' && authStore.isAuthenticated) {
    next({ name: 'home' })
  } else {
    next()
  }
})

export default router