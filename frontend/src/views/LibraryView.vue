<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listDocuments, uploadFile, clearDocuments, deleteDocument,
  ingestAll, ask, search, summarize, loadHistory, clearHistory, deleteHistoryRecord,
} from '@/api/library'
import { useSettingsStore } from '@/stores/settings'
import type { DocumentInfo, SearchResult, HistoryRecord, AskResponse } from '@/api/types'

const settings = useSettingsStore()
const activeTab = ref('manage')

// Document management
const documents = ref<DocumentInfo[]>([])
const uploadLoading = ref(false)
const indexLoading = ref(false)

// Q&A
const question = ref('')
const askResult = ref<AskResponse | null>(null)
const askLoading = ref(false)

// Search
const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const searchLoading = ref(false)

// Summary & History
const summaryResult = ref<any>(null)
const history = ref<HistoryRecord[]>([])
const summaryLoading = ref(false)

async function loadDocuments() {
  try { documents.value = await listDocuments() } catch {}
}
async function loadHistoryData() {
  try { history.value = await loadHistory() } catch {}
}

onMounted(() => { loadDocuments(); loadHistoryData() })

async function handleUpload(files: File[]) {
  uploadLoading.value = true
  try {
    for (const f of files) {
      await uploadFile(f.name, f)
    }
    ElMessage.success(`已上传 ${files.length} 个文件`)
    await loadDocuments()
  } finally { uploadLoading.value = false }
}

async function handleIndex() {
  indexLoading.value = true
  try {
    const count = await ingestAll({
      enable_bm25: settings.enableBm25,
      bm25_weight: settings.bm25Weight,
      vector_weight: settings.vectorWeight,
      rrf_k: settings.rrfK,
      enable_rerank: settings.enableRerank,
      rerank_top_n: settings.rerankTopN,
    })
    ElMessage.success(`已索引 ${count} 个片段`)
  } finally { indexLoading.value = false }
}

async function handleClearDocs() {
  await clearDocuments()
  documents.value = []
  ElMessage.success('已清空')
}

async function handleDeleteDoc(path: string) {
  await deleteDocument(path)
  await loadDocuments()
}

async function handleAsk() {
  if (!question.value.trim()) return
  askLoading.value = true
  try {
    askResult.value = await ask(question.value, settings.topK)
  } finally { askLoading.value = false }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  searchLoading.value = true
  try {
    searchResults.value = await search(searchQuery.value, settings.topK)
  } finally { searchLoading.value = false }
}

async function handleSummarize() {
  summaryLoading.value = true
  try {
    summaryResult.value = await summarize()
  } finally { summaryLoading.value = false }
}

async function handleClearHistory() {
  await clearHistory()
  history.value = []
  ElMessage.success('已清空历史')
}

async function handleDeleteHistory(id: string) {
  await deleteHistoryRecord(id)
  await loadHistoryData()
}
</script>

<template>
  <div class="page-header">
    <h2>参考资料库</h2>
    <p>管理参考资料，支持 RAG 问答和检索</p>
  </div>

  <el-tabs v-model="activeTab">
    <!-- 资料管理 -->
    <el-tab-pane label="资料管理" name="manage">
      <div class="card-section">
        <el-upload
          :auto-upload="false" :show-file-list="false" multiple accept=".pdf,.md,.txt"
          :disabled="uploadLoading"
          @change="(f: any) => f.raw && handleUpload([f.raw])"
        >
          <el-button :loading="uploadLoading" type="primary" plain>
            <el-icon><Upload /></el-icon> 上传文件
          </el-button>
          <template #tip><div class="el-upload__tip">支持 PDF / Markdown / TXT，可多选</div></template>
        </el-upload>
        <div style="margin-top:12px">
          <el-button :loading="indexLoading" @click="handleIndex">重建索引</el-button>
          <el-button type="danger" text @click="handleClearDocs">清空全部</el-button>
        </div>
      </div>
      <div class="card-section" v-if="documents.length">
        <h3>已上传文档 ({{ documents.length }})</h3>
        <div v-for="d in documents" :key="d.path" style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--color-border)">
          <span>{{ d.name }}</span>
          <el-button type="danger" size="small" text @click="handleDeleteDoc(d.path)">删除</el-button>
        </div>
      </div>
    </el-tab-pane>

    <!-- 资料问答 -->
    <el-tab-pane label="资料问答" name="qa">
      <div class="card-section">
        <el-input v-model="question" type="textarea" :rows="3" placeholder="输入问题..." />
        <el-button type="primary" :loading="askLoading" style="margin-top:12px" @click="handleAsk">基于资料回答</el-button>
      </div>
      <div class="card-section" v-if="askResult">
        <h3>回答</h3>
        <p style="white-space:pre-wrap">{{ askResult.answer }}</p>
        <div v-if="askResult.sources?.length" style="margin-top:8px">
          <el-text type="info" size="small">参考来源：</el-text>
          <div v-for="(s, i) in askResult.sources" :key="i" style="font-size:12px;color:var(--color-muted);margin-top:2px">
            {{ s.source }} (chunk #{{ s.chunk_index }})
          </div>
        </div>
      </div>
    </el-tab-pane>

    <!-- 检索调试 -->
    <el-tab-pane label="检索调试" name="debug">
      <div class="card-section">
        <el-input v-model="searchQuery" placeholder="输入检索查询" @keyup.enter="handleSearch" />
        <el-button type="primary" :loading="searchLoading" style="margin-top:12px" @click="handleSearch">查看召回片段</el-button>
      </div>
      <div class="card-section" v-if="searchResults.length">
        <h3>召回结果 ({{ searchResults.length }})</h3>
        <div v-for="(r, i) in searchResults" :key="i" style="padding:8px 0;border-bottom:1px solid var(--color-border)">
          <div style="display:flex;gap:8px;align-items:center">
            <el-tag :type="r.accepted ? 'success' : 'info'" size="small">{{ r.accepted ? '通过' : '过滤' }}</el-tag>
            <el-text type="info" size="small">{{ r.source }} · 分数: {{ r.score.toFixed(3) }}</el-text>
          </div>
          <p style="margin:4px 0 0;font-size:13px;color:var(--color-muted)">{{ r.content }}</p>
        </div>
      </div>
    </el-tab-pane>

    <!-- 摘要与历史 -->
    <el-tab-pane label="摘要与历史" name="history">
      <div class="card-section">
        <el-button :loading="summaryLoading" @click="handleSummarize">生成资料摘要</el-button>
        <el-button type="danger" text @click="handleClearHistory">清空全部历史</el-button>
      </div>
      <div class="card-section" v-if="summaryResult">
        <h3>摘要</h3>
        <p style="white-space:pre-wrap">{{ summaryResult.summary || JSON.stringify(summaryResult) }}</p>
      </div>
      <div class="card-section" v-if="history.length">
        <h3>问答历史 ({{ history.length }})</h3>
        <el-collapse>
          <el-collapse-item v-for="h in history" :key="h.history_id">
            <template #title>
              <div style="flex:1;font-size:13px">{{ h.question }}</div>
            </template>
            <p style="font-size:13px;white-space:pre-wrap">{{ h.answer }}</p>
            <el-button type="danger" size="small" text @click="handleDeleteHistory(h.history_id)">删除</el-button>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-tab-pane>
  </el-tabs>
</template>
