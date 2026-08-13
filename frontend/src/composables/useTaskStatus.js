import { useQuery } from '@tanstack/vue-query'
import api from '../services/api'
import { useUploadStore } from '../stores/uploadStore'
import { computed } from 'vue'

export function useTaskStatus() {
    const store = useUploadStore()

    return useQuery({
        queryKey: ['taskStatus', computed(() => store.taskId)],

        queryFn: async () => {
            if (!store.taskId) return null

            const response = await api.get(`/tasks/${store.taskId}`)
            const data = response.data

            if (data.status === 'SUCCESS') {
                store.setTaskState('success')
            } else if (data.status === 'FAILURE') {
                store.setTaskState('error', null, data.error || 'バックグラウンド処理でエラーが発生しました')
            }

            return data
        },

        // taskId が存在し、かつステータスが 'processing' の時だけクエリを実行
        enabled: computed(() => !!store.taskId && store.taskStatus === 'processing'),

        // 2秒間隔で自動再フェッチ（ポーリング）
        refetchInterval: 2000,
        refetchOnWindowFocus: false,
    })
}