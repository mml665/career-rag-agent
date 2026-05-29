import api from './index'
import type { ApplicationRecord } from './types'

export const listApplications = () =>
  api.get<ApplicationRecord[]>('/applications').then((r) => r.data)

export const addApplication = (data: Partial<ApplicationRecord>) =>
  api.post<ApplicationRecord>('/applications', data).then((r) => r.data)

export const updateApplication = (id: string, data: Partial<ApplicationRecord>) =>
  api.put<ApplicationRecord>(`/applications/${id}`, data).then((r) => r.data)

export const deleteApplication = (id: string) =>
  api.delete(`/applications/${id}`)
