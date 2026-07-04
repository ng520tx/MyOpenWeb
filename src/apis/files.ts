import type { FileDetail, FileRecord } from '@/types';

export async function fetchFiles(): Promise<FileRecord[]> {
  const res = await fetch('/api/files');
  if (!res.ok) {
    throw new Error(`Files request failed: HTTP ${res.status}`);
  }
  const data = (await res.json()) as { files: FileRecord[] };
  return data.files;
}

export async function uploadFile(file: File): Promise<FileRecord> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/files', {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(`上传失败：${detail}`);
  }
  return (await res.json()) as FileRecord;
}

export async function fetchFileDetail(id: string): Promise<FileDetail> {
  const res = await fetch(`/api/files/${encodeURIComponent(id)}`);
  if (!res.ok) {
    throw new Error(`File detail request failed: HTTP ${res.status}`);
  }
  return (await res.json()) as FileDetail;
}

export async function deleteFile(id: string): Promise<void> {
  const res = await fetch(`/api/files/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Delete file failed: HTTP ${res.status}`);
  }
}

export async function reextractFile(id: string): Promise<FileRecord> {
  const res = await fetch(`/api/files/${encodeURIComponent(id)}/reextract`, {
    method: 'POST',
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(`重新抽取失败：${detail}`);
  }
  return (await res.json()) as FileRecord;
}
