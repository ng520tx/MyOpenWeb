import type { ChatMessage, FileAttachment } from '@/types';

interface ChatCompletionOptions {
  model: string;
  messages: ChatMessage[];
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  stream?: boolean;
  signal?: AbortSignal;
  files?: FileAttachment[];
  agentEnabled?: boolean;
  knowledgeId?: string | null;
  metadata?: Record<string, unknown>;
}

type ContentPart =
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } };

function buildMessageContent(text: string, files?: FileAttachment[]): string | ContentPart[] {
  if (!files?.length) return text;

  const hasImages = files.some((file) => file.isImage && file.dataUrl);
  const textFiles = files.filter((file) => !file.isImage && file.content);

  let combinedText = text;
  if (textFiles.length > 0) {
    const fileContext = textFiles
      .map((file) => `--- File: ${file.name} ---\n${file.content}\n--- End ---`)
      .join('\n\n');
    combinedText = `${fileContext}\n\n${text}`;
  }

  if (!hasImages) return combinedText;

  const parts: ContentPart[] = [{ type: 'text', text: combinedText }];
  for (const file of files) {
    if (file.isImage && file.dataUrl) {
      parts.push({ type: 'image_url', image_url: { url: file.dataUrl } });
    }
  }
  return parts;
}

export async function chatCompletion(
  opts: ChatCompletionOptions
): Promise<[Response, AbortController]> {
  const controller = new AbortController();
  const mergedSignal = opts.signal
    ? anySignal([opts.signal, controller.signal])
    : controller.signal;

  const body: Record<string, unknown> = {
    model: opts.model,
    messages: opts.messages.map((msg) => {
      const files = msg === opts.messages[opts.messages.length - 1]
        ? (msg.files ?? opts.files)
        : msg.files;

      return {
        role: msg.role,
        content: buildMessageContent(msg.content, files),
      };
    }),
    stream: opts.stream ?? true,
    temperature: opts.temperature ?? 0.7,
    max_tokens: opts.maxTokens ?? 4096,
    system_prompt: opts.systemPrompt,
    metadata: opts.metadata ?? {},
  };

  if (opts.knowledgeId) {
    body.knowledge_id = opts.knowledgeId;
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const endpoint = opts.agentEnabled ? '/api/agent/completions' : '/api/chat/completions';
  const res = await fetch(endpoint, {
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
