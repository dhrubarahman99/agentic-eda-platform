import api from './client';
import type { SessionListItem } from './types';

export async function listSessions(): Promise<SessionListItem[]> {
  const { data } = await api.get<SessionListItem[]>('/sessions');
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/sessions/${sessionId}`);
}
