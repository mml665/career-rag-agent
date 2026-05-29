import api from './index'
import type { ProfileEvidence } from './types'

export const listEvidence = () =>
  api.get<ProfileEvidence[]>('/evidence').then((r) => r.data)

export const addEvidence = (data: Partial<ProfileEvidence>) =>
  api.post<ProfileEvidence>('/evidence', data).then((r) => r.data)

export const updateEvidence = (id: string, data: Partial<ProfileEvidence>) =>
  api.put<ProfileEvidence>(`/evidence/${id}`, data).then((r) => r.data)

export const deleteEvidence = (id: string) =>
  api.delete(`/evidence/${id}`)

export const saveSections = (data: { sections: Record<string, string>; source_file?: string; verified?: boolean }) =>
  api.post<ProfileEvidence[]>('/evidence/sections', data).then((r) => r.data)

export const deleteSection = (category: string) =>
  api.delete(`/evidence/section/${category}`)
