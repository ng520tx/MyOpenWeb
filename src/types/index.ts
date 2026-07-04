export type ProviderType = 'ollama' | 'openai';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  done: boolean;
  error?: string;
  model?: string;
  files?: FileAttachment[];
  agent?: AgentSummary;
  sources?: RetrievalSource[];
}

export interface AgentToolCallSummary {
  name: string;
  input?: Record<string, unknown>;
  output?: unknown;
  ok: boolean;
  error?: string | null;
}

export interface AgentSummary {
  runId: string;
  toolCalls: AgentToolCallSummary[];
}

export interface AgentRunStep {
  id: string;
  run_id: string;
  step_index: number;
  type: 'model_decision' | 'tool_call' | 'tool_result' | 'final' | string;
  name?: string | null;
  input?: unknown;
  output?: unknown;
  ok: boolean;
  error?: string | null;
  created_at: number;
}

export interface AgentRun {
  id: string;
  conversation_id?: string | null;
  message_id?: string | null;
  user_message_id?: string | null;
  model: string;
  user_input: string;
  final_answer?: string | null;
  created_at: number;
  updated_at: number;
  steps: AgentRunStep[];
}

export interface FileAttachment {
  name: string;
  size: number;
  type: string;
  content: string;
  isImage?: boolean;
  dataUrl?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
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

export type OcrMode = 'auto' | 'always';
export type RetrievalMode = 'vector' | 'hybrid';

export interface AppSettings {
  providerType: ProviderType;
  apiBaseUrl: string;
  apiKey: string;
  embeddingModel: string;
  ocrEnabled: boolean;
  ocrBaseUrl: string;
  ocrMode: OcrMode;
  retrievalMode: RetrievalMode;
  rerankEnabled: boolean;
  rerankModel: string;
  agentEnabled: boolean;
  model: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  streamOutput: boolean;
  ttsEnabled: boolean;
  ttsLang: string;
  ttsRate: number;
}

export interface ProviderConfig {
  providerType: ProviderType;
  apiBaseUrl: string;
  apiKey: string;
  embeddingModel: string;
  ocrEnabled: boolean;
  ocrBaseUrl: string;
  ocrMode: OcrMode;
  retrievalMode: RetrievalMode;
  rerankEnabled: boolean;
  rerankModel: string;
}

export interface FileRecord {
  id: string;
  filename: string;
  mime_type?: string | null;
  size: number;
  hash?: string | null;
  text_preview: string;
  text_length: number;
  meta: Record<string, unknown>;
  created_at: number;
  updated_at: number;
}

export interface FileDetail extends FileRecord {
  text_content: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  file_count: number;
  chunk_count: number;
  created_at: number;
  updated_at: number;
}

export interface KnowledgeDetail extends KnowledgeBase {
  files: FileRecord[];
}

export interface RetrievalSource {
  index: number;
  file_id: string;
  filename: string;
  chunk_index: number;
  score: number;
  preview: string;
}

export interface IndexResult {
  knowledge_id: string;
  files: number;
  chunks: number;
  embedding_model: string;
}

export type MemoryCategory = 'preference' | 'profile' | 'project' | 'fact';

export interface MemoryItem {
  id: string;
  content: string;
  category: MemoryCategory;
  enabled: boolean;
  created_at: number;
  updated_at: number;
}

export type TextStreamUpdate = {
  done: boolean;
  value: string;
  error?: string;
  usage?: ResponseUsage;
  agent?: AgentSummary;
  sources?: RetrievalSource[];
};

export type ResponseUsage = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};
