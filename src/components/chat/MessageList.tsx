import { useEffect, useRef } from 'react';
import type { ChatMessage } from '@/types';
import MessageBubble from './MessageBubble';
import ChatPlaceholder from './ChatPlaceholder';

interface MessageListProps {
  messages: ChatMessage[];
  generating: boolean;
}

export default function MessageList({ messages, generating }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  useEffect(() => {
    if (shouldAutoScroll.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    shouldAutoScroll.current = atBottom;
  };

  if (messages.length === 0) {
    return <ChatPlaceholder />;
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-4 py-3"
    >
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {generating && (
        <div className="flex items-center gap-1 py-2 px-1 text-neutral-400">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-neutral-400 animate-pulse" />
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-neutral-400 animate-pulse [animation-delay:150ms]" />
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-neutral-400 animate-pulse [animation-delay:300ms]" />
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
