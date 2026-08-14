<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import axios from 'axios'
import CustomAudioPlayer from '../components/CustomAudioPlayer.vue'

const api = axios.create({
  baseURL: 'http://localhost:8000'
})

const records = ref([])
const loading = ref(true)
const isRefreshing = ref(false)
const selectedRank = ref('ALL')
const expandedRecordIds = ref(new Set())
const actionLoading = ref({})

const toggleRecordDetail = (id) => {
  if (expandedRecordIds.value.has(id)) {
    expandedRecordIds.value.delete(id)
  } else {
    expandedRecordIds.value.add(id)
  }
}

const isRecordDetailOpen = (id) => expandedRecordIds.value.has(id)

const expandAllDetails = () => {
  filteredRecords.value.forEach(r => expandedRecordIds.value.add(r.id))
}

const collapseAllDetails = () => {
  expandedRecordIds.value.clear()
}

const fetchRecords = async () => {
  if (records.value.length === 0) {
    loading.value = true
  }
  isRefreshing.value = true
  try {
    const res = await api.get('/records/')
    records.value = res.data
  } catch (err) {
    console.error('Fetch records error:', err)
  } finally {
    loading.value = false
    isRefreshing.value = false
  }
}

const searchQuery = ref('')
const sortBy = ref('date_desc')
const activeTab = ref('records') // 'records' | 'analytics'
const selectedSalesRep = ref('')
const viewMode = ref('table') // 'table' | 'card'

const kpiStats = computed(() => {
  const total = records.value.length
  if (total === 0) {
    return { total: 0, highProspectCount: 0, avgProbability: 0, analysisRate: 0 }
  }

  const analyzed = records.value.filter(r => r.analysis)
  const highProspectCount = analyzed.filter(r => r.analysis.rank === 'S' || r.analysis.rank === 'A').length
  const probSum = analyzed.reduce((sum, r) => sum + (r.analysis.purchase_probability || 0), 0)
  const avgProbability = analyzed.length > 0 ? Math.round(probSum / analyzed.length) : 0
  const analysisRate = Math.round((analyzed.length / total) * 100)

  return { total, highProspectCount, avgProbability, analysisRate }
})

// 営業担当者別の平均成約率・ランク獲得数集計
const salesRepStats = computed(() => {
  const map = {}

  records.value.forEach(r => {
    const code = r.sales_code || '未設定'
    if (!map[code]) {
      map[code] = {
        code,
        totalCalls: 0,
        analyzedCalls: 0,
        highProspectCount: 0,
        probSum: 0,
        rankCounts: { S: 0, A: 0, B: 0, C: 0, D: 0, E: 0 }
      }
    }

    map[code].totalCalls += 1

    if (r.analysis) {
      map[code].analyzedCalls += 1
      map[code].probSum += (r.analysis.purchase_probability || 0)
      const rank = r.analysis.rank
      if (rank === 'S' || rank === 'A') {
        map[code].highProspectCount += 1
      }
      if (map[code].rankCounts[rank] !== undefined) {
        map[code].rankCounts[rank] += 1
      }
    }
  })

  return Object.values(map).map(item => {
    const avgProbability = item.analyzedCalls > 0 ? Math.round(item.probSum / item.analyzedCalls) : 0
    return {
      ...item,
      avgProbability
    }
  }).sort((a, b) => b.avgProbability - a.avgProbability || b.totalCalls - a.totalCalls)
})

const filterBySalesRep = (code) => {
  selectedSalesRep.value = code
  activeTab.value = 'records'
}

const clearSalesRepFilter = () => {
  selectedSalesRep.value = ''
}

const filteredRecords = computed(() => {
  let list = [...records.value]

  // 1. 担当者絞り込み
  if (selectedSalesRep.value) {
    list = list.filter(r => r.sales_code === selectedSalesRep.value)
  }

  // 2. ランクフィルター
  if (selectedRank.value !== 'ALL') {
    list = list.filter(r => r.analysis && r.analysis.rank === selectedRank.value)
  }

  // 3. キーワード検索（営業コード・顧客電話番号）
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(r => 
      (r.sales_code && r.sales_code.toLowerCase().includes(q)) ||
      (r.customer_phone && r.customer_phone.toLowerCase().includes(q))
    )
  }

  // 4. ソート順
  if (sortBy.value === 'date_desc') {
    list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } else if (sortBy.value === 'date_asc') {
    list.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  } else if (sortBy.value === 'prob_desc') {
    list.sort((a, b) => ((b.analysis?.purchase_probability || 0) - (a.analysis?.purchase_probability || 0)))
  } else if (sortBy.value === 'rank_asc') {
    const rankOrder = { S: 1, A: 2, B: 3, C: 4, D: 5, E: 6 }
    list.sort((a, b) => (rankOrder[a.analysis?.rank] || 99) - (rankOrder[b.analysis?.rank] || 99))
  }

  return list
})

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
          reject(new Error(res.data.error || 'バックグラウンド処理に失敗しました'))
        }
      } catch (err) {
        clearInterval(interval)
        reject(err)
      }
    }, 2000)
  })
}

const handleTranscribe = async (recordId) => {
  actionLoading.value[`${recordId}_transcribe`] = true
  try {
    const res = await api.post(`/records/${recordId}/transcribe`)
    if (res.data.task_id) {
      await pollTaskStatus(res.data.task_id)
    }
    await fetchRecords()
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '文字起こしに失敗しました'
    alert(msg)
  } finally {
    actionLoading.value[`${recordId}_transcribe`] = false
  }
}

const handleAnalyze = async (recordId) => {
  actionLoading.value[`${recordId}_analyze`] = true
  try {
    const res = await api.post(`/records/${recordId}/score`)
    if (res.data.task_id) {
      await pollTaskStatus(res.data.task_id)
    }
    await fetchRecords()
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || 'AI分析に失敗しました。先に文字起こしを実行してください。'
    alert(msg)
  } finally {
    actionLoading.value[`${recordId}_analyze`] = false
  }
}

const handleExportCsv = (recordId) => {
  window.open(`http://localhost:8000/records/${recordId}/export/csv`, '_blank')
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  // DBのUTC日時文字列に'Z'を自動付与して日本時間 (JST / UTC+9) へ正確に変換
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

const getRankFilterButtonClass = (rank, isSelected) => {
  if (rank === 'ALL') {
    return isSelected
      ? 'bg-sky-500 text-slate-950 border-sky-400 font-bold shadow-md shadow-sky-500/20'
      : 'bg-slate-900/60 text-slate-400 border-slate-700 hover:border-slate-500 hover:text-slate-200'
  }
  
  if (isSelected) {
    switch (rank) {
      case 'S': return 'bg-purple-600 text-white border-purple-400 font-bold shadow-md shadow-purple-600/40 ring-2 ring-purple-400/50'
      case 'A': return 'bg-emerald-600 text-white border-emerald-400 font-bold shadow-md shadow-emerald-600/40 ring-2 ring-emerald-400/50'
      case 'B': return 'bg-sky-600 text-white border-sky-400 font-bold shadow-md shadow-sky-600/40 ring-2 ring-sky-400/50'
      case 'C': return 'bg-yellow-500 text-slate-950 border-yellow-300 font-bold shadow-md shadow-yellow-500/40 ring-2 ring-yellow-300/50'
      case 'D': return 'bg-orange-600 text-white border-orange-400 font-bold shadow-md shadow-orange-600/40 ring-2 ring-orange-400/50'
      case 'E': return 'bg-red-600 text-white border-red-400 font-bold shadow-md shadow-red-600/40 ring-2 ring-red-400/50'
      default: return 'bg-sky-500 text-slate-950 border-sky-400'
    }
  } else {
    switch (rank) {
      case 'S': return 'bg-purple-950/70 text-purple-300 border-purple-800/80 hover:bg-purple-900/80 hover:text-purple-100 hover:border-purple-600'
      case 'A': return 'bg-emerald-950/70 text-emerald-300 border-emerald-800/80 hover:bg-emerald-900/80 hover:text-emerald-100 hover:border-emerald-600'
      case 'B': return 'bg-sky-950/70 text-sky-300 border-sky-800/80 hover:bg-sky-900/80 hover:text-sky-100 hover:border-sky-600'
      case 'C': return 'bg-yellow-950/70 text-yellow-300 border-yellow-800/80 hover:bg-yellow-900/80 hover:text-yellow-100 hover:border-yellow-600'
      case 'D': return 'bg-orange-950/70 text-orange-300 border-orange-800/80 hover:bg-orange-900/80 hover:text-orange-100 hover:border-orange-600'
      case 'E': return 'bg-red-950/70 text-red-300 border-red-800/80 hover:bg-red-900/80 hover:text-red-100 hover:border-red-600'
      default: return 'bg-slate-900/60 text-slate-400 border-slate-700'
    }
  }
}

const gaugeAnimatedMap = ref({})
const gaugeValueMap = ref({})
const activeAnimationFrames = {}

const animateCountUp = (id, targetProbability) => {
  if (activeAnimationFrames[id]) {
    cancelAnimationFrame(activeAnimationFrames[id])
  }

  const duration = 3800 // 3.8秒でゆっくり優雅にアニメーション
  const startTime = performance.now()
  const target = Math.max(0, Math.min(100, Math.round(targetProbability || 0)))

  const step = (now) => {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    
    // SVGリングの cubic-bezier(0.16, 1, 0.3, 1) イージングと同期
    const easeProgress = 1 - Math.pow(1 - progress, 3)
    gaugeValueMap.value[id] = Math.round(easeProgress * target)

    if (progress < 1) {
      activeAnimationFrames[id] = requestAnimationFrame(step)
    } else {
      delete activeAnimationFrames[id]
    }
  }

  activeAnimationFrames[id] = requestAnimationFrame(step)
}

const handleScrollGaugeCheck = () => {
  const elements = document.querySelectorAll('[data-gauge-id]')
  const windowHeight = window.innerHeight || document.documentElement.clientHeight

  elements.forEach((el) => {
    const id = el.getAttribute('data-gauge-id')
    const probAttr = el.getAttribute('data-probability')
    if (!id) return

    const rect = el.getBoundingClientRect()
    // 画面視野内（画面中央付近）に入ったか判定
    const isVisible = rect.top <= windowHeight * 0.88 && rect.bottom >= 0

    if (isVisible) {
      // 画面内に進入した時、未アニメーションなら発火
      if (!gaugeAnimatedMap.value[id]) {
        gaugeAnimatedMap.value[id] = true
        const prob = parseFloat(probAttr || '0')
        animateCountUp(id, prob)
      }
    } else {
      // 画面外（画面の上または下）へ出た時、状態をリセット（再度画面内に入った時に再発火）
      if (gaugeAnimatedMap.value[id]) {
        gaugeAnimatedMap.value[id] = false
        gaugeValueMap.value[id] = 0
        if (activeAnimationFrames[id]) {
          cancelAnimationFrame(activeAnimationFrames[id])
          delete activeAnimationFrames[id]
        }
      }
    }
  })
}

onMounted(() => {
  fetchRecords()
  window.addEventListener('scroll', handleScrollGaugeCheck, { passive: true })
  setTimeout(handleScrollGaugeCheck, 300)
  setTimeout(handleScrollGaugeCheck, 600)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScrollGaugeCheck)
})
</script>

<template>
  <!-- テレセールス・アナリティクス・メインダッシュボード -->
  <div class="w-full max-w-[1600px] mx-auto px-2 sm:px-4 py-8 text-slate-100">
    <!-- 画面右上に常に固定配置される「データ更新」ボタン -->
    <button 
      @click="fetchRecords" 
      :disabled="isRefreshing"
      class="fixed top-5 right-6 z-50 flex items-center gap-2 px-4 py-2.5 bg-slate-800/90 hover:bg-slate-700/90 backdrop-blur-md border border-slate-600/80 text-white rounded-xl text-sm font-semibold shadow-xl hover:shadow-sky-500/20 transition-all cursor-pointer disabled:opacity-50"
    >
      <span :class="['inline-block transition-transform duration-500', isRefreshing ? 'animate-spin' : '']">🔄</span>
      <span>{{ isRefreshing ? '更新中...' : 'データ更新' }}</span>
    </button>

    <!-- エグゼクティブ・ヘッダーバナー (視認性向上 ＆ ダークグラスカード) -->
    <header class="bg-gradient-to-r from-slate-900/95 via-slate-800/95 to-slate-900/95 border border-slate-700/80 rounded-2xl p-5 shadow-2xl backdrop-blur-md mb-6">
      <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="px-2.5 py-0.5 bg-sky-950 border border-sky-800 text-sky-300 text-xs font-bold rounded-full">AI Analytics System</span>
          </div>
          <h2 class="text-2xl sm:text-3xl font-black tracking-tight text-white drop-shadow-md">
            テレセールス・アナリティクス・ダッシュボード
          </h2>
          <p class="text-xs sm:text-sm font-medium text-slate-300 mt-1.5 flex items-center gap-2">
            <span>✨ 通話データのAI解析 ・ 話者識別 ・ LLMスコアリング (S〜Eランク) 管理画面</span>
          </p>
        </div>
      </div>
    </header>

    <!-- KPI エグゼクティブ・サマリーカード -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 p-4 rounded-xl shadow-lg">
        <span class="text-xs font-semibold text-slate-400 block mb-1">📞 総通話データ数</span>
        <div class="flex items-baseline justify-between">
          <span class="text-2xl font-black text-white font-mono">{{ kpiStats.total }}</span>
          <span class="text-xs text-slate-400 font-medium">件</span>
        </div>
      </div>

      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 p-4 rounded-xl shadow-lg border-l-4 border-l-emerald-400">
        <span class="text-xs font-semibold text-emerald-400 block mb-1">🔥 高見込み (S/Aランク)</span>
        <div class="flex items-baseline justify-between">
          <span class="text-2xl font-black text-emerald-300 font-mono">{{ kpiStats.highProspectCount }}</span>
          <span class="text-xs text-emerald-400/80 font-medium">件</span>
        </div>
      </div>

      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 p-4 rounded-xl shadow-lg border-l-4 border-l-sky-400">
        <span class="text-xs font-semibold text-sky-400 block mb-1">📈 平均成約率</span>
        <div class="flex items-baseline justify-between">
          <span class="text-2xl font-black text-sky-300 font-mono">{{ kpiStats.avgProbability }}%</span>
          <span class="text-xs text-sky-400/80 font-medium">平均成約率</span>
        </div>
      </div>

      <div class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 p-4 rounded-xl shadow-lg border-l-4 border-l-purple-400">
        <span class="text-xs font-semibold text-purple-400 block mb-1">🤖 AI分析完了率</span>
        <div class="flex items-baseline justify-between">
          <span class="text-2xl font-black text-purple-300 font-mono">{{ kpiStats.analysisRate }}%</span>
          <span class="text-xs text-purple-400/80 font-medium">完了</span>
        </div>
      </div>
    </div>

    <!-- メインビュー切り替えタブ (通話一覧 vs 営業担当者別アナリティクス) -->
    <div class="flex items-center gap-2 mb-6 border-b border-slate-700/60 pb-3 flex-wrap">
      <button 
        @click="activeTab = 'records'" 
        :class="[
          'px-4 py-2 rounded-xl text-sm font-bold transition-all cursor-pointer flex items-center gap-2 border',
          activeTab === 'records'
            ? 'bg-sky-600 text-white border-sky-500 shadow-lg shadow-sky-600/20'
            : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
        ]"
      >
        <span>📋 通話データ一覧</span>
        <span v-if="filteredRecords.length" class="px-2 py-0.5 text-xs bg-slate-900/80 rounded-full font-mono text-sky-300">
          {{ filteredRecords.length }}
        </span>
      </button>

      <button 
        @click="activeTab = 'analytics'" 
        :class="[
          'px-4 py-2 rounded-xl text-sm font-bold transition-all cursor-pointer flex items-center gap-2 border',
          activeTab === 'analytics'
            ? 'bg-sky-600 text-white border-sky-500 shadow-lg shadow-sky-600/20'
            : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
        ]"
      >
        <span>👔 営業担当者別 パフォーマンス集計</span>
        <span class="px-2 py-0.5 text-xs bg-slate-900/80 rounded-full font-mono text-emerald-300">
          {{ salesRepStats.length }}名
        </span>
      </button>

      <!-- 担当者フィルターアクティブバッジ -->
      <div v-if="selectedSalesRep" class="ml-auto flex items-center gap-2 bg-sky-950/90 border border-sky-800 px-3 py-1.5 rounded-xl text-xs shadow-sm">
        <span class="text-slate-400">絞り込み中:</span>
        <span class="font-bold text-sky-300">👔 {{ selectedSalesRep }}</span>
        <button @click="clearSalesRepFilter" class="text-sky-400 hover:text-white font-bold ml-1 cursor-pointer">✖ 解除</button>
      </div>
    </div>

    <!-- 営業担当者別パフォーマンス集計ビュー -->
    <div v-if="activeTab === 'analytics'" class="space-y-4 mb-8">
      <div class="bg-slate-800/60 p-4 rounded-2xl border border-slate-700/60 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h3 class="text-sm font-bold text-slate-200 flex items-center gap-2">
            <span>🏆 営業担当者別 平均成約率 ＆ ランク実績ランキング</span>
          </h3>
          <p class="text-xs text-slate-400 mt-0.5">平均成約率が高い順にランキング表示しています。「この担当者の通話履歴を絞り込む」で通話ログへダイレクトにジャンプできます。</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div 
          v-for="(rep, index) in salesRepStats" 
          :key="rep.code" 
          class="bg-slate-800/80 backdrop-blur-md border border-slate-700/60 rounded-2xl p-5 shadow-xl hover:border-sky-500/50 transition-all flex flex-col justify-between"
        >
          <div>
            <div class="flex items-center justify-between gap-2 pb-3 border-b border-slate-700/50 mb-3">
              <div class="flex items-center gap-3">
                <span :class="[
                  'w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shadow-md',
                  index === 0 ? 'bg-amber-400 text-slate-950 font-black' :
                  index === 1 ? 'bg-slate-300 text-slate-950 font-black' :
                  index === 2 ? 'bg-amber-700 text-white font-black' :
                  'bg-slate-700 text-slate-300'
                ]">
                  {{ index === 0 ? '🥇1' : index === 1 ? '🥈2' : index === 2 ? '🥉3' : (index + 1) }}
                </span>
                <div>
                  <span class="text-xs text-slate-400 block">👔 営業担当者コード</span>
                  <span class="text-base font-bold text-white">{{ rep.code }}</span>
                </div>
              </div>

              <div class="text-right">
                <span class="text-xs text-slate-400 block">平均成約率</span>
                <span class="text-xl font-black text-sky-400 font-mono">{{ rep.avgProbability }}%</span>
              </div>
            </div>

            <!-- 成果インジケーター ＆ ランク内訳 -->
            <div class="space-y-3">
              <div>
                <div class="flex justify-between text-xs text-slate-400 mb-1">
                  <span>達成度メーター</span>
                  <span class="font-mono">{{ rep.avgProbability }} / 100%</span>
                </div>
                <div class="w-full h-2.5 bg-slate-900 rounded-full overflow-hidden border border-slate-700/60 p-0.5">
                  <div 
                    class="h-full bg-gradient-to-r from-sky-400 to-emerald-400 rounded-full transition-all duration-1000"
                    :style="{ width: `${rep.avgProbability}%` }"
                  ></div>
                </div>
              </div>

              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700/50">
                  <span class="text-slate-400 block text-[11px]">総通話件数</span>
                  <span class="font-bold text-white font-mono text-sm">{{ rep.totalCalls }} 件</span>
                </div>
                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700/50">
                  <span class="text-emerald-400 block text-[11px]">🔥 S/Aランク獲得</span>
                  <span class="font-bold text-emerald-300 font-mono text-sm">{{ rep.highProspectCount }} 件</span>
                </div>
              </div>

              <!-- 獲得ランク内訳バッジ -->
              <div class="flex items-center gap-1.5 flex-wrap pt-1">
                <span class="text-[11px] text-slate-400 mr-1">獲得ランク実績:</span>
                <span v-if="rep.rankCounts.S > 0" class="px-2 py-0.5 bg-purple-950 border border-purple-800 text-purple-300 text-[11px] font-bold rounded-md">非常に有望 ×{{ rep.rankCounts.S }}</span>
                <span v-if="rep.rankCounts.A > 0" class="px-2 py-0.5 bg-green-950 border border-green-800 text-green-300 text-[11px] font-bold rounded-md">有望 ×{{ rep.rankCounts.A }}</span>
                <span v-if="rep.rankCounts.B > 0" class="px-2 py-0.5 bg-blue-950 border border-blue-800 text-blue-300 text-[11px] font-bold rounded-md">検討中 ×{{ rep.rankCounts.B }}</span>
                <span v-if="rep.rankCounts.C > 0" class="px-2 py-0.5 bg-yellow-950 border border-yellow-800 text-yellow-300 text-[11px] font-bold rounded-md">観察 ×{{ rep.rankCounts.C }}</span>
                <span v-if="rep.rankCounts.D > 0" class="px-2 py-0.5 bg-orange-950 border border-orange-800 text-orange-300 text-[11px] font-bold rounded-md">低可能性 ×{{ rep.rankCounts.D }}</span>
                <span v-if="rep.rankCounts.E > 0" class="px-2 py-0.5 bg-red-950 border border-red-800 text-red-300 text-[11px] font-bold rounded-md">不可行 ×{{ rep.rankCounts.E }}</span>
              </div>
            </div>
          </div>

          <button 
            @click="filterBySalesRep(rep.code)" 
            class="mt-4 w-full py-2 bg-slate-900 hover:bg-slate-950 border border-slate-700 hover:border-sky-500 text-sky-400 hover:text-sky-300 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1.5"
          >
            <span>🔍 この担当者の通話履歴を絞り込む</span>
            <span>➔</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 通話データ一覧ビュー (activeTab === 'records' の時のみ表示) -->
    <div v-show="activeTab === 'records'">
      <!-- 検索バー ＆ ソート ＆ ランクフィルターツールバー -->
      <div class="bg-slate-800/60 p-4 rounded-2xl border border-slate-700/60 mb-6 space-y-3">
        <div class="flex flex-col md:flex-row items-center gap-3">
          <!-- 検索バー -->
          <div class="relative flex-1 w-full">
            <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">🔍</span>
            <input 
              v-model="searchQuery" 
              type="text" 
              placeholder="営業コード (例: REP-101) または電話番号で検索..."
              class="w-full pl-9 pr-4 py-2 bg-slate-900/80 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
            />
          </div>

          <!-- ソート順選択 -->
          <div class="flex items-center gap-2 w-full md:w-auto shrink-0">
            <span class="text-xs font-semibold text-slate-400 shrink-0">並び順:</span>
            <select 
              v-model="sortBy" 
              class="w-full md:w-auto px-3 py-2 bg-slate-900/80 border border-slate-700 rounded-xl text-xs font-semibold text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
            >
              <option value="date_desc">📅 登録日時 (新しい順)</option>
              <option value="date_asc">📅 登録日時 (古い順)</option>
              <option value="prob_desc">⚡ 成約確率 (高い順)</option>
              <option value="rank_asc">🏆 顧客ランク (S➔E順)</option>
            </select>
          </div>
        </div>

        <div class="flex items-center justify-between gap-2 pt-2 border-t border-slate-700/50 flex-wrap">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-semibold text-slate-400 mr-1 uppercase tracking-wider">ランク絞り込み:</span>
            <button 
              v-for="rank in ['ALL', 'S', 'A', 'B', 'C', 'D', 'E']" 
              :key="rank"
              :class="[
                'px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer border',
                getRankFilterButtonClass(rank, selectedRank === rank)
              ]"
              @click="selectedRank = rank"
            >
              {{ rank === 'ALL' ? 'すべて' : `${rank}：${getRankLabel(rank)}` }}
            </button>
          </div>

          <!-- 表示モード切替（テーブル ⇄ カード） -->
          <div class="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-slate-700/80 shrink-0">
            <button 
              @click="viewMode = 'table'"
              :class="[
                'px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5',
                viewMode === 'table' ? 'bg-sky-500 text-slate-950 shadow-md font-extrabold' : 'text-slate-400 hover:text-slate-200'
              ]"
            >
              <span>📊</span>
              <span>テーブル</span>
            </button>
            <button 
              @click="viewMode = 'card'"
              :class="[
                'px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5',
                viewMode === 'card' ? 'bg-sky-500 text-slate-950 shadow-md font-extrabold' : 'text-slate-400 hover:text-slate-200'
              ]"
            >
              <span>🎴</span>
              <span>カード</span>
            </button>
          </div>
        </div>
      </div>

      <!-- ローディング ＆ 該当データなし -->
      <div v-if="loading && records.length === 0" class="text-center py-12 bg-slate-800/30 rounded-2xl border border-slate-800 text-slate-400">
        <div class="animate-pulse flex flex-col items-center gap-2">
          <span>通話データを読み込んでいます...</span>
        </div>
      </div>
      <div v-else-if="filteredRecords.length === 0" class="text-center py-12 bg-slate-800/30 rounded-2xl border border-slate-800 text-slate-400">
        該当する通話データが存在しません。
      </div>

      <!-- 1. テーブル（表）形式表示 (viewMode === 'table') -->
      <div v-else-if="viewMode === 'table'" class="overflow-x-auto rounded-2xl border border-slate-700/60 bg-slate-800/80 backdrop-blur-sm shadow-xl">
        <table class="w-full text-left text-xs border-collapse min-w-[900px]">
          <thead>
            <tr class="bg-slate-900/90 border-b border-slate-700/80 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
              <th class="py-3.5 px-3 text-center w-12">開閉</th>
              <th class="py-3.5 px-4 font-mono">#ID</th>
              <th class="py-3.5 px-4">📅 登録日時</th>
              <th class="py-3.5 px-4">👔 営業担当</th>
              <th class="py-3.5 px-4">📞 顧客電話番号</th>
              <th class="py-3.5 px-4">⏱ 通話時間</th>
              <th class="py-3.5 px-4">🏆 顧客ランク</th>
              <th class="py-3.5 px-4">⚡ 成約率</th>
              <th class="py-3.5 px-4 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/50">
            <template v-for="record in filteredRecords" :key="record.id">
              <tr 
                @click="toggleRecordDetail(record.id)"
                class="hover:bg-slate-700/40 transition-colors cursor-pointer group"
              >
                <!-- 開閉ボタン (最左列) -->
                <td class="py-3.5 px-3 text-center">
                  <button 
                    @click.stop="toggleRecordDetail(record.id)"
                    :class="[
                      'w-7 h-7 inline-flex items-center justify-center rounded-lg text-xs font-bold transition-all border cursor-pointer',
                      isRecordDetailOpen(record.id) 
                        ? 'bg-sky-500 text-slate-950 border-sky-400 font-black shadow-md' 
                        : 'bg-slate-900/80 text-slate-400 border-slate-700 group-hover:border-slate-500 group-hover:text-slate-200'
                    ]"
                    :title="isRecordDetailOpen(record.id) ? '詳細を閉じる' : '詳細を開く'"
                  >
                    {{ isRecordDetailOpen(record.id) ? '▲' : '▼' }}
                  </button>
                </td>
                <!-- ID -->
                <td class="py-3.5 px-4 font-mono">
                  <span class="bg-slate-900 px-2 py-0.5 rounded text-sky-400 font-bold border border-slate-700">#{{ record.id }}</span>
                </td>
                <!-- 登録日時 -->
                <td class="py-3.5 px-4 font-mono text-slate-300 whitespace-nowrap">
                  {{ formatDateTime(record.created_at) }}
                </td>
                <!-- 営業担当コード -->
                <td class="py-3.5 px-4 font-bold text-white whitespace-nowrap">
                  👔 {{ record.sales_code }}
                </td>
                <!-- 顧客電話番号 -->
                <td class="py-3.5 px-4 text-slate-200 font-mono whitespace-nowrap">
                  {{ record.customer_phone }}
                </td>
                <!-- 通話時間 -->
                <td class="py-3.5 px-4 text-slate-300 font-mono whitespace-nowrap">
                  {{ record.call_duration }} 秒
                </td>
                <!-- ランクバッジ -->
                <td class="py-3.5 px-4 whitespace-nowrap">
                  <span v-if="record.analysis" :class="['px-2.5 py-1 rounded text-xs font-black inline-block shadow-sm', getRankBadgeClass(record.analysis.rank)]">
                    {{ record.analysis.rank }}：{{ getRankLabel(record.analysis.rank) }}
                  </span>
                  <span v-else class="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-400">
                    未分析
                  </span>
                </td>
                <!-- 成約率 (カードと完全同一の拡大円形アニメーションゲージ) -->
                <td class="py-3.5 px-4 whitespace-nowrap">
                  <div v-if="record.analysis" class="flex items-center gap-2">
                    <div 
                      :data-gauge-id="`t-${record.id}`"
                      :data-probability="record.analysis.purchase_probability"
                      class="relative flex items-center justify-center w-12 h-12 shrink-0 bg-slate-950 rounded-full border border-slate-800 p-0.5 shadow-md"
                    >
                      <svg class="w-full h-full -rotate-90" viewBox="0 0 64 64">
                        <circle cx="32" cy="32" r="25" stroke="#334155" stroke-width="5" fill="none" />
                        <circle
                          cx="32"
                          cy="32"
                          r="25"
                          :stroke="`url(#gradient-t-${record.id})`"
                          stroke-width="5"
                          stroke-linecap="round"
                          fill="none"
                          stroke-dasharray="157.08"
                          :stroke-dashoffset="gaugeAnimatedMap[`t-${record.id}`] ? (157.08 - (157.08 * (record.analysis.purchase_probability || 0) / 100)) : 157.08"
                          style="transition: stroke-dashoffset 3.8s cubic-bezier(0.16, 1, 0.3, 1);"
                        />
                        <defs>
                          <linearGradient :id="`gradient-t-${record.id}`" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stop-color="#38bdf8" />
                            <stop offset="100%" stop-color="#34d399" />
                          </linearGradient>
                        </defs>
                      </svg>
                      <div class="absolute inset-0 flex items-center justify-center">
                        <span class="text-xs font-black text-white font-mono">
                          {{ gaugeValueMap[`t-${record.id}`] || 0 }}%
                        </span>
                      </div>
                    </div>
                  </div>
                  <span v-else class="text-slate-500 font-mono text-[11px]">-</span>
                </td>
                <!-- アクション操作ボタン -->
                <td class="py-3.5 px-4 text-right whitespace-nowrap" @click.stop>
                  <div class="flex items-center justify-end gap-1.5">
                    <button 
                      v-if="!record.analysis"
                      @click="handleAnalyze(record.id)" 
                      class="px-2 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded-lg font-semibold disabled:opacity-50 cursor-pointer text-xs"
                      :disabled="actionLoading[`${record.id}_analyze`]"
                    >
                      {{ actionLoading[`${record.id}_analyze`] ? '⏳ 解析中' : '⚡ AI解析' }}
                    </button>
                    <button 
                      @click="handleExportCsv(record.id)" 
                      class="px-2 py-1 bg-slate-900/80 hover:bg-slate-900 text-slate-300 border border-slate-700 hover:border-slate-600 rounded-lg font-semibold cursor-pointer text-xs"
                      title="CSVレポート出力"
                    >
                      📥 CSV
                    </button>
                    <button 
                      @click="toggleRecordDetail(record.id)"
                      :class="[
                        'px-2 py-1 font-semibold rounded-lg transition-all cursor-pointer border text-xs',
                        isRecordDetailOpen(record.id) 
                          ? 'bg-sky-500 text-slate-950 border-sky-400 font-bold' 
                          : 'bg-slate-900/60 text-slate-300 border-slate-700 hover:text-white'
                      ]"
                    >
                      {{ isRecordDetailOpen(record.id) ? '非表示 ▲' : '表示 ▼' }}
                    </button>
                    <button 
                      @click="$router.push(`/records/${record.id}`)"
                      class="px-2.5 py-1 bg-sky-950/90 hover:bg-sky-900/90 text-sky-300 hover:text-sky-200 border border-sky-800/80 hover:border-sky-600 rounded-lg font-bold transition-all cursor-pointer inline-flex items-center gap-0.5 shadow-sm text-xs"
                    >
                      <span>詳細画面</span>
                      <span>↗</span>
                    </button>
                  </div>
                </td>
              </tr>
              <!-- 行拡張アコーディオン詳細 -->
              <tr v-if="isRecordDetailOpen(record.id)" class="bg-slate-900/60">
                <td colspan="9" class="p-4 border-b border-slate-700/60">
                  <div class="flex flex-col gap-3.5 w-full max-w-full overflow-hidden">
                    <div v-if="record.audio_file_path" class="flex items-center gap-3 w-full max-w-2xl">
                      <CustomAudioPlayer :src="`http://localhost:8000/audio/${record.audio_file_path}`" />
                    </div>
                    <!-- AI分析サマリー (3ブロック構成) -->
                    <div v-if="record.analysis" class="grid grid-cols-1 md:grid-cols-3 gap-3 border border-slate-700/40 rounded-xl p-3 bg-slate-950/60 w-full">
                      <div class="bg-slate-900/90 p-3 rounded-lg border-l-4 border-emerald-400 space-y-1">
                        <h4 class="font-bold text-emerald-400 text-xs flex items-center gap-1">
                          <span>💡 顧客の関心点</span>
                        </h4>
                        <p class="text-xs text-slate-300 leading-relaxed break-words">{{ record.analysis.customer_interest }}</p>
                      </div>
                      <div class="bg-slate-900/90 p-3 rounded-lg border-l-4 border-amber-400 space-y-1">
                        <h4 class="font-bold text-amber-400 text-xs flex items-center gap-1">
                          <span>⚠️ 懸念点・反論ボトルネック</span>
                        </h4>
                        <p class="text-xs text-slate-300 leading-relaxed break-words">{{ record.analysis.concerns }}</p>
                      </div>
                      <div class="bg-slate-900/90 p-3 rounded-lg border-l-4 border-sky-400 space-y-1">
                        <h4 class="font-bold text-sky-400 text-xs flex items-center gap-1">
                          <span>🚀 推奨アクション</span>
                        </h4>
                        <p class="text-xs text-slate-300 leading-relaxed break-words">{{ record.analysis.recommended_action }}</p>
                      </div>
                    </div>
                    <!-- 話者対話ログ -->
                    <div class="space-y-2 w-full">
                      <h4 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">💬 対話ログ (話者識別: 営業 vs 顧客)</h4>
                      <div v-if="record.transcripts.length === 0" class="text-xs text-slate-500 italic py-1">
                        対話ログデータが存在しません。「AI解析」を実行してください。
                      </div>
                      <div v-else class="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1 w-full">
                        <div 
                          v-for="t in record.transcripts" 
                          :key="t.id" 
                          :class="[
                            'p-2.5 rounded-lg max-w-[85%] md:max-w-[70%] text-xs border leading-relaxed break-words',
                            t.speaker === 'Sales' 
                              ? 'self-start bg-sky-950/40 border-sky-800/50 text-sky-100' 
                              : 'self-end bg-emerald-950/40 border-emerald-800/50 text-emerald-100'
                          ]"
                        >
                          <div class="flex justify-between items-center text-[10px] text-slate-400 mb-0.5 gap-2">
                            <span class="font-bold text-slate-200">{{ t.speaker === 'Sales' ? '👔 営業担当者' : '👤 顧客' }}</span>
                            <span class="font-mono text-slate-500">{{ t.start_time.toFixed(1) }}s - {{ t.end_time.toFixed(1) }}s</span>
                          </div>
                          <div class="break-words">{{ t.text }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 2. メイソンリー（段組み・空隙自動埋め）カード表示 (viewMode === 'card') -->
      <div v-else class="columns-1 md:columns-2 lg:columns-3 gap-4 space-y-4">
        <div 
          v-for="record in filteredRecords" 
          :key="record.id" 
          class="break-inside-avoid bg-slate-800/80 backdrop-blur-sm border border-slate-700/60 rounded-xl p-4 shadow-lg hover:border-slate-500 transition-all flex flex-col justify-between mb-4"
        >
          <div class="space-y-3">
            <!-- 1. ヘッダー: ID・担当者コード ＆ ランクバッジ -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-700/50">
              <div class="flex items-center gap-2">
                <span class="font-mono bg-slate-900 px-2 py-0.5 rounded text-sky-400 font-bold border border-slate-700 text-xs">#{{ record.id }}</span>
                <span class="font-bold text-white text-xs">👔 {{ record.sales_code }}</span>
              </div>

              <div v-if="record.analysis" :class="['px-2.5 py-0.5 rounded text-xs font-black shadow-sm', getRankBadgeClass(record.analysis.rank)]">
                {{ record.analysis.rank }}
              </div>
              <div v-else class="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-400">
                未分析
              </div>
            </div>

            <!-- 2. 基本メタ情報リスト (電話番号・通話時間・日時) -->
            <div class="space-y-1.5 text-xs">
              <div class="flex items-center justify-between text-slate-300">
                <span class="text-slate-400">📞 顧客電話番号:</span>
                <span class="font-semibold text-slate-200">{{ record.customer_phone }}</span>
              </div>
              <div class="flex items-center justify-between text-slate-300">
                <span class="text-slate-400">⏱ 通話時間:</span>
                <span class="font-semibold text-slate-200">{{ record.call_duration }} 秒</span>
              </div>
              <div class="flex items-center justify-between font-mono text-[11px] text-slate-400">
                <span>📅 登録日時:</span>
                <span class="text-slate-300">{{ formatDateTime(record.created_at) }}</span>
              </div>
            </div>

            <!-- 3. スコアリング ＆ スクロール伸長式円形ゲージ ＆ 見込み判定 -->
            <div v-if="record.analysis" class="p-3 bg-slate-900/70 rounded-xl border border-slate-700/60 flex items-center gap-3.5">
              <!-- 64px 拡大円形ゲージ -->
              <div 
                :data-gauge-id="record.id"
                :data-probability="record.analysis.purchase_probability"
                class="relative flex items-center justify-center w-16 h-16 shrink-0 bg-slate-950 rounded-full border border-slate-800 p-0.5 shadow-md"
              >
                <svg class="w-full h-full -rotate-90" viewBox="0 0 64 64">
                  <circle cx="32" cy="32" r="25" stroke="#334155" stroke-width="5" fill="none" />
                  <circle
                    cx="32"
                    cy="32"
                    r="25"
                    :stroke="`url(#gradient-${record.id})`"
                    stroke-width="5"
                    stroke-linecap="round"
                    fill="none"
                    stroke-dasharray="157.08"
                    :stroke-dashoffset="gaugeAnimatedMap[record.id] ? (157.08 - (157.08 * (record.analysis.purchase_probability || 0) / 100)) : 157.08"
                    style="transition: stroke-dashoffset 3.8s cubic-bezier(0.16, 1, 0.3, 1);"
                  />
                  <defs>
                    <linearGradient :id="`gradient-${record.id}`" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#38bdf8" />
                      <stop offset="100%" stop-color="#34d399" />
                    </linearGradient>
                  </defs>
                </svg>
                <div class="absolute inset-0 flex items-center justify-center">
                  <span class="text-sm font-black text-white font-mono">
                    {{ gaugeValueMap[record.id] || 0 }}%
                  </span>
                </div>
              </div>

              <div class="space-y-0.5">
                <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">成約率</div>
                <div class="text-xs font-bold">
                  <span v-if="record.analysis.rank === 'S'" class="text-purple-400">非常に有望</span>
                  <span v-else-if="record.analysis.rank === 'A'" class="text-emerald-400">有望</span>
                  <span v-else-if="record.analysis.rank === 'B'" class="text-sky-400">検討中</span>
                  <span v-else-if="record.analysis.rank === 'C'" class="text-yellow-400">観察</span>
                  <span v-else-if="record.analysis.rank === 'D'" class="text-orange-400">低可能性</span>
                  <span v-else-if="record.analysis.rank === 'E'" class="text-red-400">不可行</span>
                  <span v-else class="text-slate-300">{{ getRankLabel(record.analysis.rank) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 4. ボタン操作バー -->
          <div class="flex items-center gap-1.5 pt-2.5 mt-3 border-t border-slate-700/60 text-xs">
            <button 
              v-if="!record.analysis"
              @click="handleAnalyze(record.id)" 
              class="px-2 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded-lg font-semibold disabled:opacity-50 cursor-pointer"
              :disabled="actionLoading[`${record.id}_analyze`]"
            >
              {{ actionLoading[`${record.id}_analyze`] ? '⏳ 解析中' : '⚡ AI解析' }}
            </button>

            <button 
              @click="handleExportCsv(record.id)" 
              class="px-2 py-1 bg-slate-900/80 hover:bg-slate-900 text-slate-300 border border-slate-700 hover:border-slate-600 rounded-lg font-semibold cursor-pointer"
              title="CSVレポート出力"
            >
              📥 CSV
            </button>

            <button 
              @click="toggleRecordDetail(record.id)"
              :class="[
                'px-2 py-1 font-semibold rounded-lg transition-all cursor-pointer border',
                isRecordDetailOpen(record.id) 
                  ? 'bg-slate-700 text-white border-slate-600' 
                  : 'bg-slate-900/60 text-slate-300 border-slate-700 hover:text-white'
              ]"
            >
              {{ isRecordDetailOpen(record.id) ? '非表示 ▲' : '表示 ▼' }}
            </button>

            <button 
              @click="$router.push(`/records/${record.id}`)"
              class="ml-auto px-2.5 py-1 bg-sky-950/90 hover:bg-sky-900/90 text-sky-300 hover:text-sky-200 border border-sky-800/80 hover:border-sky-600 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-0.5 shadow-sm"
            >
              <span>詳細画面</span>
              <span>↗</span>
            </button>
          </div>

          <!-- 5. 展開時: 音声再生 ＆ AI分析サマリー ＆ 話者別対話ログ -->
          <div v-if="isRecordDetailOpen(record.id)" class="pt-3 mt-2 border-t border-slate-700/50 flex flex-col gap-3">
            <div v-if="record.audio_file_path" class="flex items-center gap-3">
              <CustomAudioPlayer :src="`http://localhost:8000/audio/${record.audio_file_path}`" />
            </div>

            <!-- AI分析サマリー (3ブロック構成) -->
            <div v-if="record.analysis" class="grid grid-cols-1 gap-2 border border-slate-700/40 rounded-xl p-2.5 bg-slate-900/50">
              <div class="bg-slate-900/90 p-2.5 rounded-lg border-l-4 border-emerald-400 space-y-0.5">
                <h4 class="font-bold text-emerald-400 text-xs flex items-center gap-1">
                  <span>💡 顧客の関心点</span>
                </h4>
                <p class="text-xs text-slate-300 leading-relaxed">{{ record.analysis.customer_interest }}</p>
              </div>

              <div class="bg-slate-900/90 p-2.5 rounded-lg border-l-4 border-amber-400 space-y-0.5">
                <h4 class="font-bold text-amber-400 text-xs flex items-center gap-1">
                  <span>⚠️ 懸念点・反論ボトルネック</span>
                </h4>
                <p class="text-xs text-slate-300 leading-relaxed">{{ record.analysis.concerns }}</p>
              </div>

              <div class="bg-slate-900/90 p-2.5 rounded-lg border-l-4 border-sky-400 space-y-0.5">
                <h4 class="font-bold text-sky-400 text-xs flex items-center gap-1">
                  <span>🚀 推奨アクション</span>
                </h4>
                <p class="text-xs text-slate-300 leading-relaxed">{{ record.analysis.recommended_action }}</p>
              </div>
            </div>

            <!-- 話者対話ログ -->
            <div class="space-y-2">
              <h4 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">💬 対話ログ (話者識別: 営業 vs 顧客)</h4>
              <div v-if="record.transcripts.length === 0" class="text-xs text-slate-500 italic py-1">
                対話ログデータが存在しません。「AI解析」を実行してください。
              </div>
              <div v-else class="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1">
                <div 
                  v-for="t in record.transcripts" 
                  :key="t.id" 
                  :class="[
                    'p-2.5 rounded-lg max-w-[90%] text-xs border leading-relaxed',
                    t.speaker === 'Sales' 
                      ? 'self-start bg-sky-950/40 border-sky-800/50 text-sky-100' 
                      : 'self-end bg-emerald-950/40 border-emerald-800/50 text-emerald-100'
                  ]"
                >
                  <div class="flex justify-between items-center text-[10px] text-slate-400 mb-0.5 gap-2">
                    <span class="font-bold text-slate-200">{{ t.speaker === 'Sales' ? '👔 営業担当者' : '👤 顧客' }}</span>
                    <span class="font-mono text-slate-500">{{ t.start_time.toFixed(1) }}s - {{ t.end_time.toFixed(1) }}s</span>
                  </div>
                  <div>{{ t.text }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
