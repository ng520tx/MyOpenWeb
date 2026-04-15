import type { ChatMessage, FileAttachment } from '@/types';

interface ChatCompletionOptions {
  baseUrl: string;
  apiKey?: string;
  model: string;
  messages: ChatMessage[];
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  stream?: boolean;
  signal?: AbortSignal;
  files?: FileAttachment[];
}

export async function chatCompletion(
  opts: ChatCompletionOptions
): Promise<[Response, AbortController]> {
  const controller = new AbortController();
  const mergedSignal = opts.signal
    ? anySignal([opts.signal, controller.signal])
    : controller.signal;

  const apiMessages: { role: string; content: string }[] = [];

  if (opts.systemPrompt) {
    apiMessages.push({ role: 'system', content: opts.systemPrompt });
  }

  for (const msg of opts.messages) {
    if (msg.role === 'system') continue;

    let content = msg.content;
    const files = msg.files ?? (msg === opts.messages[opts.messages.length - 1] ? opts.files : undefined);
    if (files?.length) {
      const fileContext = files
        .map((f) => `--- File: ${f.name} ---\n${f.content}\n--- End ---`)
        .join('\n\n');
      content = `${fileContext}\n\n${content}`;
    }

    apiMessages.push({ role: msg.role, content });
  }

  const body = {
    model: opts.model,
    messages: apiMessages,
    stream: opts.stream ?? true,
    temperature: opts.temperature ?? 0.7,
    max_tokens: opts.maxTokens ?? 4096,
  };

  const url = `${opts.baseUrl.replace(/\/+$/, '')}/chat/completions`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (opts.apiKey) {
    headers['Authorization'] = `Bearer ${opts.apiKey}`;
  }

  const res = await fetch(url, {
    method: 'POST',
    headers,
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
