import type { AppSettings, ProviderConfig } from '@/types';
import { resolveApiUrl } from '@/utils/url';

interface ProviderConfigPayload {
  provider_type: ProviderConfig['providerType'];
  provider_base_url: string;
  provider_api_key: string;
  embedding_model: string;
  ocr_enabled: boolean;
  ocr_base_url: string;
  ocr_mode: ProviderConfig['ocrMode'];
  retrieval_mode: ProviderConfig['retrievalMode'];
  rerank_enabled: boolean;
  rerank_model: string;
  query_rewrite_enabled: boolean;
  agentic_retrieval_enabled: boolean;
  agent_tool_protocol: ProviderConfig['agentToolProtocol'];
}

type ProviderSettings = Pick<
  AppSettings,
  | 'providerType'
  | 'apiBaseUrl'
  | 'apiKey'
  | 'embeddingModel'
  | 'ocrEnabled'
  | 'ocrBaseUrl'
  | 'ocrMode'
  | 'retrievalMode'
  | 'rerankEnabled'
  | 'rerankModel'
  | 'queryRewriteEnabled'
  | 'agenticRetrievalEnabled'
  | 'agentToolProtocol'
>;

export interface ProviderVerifyResult {
  ok: boolean;
  provider_type: ProviderConfig['providerType'];
  configured_base_url: string;
  resolved_base_url?: string | null;
  endpoint_url?: string | null;
  models_count: number;
  models: Array<{
    id: string;
    name: string;
    size?: number;
    modified_at?: string;
  }>;
  error?: string | null;
}

function toProviderPayload(settings: ProviderSettings): ProviderConfigPayload {
  return {
    provider_type: settings.providerType,
    provider_base_url: resolveApiUrl(settings.apiBaseUrl.trim()),
    provider_api_key: settings.apiKey.trim(),
    embedding_model: (settings.embeddingModel || 'bge-m3').trim(),
    ocr_enabled: settings.ocrEnabled,
    ocr_base_url: (settings.ocrBaseUrl || 'http://localhost:8118').trim(),
    ocr_mode: settings.ocrMode,
    retrieval_mode: settings.retrievalMode,
    rerank_enabled: settings.rerankEnabled,
    rerank_model: (settings.rerankModel || 'BAAI/bge-reranker-base').trim(),
    query_rewrite_enabled: settings.queryRewriteEnabled,
    agentic_retrieval_enabled: settings.agenticRetrievalEnabled,
    agent_tool_protocol: settings.agentToolProtocol,
  };
}

function fromProviderPayload(payload: ProviderConfigPayload): ProviderConfig {
  return {
    providerType: payload.provider_type,
    apiBaseUrl: payload.provider_base_url,
    apiKey: payload.provider_api_key,
    embeddingModel: payload.embedding_model || 'bge-m3',
    ocrEnabled: Boolean(payload.ocr_enabled),
    ocrBaseUrl: payload.ocr_base_url || 'http://localhost:8118',
    ocrMode: payload.ocr_mode === 'always' ? 'always' : 'auto',
    retrievalMode: payload.retrieval_mode === 'vector' ? 'vector' : 'hybrid',
    rerankEnabled: Boolean(payload.rerank_enabled),
    rerankModel: payload.rerank_model || 'BAAI/bge-reranker-base',
    queryRewriteEnabled: payload.query_rewrite_enabled !== false,
    agenticRetrievalEnabled: Boolean(payload.agentic_retrieval_enabled),
    agentToolProtocol: payload.agent_tool_protocol === 'native' ? 'native' : 'prompt',
  };
}

export async function fetchProviderConfig(): Promise<ProviderConfig | null> {
  try {
    const res = await fetch('/api/config/provider');
    if (!res.ok) return null;
    const data = (await res.json()) as ProviderConfigPayload;
    return fromProviderPayload(data);
  } catch {
    return null;
  }
}

export async function syncProviderConfig(
  settings: ProviderSettings
): Promise<ProviderConfig> {
  const payload = toProviderPayload(settings);
  const res = await fetch('/api/config/provider', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Provider config sync failed: HTTP ${res.status}`);
  }

  return fromProviderPayload((await res.json()) as ProviderConfigPayload);
}

export async function verifyProviderConfig(
  settings: ProviderSettings
): Promise<ProviderVerifyResult> {
  const payload = toProviderPayload(settings);
  const res = await fetch('/api/config/provider/verify', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Provider config verify failed: HTTP ${res.status}`);
  }

  return (await res.json()) as ProviderVerifyResult;
}
