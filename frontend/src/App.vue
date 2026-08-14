<template>
  <div class="min-h-screen bg-slate-950 text-slate-100 font-sans">
    <!-- ヘッダー（ログイン画面以外、かつログイン時のみ表示） -->
    <header v-if="showNavigation" class="bg-slate-900/90 backdrop-blur-md shadow-md border-b border-slate-800 sticky top-0 z-40">
      <div class="w-full px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-16">
          
          <!-- ブランドロゴ ＆ ナビゲーションリンク -->
          <div class="flex items-center space-x-8">
            <RouterLink to="/" class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-sky-400 animate-pulse"></span>
              <h1 class="text-lg font-black text-white tracking-wide">AI Telesales Scoring</h1>
            </RouterLink>

            <nav class="hidden md:flex space-x-2">
              <RouterLink 
                to="/" 
                class="text-slate-300 hover:text-white px-3 py-2 rounded-lg text-sm font-semibold transition-all hover:bg-slate-800/80" 
                exact-active-class="text-sky-400 bg-sky-950/80 border border-sky-800/80 font-bold"
              >
                📊 ダッシュボード
              </RouterLink>
              <RouterLink 
                to="/upload" 
                class="text-slate-300 hover:text-white px-3 py-2 rounded-lg text-sm font-semibold transition-all hover:bg-slate-800/80" 
                exact-active-class="text-sky-400 bg-sky-950/80 border border-sky-800/80 font-bold"
              >
                🎙 音声アップロード
              </RouterLink>
              <RouterLink 
                to="/settings" 
                class="text-slate-300 hover:text-white px-3 py-2 rounded-lg text-sm font-semibold transition-all hover:bg-slate-800/80" 
                exact-active-class="text-sky-400 bg-sky-950/80 border border-sky-800/80 font-bold"
              >
                ⚙️ 設定
              </RouterLink>
            </nav>
          </div>

          <!-- データ更新 ＆ ログインユーザー情報 ＆ ログアウトボタン -->
          <div class="flex items-center gap-3">
            <button 
              v-if="isDashboard"
              @click="handleRefresh"
              :disabled="isRefreshing"
              class="flex items-center gap-1.5 px-3 py-1.5 bg-sky-900/80 hover:bg-sky-800/80 text-sky-200 border border-sky-700/80 hover:border-sky-500 rounded-xl text-xs font-semibold transition-all cursor-pointer disabled:opacity-50 shadow-sm"
              title="通話データを最新状態に更新"
            >
              <span :class="['inline-block transition-transform duration-500', isRefreshing ? 'animate-spin' : '']">🔄</span>
              <span>{{ isRefreshing ? '更新中...' : 'データ更新' }}</span>
            </button>

            <div v-if="authStore.user" class="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs">
              <span class="w-6 h-6 rounded-full bg-sky-900 border border-sky-700 text-sky-300 flex items-center justify-center font-bold">
                👤
              </span>
              <div class="flex flex-col">
                <span class="font-bold text-slate-200">{{ authStore.user.name }}</span>
                <span class="text-[10px] text-slate-400">{{ authStore.user.role }}</span>
              </div>
            </div>

            <button 
              @click="handleLogout"
              class="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-red-950/80 text-slate-300 hover:text-red-300 border border-slate-700 hover:border-red-800 rounded-xl text-xs font-semibold transition-all cursor-pointer shrink-0"
              title="ログアウト"
            >
              <span>🚪</span>
              <span>ログアウト</span>
            </button>
          </div>

        </div>
      </div>
    </header>

    <!-- メインコンテンツ -->
    <main :class="['w-full', showNavigation ? 'px-4 sm:px-6 lg:px-8 py-6' : 'p-0']">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/authStore'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isRefreshing = ref(false)

const showNavigation = computed(() => {
  return route.name !== 'login' && authStore.isAuthenticated
})

const isDashboard = computed(() => {
  return route.path === '/'
})

const handleRefresh = () => {
  isRefreshing.value = true
  window.dispatchEvent(new CustomEvent('trigger-dashboard-refresh'))
}

const handleRefreshFinished = () => {
  isRefreshing.value = false
}

onMounted(() => {
  window.addEventListener('dashboard-refresh-finished', handleRefreshFinished)
})

onUnmounted(() => {
  window.removeEventListener('dashboard-refresh-finished', handleRefreshFinished)
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>