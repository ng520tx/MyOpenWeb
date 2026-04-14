import { EventSourceParserStream } from 'eventsource-parser/stream';
import type { ParsedEvent } from 'eventsource-parser';
import type { TextStreamUpdate } from '@/types';

/**
 * 将 OpenAI 兼容的 SSE 响应流转换为 async generator
 * 参考自 Open WebUI: src/lib/apis/streaming/index.ts
 */
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

      if (finishReason === 'stop') {
        yield { done: true, value: delta };
        break;
      }

      yield { done: false, value: delta };
    } catch {
      continue;
    }
  }
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
