import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '@/types';
import CodeBlock from './CodeBlock';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[85%]">
          {message.files && message.files.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1 justify-end">
              {message.files.map((f) => (
                <span key={f.name} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-700/30 text-xs text-blue-200">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {f.name}
                </span>
              ))}
            </div>
          )}
          <div className="px-3.5 py-2.5 rounded-2xl rounded-br-md bg-primary-600 text-white text-sm leading-relaxed break-words whitespace-pre-wrap">
            {message.content}
          </div>
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
              remarkPlugins={[remarkGfm]}
              components={{
                pre: ({ children }) => <>{children}</>,
                code: ({ className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeStr = String(children).replace(/\n$/, '');

                  if (match) {
                    return <CodeBlock language={match[1]} code={codeStr} />;
                  }

                  if (codeStr.includes('\n')) {
                    return <CodeBlock language="" code={codeStr} />;
                  }

                  return (
                    <code className="bg-neutral-700 px-1.5 py-0.5 rounded text-xs" {...props}>
                      {children}
                    </code>
                  );
                },
                table: ({ children }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="min-w-full border-collapse text-xs">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-neutral-600 bg-neutral-750 px-3 py-1.5 text-left text-neutral-200 font-medium">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-neutral-700 px-3 py-1.5 text-neutral-300">
                    {children}
                  </td>
                ),
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
