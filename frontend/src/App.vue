<template>
  <div class="min-h-screen bg-slate-950 text-slate-100">
    <header class="bg-slate-900 border-b border-slate-800 shadow-lg">
      <div class="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center space-x-8">
            <h1 class="text-xl font-black text-sky-400">AI Telesales Scoring</h1>
            <nav class="hidden md:flex space-x-4">
              <RouterLink to="/" class="text-slate-400 hover:text-sky-400 px-3 py-2 rounded-md text-sm font-medium transition-colors" exact-active-class="text-sky-400 bg-sky-950/60 border border-sky-800/60">
                ダッシュボード
              </RouterLink>
              <RouterLink to="/upload" class="text-slate-400 hover:text-sky-400 px-3 py-2 rounded-md text-sm font-medium transition-colors" exact-active-class="text-sky-400 bg-sky-950/60 border border-sky-800/60">
                音声アップロード
              </RouterLink>
            </nav>
          </div>
        </div>
      </div>
    </header>

    <main class="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>