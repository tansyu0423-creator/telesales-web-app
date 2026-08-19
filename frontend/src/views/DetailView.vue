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
const audioPlayerRef = ref(null)

const sortedTranscripts = computed(() => {
  if (!record.value || !record.value.transcripts) return []
  return record.value.transcripts.slice().sort((a, b) => (a.start_time || 0) - (b.start_time || 0))
})

const seekAudioTo = (startTime, endTime = null) => {
  if (audioPlayerRef.value && typeof audioPlayerRef.value.seekToAndPlay === 'function') {
    audioPlayerRef.value.seekToAndPlay(startTime, endTime)
  }
}

const getTalkRatio = (transcripts) => {
  if (!transcripts || transcripts.length === 0) {
    return { salesRatio: 50, customerRatio: 50, salesDuration: 0, customerDuration: 0 }
  }
  let salesTime = 0
  let customerTime = 0
  transcripts.forEach(t => {
    const dur = Math.max(0, (t.end_time || 0) - (t.start_time || 0))
    if (t.speaker === 'Sales') {
      salesTime += dur
    } else {
      customerTime += dur
    }
  })
  const total = salesTime + customerTime
  if (total === 0) {
    return { salesRatio: 50, customerRatio: 50, salesDuration: 0, customerDuration: 0 }
  }
  const salesRatio = Math.round((salesTime / total) * 100)
  const customerRatio = 100 - salesRatio
  return {
    salesRatio,
    customerRatio,
    salesDuration: Math.round(salesTime),
    customerDuration: Math.round(customerTime)
  }
}

const getObjectionTags = (text, speaker) => {
  if (speaker !== 'Customer' || !text) return []
  const tags = []
  const t = text.toLowerCase()

  if (/高い|予算|コスト|費用|値引き|価格|金額|安く/.test(t)) {
    tags.push({ label: '💰 価格・コスト懸念', class: 'bg-amber-950/90 text-amber-300 border-amber-700/80' })
  }
  if (/検討|考え|持ち帰り|後で|時期|タイミング|追って/.test(t)) {
    tags.push({ label: '⏱ 検討・持ち帰り', class: 'bg-sky-950/90 text-sky-300 border-sky-700/80' })
  }
  if (/上司|役員|決裁|承認|相談|社長|部長|確認/.test(t)) {
    tags.push({ label: '👔 決裁・社内相談', class: 'bg-purple-950/90 text-purple-300 border-purple-700/80' })
  }
  if (/他社|比較|既存|競合|相見積|ツール|他/.test(t)) {
    tags.push({ label: '⚔️ 競合・他社比較', class: 'bg-orange-950/90 text-orange-300 border-orange-700/80' })
  }
  if (/難しい|合わない|不要|必要ない|足りない|ネック|不安/.test(t)) {
    tags.push({ label: '⚠️ ネック・不安点', class: 'bg-rose-950/90 text-rose-300 border-rose-700/80' })
  }
  return tags
}

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
    const hasTranscripts = record.value && record.value.transcripts && record.value.transcripts.length > 0
    const endpoint = hasTranscripts ? `/records/${recordId}/score` : `/records/${recordId}/pipeline`
    const res = await api.post(endpoint)
    if (res.data && res.data.task_id) {
      await pollTaskStatus(res.data.task_id)
    }
    await fetchRecordDetail()
  } catch (err) {
    alert(err.response?.data?.detail || err.message || 'AI解析に失敗しました')
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

const handleDeleteRecord = async () => {
  if (!confirm(`通話データ #${recordId} を完全に削除してもよろしいですか？\n※削除したデータおよび音声ファイル・AI解析結果は元に戻せません。`)) {
    return
  }
  isActionLoading.value = true
  try {
    await api.delete(`/records/${recordId}`)
    alert(`通話データ #${recordId} を削除しました。`)
    router.push('/')
  } catch (err) {
    alert(err.response?.data?.detail || err.message || '通話データの削除に失敗しました')
  } finally {
    isActionLoading.value = false
  }
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
        <button 
          @click="handleDeleteRecord" 
          class="px-3.5 py-2 bg-red-950/80 hover:bg-red-900 text-red-300 border border-red-800 rounded-xl text-xs font-bold transition-colors cursor-pointer disabled:opacity-50"
          :disabled="isActionLoading"
        >
          🗑️ データ削除
        </button>
      </div>
    </div>

    <!-- スケルトンローダーUI (loading === true) -->
    <div v-if="loading" class="space-y-6">
      <!-- ヘッダーカード スケルトン -->
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-6 shadow-xl animate-pulse space-y-4">
        <div class="flex justify-between items-center pb-4 border-b border-slate-700/60">
          <div class="h-6 bg-slate-700 rounded-lg w-48"></div>
          <div class="h-6 bg-slate-700 rounded-lg w-32"></div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="h-14 bg-slate-900/60 rounded-xl"></div>
          <div class="h-14 bg-slate-900/60 rounded-xl"></div>
          <div class="h-14 bg-slate-900/60 rounded-xl"></div>
          <div class="h-14 bg-slate-900/60 rounded-xl"></div>
        </div>
      </div>

      <!-- スコアリング ＆ AIサマリー スケルトン -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-6 animate-pulse flex flex-col items-center justify-center space-y-3">
          <div class="w-32 h-32 bg-slate-700/80 rounded-full"></div>
          <div class="h-5 bg-slate-700 rounded w-24"></div>
        </div>
        <div class="lg:col-span-2 bg-slate-800/60 border border-slate-700/60 rounded-2xl p-6 animate-pulse space-y-3">
          <div class="h-16 bg-slate-900/60 rounded-xl"></div>
          <div class="h-16 bg-slate-900/60 rounded-xl"></div>
          <div class="h-16 bg-slate-900/60 rounded-xl"></div>
        </div>
      </div>
    </div>

    <!-- エラー表示 (error) -->
    <div v-else-if="error" class="text-center py-12 bg-rose-950/60 border border-rose-800 rounded-2xl p-6 text-rose-100 shadow-xl space-y-4">
      <div class="w-12 h-12 rounded-full bg-rose-900/80 border border-rose-600 flex items-center justify-center mx-auto text-xl font-bold">
        ⚠️
      </div>
      <div>
        <h3 class="text-base font-bold mb-1">通話詳細データの取得に失敗しました</h3>
        <p class="text-xs text-rose-300 font-mono max-w-md mx-auto break-words">{{ error }}</p>
      </div>
      <div class="flex items-center justify-center gap-3 pt-2">
        <button @click="fetchRecordDetail" class="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-bold transition-all shadow-md cursor-pointer">
          🔄 再読み込み
        </button>
        <button @click="router.push('/')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 cursor-pointer">
          ← ダッシュボードへ戻る
        </button>
      </div>
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
          <CustomAudioPlayer ref="audioPlayerRef" :src="`http://localhost:8000/audio/${record.audio_file_path}`" />
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

      <!-- 対話時間割合 (Talk-to-Listen Ratio) メーターカード -->
      <div v-if="record.transcripts && record.transcripts.length > 0" class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 rounded-2xl p-5 shadow-xl space-y-3">
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div class="flex items-center gap-3">
            <h3 class="text-sm font-bold text-slate-200 flex items-center gap-2">
              <span>📊 対話割合 (Talk-to-Listen Ratio)</span>
            </h3>
            <span v-if="getTalkRatio(record.transcripts).salesRatio > 65" class="px-2.5 py-0.5 bg-amber-950 border border-amber-800 text-amber-300 text-xs font-bold rounded-full">
              ⚠️ 営業話しすぎ注意 (65%超)
            </span>
            <span v-else-if="getTalkRatio(record.transcripts).salesRatio < 35" class="px-2.5 py-0.5 bg-sky-950 border border-sky-800 text-sky-300 text-xs font-bold rounded-full">
              ℹ️ 顧客主導対話
            </span>
            <span v-else class="px-2.5 py-0.5 bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs font-bold rounded-full">
              ✨ 理想的な対話バランス (黄金比)
            </span>
          </div>

          <div class="font-mono text-xs text-slate-300">
            👔 営業: <strong class="text-sky-400 text-sm">{{ getTalkRatio(record.transcripts).salesRatio }}%</strong> ({{ getTalkRatio(record.transcripts).salesDuration }}秒) / 
            👤 顧客: <strong class="text-emerald-400 text-sm">{{ getTalkRatio(record.transcripts).customerRatio }}%</strong> ({{ getTalkRatio(record.transcripts).customerDuration }}秒)
          </div>
        </div>

        <div class="w-full h-3.5 bg-slate-950 rounded-full overflow-hidden flex border border-slate-700/80 p-0.5 shadow-inner">
          <div 
            class="h-full bg-gradient-to-r from-sky-500 to-blue-600 rounded-l-full transition-all duration-1000 flex items-center justify-center" 
            :style="{ width: `${getTalkRatio(record.transcripts).salesRatio}%` }"
          ></div>
          <div 
            class="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-r-full transition-all duration-1000 flex items-center justify-center" 
            :style="{ width: `${getTalkRatio(record.transcripts).customerRatio}%` }"
          ></div>
        </div>
      </div>

      <!-- フル対話ログ (クリックで音声連動再生) -->
      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 rounded-2xl p-6 shadow-xl space-y-4">
        <div class="flex justify-between items-center">
          <h3 class="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <span>💬 通話対話ログ (Pyannote 話者タイムライン)</span>
          </h3>
          <span class="text-xs text-sky-400 font-medium">💡 発話をクリックでその時間へジャンプ再生 (全 {{ record.transcripts.length }} 発話)</span>
        </div>

        <div v-if="record.transcripts.length === 0" class="text-center py-8 text-slate-500 text-xs italic">
          対話ログデータが存在しません。「AI解析」を実行してください。
        </div>

        <div v-else class="flex flex-col gap-3 max-h-[600px] overflow-y-auto pr-2">
          <div 
            v-for="t in sortedTranscripts" 
            :key="t.id" 
            @click="seekAudioTo(t.start_time, t.end_time)"
            :class="[
              'p-4 rounded-xl text-xs border leading-relaxed cursor-pointer transition-all hover:scale-[1.01] shadow-sm group',
              t.speaker === 'Sales' 
                ? 'self-start bg-sky-950/50 hover:bg-sky-900/70 border-sky-800/60 hover:border-sky-500 text-sky-100 max-w-[85%]' 
                : getObjectionTags(t.text, t.speaker).length > 0
                  ? 'self-end bg-amber-950/60 hover:bg-amber-900/80 border-amber-500/80 hover:border-amber-400 text-amber-100 max-w-[85%] ring-1 ring-amber-500/30'
                  : 'self-end bg-emerald-950/50 hover:bg-emerald-900/70 border-emerald-800/60 hover:border-emerald-500 text-emerald-100 max-w-[85%]'
            ]"
            title="クリックしてこの時間から音声再生"
          >
            <div class="flex justify-between items-center text-[11px] text-slate-400 mb-1.5 gap-4 flex-wrap">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-bold text-slate-200">
                  {{ t.speaker === 'Sales' ? '👔 営業担当者' : '👤 顧客' }}
                </span>
                <span 
                  v-for="(tag, idx) in getObjectionTags(t.text, t.speaker)" 
                  :key="idx"
                  :class="['px-2 py-0.5 text-[10px] font-bold border rounded-md shadow-xs flex items-center gap-0.5', tag.class]"
                >
                  {{ tag.label }}
                </span>
              </div>
              <span class="font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-700 group-hover:border-sky-500 group-hover:text-sky-300 transition-colors flex items-center gap-1">
                <span>▶ {{ t.start_time.toFixed(1) }}s</span>
                <span>- {{ t.end_time.toFixed(1) }}s</span>
              </span>
            </div>
            <div class="text-sm text-slate-100">{{ t.text }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
