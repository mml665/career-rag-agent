import api from './index'
import type { CandidateProfile } from './types'

export const getProfile = () =>
  api.get<CandidateProfile>('/profile').then((r) => r.data)

export const saveProfile = (data: Partial<CandidateProfile>) =>
  api.post<CandidateProfile>('/profile', data).then((r) => r.data)
