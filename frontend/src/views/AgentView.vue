<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { Promotion } from '@element-plus/icons-vue'
import { marked } from 'marked'

const store = useAgentStore()
const input = ref('')
const chatContainer = ref<HTMLElement>()

function handleSend() {
  const text = input.value.trim()
  if (!text || store.loading) return
  input.value = ''
  store.send(text)
}

function renderMd(text: string) {
  return marked.parse(text) as string
}

watch(() => store.messages.length, () => {
  nextTick(() => {
    chatContainer.value?.scrollTo({ top: chatContainer.value.scrollHeight, behavior: 'smooth' })
  })
})
</script>

<template>
  <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>智能助手</h2>
      <p>与 AI 对话，自主调用工具完成求职任务</p>
    </div>
    <el-button text @click="store.clear()">清空对话</el-button>
  </div>

  <!-- 聊天区域 -->
  <div class="chat-container" ref="chatContainer">
    <div v-if="!store.messages.length" style="text-align:center;color:var(--color-muted);padding:60px 0">
      <el-icon :size="48"><ChatDotRound /></el-icon>
      <p style="margin-top:12px">输入问题开始对话</p>
      <p style="font-size:12px">例如："列出所有岗位"、"分析岗位匹配度"、"定制简历"</p>
    </div>

    <div v-for="(msg, i) in store.messages" :key="i" :class="['chat-msg', msg.role]">
      <div class="chat-avatar">
        <el-icon v-if="msg.role === 'user'" :size="18"><User /></el-icon>
        <el-icon v-else :size="18"><Monitor /></el-icon>
      </div>
      <div class="chat-bubble">
        <div v-if="msg.role === 'assistant'" v-html="renderMd(msg.content)" class="markdown-body"></div>
        <div v-else>{{ msg.content }}</div>

        <!-- 工具调用步骤 -->
        <el-collapse v-if="msg.steps?.length" style="margin-top:8px;border:none">
          <el-collapse-item>
            <template #title>
              <el-text type="info" size="small">执行了 {{ msg.steps.length }} 个工具调用</el-text>
            </template>
            <div v-for="(step, j) in msg.steps" :key="j" style="margin-bottom:8px;font-size:12px">
              <el-tag size="small" type="info">{{ step.tool_name }}</el-tag>
              <pre style="margin:4px 0;background:#f5f5f5;padding:6px;border-radius:4px;overflow-x:auto;font-size:11px">{{ step.tool_output }}</pre>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <div v-if="store.loading" class="chat-msg assistant">
      <div class="chat-avatar"><el-icon :size="18"><Monitor /></el-icon></div>
      <div class="chat-bubble">
        <el-icon class="is-loading"><Loading /></el-icon> 思考中...
      </div>
    </div>
  </div>

  <!-- 输入框 -->
  <div class="chat-input">
    <el-input
      v-model="input"
      placeholder="输入您的问题..."
      :disabled="store.loading"
      @keyup.enter="handleSend"
    >
      <template #append>
        <el-button :icon="Promotion" :disabled="store.loading || !input.trim()" @click="handleSend" />
      </template>
    </el-input>
  </div>
</template>

<style scoped>
.chat-container {
  height: calc(100vh - 220px);
  overflow-y: auto;
  padding: 16px 0;
}
.chat-msg {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  max-width: 800px;
}
.chat-msg.user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.chat-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chat-msg.user .chat-avatar {
  background: var(--color-primary);
  color: white;
}
.chat-msg.assistant .chat-avatar {
  background: var(--color-primary-light);
  color: var(--color-primary);
}
.chat-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  max-width: calc(100% - 48px);
}
.chat-msg.user .chat-bubble {
  background: var(--color-primary);
  color: white;
  border-top-right-radius: 4px;
}
.chat-msg.assistant .chat-bubble {
  background: var(--color-white);
  border: 1px solid var(--color-border);
  border-top-left-radius: 4px;
}
.chat-input {
  position: sticky;
  bottom: 0;
  background: var(--color-bg);
  padding: 12px 0;
}
.markdown-body :deep(p) { margin: 4px 0; }
.markdown-body :deep(ul) { margin: 4px 0; padding-left: 20px; }
</style>
