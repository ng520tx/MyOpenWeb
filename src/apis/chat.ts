import type { ChatMessage } from '@/types';

interface ChatCompletionOptions {
  baseUrl: string;
  model: string;
  messages: ChatMessage[];
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  stream?: boolean;
  signal?: AbortSignal;
}

/**
 * 发送聊天补全请求，返回 [Response, AbortController]
 * 兼容 Ollama / OpenAI / 任何 OpenAI 格式的 API
 */
export async function chatCompletion(
  opts: ChatCompletionOptions
): Promise<[Response, AbortController]> {
  const controller = new AbortController();
  const mergedSignal = opts.signal
    ? anySignal([opts.signal, controller.signal])
    : controller.signal;

  const apiMessages = [];

  if (opts.systemPrompt) {
    apiMessages.push({ role: 'system', content: opts.systemPrompt });
  }

  for (const msg of opts.messages) {
    if (msg.role === 'system') continue;
    apiMessages.push({ role: msg.role, content: msg.content });
  }

  const body = {
    model: opts.model,
    messages: apiMessages,
    stream: opts.stream ?? true,
    temperature: opts.temperature ?? 0.7,
    max_tokens: opts.maxTokens ?? 4096,
  };

  const url = `${opts.baseUrl.replace(/\/+$/, '')}/chat/completions`;

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal: mergedSignal,
  });

  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      errMsg = errBody.error?.message ?? errBody.detail ?? errMsg;
    } catch { /* ignore */ }
    throw new Error(errMsg);
  }

  return [res, controller];
}

function anySignal(signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();
  for (const s of signals) {
    if (s.aborted) {
      controller.abort(s.reason);
      return controller.signal;
    }
    s.addEventListener('abort', () => controller.abort(s.reason), { once: true });
  }
  return controller.signal;
}
