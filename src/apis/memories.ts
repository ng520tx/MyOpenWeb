import type { MemoryCategory, MemoryItem } from '@/types';

export async function fetchMemories(): Promise<MemoryItem[]> {
  const res = await fetch('/api/memories');
  if (!res.ok) {
    throw new Error(`Memories request failed: HTTP ${res.status}`);
  }
  const data = (await res.json()) as { memories: MemoryItem[] };
  return data.memories;
}

export async function createMemory(payload: {
  content: string;
  category: MemoryCategory;
  enabled?: boolean;
}): Promise<MemoryItem> {
  const res = await fetch('/api/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: payload.content,
      category: payload.category,
      enabled: payload.enabled ?? true,
    }),
  });
  if (!res.ok) {
    throw new Error(`Create memory failed: HTTP ${res.status}`);
  }
  return (await res.json()) as MemoryItem;
}

export async function updateMemory(
  id: string,
  payload: Partial<Pick<MemoryItem, 'content' | 'category' | 'enabled'>>
): Promise<MemoryItem> {
  const res = await fetch(`/api/memories/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Update memory failed: HTTP ${res.status}`);
  }
  return (await res.json()) as MemoryItem;
}

export async function deleteMemory(id: string): Promise<void> {
  const res = await fetch(`/api/memories/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Delete memory failed: HTTP ${res.status}`);
  }
}
