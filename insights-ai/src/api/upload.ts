import api from './client';
import type { UploadResponse, AnalysisResponse } from './types';

export async function uploadCSV(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<UploadResponse>('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function runAnalysis(
  sessionId: string,
  targetColumn?: string | null,
): Promise<AnalysisResponse> {
  const params = targetColumn ? { target_column: targetColumn } : {}
  const { data } = await api.post<AnalysisResponse>(`/analyse/${sessionId}`, null, { params })
  return data
}
