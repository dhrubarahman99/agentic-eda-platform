import api from './client';
import type { LLMStatusResponse, EnhancedAnalysisResponse } from './types';

export async function getLLMStatus(): Promise<LLMStatusResponse> {
  const { data } = await api.get<LLMStatusResponse>('/llm/status');
  return data;
}

export async function enhanceAnalysis(sessionId: string): Promise<EnhancedAnalysisResponse> {
  const { data } = await api.post<EnhancedAnalysisResponse>(
    `/llm/enhance/analysis/${sessionId}`,
  );
  return data;
}
