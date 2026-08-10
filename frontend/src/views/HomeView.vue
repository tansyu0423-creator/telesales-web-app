<script setup>
import { ref, onMounted, computed } from 'vue'

const records = ref([])
const loading = ref(true)
const selectedRank = ref('ALL') // ランクフィルター ('ALL', 'S', 'A', 'B', 'C', 'D', 'E')
const activeRecordId = ref(null) // 詳細展開中のレコードID
const actionLoading = ref({}) // 処理中フラグ { [recordId_action]: true }

// 通話レコード一覧の取得
const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await fetch('http://localhost:8000/records/')
    if (res.ok) {
      records.value = await res.json()
    }
  } catch (err) {
    console.error('Fetch records error:', err)
  } finally {
    loading.value = false
  }
}

// ランクでフィルタリングしたレコード一覧
const filteredRecords = computed(() => {
  if (selectedRank.value === 'ALL') return records.value
  return records.value.filter(r => r.analysis && r.analysis.rank === selectedRank.value)
})

// 文字起こし (STT + 話者識別) 実行
const handleTranscribe = async (recordId) => {
  actionLoading.value[`${recordId}_transcribe`] = true
  try {
    const res = await fetch(`http://localhost:8000/records/${recordId}/transcribe`, { method: 'POST' })
    if (!res.ok) throw new Error('文字起こしに失敗しました')
    await fetchRecords()
  } catch (err) {
    alert(err.message)
  } finally {
    actionLoading.value[`${recordId}_transcribe`] = false
  }
}

// AI分析 (スコアリング) 実行
const handleAnalyze = async (recordId) => {
  actionLoading.value[`${recordId}_analyze`] = true
  try {
    const res = await fetch(`http://localhost:8000/records/${recordId}/analyze`, { method: 'POST' })
    if (!res.ok) {
      const errData = await res.json()
      throw new Error(errData.detail || 'AI分析に失敗しました。先に文字起こしを実行してください。')
    }
    await fetchRecords()
  } catch (err) {
    alert(err.message)
  } finally {
    actionLoading.value[`${recordId}_analyze`] = false
  }
}

// CSVダウンロード
const handleExportCsv = (recordId) => {
  window.open(`http://localhost:8000/records/${recordId}/export/csv`, '_blank')
}

// ランクに応じたスタイルクラスの取得
const getRankBadgeClass = (rank) => {
  switch (rank) {
    case 'S': return 'badge-s'
    case 'A': return 'badge-a'
    case 'B': return 'badge-b'
    case 'C': return 'badge-c'
    case 'D': return 'badge-d'
    case 'E': return 'badge-e'
    default: return 'badge-default'
  }
}

onMounted(() => {
  fetchRecords()
})
</script>

<template>
  <div class="dashboard-container">
    <header class="dash-header">
      <div>
        <h2>テレセールス・アナリティクス・ダッシュボード</h2>
        <p class="subtitle">通話データの文字起こし・話者識別・LLMスコアリング (S〜Eランク) 管理画面</p>
      </div>
      <button @click="fetchRecords" class="btn-refresh">データ更新</button>
    </header>

    <!-- ランク別フィルタータブ -->
    <div class="filter-bar">
      <span class="filter-label">ランクで絞り込み:</span>
      <button 
        v-for="rank in ['ALL', 'S', 'A', 'B', 'C', 'D', 'E']" 
        :key="rank"
        :class="['filter-btn', selectedRank === rank ? 'active' : '']"
        @click="selectedRank = rank"
      >
        {{ rank === 'ALL' ? 'すべて' : rank + ' ランク' }}
      </button>
    </div>

    <!-- 状態表示 -->
    <div v-if="loading" class="state-box">通話データを読み込んでいます...</div>
    <div v-else-if="filteredRecords.length === 0" class="state-box">該当する通話データが存在しません。</div>

    <!-- レコードカード一覧 -->
    <div v-else class="records-grid">
      <div v-for="record in filteredRecords" :key="record.id" class="record-card">
        <!-- カードヘッダー -->
        <div class="card-header">
          <div class="meta-info">
            <span class="sales-code">担当: {{ record.sales_code }}</span>
            <span class="phone">📞 {{ record.customer_phone }}</span>
            <span class="duration">⏱ {{ record.call_duration }}秒</span>
          </div>

          <!-- ランクバッジ -->
          <div v-if="record.analysis" :class="['rank-badge', getRankBadgeClass(record.analysis.rank)]">
            ランク {{ record.analysis.rank }}
          </div>
          <div v-else class="rank-badge badge-none">未分析</div>
        </div>

        <!-- 購買確率バー -->
        <div v-if="record.analysis" class="probability-section">
          <div class="prob-header">
            <span>成約可能性 (購入率)</span>
            <strong>{{ record.analysis.purchase_probability }}%</strong>
          </div>
          <div class="prob-bar-bg">
            <div class="prob-bar-fill" :style="{ width: record.analysis.purchase_probability + '%' }"></div>
          </div>
        </div>

        <!-- アクションボタン群 -->
        <div class="card-actions">
          <button 
            @click="handleTranscribe(record.id)" 
            class="btn btn-secondary"
            :disabled="actionLoading[`${record.id}_transcribe`]"
          >
            {{ actionLoading[`${record.id}_transcribe`] ? '文字起こし中...' : 'STT文字起こし' }}
          </button>

          <button 
            @click="handleAnalyze(record.id)" 
            class="btn btn-primary"
            :disabled="actionLoading[`${record.id}_analyze`]"
          >
            {{ actionLoading[`${record.id}_analyze`] ? '分析中...' : 'AIスコアリング' }}
          </button>

          <button @click="handleExportCsv(record.id)" class="btn btn-outline">
            📥 CSV出力
          </button>

          <button 
            @click="activeRecordId = activeRecordId === record.id ? null : record.id"
            class="btn btn-link"
          >
            {{ activeRecordId === record.id ? '閉じる ▲' : '詳細・対話ログ ▼' }}
          </button>
        </div>

        <!-- アコーディオン詳細表示 -->
        <div v-if="activeRecordId === record.id" class="card-details">
          <!-- AI分析結果カード -->
          <div v-if="record.analysis" class="analysis-box">
            <h4>💡 AI分析サマリー</h4>
            <p><strong>顧客の関心点・要約:</strong> {{ record.analysis.customer_interest }}</p>
            <p><strong>懸念点・反論:</strong> {{ record.analysis.concerns }}</p>
            <p><strong>推奨アクション:</strong> {{ record.analysis.recommended_action }}</p>
          </div>

          <!-- 話者識別タイムライン対話ログ -->
          <div class="transcripts-box">
            <h4>💬 対話ログ (話者識別: 営業 vs 顧客)</h4>
            <div v-if="record.transcripts.length === 0" class="no-transcripts">
              文字起こしデータがありません。「STT文字起こし」を実行してください。
            </div>
            <div v-else class="chat-timeline">
              <div 
                v-for="t in record.transcripts" 
                :key="t.id" 
                :class="['chat-bubble', t.speaker === 'Sales' ? 'chat-sales' : 'chat-customer']"
              >
                <div class="bubble-header">
                  <span class="speaker-tag">{{ t.speaker === 'Sales' ? '営業担当者' : '顧客' }}</span>
                  <span class="timestamp">{{ t.start_time.toFixed(1) }}s - {{ t.end_time.toFixed(1) }}s</span>
                </div>
                <div class="bubble-text">{{ t.text }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container { max-width: 1000px; margin: 0 auto; color: #f8fafc; }
.dash-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.subtitle { color: #94a3b8; font-size: 0.85rem; }
.btn-refresh { background: #334155; border: 1px solid #475569; color: white; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; }

/* フィルタータブ */
.filter-bar { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1.5rem; background: rgba(255,255,255,0.03); padding: 0.6rem 1rem; border-radius: 8px; flex-wrap: wrap; }
.filter-label { font-size: 0.85rem; color: #cbd5e1; margin-right: 0.5rem; }
.filter-btn { background: transparent; border: 1px solid #475569; color: #94a3b8; padding: 0.35rem 0.8rem; border-radius: 20px; cursor: pointer; font-size: 0.8rem; }
.filter-btn.active { background: #38bdf8; color: #0f172a; border-color: #38bdf8; font-weight: bold; }

/* レコードカード */
.records-grid { display: flex; flex-direction: column; gap: 1.2rem; }
.record-card { background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 1.2rem; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.meta-info { display: flex; gap: 1.2rem; font-size: 0.9rem; color: #e2e8f0; }

/* ランクバッジ */
.rank-badge { font-weight: bold; padding: 0.25rem 0.75rem; border-radius: 6px; font-size: 0.85rem; }
.badge-s { background: #8b5cf6; color: white; }
.badge-a { background: #22c55e; color: white; }
.badge-b { background: #3b82f6; color: white; }
.badge-c { background: #eab308; color: #0f172a; }
.badge-d { background: #f97316; color: white; }
.badge-e { background: #ef4444; color: white; }
.badge-none { background: #475569; color: #cbd5e1; }

/* 購買確率バー */
.probability-section { margin: 1rem 0; }
.prob-header { display: flex; justify-content: space-between; font-size: 0.8rem; color: #cbd5e1; margin-bottom: 0.3rem; }
.prob-bar-bg { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.prob-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #22c55e); transition: width 0.4s ease; }

/* ボタン類 */
.card-actions { display: flex; gap: 0.6rem; align-items: center; margin-top: 1rem; flex-wrap: wrap; }
.btn { padding: 0.45rem 0.9rem; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer; border: none; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: #475569; color: white; }
.btn-outline { background: transparent; border: 1px solid #475569; color: #cbd5e1; }
.btn-link { background: transparent; color: #38bdf8; border: none; font-size: 0.8rem; margin-left: auto; cursor: pointer; }

/* 詳細エリア */
.card-details { margin-top: 1.2rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1rem; display: flex; flex-direction: column; gap: 1rem; }
.analysis-box { background: rgba(15, 23, 42, 0.6); padding: 1rem; border-radius: 8px; border-left: 4px solid #38bdf8; font-size: 0.85rem; line-height: 1.6; }
.analysis-box h4 { margin-bottom: 0.5rem; color: #38bdf8; }

/* チャットタイムライン (話者色分け) */
.transcripts-box h4 { margin-bottom: 0.5rem; font-size: 0.85rem; color: #cbd5e1; }
.chat-timeline { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.5rem; }
.chat-bubble { padding: 0.6rem 0.9rem; border-radius: 8px; max-width: 85%; font-size: 0.85rem; }
.chat-sales { align-self: flex-start; background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.4); }
.chat-customer { align-self: flex-end; background: rgba(34, 197, 94, 0.2); border: 1px solid rgba(34, 197, 94, 0.4); }
.bubble-header { display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.2rem; gap: 1rem; }
.speaker-tag { font-weight: bold; color: #e2e8f0; }
.state-box { text-align: center; padding: 2rem; background: rgba(255,255,255,0.02); border-radius: 8px; color: #94a3b8; }
.no-transcripts { font-size: 0.85rem; color: #94a3b8; font-style: italic; }
</style>

