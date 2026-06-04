import client from './client'
import { getStoredToken } from './auth'
import type { AdminStats, AdminUser, AdminSession, AdminFeedbackGroup } from './types'

function authHeaders() {
  const token = getStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const { data } = await client.get<AdminStats>('/admin/stats', { headers: authHeaders() })
  return data
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const { data } = await client.get<AdminUser[]>('/admin/users', { headers: authHeaders() })
  return data
}

export async function deleteAdminUser(userId: number): Promise<void> {
  await client.delete(`/admin/users/${userId}`, { headers: authHeaders() })
}

export async function fetchAdminSessions(): Promise<AdminSession[]> {
  const { data } = await client.get<AdminSession[]>('/admin/sessions', { headers: authHeaders() })
  return data
}

export async function deleteAdminSession(sessionId: string): Promise<void> {
  await client.delete(`/admin/sessions/${sessionId}`, { headers: authHeaders() })
}

export async function fetchAdminFeedback(): Promise<AdminFeedbackGroup[]> {
  const { data } = await client.get<AdminFeedbackGroup[]>('/admin/feedback', { headers: authHeaders() })
  return data
}

export async function clearUserFeedback(userId: number): Promise<{ message: string; deleted_count: number }> {
  const { data } = await client.delete<{ message: string; deleted_count: number }>(
    `/admin/feedback/user/${userId}`,
    { headers: authHeaders() },
  )
  return data
}
