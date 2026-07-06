import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchAgentRun } from '@/apis/agent';
import type { AgentRun, AgentStepEvent, ChatMessage } from '@/types';
import CodeBlock from './CodeBlock';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const imageFiles = message.files?.filter((f) => f.isImage && f.dataUrl) ?? [];
  const textFiles = message.files?.filter((f) => !f.isImage) ?? [];
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sources = message.sources ?? [];

  const toggleAgentDetails = () => {
    if (!message.agent) return;
    const nextOpen = !agentOpen;
    setAgentOpen(nextOpen);
    if (!nextOpen || agentRun || agentLoading) return;

    setAgentLoading(true);
    setAgentError(null);
    void fetchAgentRun(message.agent.runId)
      .then(setAgentRun)
      .catch((error) => setAgentError(error instanceof Error ? error.message : String(error)))
      .finally(() => setAgentLoading(false));
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[85%]">
          {textFiles.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1 justify-end">
              {textFiles.map((f) => (
                <span key={f.name} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-700/30 text-xs text-blue-200">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {f.name}
                </span>
              ))}
            </div>
          )}
          {imageFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-1.5 justify-end">
              {imageFiles.map((f) => (
                <img
                  key={f.name}
                  src={f.dataUrl}
                  alt={f.name}
                  className="max-w-[200px] max-h-[200px] rounded-lg object-cover"
                />
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
        {message.error ? (
          <div className="px-3 py-2 rounded-xl bg-red-900/30 text-red-300 border border-red-800/50">
            <div className="flex items-center gap-1.5 mb-1 text-xs font-medium text-red-400">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" x2="9" y1="9" y2="15"/><line x1="9" x2="15" y1="9" y2="15"/></svg>
              请求失败
            </div>
            {message.error}
          </div>
        ) : (
          <>
            {!message.done && (message.agentEvents?.length ?? 0) > 0 && (
              <AgentTimeline events={message.agentEvents!} />
            )}
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
            {message.agent && message.agent.toolCalls.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={toggleAgentDetails}
                  className="mt-2 inline-flex max-w-full flex-wrap items-center gap-1.5 rounded-lg border border-blue-900/70 bg-blue-950/30 px-2.5 py-1.5 text-left text-xs text-blue-200 active:bg-blue-900/40"
                >
                  <span>Agent 调用 {message.agent.toolCalls.length} 个工具：</span>
                  {message.agent.toolCalls.map((call, index) => (
                    <span
                      key={`${message.agent?.runId}-${call.name}-${index}`}
                      className={call.ok ? 'text-blue-100' : 'text-red-300'}
                    >
                      {call.name}{index < message.agent!.toolCalls.length - 1 ? '、' : ''}
                    </span>
                  ))}
                  <span className="text-blue-300/80">{agentOpen ? '收起' : '详情'}</span>
                </button>
                {agentOpen && (
                  <div className="mt-2 max-w-full rounded-xl border border-neutral-700 bg-neutral-900/80 p-3 text-xs text-neutral-300">
                    {agentLoading && <p className="text-neutral-500">加载 Agent 日志...</p>}
                    {agentError && <p className="text-red-300">日志加载失败：{agentError}</p>}
                    {agentRun && (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2 text-neutral-400">
                          <span>Run: {agentRun.id.slice(0, 8)}</span>
                          <span>Model: {agentRun.model}</span>
                        </div>
                        {agentRun.steps.map((step) => (
                          <div key={step.id} className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-2">
                            <div className="mb-1 flex flex-wrap items-center gap-2">
                              <span className="text-blue-200">#{step.step_index}</span>
                              <span className="text-neutral-200">{step.type}</span>
                              {step.name && <span className="text-emerald-300">{step.name}</span>}
                              {!step.ok && <span className="text-red-300">{step.error || 'failed'}</span>}
                            </div>
                            {step.input !== null && step.input !== undefined && (
                              <pre className="max-h-28 overflow-auto whitespace-pre-wrap break-words text-neutral-500">{formatJson(step.input)}</pre>
                            )}
                            {step.output !== null && step.output !== undefined && (
                              <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words text-neutral-400">{formatJson(step.output)}</pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
            {sources.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => setSourcesOpen((v) => !v)}
                  className="mt-2 inline-flex max-w-full flex-wrap items-center gap-1.5 rounded-lg border border-emerald-900/70 bg-emerald-950/30 px-2.5 py-1.5 text-left text-xs text-emerald-200 active:bg-emerald-900/40"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                    <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                  </svg>
                  <span>引用来源 {sources.length} 处</span>
                  <span className="text-emerald-300/80">{sourcesOpen ? '收起' : '展开'}</span>
                </button>
                {sourcesOpen && (
                  <div className="mt-2 max-w-full space-y-2 rounded-xl border border-neutral-700 bg-neutral-900/80 p-3 text-xs text-neutral-300">
                    {sources.map((source) => (
                      <div
                        key={`${source.file_id}-${source.chunk_index}-${source.index}`}
                        className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-2"
                      >
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <span className="text-emerald-300">[{source.index}]</span>
                          <span className="break-all text-neutral-200">{source.filename}</span>
                          <span className="text-neutral-500">相似度 {(source.score * 100).toFixed(0)}%</span>
                        </div>
                        <p className="max-h-28 overflow-auto whitespace-pre-wrap break-words text-neutral-400">{source.preview}</p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Agent 生成过程实时时间线：思考 / 工具调用 / 工具结果 */
function AgentTimeline({ events }: { events: AgentStepEvent[] }) {
  return (
    <div className="mb-2 rounded-xl border border-blue-900/60 bg-blue-950/20 px-3 py-2 text-xs">
      {events.map((event, index) => {
        const isLast = index === events.length - 1;
        return (
          <div key={index} className="flex items-start gap-2 py-0.5">
            {event.type === 'thinking' && (
              <>
                <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${isLast ? 'animate-pulse bg-blue-400' : 'bg-blue-700'}`} />
                <span className="text-blue-200">
                  {isLast ? `第 ${event.round ?? 1} 轮思考中…` : `第 ${event.round ?? 1} 轮决策完成`}
                </span>
              </>
            )}
            {event.type === 'tool_call' && (
              <>
                <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${isLast ? 'animate-pulse bg-amber-400' : 'bg-amber-600'}`} />
                <span className="min-w-0 text-amber-200">
                  调用工具 <span className="font-medium">{event.name}</span>
                  {event.parameters && Object.keys(event.parameters).length > 0 && (
                    <span className="ml-1 break-all text-amber-200/60">
                      {truncateJson(event.parameters, 80)}
                    </span>
                  )}
                </span>
              </>
            )}
            {event.type === 'tool_result' && (
              <>
                <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${event.ok ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="min-w-0">
                  <span className={event.ok ? 'text-emerald-200' : 'text-red-300'}>
                    {event.name} {event.ok ? '完成' : `失败：${event.error ?? '未知错误'}`}
                  </span>
                  {event.ok && event.summary && (
                    <span className="ml-1 break-all text-neutral-500">{event.summary}</span>
                  )}
                </span>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

function truncateJson(value: unknown, limit: number): string {
  let text: string;
  try {
    text = JSON.stringify(value);
  } catch {
    text = String(value);
  }
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

function formatJson(value: unknown): string {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
