import { useState, useRef, useCallback, type KeyboardEvent } from 'react';
import VoiceButton from '@/components/chat/VoiceButton';
import FileButton from '@/components/chat/FileButton';
import FilePreviews from '@/components/chat/FilePreviews';
import { useAppStore } from '@/stores';

interface MessageInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  generating: boolean;
}

const QUICK_TOOLS = [
  { label: '日志分析', template: '请分析下面这段日志，找出错误原因并给出排查建议：\n\n' },
  { label: 'Git diff 摘要', template: '请总结下面这段 git diff 的变更内容和潜在风险：\n\n' },
  { label: '工单总结', template: '请总结下面这个工单的关键信息：\n\n' },
  { label: '测试用例', template: '请根据下面的需求生成测试用例：\n\n' },
] as const;

export default function MessageInput({ onSend, onStop, generating }: MessageInputProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const agentEnabled = useAppStore((s) => s.settings.agentEnabled);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }, []);

  const applyQuickTool = useCallback((template: string) => {
    setText(template);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    });
  }, []);

  const handleSend = useCallback(() => {
    const val = text.trim();
    if (!val) return;
    onSend(val);
    setText('');
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    });
  }, [text, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleVoiceResult = useCallback((transcript: string) => {
    setText((prev) => prev + transcript);
    textareaRef.current?.focus();
  }, []);

  return (
    <div
      className="shrink-0 bg-neutral-800"
      style={{ paddingBottom: 'var(--safe-area-bottom)' }}
    >
      <FilePreviews />
      {agentEnabled && (
        <div className="flex gap-1.5 overflow-x-auto px-3 pt-2 max-w-3xl mx-auto">
          {QUICK_TOOLS.map((tool) => (
            <button
              key={tool.label}
              onClick={() => applyQuickTool(tool.template)}
              className="shrink-0 rounded-full border border-neutral-600 bg-neutral-700/60 px-3 py-1 text-xs text-neutral-200 active:bg-neutral-600 transition-colors"
            >
              {tool.label}
            </button>
          ))}
        </div>
      )}
      <div className="px-3 py-2 border-t border-neutral-700">
        <div className="flex items-end gap-2 max-w-3xl mx-auto">
          <FileButton />

          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                adjustHeight();
              }}
              onKeyDown={handleKeyDown}
              placeholder="输入消息..."
              rows={1}
              className="w-full resize-none rounded-xl bg-neutral-700 text-sm text-neutral-100 placeholder-neutral-500 px-3.5 py-2.5 pr-10 outline-none focus:ring-1 focus:ring-primary-500 transition-shadow leading-relaxed"
              style={{ maxHeight: 160 }}
            />
          </div>

          <VoiceButton onResult={handleVoiceResult} />

          {generating ? (
            <button
              onClick={onStop}
              className="flex items-center justify-center w-11 h-11 rounded-xl bg-red-600 text-white shrink-0 active:bg-red-700 transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!text.trim()}
              className="flex items-center justify-center w-11 h-11 rounded-xl bg-primary-600 text-white shrink-0 disabled:opacity-40 active:bg-primary-700 transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m5 12 7-7 7 7" /><path d="M12 19V5" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
