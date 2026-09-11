import api from './index'
import type { MatchAnalysis, MatchFeedback } from './types'

export const listAnalyses = (jobId?: string) =>
  api.get<MatchAnalysis[]>('/analyses', { params: jobId ? { job_id: jobId } : {} }).then((r) => r.data)

export const analyzeMatch = (jobId: string) =>
  api.post<MatchAnalysis>('/analyses', null, { params: { job_id: jobId } }).then((r) => r.data)

export const enhanceAnalysis = (id: string, data: { semantic_score: number; semantic_evidence_ids?: string[]; model_explanation?: string }) =>
  api.put<MatchAnalysis>(`/analyses/${id}`, data).then((r) => r.data)

export const deleteAnalysis = (id: string) =>
  api.delete(`/analyses/${id}`)

export const listMatchFeedback = (analysisId?: string) =>
  api.get<MatchFeedback[]>('/analyses/feedback', { params: analysisId ? { analysis_id: analysisId } : {} }).then((r) => r.data)

export const addMatchFeedback = (data: { analysis_id: string; rating: string; issue_type?: string; comment?: string; correction?: string }) =>
  api.post<MatchFeedback>('/analyses/feedback', data).then((r) => r.data)
