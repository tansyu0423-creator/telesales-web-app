<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import api from '../services/api'
import CircularProgressGauge from '../components/CircularProgressGauge.vue'
import CustomAudioPlayer from '../components/CustomAudioPlayer.vue'

const records = ref([])
const loading = ref(true)
const actionLoading = ref({})
const isRefreshing = ref(false)

const openRecordIds = ref([])
const audioPlayerRefs = ref({})
const searchQuery = ref('')
const selectedRank = ref('ALL')
const sortBy = ref('date_desc')
const viewMode = ref('table')
const activeTab = ref('records')
const repSortBy = ref('high_prospect')
const selectedSalesRep = ref(null)

const gaugeValueMap = ref({})
const gaugeAnimatedMap = ref({})

const confettiParticles = ref([])

const setAudioPlayerRef = (id, el) => {
  if (el) {
    audioPlayerRefs.value[id] = el
  } else {
    delete audioPlayerRefs.value[id]
  }
}

const seekAudioTo = (recordId, startTime) => {
  const player = audioPlayerRefs.value[recordId]
  if (player && typeof player.seekToAndPlay === 'function') {
    player.seekToAndPlay(startTime)
  }
}

const toggleRecordDetail = (id) => {
  const index = openRecordIds.value.indexOf(id)
  if (index === -1) {
    openRecordIds.value.push(id)
  } else {
    openRecordIds.value.splice(index, 1)
  }
}

const isRecordDetailOpen = (id) => {
  return openRecordIds.value.includes(id)
}

const getRankLabel = (rank) => {
  const labels = {
    'S': '非常に有望',
    'A': '有望',
    'B': '検討中',
    'C': '観察',
    'D': '低可能性',
    'E': '不可行'
  }
  return labels[rank] || '未知'
}

const getRankBadgeClass = (rank) => {
  const classes = {
    'S': 'bg-purple-950/90 text-purple-300 border border-purple-700/80 shadow-purple-900/20',
    'A': 'bg-green-950/90 text-green-300 border border-green-700/80 shadow-green-900/20',
    'B': 'bg-blue-950/90 text-blue-300 border border-blue-700/80 shadow-blue-900/20',
    'C': 'bg-yellow-950/90 text-yellow-300 border border-yellow-700/80 shadow-yellow-900/20',
    'D': 'bg-orange-950/90 text-orange-300 border border-orange-700/80 shadow-orange-900/20',
    'E': 'bg-red-950/90 text-red-300 border border-red-700/80 shadow-red-900/20'
  }
  return classes[rank] || 'bg-slate-800 text-slate-300 border border-slate-700'
}

const getRankFilterButtonClass = (rank, isSelected) => {
  if (isSelected) {
    return 'bg-sky-500 text-slate-950 border-sky-400 font-extrabold shadow-md shadow-sky-500/20'
  }
  return 'bg-slate-900/80 text-slate-300 border-slate-700 hover:border-slate-500 hover:text-white'
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

const formatDateTime = (isoString) => {
  if (!isoString) return '-'
  try {
    const fixedIso = isoString.endsWith('Z') || isoString.includes('+') ? isoString : isoString + 'Z'
    const date = new Date(fixedIso)
    return date.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    })
  } catch (e) {
    return isoString
  }
}

const fetchRecords = async () => {
  isRefreshing.value = true
  try {
    const res = await api.get('/records/')
    records.value = res.data
  } catch (err) {
    console.error('通話一覧取得エラー:', err)
  } finally {
    loading.value = false
    isRefreshing.value = false
    window.dispatchEvent(new CustomEvent('dashboard-refresh-finished'))
  }
}

const handleTriggerRefresh = () => {
  fetchRecords()
}

const handleAnalyze = async (recordId) => {
  actionLoading.value[`${recordId}_analyze`] = true
  try {
    await api.post(`/records/${recordId}/analyze`)
    await fetchRecords()
  } catch (err) {
    alert('AI解析の実行に失敗しました: ' + (err.response?.data?.detail || err.message))
  } finally {
    actionLoading.value[`${recordId}_analyze`] = false
  }
}

const handleExportCsv = (recordId) => {
  window.open(`http://localhost:8000/api/records/${recordId}/export/csv`, '_blank')
}

const handleDeleteRecord = async (recordId) => {
  if (!confirm(`通話ID #${recordId} のデータを完全に削除しますか？`)) return
  actionLoading.value[`${recordId}_delete`] = true
  try {
    await api.delete(`/records/${recordId}`)
    await fetchRecords()
  } catch (err) {
    alert('削除に失敗しました: ' + (err.response?.data?.detail || err.message))
  } finally {
    actionLoading.value[`${recordId}_delete`] = false
  }
}

const filterBySalesRep = (repCode) => {
  selectedSalesRep.value = repCode
  activeTab.value = 'records'
}

const clearSalesRepFilter = () => {
  selectedSalesRep.value = null
}

const filteredRecords = computed(() => {
  let result = [...records.value]

  if (selectedSalesRep.value) {
    result = result.filter(r => r.sales_code === selectedSalesRep.value)
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    result = result.filter(r => 
      r.sales_code?.toLowerCase().includes(q) ||
      r.customer_phone?.toLowerCase().includes(q)
    )
  }

  if (selectedRank.value !== 'ALL') {
    result = result.filter(r => r.analysis && r.analysis.rank === selectedRank.value)
  }

  result.sort((a, b) => {
    if (sortBy.value === 'date_desc') {
      return new Date(b.created_at || 0) - new Date(a.created_at || 0)
    } else if (sortBy.value === 'date_asc') {
      return new Date(a.created_at || 0) - new Date(b.created_at || 0)
    } else if (sortBy.value === 'prob_desc') {
      const probA = a.analysis?.purchase_probability || 0
      const probB = b.analysis?.purchase_probability || 0
      return probB - probA
    } else if (sortBy.value === 'rank_asc') {
      const rankOrder = { 'S': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6 }
      const orderA = rankOrder[a.analysis?.rank] || 99
      const orderB = rankOrder[b.analysis?.rank] || 99
      return orderA - orderB
    }
    return 0
  })

  return result
})

const kpiStats = computed(() => {
  const total = records.value.length
  if (total === 0) {
    return { total: 0, highProspectCount: 0, avgProbability: 0, analysisRate: 0 }
  }

  let highProspectCount = 0
  let totalProb = 0
  let analyzedCount = 0

  records.value.forEach(r => {
    if (r.analysis) {
      analyzedCount++
      const prob = r.analysis.purchase_probability || 0
      totalProb += prob
      if (r.analysis.rank === 'S' || r.analysis.rank === 'A') {
        highProspectCount++
      }
    }
  })

  const avgProbability = analyzedCount > 0 ? Math.round(totalProb / analyzedCount) : 0
  const analysisRate = Math.round((analyzedCount / total) * 100)

  return {
    total,
    highProspectCount,
    avgProbability,
    analysisRate
  }
})

const salesRepStats = computed(() => {
  const repMap = {}

  records.value.forEach(r => {
    const code = r.sales_code || '不明'
    if (!repMap[code]) {
      repMap[code] = {
        code,
        totalCalls: 0,
        highProspectCount: 0,
        totalProbability: 0,
        analyzedCount: 0,
        rankCounts: { S: 0, A: 0, B: 0, C: 0, D: 0, E: 0 }
      }
    }

    repMap[code].totalCalls++
    if (r.analysis) {
      repMap[code].analyzedCount++
      const prob = r.analysis.purchase_probability || 0
      repMap[code].totalProbability += prob
      const rank = r.analysis.rank
      if (repMap[code].rankCounts[rank] !== undefined) {
        repMap[code].rankCounts[rank]++
      }
      if (rank === 'S' || rank === 'A') {
        repMap[code].highProspectCount++
      }
    }
  })

  const list = Object.values(repMap).map(rep => {
    const avgProbability = rep.analyzedCount > 0 ? Math.round(rep.totalProbability / rep.analyzedCount) : 0
    const weightedScore = (rep.highProspectCount * 25) + (avgProbability * 0.5) + (rep.totalCalls * 2)
    return {
      ...rep,
      avgProbability,
      weightedScore
    }
  })

  list.sort((a, b) => {
    if (repSortBy.value === 'high_prospect') {
      if (b.highProspectCount !== a.highProspectCount) return b.highProspectCount - a.highProspectCount
      return b.avgProbability - a.avgProbability
    } else if (repSortBy.value === 'weighted') {
      return b.weightedScore - a.weightedScore
    } else if (repSortBy.value === 'avg_prob') {
      return b.avgProbability - a.avgProbability
    } else if (repSortBy.value === 'calls') {
      return b.totalCalls - a.totalCalls
    }
    return 0
  })

  return list
})

const getConfettiParticles = (rankIndex) => {
  const colors = {
    0: ['#fbbf24', '#f59e0b', '#d97706', '#fef08a', '#ffffff'],
    1: ['#e2e8f0', '#94a3b8', '#cbd5e1', '#f8fafc', '#38bdf8'],
    2: ['#b45309', '#d97706', '#f59e0b', '#78350f', '#fef08a']
  }
  const selectedColors = colors[rankIndex] || colors[0]

  const particles = []
  for (let i = 0; i < 18; i++) {
    particles.push({
      id: i,
      left: `${(i * 5.8) + (Math.sin(i) * 2)}%`,
      size: `${6 + (i % 5)}px`,
      color: selectedColors[i % selectedColors.length],
      isCircle: i % 2 === 0,
      delay: `${(i * 0.25).toFixed(2)}s`,
      duration: `${3.5 + (i % 3) * 0.8}s`,
      rotation: `${(i * 45)}deg`
    })
  }
  return particles
}

const animateGaugeValue = (key, targetValue) => {
  if (gaugeAnimatedMap.value[key]) return
  gaugeAnimatedMap.value[key] = true

  let current = 0
  const duration = 2400
  const stepTime = 30
  const totalSteps = duration / stepTime
  const increment = targetValue / totalSteps

  const timer = setInterval(() => {
    current += increment
    if (current >= targetValue) {
      gaugeValueMap.value[key] = targetValue
      clearInterval(timer)
    } else {
      gaugeValueMap.value[key] = Math.round(current)
    }
  }, stepTime)
}

const handleScrollGaugeCheck = () => {
  nextTick(() => {
    const gaugeElements = document.querySelectorAll('[data-gauge-id]')
    const windowHeight = window.innerHeight

    gaugeElements.forEach(el => {
      const rect = el.getBoundingClientRect()
      if (rect.top <= windowHeight * 0.95 && rect.bottom >= 0) {
        const id = el.getAttribute('data-gauge-id')
        const prob = parseInt(el.getAttribute('data-probability') || '0', 10)
        if (id) {
          animateGaugeValue(id, prob)
          animateGaugeValue(`t-${id}`, prob)
        }
      }
    })
  })
}

watch(filteredRecords, () => {
  handleScrollGaugeCheck()
}, { deep: true, immediate: true })

onMounted(() => {
  fetchRecords()
  window.addEventListener('trigger-dashboard-refresh', handleTriggerRefresh)
  window.addEventListener('scroll', handleScrollGaugeCheck, { capture: true })
  window.addEventListener('resize', handleScrollGaugeCheck)
})

onUnmounted(() => {
  window.removeEventListener('trigger-dashboard-refresh', handleTriggerRefresh)
  window.removeEventListener('scroll', handleScrollGaugeCheck, { capture: true })
  window.removeEventListener('resize', handleScrollGaugeCheck)
})
</script>

<template>
  <!-- テレセールス・アナリティクス・メインダッシュボード (全画面フルレスポンシブ 1600px) -->
  <div class="w-full max-w-[1600px] mx-auto px-2 sm:px-4 py-4 text-slate-100 bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl">
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
            <span>通話データのAI解析 ・ 話者識別 ・ LLMスコアリング (S〜Eランク) 管理画面</span>
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
            <span>🏆 営業担当者別 パフォーマンスランキング</span>
          </h3>
          <p class="text-xs text-slate-400 mt-0.5">成果実績（S/Aランク獲得数）や架電数を考慮してランキングを表示します。</p>
        </div>

        <div class="flex items-center gap-2">
          <label class="text-xs text-slate-400 font-medium whitespace-nowrap">並び順:</label>
          <select 
            v-model="repSortBy" 
            class="bg-slate-900 border border-slate-700 focus:border-sky-500 text-xs text-white rounded-xl px-3 py-1.5 outline-none font-medium"
          >
            <option value="high_prospect">🔥 S/Aランク獲得数順 (成果重視)</option>
            <option value="weighted">⚖️ 総合補正スコア順 (件数＋確度)</option>
            <option value="avg_prob">📈 平均成約率順</option>
            <option value="calls">📞 総架電件数順</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div 
          v-for="(rep, index) in salesRepStats" 
          :key="rep.code" 
          :class="[
            'relative overflow-hidden bg-slate-800/80 backdrop-blur-md border rounded-2xl p-5 shadow-xl transition-all flex flex-col justify-between',
            index === 0 ? 'border-amber-500/70 shadow-amber-500/10 hover:border-amber-400' :
            index === 1 ? 'border-slate-400/60 shadow-slate-400/10 hover:border-slate-300' :
            index === 2 ? 'border-amber-700/70 shadow-amber-700/10 hover:border-amber-600' :
            'border-slate-700/60 hover:border-sky-500/50'
          ]"
        >
          <!-- 1〜3位のメダル色紙吹雪エフェクト (金・銀・銅) -->
          <div v-if="index < 3" class="absolute inset-0 pointer-events-none overflow-hidden z-0">
            <div 
              v-for="particle in getConfettiParticles(index)" 
              :key="particle.id"
              class="confetti-particle absolute -top-3"
              :style="{
                left: particle.left,
                width: particle.size,
                height: particle.isCircle ? particle.size : `${parseInt(particle.size) * 1.8}px`,
                backgroundColor: particle.color,
                borderRadius: particle.isCircle ? '50%' : '2px',
                animationDelay: particle.delay,
                animationDuration: particle.duration,
                transform: `rotate(${particle.rotation})`
              }"
            ></div>
          </div>

          <div class="relative z-10 flex flex-col justify-between h-full">
            <div>
              <div class="flex items-center justify-between gap-2 pb-3 border-b border-slate-700/50 mb-3">
                <div class="flex items-center gap-3">
                  <span :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shadow-md',
                    index === 0 ? 'bg-amber-400 text-slate-950 font-black ring-2 ring-amber-300/50' :
                    index === 1 ? 'bg-slate-300 text-slate-950 font-black ring-2 ring-slate-200/50' :
                    index === 2 ? 'bg-amber-700 text-white font-black ring-2 ring-amber-600/50' :
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
                  <div class="bg-slate-900/60 backdrop-blur-sm p-2.5 rounded-lg border border-slate-700/50">
                    <span class="text-slate-400 block text-[11px]">総通話件数</span>
                    <span class="font-bold text-white font-mono text-sm">{{ rep.totalCalls }} 件</span>
                  </div>
                  <div class="bg-slate-900/60 backdrop-blur-sm p-2.5 rounded-lg border border-slate-700/50">
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
              class="mt-4 w-full py-2 bg-slate-900/90 hover:bg-slate-950 border border-slate-700 hover:border-sky-500 text-sky-400 hover:text-sky-300 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1.5 shadow-sm"
            >
              <span>🔍 この担当者の通話履歴を絞り込む</span>
              <span>➔</span>
            </button>
          </div>
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

      <!-- 1. テーブル（表 `<table>`）形式表示 (viewMode === 'table') -->
      <div v-else-if="viewMode === 'table'" class="w-full rounded-2xl border border-slate-700/60 bg-slate-800/80 backdrop-blur-sm shadow-xl overflow-hidden">
        <table class="w-full text-left text-xs border-collapse table-fixed">
          <thead>
            <tr class="bg-slate-900/90 border-b border-slate-700/80 text-slate-400 font-semibold uppercase tracking-wider text-[10px] sm:text-[11px]">
              <th class="py-3 px-1 sm:px-2 text-center w-8">開閉</th>
              <th class="py-3 px-1 sm:px-2 font-mono w-11 sm:w-14">#ID</th>
              <th class="py-3 px-1 sm:px-2 w-24 sm:w-32">📅 登録日時</th>
              <th class="py-3 px-1 sm:px-2 w-16 sm:w-20">👔 営業</th>
              <th class="py-3 px-1 sm:px-2 hidden lg:table-cell w-28">📞 顧客電話番号</th>
              <th class="py-3 px-1 sm:px-2 hidden lg:table-cell w-20">⏱ 通話時間</th>
              <th class="py-3 px-1 sm:px-2 w-20 sm:w-24">🏆 ランク</th>
              <th class="py-3 px-1 sm:px-2 w-16 sm:w-20 text-center">⚡ 成約率</th>
              <th class="py-3 px-1 sm:px-2 text-right w-28 sm:w-36">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/50">
            <template v-for="record in filteredRecords" :key="record.id">
              <tr 
                @click="toggleRecordDetail(record.id)"
                class="hover:bg-slate-700/40 transition-colors cursor-pointer group"
              >
                <!-- 開閉ボタン (最左列) -->
                <td class="py-2.5 px-1 sm:px-2 text-center">
                  <button 
                    @click.stop="toggleRecordDetail(record.id)"
                    :class="[
                      'w-6 h-6 inline-flex items-center justify-center rounded-lg text-xs font-bold transition-all border cursor-pointer',
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
                <td class="py-2.5 px-1 sm:px-2 font-mono">
                  <span class="bg-slate-900 px-1.5 py-0.5 rounded text-sky-400 font-bold border border-slate-700 text-[11px]">#{{ record.id }}</span>
                </td>
                <!-- 登録日時 -->
                <td class="py-2.5 px-1 sm:px-2 font-mono text-slate-300 truncate text-[11px]">
                  {{ formatDateTime(record.created_at) }}
                </td>
                <!-- 営業担当コード -->
                <td class="py-2.5 px-1 sm:px-2 font-bold text-white truncate text-[11px]">
                  👔 {{ record.sales_code }}
                </td>
                <!-- 顧客電話番号 (大画面のみ表示) -->
                <td class="py-2.5 px-1 sm:px-2 text-slate-200 font-mono truncate hidden lg:table-cell text-[11px]">
                  {{ record.customer_phone }}
                </td>
                <!-- 通話時間 (大画面のみ表示) -->
                <td class="py-2.5 px-1 sm:px-2 text-slate-300 font-mono truncate hidden lg:table-cell text-[11px]">
                  {{ record.call_duration }} 秒
                </td>
                <!-- ランクバッジ -->
                <td class="py-2.5 px-1 sm:px-2 truncate">
                  <span v-if="record.analysis" :class="['px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-black inline-block shadow-sm truncate max-w-full', getRankBadgeClass(record.analysis.rank)]">
                    {{ record.analysis.rank }}：{{ getRankLabel(record.analysis.rank) }}
                  </span>
                  <span v-else class="text-slate-500 text-[11px] italic">未解析</span>
                </td>
                <!-- 成約率ゲージ -->
                <td class="py-2.5 px-1 sm:px-2 text-center">
                  <div v-if="record.analysis" class="flex justify-center">
                    <div 
                      :data-gauge-id="record.id"
                      :data-probability="record.analysis.purchase_probability"
                      class="relative flex items-center justify-center w-[36px] h-[36px] bg-slate-950 rounded-full border border-slate-800 p-0.5 shadow-sm"
                    >
                      <svg class="w-full h-full -rotate-90" viewBox="0 0 64 64">
                        <circle cx="32" cy="32" r="25" stroke="#334155" stroke-width="6" fill="none" />
                        <circle
                          cx="32"
                          cy="32"
                          r="25"
                          :stroke="`url(#gradient-t-${record.id})`"
                          stroke-width="6"
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
                        <span class="text-[11px] font-black text-white font-mono">
                          {{ gaugeValueMap[`t-${record.id}`] || 0 }}%
                        </span>
                      </div>
                    </div>
                  </div>
                  <span v-else class="text-slate-500 font-mono text-[10px]">-</span>
                </td>
                <!-- アクション操作ボタン -->
                <td class="py-2.5 px-1 sm:px-2 text-right" @click.stop>
                  <div class="flex items-center justify-end gap-1">
                    <button 
                      v-if="!record.analysis"
                      @click="handleAnalyze(record.id)" 
                      class="px-2 py-1 bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-600 hover:from-sky-400 hover:to-purple-500 text-white rounded-lg font-bold text-[10px] sm:text-xs shrink-0 cursor-pointer shadow-md shadow-sky-500/25 hover:scale-105 active:scale-95 transition-all flex items-center gap-1 border border-sky-400/30 disabled:opacity-50"
                      :disabled="actionLoading[`${record.id}_analyze`]"
                      title="AIスコアリング解析を実行"
                    >
                      <span v-if="actionLoading[`${record.id}_analyze`]" class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                      <span>{{ actionLoading[`${record.id}_analyze`] ? 'AI解析中...' : 'AI解析' }}</span>
                    </button>
                    <button 
                      @click="handleExportCsv(record.id)" 
                      class="px-1.5 py-1 bg-slate-900/90 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-500 rounded-md font-semibold text-[10px] sm:text-xs shrink-0 cursor-pointer shadow-sm"
                      title="CSV出力"
                    >
                      📥
                    </button>
                    <button 
                      @click="handleDeleteRecord(record.id)" 
                      class="px-1.5 py-1 bg-rose-950/80 hover:bg-rose-900/90 text-rose-300 hover:text-rose-100 border border-rose-800/80 hover:border-rose-600 rounded-md font-bold text-[10px] sm:text-xs shrink-0 cursor-pointer transition-all shadow-sm"
                      :disabled="actionLoading[`${record.id}_delete`]"
                      title="完全削除"
                    >
                      {{ actionLoading[`${record.id}_delete`] ? '⏳' : '🗑️' }}
                    </button>
                    <button 
                      @click="$router.push(`/records/${record.id}`)"
                      class="px-1.5 py-1 bg-sky-950/90 hover:bg-sky-900/90 text-sky-300 hover:text-sky-200 border border-sky-800/80 hover:border-sky-600 rounded-md font-bold text-[10px] sm:text-xs shrink-0 cursor-pointer inline-flex items-center gap-0.5 shadow-sm"
                      title="詳細画面を開く"
                    >
                      <span>詳細画面 ↗</span>
                    </button>
                  </div>
                </td>
              </tr>
              <!-- 行拡張アコーディオン詳細 -->
              <tr v-if="isRecordDetailOpen(record.id)" class="bg-slate-900/80">
                <td colspan="9" class="p-2 sm:p-4 border-b border-slate-700/60">
                  <div class="flex flex-col gap-3.5 w-full max-w-full overflow-hidden">
                    <div v-if="record.audio_file_path" class="flex items-center gap-3 w-full max-w-2xl">
                      <CustomAudioPlayer :src="`http://localhost:8000/audio/${record.audio_file_path}`" />
                    </div>
                    <!-- AI分析サマリー -->
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
                      <div v-else class="flex flex-col gap-2.5 max-h-80 overflow-y-auto pr-2 w-full">
                        <div 
                          v-for="t in record.transcripts" 
                          :key="t.id" 
                          :class="[
                            'p-3 rounded-xl max-w-[85%] md:max-w-[70%] text-xs border leading-relaxed break-words shadow-sm',
                            t.speaker === 'Sales' 
                              ? 'self-start bg-sky-950/60 border-sky-800/60 text-sky-100' 
                              : 'self-end bg-emerald-950/60 border-emerald-800/60 text-emerald-100'
                          ]"
                        >
                          <div class="flex justify-between items-center text-[10px] text-slate-400 mb-1 gap-2">
                            <span class="font-bold text-slate-200">{{ t.speaker === 'Sales' ? '👔 営業担当者' : '👤 顧客' }}</span>
                            <span class="font-mono text-slate-500">{{ t.start_time.toFixed(1) }}s - {{ t.end_time.toFixed(1) }}s</span>
                          </div>
                          <div class="break-words leading-relaxed">{{ t.text }}</div>
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

      <!-- 2. メイソンリーカード表示 (viewMode === 'card') -->
      <div v-else class="columns-1 md:columns-2 lg:columns-3 gap-4 space-y-4">
        <div 
          v-for="record in filteredRecords" 
          :key="record.id" 
          @click="toggleRecordDetail(record.id)"
          class="break-inside-avoid bg-slate-800/80 backdrop-blur-sm border border-slate-700/60 rounded-xl p-4 shadow-lg hover:border-slate-500 transition-all flex flex-col justify-between mb-4 cursor-pointer group"
        >
          <div class="space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-slate-700/50">
              <div class="flex items-center gap-2">
                <button 
                  @click.stop="toggleRecordDetail(record.id)"
                  :class="[
                    'w-7 h-7 inline-flex items-center justify-center rounded-lg text-xs font-bold transition-all border cursor-pointer',
                    isRecordDetailOpen(record.id) 
                      ? 'bg-sky-500 text-slate-950 border-sky-400 font-black shadow-md' 
                      : 'bg-slate-900/80 text-slate-400 border-slate-700 group-hover:border-slate-500 group-hover:text-slate-200'
                  ]"
                >
                  {{ isRecordDetailOpen(record.id) ? '▲' : '▼' }}
                </button>
                <span class="font-mono bg-slate-900 px-2 py-0.5 rounded text-sky-400 font-bold border border-slate-700 text-xs">#{{ record.id }}</span>
                <span class="font-bold text-white text-xs">👔 {{ record.sales_code }}</span>
              </div>
              <div v-if="record.analysis" :class="['px-2.5 py-0.5 rounded text-xs font-black shadow-sm', getRankBadgeClass(record.analysis.rank)]">
                {{ record.analysis.rank }}：{{ getRankLabel(record.analysis.rank) }}
              </div>
            </div>

            <!-- 基本メタ情報リスト -->
            <div class="space-y-1.5 text-xs">
              <div class="flex items-center justify-between text-slate-300">
                <span class="text-slate-400">📞 顧客電話番号:</span>
                <span class="font-semibold text-slate-200">{{ record.customer_phone }}</span>
              </div>
              <div class="flex items-center justify-between text-slate-300">
                <span class="text-slate-400">⏱ 通話時間:</span>
                <span class="font-semibold text-slate-200">{{ record.call_duration }} 秒</span>
              </div>
            </div>

            <!-- スコアリング ＆ 円形ゲージ -->
            <div v-if="record.analysis" class="p-3 bg-slate-900/70 rounded-xl border border-slate-700/60 flex items-center gap-3.5">
              <div 
                :data-gauge-id="record.id"
                :data-probability="record.analysis.purchase_probability"
                class="relative flex items-center justify-center w-[56px] h-[56px] shrink-0 bg-slate-950 rounded-full border border-slate-800 p-0.5 shadow-md"
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
                  <span class="text-xs font-black text-white font-mono">
                    {{ gaugeValueMap[record.id] || 0 }}%
                  </span>
                </div>
              </div>
              <div class="space-y-0.5">
                <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">成約率</div>
                <div class="text-xs font-bold">{{ getRankLabel(record.analysis.rank) }}</div>
              </div>
            </div>
          </div>

          <!-- 操作バー -->
          <div class="flex items-center justify-between gap-1.5 pt-2.5 mt-3 border-t border-slate-700/60 text-xs" @click.stop>
            <div class="flex items-center gap-1.5">
              <button 
                v-if="!record.analysis"
                @click="handleAnalyze(record.id)" 
                class="px-2.5 py-1 bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-600 hover:from-sky-400 hover:to-purple-500 text-white rounded-lg font-bold text-xs shrink-0 cursor-pointer shadow-md shadow-sky-500/25 hover:scale-105 active:scale-95 transition-all flex items-center gap-1 border border-sky-400/30 disabled:opacity-50"
                :disabled="actionLoading[`${record.id}_analyze`]"
              >
                <span v-if="actionLoading[`${record.id}_analyze`]" class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                <span>{{ actionLoading[`${record.id}_analyze`] ? 'AI解析中...' : 'AI解析' }}</span>
              </button>

              <button 
                @click="handleExportCsv(record.id)" 
                class="px-2 py-1 bg-slate-900/80 hover:bg-slate-900 text-slate-300 border border-slate-700 hover:border-slate-600 rounded-lg font-semibold cursor-pointer"
                title="CSVレポート出力"
              >
                📥 CSV
              </button>

              <button 
                @click="handleDeleteRecord(record.id)" 
                class="px-2 py-1 bg-rose-950/80 hover:bg-rose-900/90 text-rose-300 hover:text-rose-100 border border-rose-800/80 hover:border-rose-600 rounded-lg font-bold transition-all cursor-pointer shadow-sm disabled:opacity-50"
                :disabled="actionLoading[`${record.id}_delete`]"
                title="完全削除"
              >
                {{ actionLoading[`${record.id}_delete`] ? '⏳' : '🗑️' }}
              </button>
            </div>

            <button 
              @click="$router.push(`/records/${record.id}`)"
              class="ml-auto px-2.5 py-1 bg-sky-950/90 hover:bg-sky-900/90 text-sky-300 hover:text-sky-200 border border-sky-800/80 hover:border-sky-600 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-0.5 shadow-sm"
            >
              <span>詳細画面</span>
              <span>↗</span>
            </button>
          </div>

          <!-- 5. 展開時: 音声再生 ＆ AI分析サマリー ＆ 話者別対話ログ -->
          <div v-if="isRecordDetailOpen(record.id)" class="pt-3 mt-2 border-t border-slate-700/50 flex flex-col gap-3 w-full max-w-full overflow-hidden">
            <div v-if="record.audio_file_path" class="flex items-center gap-3 w-full">
              <CustomAudioPlayer 
                :ref="el => setAudioPlayerRef(record.id, el)"
                :src="`http://localhost:8000/audio/${record.audio_file_path}`" 
              />
            </div>

            <!-- AI分析サマリー (3ブロック構成) -->
            <div v-if="record.analysis" class="grid grid-cols-1 gap-2 border border-slate-700/40 rounded-xl p-2.5 bg-slate-900/50 w-full">
              <div class="bg-slate-900/90 p-2.5 rounded-lg border-l-4 border-emerald-400 space-y-0.5">
                <h4 class="font-bold text-emerald-400 text-xs flex items-center gap-1">
                  <span>💡 顧客の関心点</span>
                </h4>
                <p class="text-xs text-slate-300 leading-relaxed break-words">{{ record.analysis.customer_interest }}</p>
              </div>

              <div class="bg-slate-900/90 p-2.5 rounded-lg border-l-4 border-amber-400 space-y-0.5">
                <h4 class="font-bold text-amber-400 text-xs flex items-center gap-1">
                  <span>⚠️ 懸念点・反論ボトルネック</span>
                </h4>
                <p class="text-xs text-slate-300 leading-relaxed break-words">{{ record.analysis.concerns }}</p>
              </div>

              <div class="bg-slate-900/90 p-2.5 rounded-lg border-l-4 border-sky-400 space-y-0.5">
                <h4 class="font-bold text-sky-400 text-xs flex items-center gap-1">
                  <span>🚀 推奨アクション</span>
                </h4>
                <p class="text-xs text-slate-300 leading-relaxed break-words">{{ record.analysis.recommended_action }}</p>
              </div>
            </div>

            <!-- 対話時間割合 (Talk-to-Listen Ratio) メーター -->
            <div v-if="record.transcripts && record.transcripts.length > 0" class="bg-slate-900/60 border border-slate-700/50 p-3 rounded-xl space-y-1.5 w-full">
              <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-1 text-xs">
                <span class="font-bold text-slate-300 flex items-center gap-2">
                  <span>📊 対話割合 (Talk-to-Listen Ratio)</span>
                  <span v-if="getTalkRatio(record.transcripts).salesRatio > 65" class="px-2 py-0.5 bg-amber-950/90 border border-amber-800 text-amber-300 text-[10px] font-bold rounded-full">⚠️ 営業話しすぎ注意 (65%超)</span>
                  <span v-else-if="getTalkRatio(record.transcripts).salesRatio < 35" class="px-2 py-0.5 bg-sky-950/90 border border-sky-800 text-sky-300 text-[10px] font-bold rounded-full">ℹ️ 顧客主導対話</span>
                  <span v-else class="px-2 py-0.5 bg-emerald-950/90 border border-emerald-800 text-emerald-300 text-[10px] font-bold rounded-full">✨ 理想的な対話バランス</span>
                </span>
                <span class="font-mono text-slate-400 text-[11px]">
                  👔 営業: <strong class="text-sky-400">{{ getTalkRatio(record.transcripts).salesRatio }}%</strong> ({{ getTalkRatio(record.transcripts).salesDuration }}秒) / 
                  👤 顧客: <strong class="text-emerald-400">{{ getTalkRatio(record.transcripts).customerRatio }}%</strong> ({{ getTalkRatio(record.transcripts).customerDuration }}秒)
                </span>
              </div>

              <div class="w-full h-3 bg-slate-950 rounded-full overflow-hidden flex border border-slate-700/80 p-0.5 shadow-inner">
                <div 
                  class="h-full bg-gradient-to-r from-sky-500 to-blue-600 rounded-l-full transition-all duration-700" 
                  :style="{ width: `${getTalkRatio(record.transcripts).salesRatio}%` }"
                  :title="`営業発話: ${getTalkRatio(record.transcripts).salesRatio}%`"
                ></div>
                <div 
                  class="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-r-full transition-all duration-700" 
                  :style="{ width: `${getTalkRatio(record.transcripts).customerRatio}%` }"
                  :title="`顧客発話: ${getTalkRatio(record.transcripts).customerRatio}%`"
                ></div>
              </div>
            </div>

            <!-- 話者対話ログ (クリックで音声連動再生) -->
            <div class="space-y-2 w-full">
              <div class="flex justify-between items-center">
                <h4 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">💬 対話ログ (話者識別: 営業 vs 顧客)</h4>
                <span class="text-[10px] text-sky-400 font-medium">💡 発話をクリックでその時間へジャンプ再生</span>
              </div>

              <div v-if="record.transcripts.length === 0" class="text-xs text-slate-500 italic py-1">
                対話ログデータが存在しません。「AI解析」を実行してください。
              </div>
              <div v-else class="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1 w-full">
                <div 
                  v-for="t in record.transcripts" 
                  :key="t.id" 
                  @click="seekAudioTo(record.id, t.start_time)"
                  :class="[
                    'p-2.5 rounded-lg max-w-[85%] text-xs border leading-relaxed break-words cursor-pointer transition-all hover:scale-[1.01] shadow-sm group',
                    t.speaker === 'Sales' 
                      ? 'self-start bg-sky-950/40 hover:bg-sky-900/60 border-sky-800/50 hover:border-sky-500 text-sky-100' 
                      : getObjectionTags(t.text, t.speaker).length > 0
                        ? 'self-end bg-amber-950/50 hover:bg-amber-900/70 border-amber-500/80 hover:border-amber-400 text-amber-100 ring-1 ring-amber-500/30'
                        : 'self-end bg-emerald-950/40 hover:bg-emerald-900/60 border-emerald-800/50 hover:border-emerald-500 text-emerald-100'
                  ]"
                  title="クリックしてこの時間から音声再生"
                >
                  <div class="flex justify-between items-center text-[10px] text-slate-400 mb-1 gap-2 flex-wrap">
                    <div class="flex items-center gap-1.5 flex-wrap">
                      <span class="font-bold text-slate-200">{{ t.speaker === 'Sales' ? '👔 営業担当者' : '👤 顧客' }}</span>
                      <span 
                        v-for="(tag, idx) in getObjectionTags(t.text, t.speaker)" 
                        :key="idx"
                        :class="['px-1.5 py-0.2 text-[9px] font-bold border rounded-md shadow-xs flex items-center gap-0.5', tag.class]"
                      >
                        {{ tag.label }}
                      </span>
                    </div>
                    <span class="font-mono text-slate-400 group-hover:text-sky-300 flex items-center gap-1 transition-colors">
                      <span class="text-[9px] px-1 py-0.2 bg-slate-900/80 rounded border border-slate-700 group-hover:border-sky-500">▶ {{ t.start_time.toFixed(1) }}s</span>
                      <span>- {{ t.end_time.toFixed(1) }}s</span>
                    </span>
                  </div>
                  <div class="break-words">{{ t.text }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes confetti-fall {
  0% {
    transform: translateY(-10px) rotate(0deg) scale(0.8);
    opacity: 0;
  }
  20% {
    opacity: 0.85;
  }
  80% {
    opacity: 0.85;
  }
  100% {
    transform: translateY(320px) rotate(360deg) scale(1.1);
    opacity: 0;
  }
}

.confetti-particle {
  animation: confetti-fall linear infinite;
  box-shadow: 0 0 6px currentColor;
}
</style>
