import { EventSourceParserStream } from 'eventsource-parser/stream';
import type { ParsedEvent } from 'eventsource-parser';
import type { AgentStepEvent, AgentSummary, ResponseUsage, RetrievalSource, TextStreamUpdate } from '@/types';

export async function createOpenAITextStream(
  responseBody: ReadableStream<Uint8Array>,
  splitLargeDeltas = false
): Promise<AsyncGenerator<TextStreamUpdate>> {
  const eventStream = responseBody
    .pipeThrough(new TextDecoderStream() as unknown as TransformStream<Uint8Array, string>)
    .pipeThrough(new EventSourceParserStream())
    .getReader();

  let iterator = openAIStreamToIterator(eventStream);
  if (splitLargeDeltas) {
    iterator = streamLargeDeltasAsRandomChunks(iterator);
  }
  return iterator;
}

/**
 * Ollama /api/chat 返回 NDJSON 格式（每行一个 JSON），不是 SSE
 */
export async function createOllamaTextStream(
  responseBody: ReadableStream<Uint8Array>
): Promise<AsyncGenerator<TextStreamUpdate>> {
  const reader = responseBody
    .pipeThrough(new TextDecoderStream() as unknown as TransformStream<Uint8Array, string>)
    .getReader();

  return ollamaStreamToIterator(reader);
}

async function* ollamaStreamToIterator(
  reader: ReadableStreamDefaultReader<string>
): AsyncGenerator<TextStreamUpdate> {
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      if (buffer.trim()) {
        const update = parseOllamaLine(buffer.trim());
        if (update) yield update;
      }
      yield { done: true, value: '' };
      break;
    }

    buffer += value;
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const update = parseOllamaLine(trimmed);
      if (update) {
        yield update;
        if (update.done) return;
      }
    }
  }
}

function parseOllamaLine(line: string): TextStreamUpdate | null {
  try {
    const parsed = JSON.parse(line);

    if (parsed.error) {
      return { done: true, value: '', error: parsed.error };
    }

    const content = parsed.message?.content ?? '';
    const isDone = parsed.done === true;

    if (isDone) {
      return { done: true, value: content, usage: ollamaUsage(parsed) };
    }

    return { done: false, value: content };
  } catch {
    return null;
  }
}

/** Ollama done 帧的 eval 计数换算为 OpenAI usage 结构 */
function ollamaUsage(parsed: Record<string, unknown>): ResponseUsage | undefined {
  const promptTokens = Number(parsed.prompt_eval_count ?? 0);
  const completionTokens = Number(parsed.eval_count ?? 0);
  if (!promptTokens && !completionTokens) return undefined;
  return {
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    total_tokens: promptTokens + completionTokens,
  };
}

async function* openAIStreamToIterator(
  reader: ReadableStreamDefaultReader<ParsedEvent>
): AsyncGenerator<TextStreamUpdate> {
  // OpenAI 带 stream_options 时 usage 帧在 finish_reason=stop 之后才到，
  // 因此 stop 帧先挂起，读到 [DONE]/EOF 再补齐 usage 一起吐出。
  let pendingDone: TextStreamUpdate | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      yield pendingDone ?? { done: true, value: '' };
      break;
    }
    if (!value) continue;

    const data = value.data;
    if (data.startsWith('[DONE]')) {
      yield pendingDone ?? { done: true, value: '' };
      break;
    }

    try {
      const parsed = JSON.parse(data);

      if (parsed.error) {
        yield { done: true, value: '', error: parsed.error?.message ?? String(parsed.error) };
        break;
      }

      const delta = parsed.choices?.[0]?.delta?.content ?? '';
      const finishReason = parsed.choices?.[0]?.finish_reason;
      const agent = isAgentSummary(parsed.agent) ? parsed.agent : undefined;
      const sources = Array.isArray(parsed.sources) ? (parsed.sources as RetrievalSource[]) : undefined;
      const agentEvent = isAgentStepEvent(parsed.agent_event) ? parsed.agent_event : undefined;
      const usage = isResponseUsage(parsed.usage) ? parsed.usage : undefined;

      if (pendingDone) {
        if (usage) pendingDone.usage = usage;
        if (agent) pendingDone.agent = agent;
        if (sources) pendingDone.sources = sources;
        continue;
      }

      if (finishReason === 'stop') {
        pendingDone = { done: true, value: delta, agent, sources, agentEvent, usage };
        continue;
      }

      yield { done: false, value: delta, agent, sources, agentEvent, usage };
    } catch {
      continue;
    }
  }
}

function isAgentSummary(value: unknown): value is AgentSummary {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<AgentSummary>;
  return typeof candidate.runId === 'string' && Array.isArray(candidate.toolCalls);
}

function isResponseUsage(value: unknown): value is ResponseUsage {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<ResponseUsage>;
  return typeof candidate.total_tokens === 'number';
}

function isAgentStepEvent(value: unknown): value is AgentStepEvent {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<AgentStepEvent>;
  return candidate.type === 'thinking' || candidate.type === 'tool_call' || candidate.type === 'tool_result';
}

async function* streamLargeDeltasAsRandomChunks(
  iterator: AsyncGenerator<TextStreamUpdate>
): AsyncGenerator<TextStreamUpdate> {
  for await (const update of iterator) {
    if (update.done || update.value.length < 20) {
      yield update;
      continue;
    }
    let content = update.value;
    while (content.length > 0) {
      const chunkSize = Math.min(
        content.length,
        Math.floor(Math.random() * 12) + 3
      );
      yield { done: false, value: content.slice(0, chunkSize) };
      content = content.slice(chunkSize);
      await new Promise((r) => setTimeout(r, 5));
    }
  }
}
