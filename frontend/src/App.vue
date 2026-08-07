<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="header-inner">
        <h1 class="brand-title">テレセールス・リード・スコアリング</h1>
        <nav class="nav-links">
          <router-link to="/" class="nav-item">一覧画面</router-link>
          <router-link to="/upload" class="nav-item">音声アップロード</router-link>
        </nav>
      </div>
    </header>

    <main class="app-container">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: #1e293b;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding: 1rem 2rem;
}

.header-inner {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand-title {
  font-size: 1.2rem;
  font-weight: bold;
  color: white;
}

.nav-links {
  display: flex;
  gap: 1.5rem;
}

.nav-item {
  color: #94a3b8;
  text-decoration: none;
  font-weight: 500;
  font-size: 0.9rem;
}

.nav-item.router-link-active {
  color: #38bdf8;
  font-weight: bold;
}

.app-container {
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
  padding: 2rem;
  flex: 1;
}
</style>
