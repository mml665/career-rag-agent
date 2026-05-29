import api from './index'
import type { ResumeVersion } from './types'

export const listResumeVersions = (jobId?: string) =>
  api.get<ResumeVersion[]>('/resume-versions', { params: jobId ? { job_id: jobId } : {} }).then((r) => r.data)

export const addResumeVersion = (data: Partial<ResumeVersion>) =>
  api.post<ResumeVersion>('/resume-versions', data).then((r) => r.data)

export const deleteResumeVersion = (id: string) =>
  api.delete(`/resume-versions/${id}`)
