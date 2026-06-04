import api from './client';

export interface FeedbackRequest {
  query_id: string;
  session_id: string;
  question: string;
  intent: string;
  columns_used: string[];
  plain_summary: string;
  feedback: 'positive' | 'negative';
}

export interface FeedbackResponse {
  record_id: string;
  message: string;
}

export async function submitFeedback(payload: FeedbackRequest): Promise<FeedbackResponse> {
  const { data } = await api.post<FeedbackResponse>('/feedback', payload);
  return data;
}
