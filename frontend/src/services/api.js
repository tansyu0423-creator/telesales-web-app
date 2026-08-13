import axios from 'axios'

const api = axios.create({
    // FastAPIのデフォルトポートを指定（環境に合わせて変更してください）
    baseURL: 'http://localhost:8000',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 必要に応じてリクエスト・レスポンスのインターセプターをここに追加できます
api.interceptors.response.use(
    response => response,
    error => {
        console.error('API Error:', error.response || error.message)
        return Promise.reject(error)
    }
)

export default api