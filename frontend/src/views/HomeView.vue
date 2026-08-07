<script setup>
import { ref, onMounted } from 'vue'

const records = ref([])
const loading = ref(true)

const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await fetch('http://localhost:8000/records/')
    if (res.ok) {
      records.value = await res.json()
    }
  } catch (err) {
    console.error('Error fetching records:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRecords()
})
</script>

<template>
  <div class="home-view">
    <h2>通話記録一覧 (DAY 3 初期画面)</h2>
    <p class="subtitle">バックエンド API (FastAPI + PostgreSQL + MinIO) 連携確認用</p>

    <div v-if="loading" class="loading">
      通話データを読み込んでいます...
    </div>

    <div v-else-if="records.length === 0" class="empty">
      登録された通話データがありません。「音声アップロード」メニューからファイルを保存してください。
    </div>

    <div v-else class="records-list">
      <div v-for="record in records" :key="record.id" class="record-item">
        <div class="item-header">
          <strong>担当コード: {{ record.sales_code }}</strong>
          <span>電話番号: {{ record.customer_phone }}</span>
        </div>
        <div class="item-body">
          <span>通話時間: {{ record.call_duration }}秒</span>
          <span>音声ファイル: {{ record.audio_file_path || 'なし' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  padding: 1rem 0;
}
.subtitle {
  color: #94a3b8;
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
}
.loading, .empty {
  padding: 2rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  text-align: center;
  color: #94a3b8;
}
.records-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.record-item {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 1rem;
  border-radius: 8px;
}
.item-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}
.item-body {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: #94a3b8;
}
</style>
