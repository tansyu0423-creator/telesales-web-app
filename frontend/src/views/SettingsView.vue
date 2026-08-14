<template>
  <div class="w-full px-2 sm:px-4 py-4 text-slate-100 bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl space-y-6">
    <!-- ヘッダーバナー -->
    <header class="bg-gradient-to-r from-slate-900/95 via-slate-800/95 to-slate-900/95 border border-slate-700/80 rounded-2xl p-5 shadow-2xl backdrop-blur-md">
      <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="px-2.5 py-0.5 bg-sky-950 border border-sky-800 text-sky-300 text-xs font-bold rounded-full">System Administration</span>
          </div>
          <h2 class="text-2xl sm:text-3xl font-black tracking-tight text-white drop-shadow-md">
            システム環境設定・ユーザー管理
          </h2>
          <p class="text-xs sm:text-sm font-medium text-slate-300 mt-1.5">
            アカウント登録、LLM APIキー、およびAIスコアリングの判定閾値を管理
          </p>
        </div>
      </div>
    </header>

    <!-- トースト通知メッセージ -->
    <div 
      v-if="toastMessage" 
      :class="['p-4 rounded-xl border text-sm font-semibold transition-all flex items-center justify-between', toastType === 'success' ? 'bg-emerald-950/90 border-emerald-700 text-emerald-200' : 'bg-red-950/90 border-red-700 text-red-200']"
    >
      <span>{{ toastMessage }}</span>
      <button @click="toastMessage = ''" class="text-xs font-bold px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700">✕</button>
    </div>

    <!-- タブ切替ヘッダー -->
    <div class="flex border-b border-slate-800 space-x-4">
      <button 
        @click="activeTab = 'users'"
        :class="['pb-3 px-2 text-sm font-bold transition-all border-b-2 cursor-pointer flex items-center gap-2', activeTab === 'users' ? 'border-sky-500 text-sky-400 font-extrabold' : 'border-transparent text-slate-400 hover:text-slate-200']"
      >
        <span>👥</span>
        <span>ユーザー管理</span>
      </button>
      <button 
        @click="activeTab = 'ai'"
        :class="['pb-3 px-2 text-sm font-bold transition-all border-b-2 cursor-pointer flex items-center gap-2', activeTab === 'ai' ? 'border-sky-500 text-sky-400 font-extrabold' : 'border-transparent text-slate-400 hover:text-slate-200']"
      >
        <span>⚙️</span>
        <span>AI解析・評価基準設定</span>
      </button>
    </div>

    <!-- TAB 1: ユーザー管理 -->
    <div v-if="activeTab === 'users'" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- ユーザー追加フォーム -->
        <div class="bg-slate-900/85 backdrop-blur-md border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4">
          <h3 class="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <span>➕</span>
            <span>新規ユーザー登録</span>
          </h3>

          <form @submit.prevent="handleAddUser" class="space-y-3">
            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">ユーザーID (username)</label>
              <input 
                v-model="newUser.username" 
                type="text" 
                placeholder="例: sales102" 
                required
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none"
              />
            </div>

            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">表示名 (氏名)</label>
              <input 
                v-model="newUser.name" 
                type="text" 
                placeholder="例: 鈴木 一郎" 
                required
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none"
              />
            </div>

            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">役職・権限</label>
              <select 
                v-model="newUser.role" 
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none"
              >
                <option value="管理者">👑 管理者</option>
                <option value="マネージャー">👔 マネージャー</option>
                <option value="営業担当者">📞 営業担当者</option>
              </select>
            </div>

            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">パスワード</label>
              <input 
                v-model="newUser.password" 
                type="text" 
                placeholder="例: password2026!" 
                required
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none font-mono"
              />
            </div>

            <button 
              type="submit" 
              :disabled="isSubmittingUser"
              class="w-full py-2.5 px-4 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-xl text-xs shadow-md transition-all cursor-pointer disabled:opacity-50 mt-2"
            >
              {{ isSubmittingUser ? '登録中...' : 'ユーザーを登録' }}
            </button>
          </form>
        </div>

        <!-- 登録ユーザー一覧テーブル -->
        <div class="lg:col-span-2 bg-slate-900/85 backdrop-blur-md border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 class="text-base font-bold text-white flex items-center gap-2">
              <span>📋</span>
              <span>登録アカウント一覧</span>
            </h3>
            <span class="text-xs text-slate-400 font-mono">計 {{ users.length }} アカウント</span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="border-b border-slate-800 text-slate-400">
                  <th class="py-2.5 px-3">ユーザーID</th>
                  <th class="py-2.5 px-3">表示名</th>
                  <th class="py-2.5 px-3">役職</th>
                  <th class="py-2.5 px-3">パスワード</th>
                  <th class="py-2.5 px-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                <tr v-for="user in users" :key="user.username" class="hover:bg-slate-800/40">
                  <td class="py-3 px-3 font-mono font-bold text-slate-200">{{ user.username }}</td>
                  <td class="py-3 px-3 font-semibold text-white">{{ user.name }}</td>
                  <td class="py-3 px-3">
                    <span :class="['px-2 py-0.5 text-[11px] font-bold rounded-full border', getRoleBadgeStyle(user.role)]">
                      {{ user.role }}
                    </span>
                  </td>
                  <td class="py-3 px-3 font-mono text-slate-400">{{ user.passwords?.join(', ') || '-' }}</td>
                  <td class="py-3 px-3 text-right">
                    <button 
                      @click="handleDeleteUser(user.username)"
                      class="px-2 py-1 bg-red-950/80 hover:bg-red-900 border border-red-800 text-red-300 rounded-lg text-[11px] font-semibold cursor-pointer"
                      title="ユーザー削除"
                    >
                      🗑️ 削除
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: AI解析・評価基準設定 -->
    <div v-if="activeTab === 'ai'" class="space-y-6">
      <form @submit.prevent="handleSaveConfig" class="space-y-6">
        
        <!-- LLM APIキー ＆ プロバイダ設定 -->
        <div class="bg-slate-900/85 backdrop-blur-md border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4">
          <h3 class="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <span>🔑</span>
            <span>LLM プロバイダ ＆ APIキー設定</span>
          </h3>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">Gemini API Key</label>
              <input 
                v-model="config.gemini_api_key" 
                type="password" 
                placeholder="AIzaSy..." 
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none font-mono"
              />
            </div>

            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">Groq API Key</label>
              <input 
                v-model="config.groq_api_key" 
                type="password" 
                placeholder="gsk_..." 
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none font-mono"
              />
            </div>

            <div class="space-y-1">
              <label class="block text-xs font-semibold text-slate-300">OpenRouter API Key (Optional)</label>
              <input 
                v-model="config.openrouter_api_key" 
                type="password" 
                placeholder="sk-or-..." 
                class="w-full px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none font-mono"
              />
            </div>
          </div>

          <div class="pt-2">
            <label class="block text-xs font-semibold text-slate-300 mb-1">優先使用LLMプロバイダ</label>
            <select 
              v-model="config.llm_provider" 
              class="w-full sm:w-64 px-3 py-2 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none font-bold"
            >
              <option value="gemini">Google Gemini (推奨)</option>
              <option value="groq">Groq (Llama-3.3)</option>
              <option value="openrouter">OpenRouter</option>
            </select>
          </div>
        </div>

        <!-- ランク判定閾値設定 -->
        <div class="bg-slate-900/85 backdrop-blur-md border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4">
          <h3 class="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <span>🎯</span>
            <span>成約見込みランク (S〜E) 判定閾値設定 (%)</span>
          </h3>

          <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div class="p-3 bg-slate-950 border border-emerald-800/80 rounded-xl space-y-1.5 text-center">
              <span class="text-xs font-extrabold text-emerald-400 block">S ランク</span>
              <span class="text-[10px] text-slate-400 block">成約率 {{ config.rank_thresholds.s_rank }}% 以上</span>
              <input 
                v-model.number="config.rank_thresholds.s_rank" 
                type="number" 
                min="0" max="100" 
                class="w-full text-center py-1 bg-slate-900 border border-slate-700 text-white text-xs font-bold rounded"
              />
            </div>

            <div class="p-3 bg-slate-950 border border-sky-800/80 rounded-xl space-y-1.5 text-center">
              <span class="text-xs font-extrabold text-sky-400 block">A ランク</span>
              <span class="text-[10px] text-slate-400 block">成約率 {{ config.rank_thresholds.a_rank }}% 以上</span>
              <input 
                v-model.number="config.rank_thresholds.a_rank" 
                type="number" 
                min="0" max="100" 
                class="w-full text-center py-1 bg-slate-900 border border-slate-700 text-white text-xs font-bold rounded"
              />
            </div>

            <div class="p-3 bg-slate-950 border border-indigo-800/80 rounded-xl space-y-1.5 text-center">
              <span class="text-xs font-extrabold text-indigo-400 block">B ランク</span>
              <span class="text-[10px] text-slate-400 block">成約率 {{ config.rank_thresholds.b_rank }}% 以上</span>
              <input 
                v-model.number="config.rank_thresholds.b_rank" 
                type="number" 
                min="0" max="100" 
                class="w-full text-center py-1 bg-slate-900 border border-slate-700 text-white text-xs font-bold rounded"
              />
            </div>

            <div class="p-3 bg-slate-950 border border-amber-800/80 rounded-xl space-y-1.5 text-center">
              <span class="text-xs font-extrabold text-amber-400 block">C ランク</span>
              <span class="text-[10px] text-slate-400 block">成約率 {{ config.rank_thresholds.c_rank }}% 以上</span>
              <input 
                v-model.number="config.rank_thresholds.c_rank" 
                type="number" 
                min="0" max="100" 
                class="w-full text-center py-1 bg-slate-900 border border-slate-700 text-white text-xs font-bold rounded"
              />
            </div>

            <div class="p-3 bg-slate-950 border border-rose-800/80 rounded-xl space-y-1.5 text-center col-span-2 sm:col-span-1">
              <span class="text-xs font-extrabold text-rose-400 block">D ランク</span>
              <span class="text-[10px] text-slate-400 block">成約率 {{ config.rank_thresholds.d_rank }}% 以上</span>
              <input 
                v-model.number="config.rank_thresholds.d_rank" 
                type="number" 
                min="0" max="100" 
                class="w-full text-center py-1 bg-slate-900 border border-slate-700 text-white text-xs font-bold rounded"
              />
            </div>
          </div>
        </div>

        <!-- カスタムプロンプト指示 -->
        <div class="bg-slate-900/85 backdrop-blur-md border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-3">
          <h3 class="text-base font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <span>📝</span>
            <span>AI評価視点・カスタム指示文</span>
          </h3>

          <p class="text-xs text-slate-400">
            LLM分析実行時にプロンプトへ挿入する業界・自社固有の評価指針を指定します。
          </p>

          <textarea 
            v-model="config.custom_prompt_instructions" 
            rows="3" 
            placeholder="例: 顧客の予算感、導入時期、決裁権限者の有無を重視して評価を行ってください。"
            class="w-full p-3 bg-slate-950 border border-slate-700 focus:border-sky-500 text-white text-xs rounded-xl outline-none leading-relaxed"
          ></textarea>
        </div>

        <!-- 保存ボタン -->
        <div class="flex justify-end pt-2">
          <button 
            type="submit" 
            :disabled="isSavingConfig"
            class="px-6 py-3 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-sky-500/25 transition-all cursor-pointer disabled:opacity-50 flex items-center gap-2"
          >
            <span v-if="isSavingConfig" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            <span>{{ isSavingConfig ? '保存中...' : '設定を保存する' }}</span>
          </button>
        </div>
      </form>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000'
})

const activeTab = ref('users')
const users = ref([])
const isSubmittingUser = ref(false)

const newUser = ref({
  username: '',
  name: '',
  role: '営業担当者',
  password: ''
})

const config = ref({
  gemini_api_key: '',
  groq_api_key: '',
  openrouter_api_key: '',
  llm_provider: 'gemini',
  rank_thresholds: {
    s_rank: 90,
    a_rank: 70,
    b_rank: 50,
    c_rank: 30,
    d_rank: 10
  },
  custom_prompt_instructions: ''
})

const isSavingConfig = ref(false)
const toastMessage = ref('')
const toastType = ref('success')

const showToast = (msg, type = 'success') => {
  toastMessage.value = msg
  toastType.value = type
  setTimeout(() => {
    if (toastMessage.value === msg) {
      toastMessage.value = ''
    }
  }, 4000)
}

const fetchUsers = async () => {
  try {
    const res = await api.get('/settings/users')
    users.value = res.data
  } catch (err) {
    console.error('Fetch users error:', err)
  }
}

const fetchConfig = async () => {
  try {
    const res = await api.get('/settings/config')
    if (res.data) {
      config.value = {
        ...config.value,
        ...res.data,
        rank_thresholds: {
          ...config.value.rank_thresholds,
          ...(res.data.rank_thresholds || {})
        }
      }
    }
  } catch (err) {
    console.error('Fetch config error:', err)
  }
}

const handleAddUser = async () => {
  if (!newUser.value.username || !newUser.value.password || !newUser.value.name) {
    showToast('すべての項目を入力してください。', 'error')
    return
  }

  isSubmittingUser.value = true
  try {
    await api.post('/settings/users', newUser.value)
    showToast(`ユーザー「${newUser.value.name}」を登録しました。`)
    newUser.value = { username: '', name: '', role: '営業担当者', password: '' }
    await fetchUsers()
  } catch (err) {
    const detail = err.response?.data?.detail || 'ユーザー登録に失敗しました。'
    showToast(detail, 'error')
  } finally {
    isSubmittingUser.value = false
  }
}

const handleDeleteUser = async (username) => {
  if (!confirm(`ユーザー「${username}」を削除してもよろしいですか？`)) {
    return
  }

  try {
    await api.delete(`/settings/users/${username}`)
    showToast(`ユーザー「${username}」を削除しました。`)
    await fetchUsers()
  } catch (err) {
    showToast('ユーザー削除に失敗しました。', 'error')
  }
}

const handleSaveConfig = async () => {
  isSavingConfig.value = true
  try {
    await api.post('/settings/config', config.value)
    showToast('システム・AI設定を保存しました。')
  } catch (err) {
    showToast('設定の保存に失敗しました。', 'error')
  } finally {
    isSavingConfig.value = false
  }
}

const getRoleBadgeStyle = (role) => {
  switch (role) {
    case '管理者':
      return 'bg-purple-950 text-purple-300 border-purple-800'
    case 'マネージャー':
      return 'bg-emerald-950 text-emerald-300 border-emerald-800'
    default:
      return 'bg-sky-950 text-sky-300 border-sky-800'
  }
}

onMounted(() => {
  fetchUsers()
  fetchConfig()
})
</script>
