import api from './index'
import type { AskResponse, SearchResult, DocumentInfo, HistoryRecord, AgentResponse, ResumeExtraction, JobExtraction, TailorResult, SemanticMatchResult } from './types'

// Config
export const isConfigured = () =>
  api.get<{ configured: boolean }>('/library/configured').then((r) => r.data.configured)

export const getUploadDir = () =>
  api.get<{ upload_dir: string }>('/library/upload-dir').then((r) => r.data.upload_dir)

// Q&A
export const ask = (question: string, topK = 4) =>
  api.post<AskResponse>('/library/ask', { question, top_k: topK }).then((r) => r.data)

// Search
export const search = (question: string, topK = 5) =>
  api.get<SearchResult[]>('/library/search', { params: { question, top_k: topK } }).then((r) => r.data)

// Index
export const ingestAll = (params?: { enable_bm25?: boolean; bm25_weight?: number; vector_weight?: number; rrf_k?: number; enable_rerank?: boolean; rerank_top_n?: number }) =>
  api.post<{ count: number }>('/library/index', params || {}).then((r) => r.data.count)

// Upload
export const uploadFile = (filename: string, content: Blob) =>
  api.post('/library/upload', { file: new File([content], filename) }, { headers: { 'Content-Type': 'multipart/form-data' } })

// Documents
export const listDocuments = () =>
  api.get<DocumentInfo[]>('/library/documents').then((r) => r.data)

export const deleteDocument = (path: string) =>
  api.delete(`/library/documents/${encodeURIComponent(path)}`)

export const clearDocuments = () =>
  api.delete('/library/documents')

// Extract
export const extractResume = (filename: string, content: Blob) =>
  api.post<ResumeExtraction>('/library/extract-resume', { file: new File([content], filename) }, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)

export const extractJobText = (rawDescription: string) =>
  api.post<JobExtraction>('/library/extract-job-text', { raw_description: rawDescription }).then((r) => r.data)

export const extractJobFile = (filename: string, content: Blob) =>
  api.post<JobExtraction>('/library/extract-job-file', { file: new File([content], filename) }, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)

// Semantic Match
export const semanticMatch = (jobDescription: string, evidence: [string, string][], keywordSummary: string) =>
  api.post<SemanticMatchResult>('/library/semantic-match', {
    job_description: jobDescription,
    evidence,
    keyword_summary: keywordSummary,
  }).then((r) => r.data)

// Tailor Resume
export const tailorResume = (jobDescription: string, evidence: string[], currentText = '', request = '') =>
  api.post<TailorResult>('/library/tailor-resume', {
    job_description: jobDescription,
    evidence,
    current_text: currentText,
    request,
  }).then((r) => r.data)

// Export
export const exportResume = (
  format: 'docx' | 'pdf',
  payload: { name?: string; content?: string; target_category?: string } = {},
) =>
  api.post('/library/export-resume', { format, ...payload }, { responseType: 'blob' }).then((r) => r.data)

// Agent
export const agentChat = (message: string, maxIterations = 10) =>
  api.post<AgentResponse>('/library/agent', { message, max_iterations: maxIterations }).then((r) => r.data)

// Summarize
export const summarize = () =>
  api.post<any>('/library/summarize').then((r) => r.data)

// History
export const loadHistory = (limit?: number) =>
  api.get<HistoryRecord[]>('/library/history', { params: limit ? { limit } : {} }).then((r) => r.data)

export const deleteHistoryRecord = (id: string) =>
  api.delete(`/library/history/${id}`)

export const clearHistory = () =>
  api.delete('/library/history')
