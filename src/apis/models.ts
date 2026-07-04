export interface ModelInfo {
  id: string;
  name: string;
  size?: number;
  modified_at?: string;
}

export async function fetchModels(): Promise<ModelInfo[]> {
  try {
    const res = await fetch('/api/models', { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return [];
    const data = await res.json();
    const list = data.data ?? data.models ?? [];
    return list.map((m: Record<string, unknown>) => ({
      id: (m.id ?? m.name ?? '') as string,
      name: (m.id ?? m.name ?? '') as string,
      size: m.size as number | undefined,
      modified_at: m.modified_at as string | undefined,
    }));
  } catch {
    return [];
  }
}
