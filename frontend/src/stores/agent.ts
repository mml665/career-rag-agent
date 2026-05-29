import { defineStore } from 'pinia'
import { ref } from 'vue'
import { agentChat } from '@/api/library'
import type { AgentStepResponse } from '@/api/types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  steps?: AgentStepResponse[]
}

export const useAgentStore = defineStore('agent', () => {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)

  async function send(text: string) {
    messages.value.push({ role: 'user', content: text })
    loading.value = true
    try {
      const res = await agentChat(text)
      messages.value.push({
        role: 'assistant',
        content: res.answer,
        steps: res.steps,
      })
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || '请求失败，请稍后重试。'
      messages.value.push({ role: 'assistant', content: `错误: ${msg}` })
    } finally {
      loading.value = false
    }
  }

  function clear() {
    messages.value = []
  }

  return { messages, loading, send, clear }
})
