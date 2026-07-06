import { EventSourceParserStream } from 'eventsource-parser/stream';
import type { ParsedEvent } from 'eventsource-parser';
import type { AgentStepEvent, AgentSummary, RetrievalSource, TextStreamUpdate } from '@/types';

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
      return { done: true, value: content };
    }

    return { done: false, value: content };
  } catch {
    return null;
  }
}

async function* openAIStreamToIterator(
  reader: ReadableStreamDefaultReader<ParsedEvent>
): AsyncGenerator<TextStreamUpdate> {
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      yield { done: true, value: '' };
      break;
    }
    if (!value) continue;

    const data = value.data;
    if (data.startsWith('[DONE]')) {
      yield { done: true, value: '' };
      break;
    }

    try {
      const parsed = JSON.parse(data);

      if (parsed.error) {
        yield { done: true, value: '', error: parsed.error?.message ?? String(parsed.error) };
        break;
      }

      if (parsed.usage) {
        yield { done: false, value: '', usage: parsed.usage };
        continue;
      }

      const delta = parsed.choices?.[0]?.delta?.content ?? '';
      const finishReason = parsed.choices?.[0]?.finish_reason;
      const agent = isAgentSummary(parsed.agent) ? parsed.agent : undefined;
      const sources = Array.isArray(parsed.sources) ? (parsed.sources as RetrievalSource[]) : undefined;
      const agentEvent = isAgentStepEvent(parsed.agent_event) ? parsed.agent_event : undefined;

      if (finishReason === 'stop') {
        yield { done: true, value: delta, agent, sources, agentEvent };
        break;
      }

      yield { done: false, value: delta, agent, sources, agentEvent };
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
