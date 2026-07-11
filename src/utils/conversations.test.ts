import { describe, expect, it } from 'vitest';
import { mergeConversations } from './conversations';
import type { Conversation } from '@/types';

function conv(id: string, updatedAt: number, title = id): Conversation {
  return { id, title, messages: [], createdAt: 0, updatedAt };
}

describe('mergeConversations', () => {
  it('keeps the local copy and schedules an upload when local is newer', () => {
    const local = [conv('a', 200, 'local-a')];
    const remote = [conv('a', 100, 'remote-a')];

    const { merged, uploads } = mergeConversations(local, remote);

    expect(merged).toHaveLength(1);
    expect(merged[0].title).toBe('local-a');
    expect(uploads.map((c) => c.id)).toEqual(['a']);
  });

  it('prefers the remote copy when it is newer and does not upload it', () => {
    const local = [conv('a', 100, 'local-a')];
    const remote = [conv('a', 200, 'remote-a')];

    const { merged, uploads } = mergeConversations(local, remote);

    expect(merged[0].title).toBe('remote-a');
    expect(uploads).toHaveLength(0);
  });

  it('appends remote-only conversations and uploads local-only ones', () => {
    const local = [conv('local-only', 50)];
    const remote = [conv('remote-only', 80)];

    const { merged, uploads } = mergeConversations(local, remote);

    expect(merged.map((c) => c.id)).toEqual(['remote-only', 'local-only']);
    expect(uploads.map((c) => c.id)).toEqual(['local-only']);
  });

  it('sorts the merged list by updatedAt descending', () => {
    const local = [conv('a', 10), conv('b', 300)];
    const remote = [conv('c', 200)];

    const { merged } = mergeConversations(local, remote);

    expect(merged.map((c) => c.id)).toEqual(['b', 'c', 'a']);
  });

  it('treats equal timestamps as local-wins (offline edits survive)', () => {
    const local = [conv('a', 100, 'local-a')];
    const remote = [conv('a', 100, 'remote-a')];

    const { merged, uploads } = mergeConversations(local, remote);

    expect(merged[0].title).toBe('local-a');
    expect(uploads.map((c) => c.id)).toEqual(['a']);
  });
});
