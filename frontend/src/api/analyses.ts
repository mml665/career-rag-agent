import api from './index'
import type { MatchAnalysis } from './types'

export const listAnalyses = (jobId?: string) =>
  api.get<MatchAnalysis[]>('/analyses', { params: jobId ? { job_id: jobId } : {} }).then((r) => r.data)

export const analyzeMatch = (jobId: string) =>
  api.post<MatchAnalysis>('/analyses', null, { params: { job_id: jobId } }).then((r) => r.data)

export const enhanceAnalysis = (id: string, data: { semantic_score: number; semantic_evidence_ids?: string[]; model_explanation?: string }) =>
  api.put<MatchAnalysis>(`/analyses/${id}`, data).then((r) => r.data)

export const deleteAnalysis = (id: string) =>
  api.delete(`/analyses/${id}`)
