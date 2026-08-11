<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000'
})

const records = ref([])
const loading = ref(true)
const selectedRank = ref('ALL')
const activeRecordId = ref(null)
const actionLoading = ref({})

const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await api.get('/records/')
    records.value = res.data
  } catch (err) {
    console.error('Fetch records error:', err)
  } finally {
    loading.value = false
  }
}

const filteredRecords = computed(() => {
  if (selectedRank.value === 'ALL') return records.value
  return records.value.filter(r => r.analysis && r.analysis.rank === selectedRank.value)
})

const handleTranscribe = async (recordId) => {
  actionLoading.value[`${recordId}_transcribe`] = true
  try {
    await api.post(`/records/${recordId}/transcribe`)
    await fetchRecords()
  } catch (err) {
    const msg = err.response?.data?.detail || '文字起こしに失敗しました'
    alert(msg)
  } finally {
    actionLoading.value[`${recordId}_transcribe`] = false
  }
}

const handleAnalyze = async (recordId) => {
  actionLoading.value[`${recordId}_analyze`] = true
  try {
    await api.post(`/records/${recordId}/score`)
    await fetchRecords()
  } catch (err) {
    const msg = err.response?.data?.detail || 'AI分析に失敗しました。先に文字起こしを実行してください。'
    alert(msg)
  } finally {
    actionLoading.value[`${recordId}_analyze`] = false
  }
}

const handleExportCsv = (recordId) => {
  window.open(`http://localhost:8000/records/${recordId}/export/csv`, '_blank')
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
  fetchRecords()
})
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 py-8 text-slate-100">
    <header class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-white">テレセールス・アナリティクス・ダッシュボード</h2>
        <p class="text-sm text-slate-400 mt-1">通話データの文字起こし・話者識別・LLMスコアリング (S〜Eランク) 管理画面</p>
      </div>
      <button 
        @click="fetchRecords" 
        class="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-sm font-medium transition-colors cursor-pointer"
      >
        🔄 データ更新
      </button>
    </header>

    <div class="flex items-center gap-2 mb-6 bg-slate-800/50 p-3 rounded-xl border border-slate-800 flex-wrap">
      <span class="text-xs font-semibold text-slate-400 mr-2 uppercase tracking-wider">ランクで絞り込み:</span>
      <button 
        v-for="rank in ['ALL', 'S', 'A', 'B', 'C', 'D', 'E']" 
        :key="rank"
        :class="[
          'px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer border',
          selectedRank === rank 
            ? 'bg-sky-500 text-slate-950 border-sky-400 shadow-md shadow-sky-500/20' 
            : 'bg-slate-900/60 text-slate-400 border-slate-700 hover:border-slate-500 hover:text-slate-200'
        ]"
        @click="selectedRank = rank"
      >
        {{ rank === 'ALL' ? 'すべて' : rank + ' ランク' }}
      </button>
    </div>

    <div v-if="loading" class="text-center py-12 bg-slate-800/30 rounded-2xl border border-slate-800 text-slate-400">
      <div class="animate-pulse flex flex-col items-center gap-2">
        <span>通話データを読み込んでいます...</span>
      </div>
    </div>
    <div v-else-if="filteredRecords.length === 0" class="text-center py-12 bg-slate-800/30 rounded-2xl border border-slate-800 text-slate-400">
      該当する通話データが存在しません。
    </div>

    <div v-else class="flex flex-col gap-5">
      <div 
        v-for="record in filteredRecords" 
        :key="record.id" 
        class="bg-slate-800/80 backdrop-blur-sm border border-slate-700/60 rounded-2xl p-5 shadow-xl transition-all"
      >
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-4 border-b border-slate-700/50">
          <div class="flex flex-wrap items-center gap-4 text-sm">
            <span class="font-mono bg-slate-900/80 px-2.5 py-1 rounded-md text-slate-300 border border-slate-700">ID: {{ record.id }}</span>
            <span class="text-slate-300 font-medium">担当: {{ record.sales_code }}</span>
            <span class="text-slate-400">📞 {{ record.customer_phone }}</span>
            <span class="text-slate-400">⏱ {{ record.call_duration }}秒</span>
          </div>

          <div v-if="record.analysis" :class="['px-3 py-1 rounded-lg text-xs font-bold shadow-sm', getRankBadgeClass(record.analysis.rank)]">
            ランク {{ record.analysis.rank }}
          </div>
          <div v-else class="px-3 py-1 rounded-lg text-xs font-medium bg-slate-700 text-slate-400">
            未分析
          </div>
        </div>

        <div v-if="record.analysis" class="my-4">
          <div class="flex justify-between text-xs font-medium text-slate-400 mb-1.5">
            <span>成約可能性 (購入確率)</span>
            <span class="text-sky-400 font-bold text-sm">{{ record.analysis.purchase_probability }}%</span>
          </div>
          <div class="h-2 w-full bg-slate-900 rounded-full overflow-hidden p-0.5 border border-slate-700/50">
            <div 
              class="h-full bg-gradient-to-r from-sky-500 to-emerald-400 rounded-full transition-all duration-500" 
              :style="{ width: record.analysis.purchase_probability + '%' }"
            ></div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 mt-4 pt-2">
          <button 
            @click="handleTranscribe(record.id)" 
            class="px-3.5 py-2 bg-slate-700 hover:bg-slate-600 text-slate-100 rounded-xl text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
            :disabled="actionLoading[`${record.id}_transcribe`]"
          >
            {{ actionLoading[`${record.id}_transcribe`] ? '⏳ 文字起こし中...' : '🎙️ STT文字起こし' }}
          </button>

          <button 
            @click="handleAnalyze(record.id)" 
            class="px-3.5 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-sky-600/20 transition-all cursor-pointer disabled:opacity-50"
            :disabled="actionLoading[`${record.id}_analyze`]"
          >
            {{ actionLoading[`${record.id}_analyze`] ? '⚡ 分析中...' : '🤖 AIスコアリング' }}
          </button>

          <button 
            @click="handleExportCsv(record.id)" 
            class="px-3.5 py-2 bg-slate-900/60 hover:bg-slate-900 text-slate-300 border border-slate-700 hover:border-slate-600 rounded-xl text-xs font-semibold transition-all cursor-pointer"
          >
            📥 CSV出力
          </button>

          <button 
            @click="activeRecordId = activeRecordId === record.id ? null : record.id"
            class="ml-auto px-3 py-1.5 text-sky-400 hover:text-sky-300 text-xs font-semibold transition-colors cursor-pointer"
          >
            {{ activeRecordId === record.id ? '閉じる ▲' : '詳細・対話ログ ▼' }}
          </button>
        </div>

        <div v-if="activeRecordId === record.id" class="mt-5 pt-5 border-t border-slate-700/50 flex flex-col gap-4">
          <div v-if="record.analysis" class="bg-slate-900/90 p-4 rounded-xl border-l-4 border-sky-400 text-xs leading-relaxed space-y-2">
            <h4 class="font-bold text-sky-400 text-sm mb-2">💡 AI分析サマリー</h4>
            <p><span class="font-semibold text-slate-300">顧客の関心点:</span> <span class="text-slate-300">{{ record.analysis.customer_interest }}</span></p>
            <p><span class="font-semibold text-slate-300">懸念点・課題:</span> <span class="text-slate-300">{{ record.analysis.concerns }}</span></p>
            <p><span class="font-semibold text-slate-300">推奨アクション:</span> <span class="text-slate-300">{{ record.analysis.recommended_action }}</span></p>
          </div>

          <div class="space-y-3">
            <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider">💬 対話ログ (話者識別: 営業 vs 顧客)</h4>
            <div v-if="record.transcripts.length === 0" class="text-xs text-slate-500 italic py-2">
              文字起こしデータがありません。「STT文字起こし」を実行してください。
            </div>
            <div v-else class="flex flex-col gap-2.5 max-h-96 overflow-y-auto pr-1">
              <div 
                v-for="t in record.transcripts" 
                :key="t.id" 
                :class="[
                  'p-3 rounded-xl max-w-[85%] text-xs border leading-relaxed',
                  t.speaker === 'Sales' 
                    ? 'self-start bg-sky-950/40 border-sky-800/50 text-sky-100' 
                    : 'self-end bg-emerald-950/40 border-emerald-800/50 text-emerald-100'
                ]"
              >
                <div class="flex justify-between items-center text-[10px] text-slate-400 mb-1 gap-4">
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
</template>
