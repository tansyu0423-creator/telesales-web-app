<template>
  <div class="max-w-3xl mx-auto p-6 sm:p-8 bg-slate-900 rounded-2xl shadow-2xl border border-slate-800 mt-6 text-slate-100">
    <div class="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
      <div>
        <h1 class="text-2xl font-black text-white tracking-tight">🎙 音声ファイル・メタデータ登録</h1>
        <p class="text-xs text-slate-400 mt-1">通話音声（MP3/WAV）をアップロードし、話者分離とAIスコアリングを実行します。</p>
      </div>
      <span class="px-3 py-1 bg-sky-950 border border-sky-800 text-sky-300 text-xs font-bold rounded-full">New Record</span>
    </div>

    <!-- アップロードフォーム -->
    <form @submit.prevent="handleSubmit" class="space-y-6">
      
      <!-- ドラッグ＆ドロップ対応 ファイルアップロード領域 -->
      <div
        class="border-2 border-dashed rounded-2xl p-8 sm:p-10 text-center transition-all duration-200"
        :class="isDragging ? 'border-sky-400 bg-sky-950/60 shadow-lg shadow-sky-500/10' : 'border-slate-700 bg-slate-950/60 hover:border-slate-500 hover:bg-slate-950/80'"
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
          <div class="p-4 bg-sky-950 border border-sky-800 rounded-full text-sky-400 shadow-inner">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
          </div>
          <span class="text-slate-200 font-semibold text-sm">
            ここに音声ファイルをドラッグ＆ドロップするか、
            <span class="text-sky-400 hover:text-sky-300 underline font-bold">ファイルを選択</span>
          </span>
          <span class="text-xs text-slate-400">対応フォーマット: MP3, WAV (最大 25MB)</span>
        </label>

        <!-- 選択されたファイル名と試聴プレビュー ＆ クリアボタン -->
        <div v-if="store.audioFile" class="mt-6 p-4 bg-slate-900 rounded-xl border border-slate-700 shadow-md inline-block w-full max-w-md">
          <div class="flex items-center justify-between gap-2 mb-3">
            <p class="text-xs font-bold text-sky-300 truncate text-left font-mono">🎵 {{ store.audioFile.name }}</p>
            <button 
              type="button" 
              @click="store.clearAudioFile" 
              class="text-xs font-bold text-rose-400 hover:text-rose-300 hover:bg-rose-950/80 px-2.5 py-1 rounded-md transition-colors shrink-0 cursor-pointer flex items-center gap-1 border border-rose-800/80"
              title="選択した音声ファイルを削除・解除"
            >
              <span>✖ 選択解除</span>
            </button>
          </div>
          <audio :src="store.audioPreviewUrl" controls @loadedmetadata="handleAudioMetadata" class="w-full h-10 outline-none rounded-lg"></audio>
        </div>
      </div>

      <!-- メタデータ入力フォーム -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5 bg-slate-950/80 p-6 rounded-2xl border border-slate-800 shadow-inner">
        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">営業担当者コード <span class="text-rose-400">*</span></label>
          <input
            v-model="store.metadata.sales_rep_code"
            type="text"
            required
            class="w-full bg-slate-900 border-slate-700 text-white placeholder-slate-500 rounded-xl shadow-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 p-3 border text-sm font-semibold transition-all outline-none"
            placeholder="例: EMP-101"
          />
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">顧客電話番号 <span class="text-rose-400">*</span></label>
          <input
            v-model="store.metadata.customer_phone"
            type="tel"
            required
            class="w-full bg-slate-900 border-slate-700 text-white placeholder-slate-500 rounded-xl shadow-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 p-3 border text-sm font-semibold transition-all outline-none"
            placeholder="例: 090-1234-5678"
          />
        </div>
        <div class="md:col-span-2">
          <div class="flex items-center justify-between mb-1.5">
            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider">通話時間（秒） <span class="text-rose-400">*</span></label>
            <span v-if="store.metadata.duration > 0" class="text-[11px] text-emerald-300 font-semibold flex items-center gap-1 bg-emerald-950/80 px-2.5 py-0.5 rounded-full border border-emerald-800">
              ✨ 音声ファイルより自動検出されました
            </span>
          </div>
          <input
            v-model.number="store.metadata.duration"
            type="number"
            min="1"
            required
            class="w-full bg-slate-900 border-slate-700 text-white placeholder-slate-500 rounded-xl shadow-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 p-3 border text-sm font-bold transition-all outline-none font-mono"
          />
        </div>
      </div>

      <!-- 送信ボタン -->
      <button
        type="submit"
        :disabled="!store.audioFile || isUploading || store.taskStatus === 'processing'"
        class="w-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-600 hover:from-sky-400 hover:to-purple-500 text-white font-black py-4 px-4 rounded-xl transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-sky-500/25 text-sm tracking-wide cursor-pointer border border-sky-400/30"
      >
        {{ isUploading ? 'アップロード中...' : '登録してAI解析を開始 ➔' }}
      </button>
    </form>

    <!-- 進捗ステータスカード -->
    <div v-if="store.taskStatus !== 'idle'" class="mt-8 p-6 rounded-2xl border transition-all duration-300 shadow-md" :class="{
      'bg-slate-950 border-sky-800 text-sky-100': store.taskStatus === 'uploading' || store.taskStatus === 'processing',
      'bg-emerald-950/80 border-emerald-700 text-emerald-100': store.taskStatus === 'success',
      'bg-rose-950/90 border-rose-800 text-rose-100': store.taskStatus === 'error'
    }">
      <div class="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
        <h2 class="text-sm font-bold flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full" :class="{
            'bg-sky-400 animate-ping': store.taskStatus === 'processing' || store.taskStatus === 'uploading',
            'bg-emerald-400': store.taskStatus === 'success',
            'bg-rose-500': store.taskStatus === 'error'
          }"></span>
          <span>処理ステータス</span>
        </h2>
        <span class="text-xs font-mono px-2.5 py-0.5 rounded-full border" :class="{
          'bg-sky-950 border-sky-700 text-sky-300': store.taskStatus === 'processing' || store.taskStatus === 'uploading',
          'bg-emerald-900 border-emerald-600 text-emerald-200': store.taskStatus === 'success',
          'bg-rose-900 border-rose-600 text-rose-200': store.taskStatus === 'error'
        }">
          {{ store.taskStatus.toUpperCase() }}
        </span>
      </div>

      <div v-if="store.taskStatus === 'uploading'" class="flex items-center space-x-3 py-2">
        <span class="animate-spin h-5 w-5 border-2 border-sky-400 border-t-transparent rounded-full shrink-0"></span>
        <span class="text-sm font-medium">音声ファイルをサーバーに安全にアップロードしています...</span>
      </div>

      <!-- 3段階ステップ進行ローディングアニメーション -->
      <div v-else-if="store.taskStatus === 'processing'" class="space-y-4 py-2">
        <div class="text-xs font-semibold text-sky-300 flex items-center gap-2 mb-1">
          <span class="animate-spin h-4 w-4 border-2 border-sky-400 border-t-transparent rounded-full shrink-0"></span>
          <span>AI解析パイプラインを実行中です（約10〜20秒で完了します）</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div class="p-3 bg-slate-900 border border-sky-800 rounded-xl flex items-center gap-2.5">
            <span class="w-6 h-6 rounded-full bg-sky-900 border border-sky-600 text-sky-300 flex items-center justify-center font-bold text-[10px] shrink-0 animate-pulse">1</span>
            <div>
              <div class="font-bold text-white">🎙 文字起こし (STT)</div>
              <div class="text-[10px] text-slate-400">Groq Whisper (ja, t=0)</div>
            </div>
          </div>
          <div class="p-3 bg-slate-900 border border-indigo-800 rounded-xl flex items-center gap-2.5">
            <span class="w-6 h-6 rounded-full bg-indigo-900 border border-indigo-600 text-indigo-300 flex items-center justify-center font-bold text-[10px] shrink-0 animate-pulse">2</span>
            <div>
              <div class="font-bold text-white">👤 話者分離 ＆ 役割識別</div>
              <div class="text-[10px] text-slate-400">Pyannote + Llama 3.3</div>
            </div>
          </div>
          <div class="p-3 bg-slate-900 border border-purple-800 rounded-xl flex items-center gap-2.5">
            <span class="w-6 h-6 rounded-full bg-purple-900 border border-purple-600 text-purple-300 flex items-center justify-center font-bold text-[10px] shrink-0 animate-pulse">3</span>
            <div>
              <div class="font-bold text-white">🤖 AIスコアリング</div>
              <div class="text-[10px] text-slate-400">Gemini 2.0 Flash (Few-shot)</div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="store.taskStatus === 'success'" class="font-medium flex items-center space-x-2 py-2 text-emerald-200">
        <span class="text-lg">🎉</span>
        <span class="text-sm">解析が完了しました！自動的にダッシュボード画面へ移動します...</span>
      </div>

      <div v-else-if="store.taskStatus === 'error'" class="space-y-3 py-1">
        <div class="flex items-start gap-2 text-rose-200">
          <span class="text-base shrink-0">⚠️</span>
          <div class="text-sm font-medium">エラーが発生しました: {{ store.taskError }}</div>
        </div>
        <button 
          @click="store.resetStore()" 
          class="px-3.5 py-1.5 bg-rose-900 hover:bg-rose-800 text-white rounded-lg text-xs font-bold transition-all border border-rose-700 cursor-pointer shadow-sm"
        >
          🔄 リセットして再試行
        </button>
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
  const duration = Math.round(e.target.duration)
  if (duration && !isNaN(duration)) {
    store.metadata.duration = duration
  }
}

const handleSubmit = () => {
  if (!store.audioFile) {
    alert('音声ファイルを選択してください')
    return
  }
  uploadAudio()
}
</script>