import { useAppStore } from '@/stores';

const BTN = 'flex items-center justify-center w-10 h-10 rounded-lg text-neutral-400 active:text-neutral-100 active:bg-neutral-600 transition-colors';

export default function ChatNavbar() {
  const { settings, activeKnowledgeId, setSidebarOpen, setSettingsOpen, setKnowledgeOpen, clearMessages } = useAppStore();

  return (
    <nav
      className="flex items-center justify-between px-2 h-12 bg-neutral-800 border-b border-neutral-700 shrink-0"
      style={{ paddingTop: 'var(--safe-area-top)' }}
    >
      <div className="flex items-center gap-0.5 min-w-0">
        <button onClick={() => setSidebarOpen(true)} className={BTN}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" x2="20" y1="12" y2="12" /><line x1="4" x2="20" y1="6" y2="6" /><line x1="4" x2="20" y1="18" y2="18" />
          </svg>
        </button>
        <span className="text-sm font-semibold truncate text-neutral-100">MyOpenWeb</span>
        {settings.agentEnabled && (
          <span className="text-[11px] text-blue-300 bg-blue-950/70 border border-blue-800/60 rounded-full px-2 py-0.5 ml-1 shrink-0">Agent</span>
        )}
        {activeKnowledgeId && (
          <span className="text-[11px] text-emerald-300 bg-emerald-950/70 border border-emerald-800/60 rounded-full px-2 py-0.5 ml-1 shrink-0">知识库</span>
        )}
        <span className="text-xs text-neutral-400 truncate ml-1">{settings.model}</span>
      </div>

      <div className="flex items-center gap-0.5">
        <button onClick={() => setKnowledgeOpen(true)} className={BTN}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
          </svg>
        </button>
        <button onClick={clearMessages} className={BTN}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
          </svg>
        </button>
        <button onClick={() => setSettingsOpen(true)} className={BTN}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
      </div>
    </nav>
  );
}
