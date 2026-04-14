import ReactMarkdown from 'react-markdown';
import type { ChatMessage } from '@/types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-br-md bg-primary-600 text-white text-sm leading-relaxed break-words whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-3">
      <div className="max-w-[92%] text-sm leading-relaxed text-neutral-100">
        {message.error && !message.content ? (
          <div className="px-3 py-2 rounded-xl bg-red-900/30 text-red-300 border border-red-800/50">
            {message.error}
          </div>
        ) : (
          <div className="markdown-body prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              components={{
                pre: ({ children }) => (
                  <pre className="bg-neutral-800 rounded-lg p-3 overflow-x-auto text-xs my-2">
                    {children}
                  </pre>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !className;
                  if (isInline) {
                    return (
                      <code className="bg-neutral-700 px-1.5 py-0.5 rounded text-xs" {...props}>
                        {children}
                      </code>
                    );
                  }
                  return <code className={className} {...props}>{children}</code>;
                },
              }}
            >
              {message.content || ' '}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
