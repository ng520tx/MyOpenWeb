import type { AppSettings } from '@/types';

export const APP_NAME = 'MyOpenWeb';

function detectApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:11434/v1`;
    }
  }
  return 'http://localhost:11434/v1';
}

export const DEFAULT_API_BASE_URL = detectApiBaseUrl();
export const DEFAULT_PROVIDER_TYPE = 'ollama';
export const DEFAULT_MODEL = 'qwen3.5:4b';
export const DEFAULT_EMBEDDING_MODEL = 'bge-m3';
export const DEFAULT_OCR_BASE_URL = 'http://localhost:8118';
export const DEFAULT_RERANK_MODEL = 'BAAI/bge-reranker-base';
export const DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.';

export const DEFAULT_SETTINGS: AppSettings = {
  providerType: DEFAULT_PROVIDER_TYPE,
  apiBaseUrl: DEFAULT_API_BASE_URL,
  apiKey: '',
  embeddingModel: DEFAULT_EMBEDDING_MODEL,
  ocrEnabled: false,
  ocrBaseUrl: DEFAULT_OCR_BASE_URL,
  ocrMode: 'auto',
  retrievalMode: 'hybrid',
  rerankEnabled: false,
  rerankModel: DEFAULT_RERANK_MODEL,
  queryRewriteEnabled: true,
  agenticRetrievalEnabled: false,
  agentEnabled: false,
  agentToolProtocol: 'prompt',
  model: DEFAULT_MODEL,
  systemPrompt: DEFAULT_SYSTEM_PROMPT,
  temperature: 0.7,
  maxTokens: 4096,
  streamOutput: true,
  ttsEnabled: false,
  ttsLang: 'zh-CN',
  ttsRate: 1.0,
};

export const STORAGE_KEYS = {
  SETTINGS: 'mow-settings',
  CONVERSATIONS: 'mow-conversations',
  ACTIVE_CONVERSATION_ID: 'mow-active-id',
  ACTIVE_KNOWLEDGE_ID: 'mow-active-knowledge-id',
} as const;

export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
export const ACCEPTED_TEXT_TYPES = '.txt,.md,.json,.csv,.xml,.html,.css,.js,.ts,.jsx,.tsx,.py,.java,.c,.cpp,.go,.rs,.sql,.yaml,.yml,.log,.ini,.conf,.toml,.sh,.bat';
export const ACCEPTED_IMAGE_TYPES = '.jpg,.jpeg,.png,.gif,.webp';
export const ACCEPTED_FILE_TYPES = `${ACCEPTED_TEXT_TYPES},${ACCEPTED_IMAGE_TYPES}`;
export const IMAGE_MIME_PREFIXES = ['image/'];
