const BASE = 'http://localhost:8000/api';

function triggerDownload(href: string, filename: string): void {
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export function downloadCleanedDataset(sessionId: string): void {
  triggerDownload(`${BASE}/export/${sessionId}/cleaned-dataset.csv`, 'cleaned_dataset.csv');
}

export function downloadPreprocessingReport(sessionId: string): void {
  triggerDownload(`${BASE}/export/${sessionId}/preprocessing.txt`, 'preprocessing_report.txt');
}
