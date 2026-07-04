import type { IndexResult, KnowledgeBase, KnowledgeDetail, RetrievalSource } from '@/types';

export async function fetchKnowledgeList(): Promise<KnowledgeBase[]> {
  const res = await fetch('/api/knowledge');
  if (!res.ok) {
    throw new Error(`Knowledge request failed: HTTP ${res.status}`);
  }
  const data = (await res.json()) as { knowledge: KnowledgeBase[] };
  return data.knowledge;
}

export async function createKnowledge(name: string, description = ''): Promise<KnowledgeBase> {
  const res = await fetch('/api/knowledge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    throw new Error(`Create knowledge failed: HTTP ${res.status}`);
  }
  return (await res.json()) as KnowledgeBase;
}

export async function fetchKnowledgeDetail(id: string): Promise<KnowledgeDetail> {
  const res = await fetch(`/api/knowledge/${encodeURIComponent(id)}`);
  if (!res.ok) {
    throw new Error(`Knowledge detail failed: HTTP ${res.status}`);
  }
  return (await res.json()) as KnowledgeDetail;
}

export async function updateKnowledge(
  id: string,
  payload: { name?: string; description?: string }
): Promise<KnowledgeBase> {
  const res = await fetch(`/api/knowledge/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Update knowledge failed: HTTP ${res.status}`);
  }
  return (await res.json()) as KnowledgeBase;
}

export async function deleteKnowledge(id: string): Promise<void> {
  const res = await fetch(`/api/knowledge/${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!res.ok) {
    throw new Error(`Delete knowledge failed: HTTP ${res.status}`);
  }
}

export async function bindKnowledgeFile(knowledgeId: string, fileId: string): Promise<KnowledgeDetail> {
  const res = await fetch(`/api/knowledge/${encodeURIComponent(knowledgeId)}/files`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_id: fileId }),
  });
  if (!res.ok) {
    throw new Error(`Bind file failed: HTTP ${res.status}`);
  }
  return (await res.json()) as KnowledgeDetail;
}

export async function unbindKnowledgeFile(knowledgeId: string, fileId: string): Promise<KnowledgeDetail> {
  const res = await fetch(
    `/api/knowledge/${encodeURIComponent(knowledgeId)}/files/${encodeURIComponent(fileId)}`,
    { method: 'DELETE' }
  );
  if (!res.ok) {
    throw new Error(`Unbind file failed: HTTP ${res.status}`);
  }
  return (await res.json()) as KnowledgeDetail;
}

export async function indexKnowledge(id: string): Promise<IndexResult> {
  const res = await fetch(`/api/knowledge/${encodeURIComponent(id)}/index`, { method: 'POST' });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(`建立索引失败：${detail}`);
  }
  return (await res.json()) as IndexResult;
}

export async function queryKnowledge(
  id: string,
  query: string,
  topK = 4
): Promise<RetrievalSource[]> {
  const res = await fetch(`/api/knowledge/${encodeURIComponent(id)}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) {
    throw new Error(`Query knowledge failed: HTTP ${res.status}`);
  }
  const data = (await res.json()) as { chunks: Array<Record<string, unknown>> };
  return (data.chunks ?? []).map((chunk, idx) => ({
    index: idx + 1,
    file_id: String(chunk.file_id ?? ''),
    filename: String(chunk.filename ?? ''),
    chunk_index: Number(chunk.chunk_index ?? 0),
    score: Number(chunk.score ?? 0),
    preview: String(chunk.content ?? ''),
  }));
}
