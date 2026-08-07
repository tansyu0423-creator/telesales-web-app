<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const salesCode = ref('')
const customerPhone = ref('')
const callDuration = ref(120)
const selectedFile = ref(null)
const isUploading = ref(false)
const message = ref('')
const isError = ref(false)

const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (file) {
    if (!file.name.match(/\.(wav|mp3)$/i)) {
      message.value = '.wav または .mp3 の音声ファイルを選択してください。'
      isError.value = true
      selectedFile.value = null
      return
    }
    selectedFile.value = file
    message.value = ''
    isError.value = false
  }
}

const handleUpload = async () => {
  if (!salesCode.value || !customerPhone.value || !selectedFile.value) {
    message.value = '全必須項目を入力・選択してください。'
    isError.value = true
    return
  }

  isUploading.value = true
  message.value = ''

  try {
    // 1. MinIO /upload/ へ送信
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const uploadRes = await fetch('http://localhost:8000/upload/', {
      method: 'POST',
      body: formData,
    })

    if (!uploadRes.ok) {
      throw new Error('音声ファイルのアップロードに失敗しました')
    }

    const uploadData = await uploadRes.json()

    // 2. DB /records/ へ登録
    const recordPayload = {
      sales_code: salesCode.value,
      customer_phone: customerPhone.value,
      call_duration: parseInt(callDuration.value, 10),
      audio_file_path: uploadData.saved_filename,
    }

    const recordRes = await fetch('http://localhost:8000/records/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recordPayload),
    })

    if (!recordRes.ok) {
      throw new Error('通話レコードの登録に失敗しました')
    }

    message.value = 'アップロードとレコード登録が完了しました！'
    isError.value = false
    setTimeout(() => {
      router.push('/')
    }, 1200)
  } catch (err) {
    message.value = err.message || 'エラーが発生しました'
    isError.value = true
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <div class="upload-view">
    <h2>音声ファイルの保存 (MinIO連携)</h2>
    <p class="subtitle">DAY 3 音声アップロードAPIおよびレコード作成機能</p>

    <div v-if="message" :class="['alert', isError ? 'alert-error' : 'alert-success']">
      {{ message }}
    </div>

    <form @submit.prevent="handleUpload" class="upload-form">
      <div class="form-group">
        <label>営業担当者コード *</label>
        <input v-model="salesCode" type="text" placeholder="例: REP-101" required />
      </div>

      <div class="form-group">
        <label>顧客電話番号 *</label>
        <input v-model="customerPhone" type="tel" placeholder="例: 090-1234-5678" required />
      </div>

      <div class="form-group">
        <label>通話時間 (秒) *</label>
        <input v-model="callDuration" type="number" min="1" required />
      </div>

      <div class="form-group">
        <label>音声ファイル (.mp3 / .wav) *</label>
        <input type="file" accept=".wav,.mp3" @change="handleFileChange" required />
      </div>

      <button type="submit" class="submit-btn" :disabled="isUploading">
        {{ isUploading ? '保存中...' : 'アップロード実行' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.upload-view {
  max-width: 500px;
  margin: 0 auto;
  padding: 1rem 0;
}
.subtitle {
  color: #94a3b8;
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
}
.upload-form {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  background: rgba(255, 255, 255, 0.05);
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.form-group label {
  font-size: 0.85rem;
  color: #cbd5e1;
}
.form-group input {
  padding: 0.6rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  color: white;
}
.submit-btn {
  padding: 0.75rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  font-weight: bold;
  cursor: pointer;
  margin-top: 0.5rem;
}
.submit-btn:disabled {
  opacity: 0.6;
}
.alert {
  padding: 0.75rem 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}
.alert-error {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid #ef4444;
  color: #fca5a5;
}
.alert-success {
  background: rgba(34, 197, 94, 0.2);
  border: 1px solid #22c55e;
  color: #86efac;
}
</style>
