import { describe, expect, it } from 'vitest';
import { createOllamaTextStream, createOpenAITextStream } from './streaming';
import type { TextStreamUpdate } from '@/types';

function bytesStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

function sse(payload: unknown): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

async function collect(iterator: AsyncGenerator<TextStreamUpdate>): Promise<TextStreamUpdate[]> {
  const updates: TextStreamUpdate[] = [];
  for await (const update of iterator) {
    updates.push(update);
    if (update.done) break;
  }
  return updates;
}

describe('createOpenAITextStream', () => {
  it('yields content deltas in order and terminates on [DONE]', async () => {
    const stream = bytesStream([
      sse({ choices: [{ delta: { content: '?' }, finish_reason: null }] }),
      sse({ choices: [{ delta: { content: '?' }, finish_reason: null }] }),
      'data: [DONE]\n\n',
    ]);

    const updates = await collect(await createOpenAITextStream(stream));

    expect(updates.map((u) => u.value)).toEqual(['?', '?', '']);
    expect(updates[updates.length - 1]?.done).toBe(true);
  });

  it('holds the stop frame until the late usage frame arrives (stream_options)', async () => {
    const stream = bytesStream([
      sse({ choices: [{ delta: { content: 'hi' }, finish_reason: null }] }),
      sse({ choices: [{ delta: {}, finish_reason: 'stop' }] }),
      sse({ choices: [], usage: { prompt_tokens: 3, completion_tokens: 5, total_tokens: 8 } }),
      'data: [DONE]\n\n',
    ]);

    const updates = await collect(await createOpenAITextStream(stream));
    const final = updates[updates.length - 1];

    expect(final?.done).toBe(true);
    expect(final?.usage).toEqual({ prompt_tokens: 3, completion_tokens: 5, total_tokens: 8 });
  });

  it('passes retrieval sources and agent events through', async () => {
    const sources = [
      { index: 1, file_id: 'f1', filename: 'doc.md', chunk_index: 0, score: 0.9, preview: 'p' },
    ];
    const stream = bytesStream([
      sse({ sources, choices: [{ delta: {}, finish_reason: null }] }),
      sse({ agent_event: { type: 'tool_call', name: 'calculator' }, choices: [{ delta: {}, finish_reason: null }] }),
      sse({ choices: [{ delta: { content: '42' }, finish_reason: null }] }),
      'data: [DONE]\n\n',
    ]);

    const updates = await collect(await createOpenAITextStream(stream));

    expect(updates[0].sources).toEqual(sources);
    expect(updates[1].agentEvent).toEqual({ type: 'tool_call', name: 'calculator' });
    expect(updates[2].value).toBe('42');
  });

  it('passes the retrieval degradation warning through', async () => {
    const stream = bytesStream([
      sse({ retrieval_warning: '??????????????????', choices: [{ delta: {}, finish_reason: null }] }),
      sse({ choices: [{ delta: { content: '????' }, finish_reason: null }] }),
      'data: [DONE]\n\n',
    ]);

    const updates = await collect(await createOpenAITextStream(stream));

    expect(updates[0].retrievalWarning).toContain('???????');
    expect(updates[1].value).toBe('????');
  });

  it('surfaces upstream error frames as a terminal error update', async () => {
    const stream = bytesStream([
      sse({ error: { message: 'model not found' } }),
    ]);

    const updates = await collect(await createOpenAITextStream(stream));

    expect(updates).toHaveLength(1);
    expect(updates[0].done).toBe(true);
    expect(updates[0].error).toBe('model not found');
  });
});

describe('createOllamaTextStream', () => {
  it('parses NDJSON lines split across network chunks', async () => {
    const lineA = JSON.stringify({ message: { content: '?' }, done: false });
    const lineB = JSON.stringify({
      message: { content: '' },
      done: true,
      prompt_eval_count: 7,
      eval_count: 2,
    });
    // Split mid-line to exercise the buffer stitching.
    const stream = bytesStream([lineA.slice(0, 5), lineA.slice(5) + '\n', lineB + '\n']);

    const updates = await collect(await createOllamaTextStream(stream));

    expect(updates[0]).toMatchObject({ done: false, value: '?' });
    expect(updates[updates.length - 1]).toMatchObject({
      done: true,
      usage: { prompt_tokens: 7, completion_tokens: 2, total_tokens: 9 },
    });
  });

  it('propagates Ollama error payloads', async () => {
    const stream = bytesStream([JSON.stringify({ error: 'out of memory' }) + '\n']);

    const updates = await collect(await createOllamaTextStream(stream));

    expect(updates[0].error).toBe('out of memory');
    expect(updates[0].done).toBe(true);
  });
});
