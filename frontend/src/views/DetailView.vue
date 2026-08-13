<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import CircularProgressGauge from '../components/CircularProgressGauge.vue'
import CustomAudioPlayer from '../components/CustomAudioPlayer.vue'

const route = useRoute()
const router = useRouter()
const recordId = route.params.id

const record = ref(null)
const loading = ref(true)
const error = ref('')
const isActionLoading = ref(false)

const fetchRecordDetail = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get(`/records/${recordId}`)
    record.value = res.data
  } catch (err) {
    console.error('Fetch record detail error:', err)
    error.value = err.response?.data?.detail || '通話詳細データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const handleTranscribe = async () => {
  isActionLoading.value = true
  try {
    const res = await api.post(`/records/${recordId}/transcribe`)
    if (res.data.task_id) {
      await pollTaskStatus(res.data.task_id)
    }
    await fetchRecordDetail()
  } catch (err) {
    alert(err.response?.data?.detail || err.message || '文字起こしに失敗しました')
  } finally {
    isActionLoading.value = false
  }
}

const handleAnalyze = async () => {
  isActionLoading.value = true
  try {
    const res = await api.post(`/records/${recordId}/score`)
    if (res.data.task_id) {
      await pollTaskStatus(res.data.task_id)
    }
    await fetchRecordDetail()
  } catch (err) {
    alert(err.response?.data?.detail || err.message || 'AIスコアリングに失敗しました')
  } finally {
    isActionLoading.value = false
  }
}

const pollTaskStatus = async (taskId) => {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/tasks/${taskId}`)
        if (res.data.status === 'SUCCESS') {
          clearInterval(interval)
          resolve(res.data.result)
        } else if (res.data.status === 'FAILURE') {
          clearInterval(interval)
          reject(new Error(res.data.error || 'タスク処理に失敗しました'))
        }
      } catch (err) {
        clearInterval(interval)
        reject(err)
      }
    }, 2000)
  })
}

const handleExportCsv = () => {
  window.open(`http://localhost:8000/records/${recordId}/export/csv`, '_blank')
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const isoStr = typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+') 
    ? `${dateStr}Z` 
    : dateStr
  return new Date(isoStr).toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getRankLabel = (rank) => {
  switch (rank) {
    case 'S': return '非常に有望'
    case 'A': return '有望'
    case 'B': return '検討中'
    case 'C': return '観察'
    case 'D': return '低可能性'
    case 'E': return '不可行'
    default: return ''
  }
}

const getRankBadgeClass = (rank) => {
  switch (rank) {
    case 'S': return 'bg-purple-600 text-white'
    case 'A': return 'bg-green-600 text-white'
    case 'B': return 'bg-blue-600 text-white'
    case 'C': return 'bg-yellow-500 text-slate-900'
    case 'D': return 'bg-orange-500 text-white'
    case 'E': return 'bg-red-600 text-white'
    default: return 'bg-slate-600 text-slate-200'
  }
}

onMounted(() => {
  fetchRecordDetail()
})
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 py-8 text-slate-100">
    <!-- ナビゲーションヘッダー -->
    <div class="flex items-center justify-between gap-4 mb-6">
      <button 
        @click="router.push('/')" 
        class="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-sm font-semibold border border-slate-700 transition-colors cursor-pointer"
      >
        ← ダッシュボードへ戻る
      </button>

      <div class="flex items-center gap-2">
        <button 
          @click="fetchRecordDetail" 
          class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition-colors cursor-pointer"
        >
          🔄 最新情報に更新
        </button>
        <button 
          @click="handleExportCsv" 
          class="px-3.5 py-2 bg-slate-900 hover:bg-slate-950 text-slate-300 border border-slate-700 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
        >
          📥 CSV出力
        </button>
      </div>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading" class="text-center py-20 bg-slate-800/40 rounded-2xl border border-slate-800">
      <div class="animate-pulse flex flex-col items-center gap-3">
        <span class="text-3xl">⏳</span>
        <span class="text-slate-400 font-medium">通話分析詳細データを読み込んでいます...</span>
      </div>
    </div>

    <!-- エラー状態 -->
    <div v-else-if="error" class="text-center py-16 bg-red-950/30 rounded-2xl border border-red-800/50 text-red-300 p-6">
      <p class="text-lg font-bold mb-2">⚠️ エラーが発生しました</p>
      <p class="text-sm mb-4">{{ error }}</p>
      <button @click="router.push('/')" class="px-4 py-2 bg-red-800 text-white rounded-lg text-sm font-semibold">一覧へ戻る</button>
    </div>

    <!-- 詳細コンテンツ -->
    <div v-else-if="record" class="flex flex-col gap-6">
      <!-- 基本情報ヘッダーカード -->
      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 rounded-2xl p-6 shadow-xl">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-4 border-b border-slate-700/60">
          <div>
            <div class="flex items-center gap-3 mb-1">
              <span class="font-mono bg-slate-900 px-3 py-1 rounded-md text-sky-400 font-bold border border-slate-700 text-sm">RECORD #{{ record.id }}</span>
              <h2 class="text-xl font-bold text-white">通話詳細・AIスコアリングレポート</h2>
            </div>
            <p class="text-xs text-slate-400 mt-1">登録日時: {{ formatDateTime(record.created_at) }}</p>
          </div>

          <div v-if="record.analysis" :class="['px-4 py-1.5 rounded-xl text-sm font-extrabold shadow-md', getRankBadgeClass(record.analysis.rank)]">
            {{ record.analysis.rank }}
          </div>
          <div v-else class="px-4 py-1.5 rounded-xl text-sm font-medium bg-slate-700 text-slate-400">
            未分析
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4 text-sm">
          <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-700/50">
            <span class="text-xs text-slate-400 block mb-0.5">👔 営業担当者コード</span>
            <span class="font-bold text-slate-200">{{ record.sales_code }}</span>
          </div>
          <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-700/50">
            <span class="text-xs text-slate-400 block mb-0.5">📞 顧客電話番号</span>
            <span class="font-bold text-slate-200">{{ record.customer_phone }}</span>
          </div>
          <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-700/50">
            <span class="text-xs text-slate-400 block mb-0.5">⏱️ 通話時間</span>
            <span class="font-bold text-slate-200">{{ record.call_duration }} 秒</span>
          </div>
        </div>

        <!-- 音声試聴プレイヤー -->
        <div v-if="record.audio_file_path" class="mt-4">
          <CustomAudioPlayer :src="`http://localhost:8000/audio/${record.audio_file_path}`" />
        </div>
      </div>

      <!-- AI スコアリング ＆ 成約可能性ゲージ -->
      <div v-if="record.analysis" class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 rounded-2xl p-6 shadow-xl space-y-6">
        <div class="flex flex-col sm:flex-row items-center gap-6 p-4 bg-slate-900/70 rounded-xl border border-slate-700/60">
          <CircularProgressGauge :probability="record.analysis.purchase_probability" :recordId="record.id" />

          <div>
            <h3 class="text-sm font-bold text-slate-400 uppercase tracking-wider mb-1">成約率</h3>
            <div class="text-lg font-bold">
              <span v-if="record.analysis.rank === 'S'" class="text-purple-400">非常に有望</span>
              <span v-else-if="record.analysis.rank === 'A'" class="text-emerald-400">有望</span>
              <span v-else-if="record.analysis.rank === 'B'" class="text-sky-400">検討中</span>
              <span v-else-if="record.analysis.rank === 'C'" class="text-yellow-400">観察</span>
              <span v-else-if="record.analysis.rank === 'D'" class="text-orange-400">低可能性</span>
              <span v-else-if="record.analysis.rank === 'E'" class="text-red-400">不可行</span>
              <span v-else class="text-slate-200">{{ getRankLabel(record.analysis.rank) }}</span>
            </div>
          </div>
        </div>

        <!-- AI 分析サマリー詳細カード -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="bg-slate-900/80 p-4 rounded-xl border-l-4 border-emerald-400 space-y-2">
            <h4 class="font-bold text-emerald-400 text-sm flex items-center gap-1.5">
              <span>💡 顧客の関心点</span>
            </h4>
            <p class="text-xs text-slate-300 leading-relaxed">{{ record.analysis.customer_interest }}</p>
          </div>

          <div class="bg-slate-900/80 p-4 rounded-xl border-l-4 border-amber-400 space-y-2">
            <h4 class="font-bold text-amber-400 text-sm flex items-center gap-1.5">
              <span>⚠️ 懸念点・反論ボトルネック</span>
            </h4>
            <p class="text-xs text-slate-300 leading-relaxed">{{ record.analysis.concerns }}</p>
          </div>

          <div class="bg-slate-900/80 p-4 rounded-xl border-l-4 border-sky-400 space-y-2">
            <h4 class="font-bold text-sky-400 text-sm flex items-center gap-1.5">
              <span>🚀 推奨アクション</span>
            </h4>
            <p class="text-xs text-slate-300 leading-relaxed">{{ record.analysis.recommended_action }}</p>
          </div>
        </div>
      </div>

      <!-- 未分析時のアクション誘導 -->
      <div v-else class="bg-slate-800/80 p-6 rounded-2xl border border-slate-700 text-center space-y-4">
        <p class="text-slate-300 font-medium">この通話データはまだAIスコアリング分析が完了していません。</p>
        <div class="flex justify-center gap-3">
          <button @click="handleAnalyze" :disabled="isActionLoading" class="px-5 py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-sky-600/20 transition-all cursor-pointer disabled:opacity-50">
            {{ isActionLoading ? '⏳ AI解析を実行中...' : '⚡ AI解析を実行' }}
          </button>
        </div>
      </div>

      <!-- フル対話ログ (話者識別: 営業 vs 顧客) -->
      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 rounded-2xl p-6 shadow-xl space-y-4">
        <div class="flex justify-between items-center">
          <h3 class="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <span>💬 通話対話ログ (Pyannote 話者タイムライン)</span>
          </h3>
          <span class="text-xs text-slate-400">全 {{ record.transcripts.length }} 発話</span>
        </div>

        <div v-if="record.transcripts.length === 0" class="text-center py-8 text-slate-500 text-xs italic">
          対話ログデータが存在しません。「AI解析」を実行してください。
        </div>

        <div v-else class="flex flex-col gap-3 max-h-[600px] overflow-y-auto pr-2">
          <div 
            v-for="t in record.transcripts" 
            :key="t.id" 
            :class="[
              'p-4 rounded-xl text-xs border leading-relaxed transition-all',
              t.speaker === 'Sales' 
                ? 'self-start bg-sky-950/50 border-sky-800/60 text-sky-100 max-w-[85%]' 
                : 'self-end bg-emerald-950/50 border-emerald-800/60 text-emerald-100 max-w-[85%]'
            ]"
          >
            <div class="flex justify-between items-center text-[11px] text-slate-400 mb-1.5 gap-4">
              <span class="font-bold text-slate-200">
                {{ t.speaker === 'Sales' ? '👔 営業担当者' : '👤 顧客' }}
              </span>
              <span class="font-mono text-slate-400 bg-slate-900/80 px-2 py-0.5 rounded border border-slate-700">
                ⏱ {{ t.start_time.toFixed(1) }}s - {{ t.end_time.toFixed(1) }}s
              </span>
            </div>
            <div class="text-sm text-slate-100">{{ t.text }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
