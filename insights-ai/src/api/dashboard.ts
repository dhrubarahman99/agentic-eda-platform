import api from './client';
import type { DashboardResponse, DataPreviewResponse, ColumnDetailResponse } from './types';

export async function getDashboard(sessionId: string): Promise<DashboardResponse> {
  const { data } = await api.get<DashboardResponse>(`/dashboard/${sessionId}`);
  return data;
}

export async function getPreview(
  sessionId: string,
  rows = 100,
  offset = 0,
): Promise<DataPreviewResponse> {
  const { data } = await api.get<DataPreviewResponse>(`/dashboard/${sessionId}/preview`, {
    params: { rows, offset },
  })
  return data
}

export async function getColumnDetail(
  sessionId: string,
  colName: string,
  useClean = false,
): Promise<ColumnDetailResponse> {
  const { data } = await api.get<ColumnDetailResponse>(
    `/dashboard/${sessionId}/column/${colName}`,
    useClean ? { params: { use_clean: true } } : undefined,
  );
  return data;
}
