import type { AppSettings } from '@/types';

export const APP_NAME = 'MyOpenWeb';

export const DEFAULT_API_BASE_URL = 'http://localhost:11434/v1';
export const DEFAULT_MODEL = 'qwen2.5:3b';
export const DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.';

export const DEFAULT_SETTINGS: AppSettings = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  apiKey: '',
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
} as const;

export const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
export const ACCEPTED_FILE_TYPES = '.txt,.md,.json,.csv,.xml,.html,.css,.js,.ts,.jsx,.tsx,.py,.java,.c,.cpp,.go,.rs,.sql,.yaml,.yml,.log,.ini,.conf,.toml,.sh,.bat';
