import type { Conversation } from '@/types';

interface ChatsResponse {
  conversations: Conversation[];
}

export async function fetchChats(): Promise<Conversation[]> {
  try {
    const res = await fetch('/api/chats');
    if (!res.ok) return [];
    const data = (await res.json()) as ChatsResponse;
    return data.conversations ?? [];
  } catch {
    return [];
  }
}

export async function saveChat(conversation: Conversation): Promise<void> {
  const res = await fetch(`/api/chats/${conversation.id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(conversation),
  });

  if (!res.ok) {
    throw new Error(`Chat sync failed: HTTP ${res.status}`);
  }
}

export async function removeChat(chatId: string): Promise<void> {
  const res = await fetch(`/api/chats/${chatId}`, {
    method: 'DELETE',
  });

  if (!res.ok) {
    throw new Error(`Chat delete failed: HTTP ${res.status}`);
  }
}
