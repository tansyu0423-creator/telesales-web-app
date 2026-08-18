<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  src: {
    type: String,
    required: true
  }
})

const audioRef = ref(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const isMuted = ref(false)
const showVolumeSlider = ref(false)
const stopTime = ref(null)

const formatTime = (seconds) => {
  if (isNaN(seconds) || !isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s < 10 ? '0' : ''}${s}`
}

const togglePlay = () => {
  if (!audioRef.value) return
  stopTime.value = null
  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
}

const onTimeUpdate = () => {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
    if (stopTime.value !== null && audioRef.value.currentTime >= stopTime.value) {
      audioRef.value.pause()
      stopTime.value = null
      isPlaying.value = false
    }
  }
}

const onLoadedMetadata = () => {
  if (audioRef.value) {
    duration.value = audioRef.value.duration
  }
}

const onEnded = () => {
  isPlaying.value = false
  currentTime.value = 0
  stopTime.value = null
}

const seek = (e) => {
  if (!audioRef.value) return
  stopTime.value = null
  const time = parseFloat(e.target.value)
  audioRef.value.currentTime = time
  currentTime.value = time
}

const changeVolume = (e) => {
  const vol = parseFloat(e.target.value)
  volume.value = vol
  if (audioRef.value) {
    audioRef.value.volume = vol
    isMuted.value = vol === 0
  }
}

const toggleMute = () => {
  if (!audioRef.value) return
  if (isMuted.value) {
    audioRef.value.volume = volume.value > 0 ? volume.value : 0.8
    isMuted.value = false
  } else {
    audioRef.value.volume = 0
    isMuted.value = true
  }
}

watch(() => props.src, () => {
  isPlaying.value = false
  currentTime.value = 0
  stopTime.value = null
  if (audioRef.value) {
    audioRef.value.load()
  }
})

const seekToAndPlay = async (seconds, stopAt = null) => {
  if (!audioRef.value) return
  const targetTime = Math.max(0, parseFloat(seconds) || 0)
  if (stopAt !== null && stopAt !== undefined && parseFloat(stopAt) > targetTime) {
    stopTime.value = parseFloat(stopAt)
  } else {
    stopTime.value = null
  }
  
  try {
    if (audioRef.value.readyState === 0) {
      audioRef.value.load()
    }
    audioRef.value.currentTime = targetTime
    currentTime.value = targetTime
    if (audioRef.value.paused) {
      await audioRef.value.play()
      isPlaying.value = true
    }
  } catch (err) {
    console.error("Audio playback error:", err)
  }
}

defineExpose({
  seekToAndPlay
})

onUnmounted(() => {
  if (audioRef.value) {
    audioRef.value.pause()
  }
})
</script>

<template>
  <div class="relative flex items-center gap-3 w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-3.5 py-2 text-slate-200 shadow-inner">
    <audio 
      ref="audioRef" 
      :src="src" 
      @timeupdate="onTimeUpdate" 
      @loadedmetadata="onLoadedMetadata" 
      @play="isPlaying = true" 
      @pause="isPlaying = false" 
      @ended="onEnded" 
      preload="metadata"
      class="hidden"
    ></audio>

    <!-- 再生/一時停止ボタン -->
    <button 
      type="button" 
      @click="togglePlay" 
      class="w-8 h-8 flex items-center justify-center bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-full font-bold transition-all shadow-md shrink-0 cursor-pointer"
    >
      <span v-if="!isPlaying" class="ml-0.5 text-xs">▶</span>
      <span v-else class="text-xs">❚❚</span>
    </button>

    <!-- 時間表示 -->
    <span class="text-xs font-mono text-slate-400 shrink-0 min-w-[75px]">
      {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
    </span>

    <!-- シークバー (タイムライン) -->
    <div class="relative flex-1 min-w-0 flex items-center">
      <input 
        type="range" 
        min="0" 
        :max="duration || 100" 
        step="0.1" 
        :value="currentTime" 
        @input="seek" 
        class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400 focus:outline-none"
      />
    </div>

    <!-- 音量調整ボタン ＆ 縦向き（上方向）ポップアップバー -->
    <div 
      class="relative shrink-0 flex items-center" 
      @mouseleave="showVolumeSlider = false"
    >
      <!-- 音量アイコンボタン -->
      <button 
        type="button" 
        @click="toggleMute" 
        @mouseenter="showVolumeSlider = true" 
        class="p-1.5 text-slate-400 hover:text-white rounded-lg transition-colors cursor-pointer"
        title="音量調整"
      >
        <span v-if="isMuted || volume === 0">🔇</span>
        <span v-else-if="volume < 0.5">🔉</span>
        <span v-else>🔊</span>
      </button>

      <!-- 縦向き（上方向 popup）音量スライダー -->
      <div 
        v-show="showVolumeSlider" 
        class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 p-3 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 flex flex-col items-center gap-2 backdrop-blur-md"
      >
        <span class="text-[10px] font-mono text-slate-300 font-bold">{{ Math.round((isMuted ? 0 : volume) * 100) }}%</span>
        <div class="h-24 flex items-center justify-center px-1">
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.01" 
            :value="isMuted ? 0 : volume" 
            @input="changeVolume" 
            class="h-20 w-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400 focus:outline-none [writing-mode:vertical-lr] [direction:rtl]"
          />
        </div>
      </div>
    </div>
  </div>
</template>
