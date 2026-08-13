import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useUploadStore = defineStore('upload', () => {
    // === 1. 状態 (State) ===

    // 音声ファイルとプレビュー用URL
    const audioFile = ref(null)
    const audioPreviewUrl = ref(null)

    // 入力フォームのメタデータ
    const metadata = reactive({
        sales_rep_code: '',
        customer_phone: '',
        duration: 0
    })

    // バックグラウンド処理（Celeryタスク）の管理
    const taskId = ref(null)
    const taskStatus = ref('idle') // idle, uploading, processing, success, error
    const taskError = ref(null)

    // === 2. アクション (Actions) ===

    // ファイルをセットし、プレビュー用のURLを生成する ＆ 通話時間(秒)を自動検出する
    const setAudioFile = (file) => {
        audioFile.value = file
        if (audioPreviewUrl.value) {
            URL.revokeObjectURL(audioPreviewUrl.value) // メモリリーク防止
        }
        if (file) {
            const url = URL.createObjectURL(file)
            audioPreviewUrl.value = url

            // イベントリスナーを src 代入前に登録して確実に発火させる
            const audio = new Audio()
            audio.preload = 'metadata'
            audio.onloadedmetadata = () => {
                const dur = Math.round(audio.duration)
                if (!isNaN(dur) && isFinite(dur) && dur > 0) {
                    metadata.duration = dur
                }
            }
            audio.src = url
            audio.load()
        }
    }

    // ドラッグ＆ドロップなどでファイルをクリアする時用
    const clearAudioFile = () => {
        audioFile.value = null
        if (audioPreviewUrl.value) {
            URL.revokeObjectURL(audioPreviewUrl.value)
            audioPreviewUrl.value = null
        }
        metadata.duration = 0
    }

    // タスクの進捗ステータスを更新する
    const setTaskState = (status, id = null, error = null) => {
        taskStatus.value = status
        if (id) taskId.value = id
        if (error) taskError.value = error
    }

    // フォーム全体の初期化（アップロード完了後に次の入力へ備えるため）
    const resetStore = () => {
        clearAudioFile()
        metadata.sales_rep_code = ''
        metadata.customer_phone = ''
        metadata.duration = 0
        taskId.value = null
        taskStatus.value = 'idle'
        taskError.value = null
    }

    return {
        audioFile,
        audioPreviewUrl,
        metadata,
        taskId,
        taskStatus,
        taskError,
        setAudioFile,
        clearAudioFile,
        setTaskState,
        resetStore
    }
})