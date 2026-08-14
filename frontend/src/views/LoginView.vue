<template>
  <div class="min-h-screen w-full flex items-center justify-center bg-slate-950 text-slate-100 relative overflow-hidden px-4">
    <!-- 背景グラデーション・グローエフェクト -->
    <div class="absolute -top-40 -left-40 w-96 h-96 bg-sky-600/20 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-40 -right-40 w-96 h-96 bg-emerald-600/20 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

    <!-- メイン・ログインカード (ダークグラスモフィズム) -->
    <div class="relative w-full max-w-md bg-slate-900/85 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 shadow-2xl z-10 space-y-6">
      
      <!-- ブランドロゴ ＆ ヘッダー -->
      <div class="text-center space-y-2">
        <div class="inline-flex items-center gap-2 px-3 py-1 bg-sky-950/80 border border-sky-800/80 text-sky-400 text-xs font-bold rounded-full shadow-inner">
          <span class="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></span>
          AI Telesales Scoring System
        </div>
        <h1 class="text-2xl sm:text-3xl font-black tracking-tight text-white">
          アカウントログイン
        </h1>
        <p class="text-xs text-slate-400">
          テレセールス AI 分析ダッシュボードへアクセス
        </p>
      </div>

      <!-- エラーアラート表示 -->
      <div 
        v-if="errorMessage" 
        class="flex items-center gap-2.5 p-3.5 bg-red-950/80 border border-red-800/80 text-red-300 text-xs rounded-xl animate-shake"
      >
        <span class="text-base shrink-0">⚠️</span>
        <span class="font-medium">{{ errorMessage }}</span>
      </div>

      <!-- ログインフォーム -->
      <form @submit.prevent="handleLogin" class="space-y-4">
        <!-- ユーザー名入力欄 -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold text-slate-300">ユーザー名 (ID)</label>
          <div class="relative flex items-center">
            <span class="absolute left-3.5 text-slate-400 text-sm">👤</span>
            <input 
              v-model="username" 
              type="text" 
              placeholder="例: admin" 
              required
              class="w-full pl-10 pr-4 py-3 bg-slate-950/80 border border-slate-700/80 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 text-white placeholder-slate-500 rounded-xl text-sm transition-all outline-none"
            />
          </div>
        </div>

        <!-- パスワード入力欄 -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold text-slate-300">パスワード</label>
          <div class="relative flex items-center">
            <span class="absolute left-3.5 text-slate-400 text-sm">🔒</span>
            <input 
              v-model="password" 
              :type="showPassword ? 'text' : 'password'" 
              placeholder="例: password または telesales2026!" 
              required
              class="w-full pl-10 pr-10 py-3 bg-slate-950/80 border border-slate-700/80 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 text-white placeholder-slate-500 rounded-xl text-sm transition-all outline-none"
            />
            <button 
              type="button" 
              @click="showPassword = !showPassword"
              class="absolute right-3.5 text-slate-400 hover:text-slate-200 text-xs font-semibold"
            >
              {{ showPassword ? '隠す' : '表示' }}
            </button>
          </div>
        </div>

        <!-- ログイン実行ボタン -->
        <button 
          type="submit" 
          :disabled="isLoading"
          class="w-full py-3.5 px-4 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-sky-500/25 transition-all cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2 mt-2"
        >
          <span v-if="isLoading" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          <span>{{ isLoading ? '認証中...' : 'ログイン' }}</span>
        </button>
      </form>

      <!-- 1クリックデモアカウントログイン枠 -->
      <div class="pt-4 border-t border-slate-800 space-y-2.5">
        <div class="text-[11px] font-semibold text-slate-400 text-center">
          💡 デモアカウントでクイックテスト
        </div>
        <div class="grid grid-cols-3 gap-2">
          <button 
            @click="fillDemoAccount('admin')" 
            class="py-2 px-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-[11px] font-semibold text-sky-300 hover:text-sky-200 transition-all cursor-pointer text-center truncate"
          >
            👑 管理者
          </button>
          <button 
            @click="fillDemoAccount('sales')" 
            class="py-2 px-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-[11px] font-semibold text-emerald-300 hover:text-emerald-200 transition-all cursor-pointer text-center truncate"
          >
            👔 マネージャー
          </button>
          <button 
            @click="fillDemoAccount('rep101')" 
            class="py-2 px-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-[11px] font-semibold text-amber-300 hover:text-amber-200 transition-all cursor-pointer text-center truncate"
          >
            📞 営業担当
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')

const handleLogin = async () => {
  if (!username.value || !password.value) {
    errorMessage.value = 'ユーザー名とパスワードを入力してください。'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  const res = await authStore.login(username.value, password.value)
  isLoading.value = false

  if (res.success) {
    const redirectPath = route.query.redirect || '/'
    router.push(redirectPath)
  } else {
    errorMessage.value = res.message
  }
}

const fillDemoAccount = (roleKey) => {
  username.value = roleKey
  password.value = 'telesales2026!'
  errorMessage.value = ''
  handleLogin()
}
</script>
