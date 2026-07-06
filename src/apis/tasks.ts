import type { ChatMessage } from '@/types';

/** LLM 对话标题生成。失败返回 null，调用方保持原标题。 */
export async function generateTitle(
  model: string,
  userText: string,
  assistantText?: string
): Promise<string | null> {
  try {
    const res = await fetch('/api/tasks/title', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        user_text: userText,
        assistant_text: assistantText ?? '',
      }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { title?: string | null };
    return data.title?.trim() || null;
  } catch {
    return null;
  }
}

/** 追问建议生成。失败返回空数组，前端不渲染 chip。 */
export async function generateFollowUps(
  model: string,
  messages: ChatMessage[]
): Promise<string[]> {
  try {
    const res = await fetch('/api/tasks/follow_ups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        messages: messages.map((m) => ({ role: m.role, content: m.content })),
      }),
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { follow_ups?: string[] };
    return Array.isArray(data.follow_ups) ? data.follow_ups : [];
  } catch {
    return [];
  }
}
