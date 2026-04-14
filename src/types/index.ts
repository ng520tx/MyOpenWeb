export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  done: boolean;
  error?: string;
  model?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  model: string;
  createdAt: number;
  updatedAt: number;
}

export interface ModelConfig {
  id: string;
  name: string;
  provider: 'ollama' | 'openai';
  baseUrl: string;
  apiKey?: string;
}

export interface AppSettings {
  apiBaseUrl: string;
  model: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  streamOutput: boolean;
}

export type TextStreamUpdate = {
  done: boolean;
  value: string;
  error?: string;
  usage?: ResponseUsage;
};

export type ResponseUsage = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};
