<template>
  <div class="max-w-3xl mx-auto p-6 bg-white rounded-xl shadow-sm border border-gray-100 mt-10">
    <h1 class="text-2xl font-bold mb-6 text-gray-800">音声ファイル・メタデータ登録</h1>

    <!-- アップロードフォーム -->
    <form @submit.prevent="handleSubmit" class="space-y-6">
      
      <!-- ドラッグ＆ドロップ対応 ファイルアップロード領域 -->
      <div
        class="border-2 border-dashed rounded-xl p-10 text-center transition-colors duration-200"
        :class="isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:bg-gray-50'"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <input
          type="file"
          id="audio-upload"
          class="hidden"
          accept="audio/*"
          @change="handleFileSelect"
        />
        <label for="audio-upload" class="cursor-pointer flex flex-col items-center justify-center space-y-3">
          <div class="p-4 bg-blue-50 rounded-full text-blue-600">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
          </div>
          <span class="text-gray-600 font-medium">
            ここに音声ファイルをドラッグ＆ドロップするか、
            <span class="text-blue-600 hover:underline">ファイルを選択</span>
          </span>
          <span class="text-sm text-gray-400">対応フォーマット: MP3, WAV</span>
        </label>

        <!-- 選択されたファイル名と試聴プレビュー ＆ クリアボタン -->
        <div v-if="store.audioFile" class="mt-6 p-4 bg-white rounded-lg border border-gray-200 shadow-sm inline-block w-full max-w-md">
          <div class="flex items-center justify-between gap-2 mb-3">
            <p class="text-sm font-semibold text-gray-700 truncate text-left">{{ store.audioFile.name }}</p>
            <button 
              type="button" 
              @click="store.clearAudioFile" 
              class="text-xs font-bold text-red-500 hover:text-red-700 hover:bg-red-50 px-2.5 py-1 rounded-md transition-colors shrink-0 cursor-pointer flex items-center gap-1 border border-red-200"
              title="選択した音声ファイルを削除・解除"
            >
              <span>✖ 選択解除</span>
            </button>
          </div>
          <audio :src="store.audioPreviewUrl" controls @loadedmetadata="handleAudioMetadata" class="w-full h-10 outline-none"></audio>
        </div>
      </div>

      <!-- メタデータ入力フォーム -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5 bg-gray-50 p-6 rounded-xl border border-gray-100">
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-1">営業担当者コード</label>
          <input
            v-model="store.metadata.sales_rep_code"
            type="text"
            required
            class="w-full border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2.5 border transition-shadow"
            placeholder="例: EMP-1234"
          />
        </div>
        <div>
          <label class="block text-sm font-bold text-gray-700 mb-1">顧客電話番号</label>
          <input
            v-model="store.metadata.customer_phone"
            type="tel"
            required
            class="w-full border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2.5 border transition-shadow"
            placeholder="例: 090-1234-5678"
          />
        </div>
        <div class="md:col-span-2">
          <div class="flex items-center justify-between mb-1">
            <label class="block text-sm font-bold text-gray-700">通話時間（秒）</label>
            <span v-if="store.metadata.duration > 0" class="text-xs text-emerald-600 font-semibold flex items-center gap-1 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
              音声ファイルより自動検出されました
            </span>
          </div>
          <input
            v-model.number="store.metadata.duration"
            type="number"
            min="1"
            required
            class="w-full border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2.5 border transition-shadow"
          />
        </div>
      </div>

      <!-- 送信ボタン -->
      <button
        type="submit"
        :disabled="!store.audioFile || isUploading || store.taskStatus === 'processing'"
        class="w-full bg-blue-600 text-white font-bold py-3.5 px-4 rounded-lg hover:bg-blue-700 transition-all active:scale-[0.98] disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed shadow-sm"
      >
        {{ isUploading ? 'アップロード中...' : '登録してAI解析を開始' }}
      </button>
    </form>

    <!-- 進捗ステータスカード -->
    <div v-if="store.taskStatus !== 'idle'" class="mt-8 p-5 rounded-xl border" :class="{
      'bg-blue-50 border-blue-200': store.taskStatus === 'uploading' || store.taskStatus === 'processing',
      'bg-green-50 border-green-200': store.taskStatus === 'success',
      'bg-red-50 border-red-200': store.taskStatus === 'error'
    }">
      <h2 class="text-sm font-bold text-gray-800 mb-2">ステータス</h2>
      <div v-if="store.taskStatus === 'uploading'" class="text-blue-700 flex items-center space-x-2">
        <span class="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
        <span>音声ファイルをサーバーにアップロードしています...</span>
      </div>
      <div v-else-if="store.taskStatus === 'processing'" class="text-blue-700 flex items-center space-x-2">
        <span class="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
        <span>AI解析（文字起こし・話者分離・スコアリング）を実行中です...</span>
      </div>
      <div v-else-if="store.taskStatus === 'success'" class="text-green-700 font-medium flex items-center space-x-2">
        <span>🎉 解析が完了しました！自動的にダッシュボード画面へ移動します...</span>
      </div>
      <div v-else-if="store.taskStatus === 'error'" class="text-red-700 font-medium">
        エラーが発生しました: {{ store.taskError }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUploadStore } from '../stores/uploadStore'
import { useUploadAudio } from '../composables/useUploadAudio'
import { useTaskStatus } from '../composables/useTaskStatus'

const store = useUploadStore()
const router = useRouter()
const { mutate: uploadAudio, isPending: isUploading } = useUploadAudio()

// TanStack Queryによるポーリング開始
useTaskStatus()

// AI解析が成功完了したら、1.5秒後に自動的にダッシュボード画面 (/) へ遷移
watch(() => store.taskStatus, (newStatus) => {
  if (newStatus === 'success') {
    setTimeout(() => {
      store.resetStore()
      router.push('/')
    }, 1500)
  }
})

const isDragging = ref(false)

const handleDrop = (e) => {
  isDragging.value = false
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    store.setAudioFile(e.dataTransfer.files[0])
  }
}

const handleFileSelect = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    store.setAudioFile(e.target.files[0])
  }
}

const handleAudioMetadata = (e) => {
  const dur = Math.round(e.target.duration)
  if (!isNaN(dur) && isFinite(dur) && dur > 0) {
    store.metadata.duration = dur
  }
}

const handleSubmit = () => {
  if (store.audioFile) uploadAudio()
}
</script>