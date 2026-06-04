import api from './client';
import type { QueryResult } from './types';

export async function askQuestion(sessionId: string, question: string): Promise<QueryResult> {
  const { data } = await api.post<QueryResult>(`/query/${sessionId}`, { question });
  return data;
}
