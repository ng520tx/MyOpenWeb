import type { Conversation } from '@/types';

/**
 * 本地缓存与后端会话的双向合并：updatedAt 新者胜；
 * 本地较新（或后端没有）的会话进入 uploads 等待回传。
 */
export function mergeConversations(
  localConversations: Conversation[],
  remoteConversations: Conversation[]
): { merged: Conversation[]; uploads: Conversation[] } {
  const remoteById = new Map(remoteConversations.map((conversation) => [conversation.id, conversation]));
  const merged: Conversation[] = [];
  const uploads: Conversation[] = [];

  for (const localConversation of localConversations) {
    const remoteConversation = remoteById.get(localConversation.id);
    if (!remoteConversation || localConversation.updatedAt >= remoteConversation.updatedAt) {
      merged.push(localConversation);
      uploads.push(localConversation);
    } else {
      merged.push(remoteConversation);
    }
    remoteById.delete(localConversation.id);
  }

  merged.push(...remoteById.values());
  merged.sort((a, b) => b.updatedAt - a.updatedAt);
  return { merged, uploads };
}
