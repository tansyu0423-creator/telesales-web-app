<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  probability: {
    type: Number,
    required: true,
    default: 0
  },
  recordId: {
    type: [Number, String],
    required: true
  }
})

const containerRef = ref(null)
const currentPercent = ref(0)
const dashOffset = ref(201.06) // 201.06 = 0% (全空)
let observer = null
let animationTimer = null
let hasAnimated = false

const runAnimation = () => {
  if (hasAnimated) return
  hasAnimated = true

  const target = Math.max(0, Math.min(100, Math.round(props.probability || 0)))

  // 1. SVGストロークのCSSトランジション発火 (201.06 -> 目標オフセット)
  dashOffset.value = 201.06 - (201.06 * target / 100)

  // 2. テキスト数字のカウントアップ (0% -> target%)
  if (animationTimer) clearInterval(animationTimer)
  currentPercent.value = 0

  if (target === 0) return

  let val = 0
  const duration = 1000 // 1秒間
  const intervalTime = Math.max(10, Math.floor(duration / target))

  animationTimer = setInterval(() => {
    val += 1
    if (val >= target) {
      currentPercent.value = target
      clearInterval(animationTimer)
    } else {
      currentPercent.value = val
    }
  }, intervalTime)
}

onMounted(() => {
  // 初期状態は 0% (全空)
  dashOffset.value = 201.06
  currentPercent.value = 0

  // IntersectionObserver で画面中央付近に現れたタイミングを検知
  if (containerRef.value && 'IntersectionObserver' in window) {
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasAnimated) {
            runAnimation()
          }
        })
      },
      {
        root: null,
        rootMargin: '0px 0px -15% 0px', // 画面視野内（下部〜中央15%）に入った時点で発火
        threshold: 0.15
      }
    )
    observer.observe(containerRef.value)
  } else {
    setTimeout(runAnimation, 200)
  }
})

onUnmounted(() => {
  if (observer) observer.disconnect()
  if (animationTimer) clearInterval(animationTimer)
})

watch(() => props.probability, () => {
  hasAnimated = false
  dashOffset.value = 201.06
  currentPercent.value = 0
  setTimeout(runAnimation, 100)
})
</script>

<template>
  <div ref="containerRef" class="relative flex items-center justify-center w-20 h-20 shrink-0 bg-slate-950/60 rounded-full border border-slate-800 p-1">
    <svg class="w-full h-full -rotate-90" viewBox="0 0 80 80">
      <!-- 背景トラック -->
      <circle
        cx="40"
        cy="40"
        r="32"
        stroke="#334155"
        stroke-width="6"
        fill="none"
      />
      <!-- アニメーション付きプログレスリング -->
      <circle
        cx="40"
        cy="40"
        r="32"
        :stroke="`url(#gauge-grad-${recordId})`"
        stroke-width="6"
        stroke-linecap="round"
        fill="none"
        stroke-dasharray="201.06"
        :stroke-dashoffset="dashOffset"
        style="transition: stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1);"
      />
      <defs>
        <linearGradient :id="`gauge-grad-${recordId}`" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="100%" stop-color="#34d399" />
        </linearGradient>
      </defs>
    </svg>
    <!-- 中央パーセンテージ数値 -->
    <div class="absolute inset-0 flex items-center justify-center text-center">
      <span class="text-base font-extrabold text-white font-mono">{{ currentPercent }}%</span>
    </div>
  </div>
</template>
