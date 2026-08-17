import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('auth_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('auth_user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  const login = async (username, password) => {
    try {
      const res = await axios.post('http://localhost:8000/login', {
        username,
        password
      })

      token.value = res.data.access_token
      user.value = {
        username: res.data.username,
        name: res.data.name,
        role: res.data.role
      }

      localStorage.setItem('auth_token', token.value)
      localStorage.setItem('auth_user', JSON.stringify(user.value))

      return { success: true }
    } catch (err) {
      const message = err.response?.data?.detail || 'ログイン処理に失敗しました。'
      return { success: false, message }
    }
  }

  const logout = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    logout
  }
})
