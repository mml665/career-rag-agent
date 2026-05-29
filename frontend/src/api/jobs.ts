import api from './index'
import type { JobPosting } from './types'

export const listJobs = () =>
  api.get<JobPosting[]>('/jobs').then((r) => r.data)

export const addJob = (data: Partial<JobPosting>) =>
  api.post<JobPosting>('/jobs', data).then((r) => r.data)

export const deleteJob = (id: string) =>
  api.delete(`/jobs/${id}`)
