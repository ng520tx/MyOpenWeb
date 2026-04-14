interface ChatNavbarProps {
  model: string;
  onClear: () => void;
}

export default function ChatNavbar({ model, onClear }: ChatNavbarProps) {
  return (
    <nav
      className="flex items-center justify-between px-4 h-12 bg-neutral-800 border-b border-neutral-700 shrink-0"
      style={{ paddingTop: 'var(--safe-area-top)' }}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm font-semibold truncate text-neutral-100">
          MyOpenWeb
        </span>
        <span className="text-xs text-neutral-400 truncate">
          {model}
        </span>
      </div>
      <button
        onClick={onClear}
        className="flex items-center justify-center w-8 h-8 rounded-lg text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 active:bg-neutral-600 transition-colors"
        title="新对话"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
      </button>
    </nav>
  );
}
