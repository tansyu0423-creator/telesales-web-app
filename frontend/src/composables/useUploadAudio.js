import { useMutation } from '@tanstack/vue-query'
import api from '../services/api'
import { useUploadStore } from '../stores/uploadStore'

export function useUploadAudio() {
    const store = useUploadStore()

    return useMutation({
        mutationFn: async () => {
            if (!store.audioFile) throw new Error("音声ファイルが選択されていません")

            const formData = new FormData()
            formData.append('file', store.audioFile)
            formData.append('sales_rep_code', store.metadata.sales_rep_code)
            formData.append('customer_phone', store.metadata.customer_phone)
            formData.append('duration', store.metadata.duration)

            // バックエンドのアップロードエンドポイントへ送信
            const response = await api.post('/records/upload-and-transcribe', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            })

            // バックエンドから返却された task_id を返す
            return response.data
        },
        onMutate: () => {
            store.setTaskState('uploading')
        },
        onSuccess: (data) => {
            store.setTaskState('processing', data.task_id)
        },
        onError: (error) => {
            console.error("Upload failed:", error)
            store.setTaskState('error', null, error.message || 'アップロードに失敗しました')
        }
    })
}