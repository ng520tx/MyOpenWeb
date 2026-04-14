export default function ChatPlaceholder() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 text-center">
      <div className="w-14 h-14 rounded-full bg-neutral-800 flex items-center justify-center mb-4">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-neutral-400">
          <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7Z" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M10 21h4" strokeLinecap="round" />
          <path d="M10 17v-2.26" strokeLinecap="round" />
          <path d="M14 17v-2.26" strokeLinecap="round" />
        </svg>
      </div>
      <h2 className="text-lg font-medium text-neutral-200 mb-1">
        MyOpenWeb
      </h2>
      <p className="text-sm text-neutral-500 max-w-xs">
        输入消息开始对话，支持流式输出与 Ollama / OpenAI 兼容 API
      </p>
    </div>
  );
}
