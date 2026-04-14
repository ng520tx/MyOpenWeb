export const APP_NAME = 'MyOpenWeb';

export const DEFAULT_API_BASE_URL = 'http://localhost:11434/v1';
export const DEFAULT_MODEL = 'qwen2.5:7b';
export const DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.';

export const DEFAULT_SETTINGS = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  model: DEFAULT_MODEL,
  systemPrompt: DEFAULT_SYSTEM_PROMPT,
  temperature: 0.7,
  maxTokens: 4096,
  streamOutput: true,
};
