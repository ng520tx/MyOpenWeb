import type { Conversation } from '@/types';

function formatTime(ts: number): string {
  return new Date(ts).toLocaleString('zh-CN');
}

export function exportAsMarkdown(conv: Conversation): string {
  const lines: string[] = [
    `# ${conv.title}`,
    '',
    `> 创建时间：${formatTime(conv.createdAt)}`,
    '',
    '---',
    '',
  ];

  for (const msg of conv.messages) {
    if (msg.role === 'user') {
      lines.push(`**用户** (${formatTime(msg.timestamp)})：`);
    } else if (msg.role === 'assistant') {
      lines.push(`**AI** (${formatTime(msg.timestamp)})：`);
    }
    lines.push('');
    lines.push(msg.content);
    lines.push('');
    lines.push('---');
    lines.push('');
  }

  return lines.join('\n');
}

export function exportAsJSON(conv: Conversation): string {
  const data = {
    title: conv.title,
    createdAt: formatTime(conv.createdAt),
    updatedAt: formatTime(conv.updatedAt),
    messages: conv.messages.map((m) => ({
      role: m.role,
      content: m.content,
      timestamp: formatTime(m.timestamp),
      ...(m.files?.length ? { files: m.files.map((f) => f.name) } : {}),
    })),
  };
  return JSON.stringify(data, null, 2);
}

export function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
