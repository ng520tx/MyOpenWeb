import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/stores';
import { exportAsMarkdown, exportAsJSON, downloadFile } from '@/utils/export';
import { removeChat } from '@/apis/chats';

export default function Sidebar() {
  const {
    conversations,
    activeConversationId,
    sidebarOpen,
    setSidebarOpen,
    createConversation,
    switchConversation,
    deleteConversation,
    setSettingsOpen,
  } = useAppStore();
  const backdropRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [exportMenuId, setExportMenuId] = useState<string | null>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    if (sidebarOpen) window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [sidebarOpen, setSidebarOpen]);

  useEffect(() => {
    if (!sidebarOpen) {
      setSearchQuery('');
      setExportMenuId(null);
    }
  }, [sidebarOpen]);

  const handleBackdrop = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === backdropRef.current) setSidebarOpen(false);
    },
    [setSidebarOpen]
  );

  const handleNew = useCallback(() => {
    createConversation();
    setSidebarOpen(false);
  }, [createConversation, setSidebarOpen]);

  const handleSelect = useCallback(
    (id: string) => {
      switchConversation(id);
      setSidebarOpen(false);
    },
    [switchConversation, setSidebarOpen]
  );

  const handleDelete = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      deleteConversation(id);
      void removeChat(id);
      setExportMenuId(null);
    },
    [deleteConversation]
  );

  const handleExport = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      setExportMenuId((prev) => (prev === id ? null : id));
    },
    []
  );

  const doExport = useCallback(
    (id: string, format: 'md' | 'json') => {
      const conv = conversations.find((c) => c.id === id);
      if (!conv) return;
      const safeTitle = conv.title.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, '_').slice(0, 30);
      if (format === 'md') {
        downloadFile(exportAsMarkdown(conv), `${safeTitle}.md`, 'text/markdown');
      } else {
        downloadFile(exportAsJSON(conv), `${safeTitle}.json`, 'application/json');
      }
      setExportMenuId(null);
    },
    [conversations]
  );

  const handleOpenSettings = useCallback(() => {
    setSidebarOpen(false);
    setTimeout(() => setSettingsOpen(true), 150);
  }, [setSidebarOpen, setSettingsOpen]);

  const filteredConversations = searchQuery.trim()
    ? conversations.filter((c) => {
        const q = searchQuery.toLowerCase();
        if (c.title.toLowerCase().includes(q)) return true;
        return c.messages.some((m) => m.content.toLowerCase().includes(q));
      })
    : conversations;

  if (!sidebarOpen) return null;

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdrop}
      className="fixed inset-0 z-40 bg-black/50"
    >
      <div className="absolute left-0 top-0 bottom-0 w-[280px] max-w-[80vw] bg-neutral-800 shadow-xl flex flex-col animate-slide-in-left">
        <div className="flex items-center justify-between px-4 h-12 border-b border-neutral-700 shrink-0">
          <span className="text-sm font-semibold">对话列表</span>
          <button
            onClick={() => setSidebarOpen(false)}
            className="w-10 h-10 flex items-center justify-center rounded-lg text-neutral-400 active:text-neutral-100 active:bg-neutral-600"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18" /><path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="px-3 py-2 space-y-2 shrink-0">
          <button
            onClick={handleNew}
            className="w-full flex items-center gap-2 px-3 min-h-[44px] rounded-lg text-sm text-neutral-200 bg-neutral-700 active:bg-neutral-500 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14" /><path d="M5 12h14" />
            </svg>
            新对话
          </button>

          <div className="relative">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索对话..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-neutral-700 text-xs text-neutral-200 placeholder-neutral-500 outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pb-2">
          {filteredConversations.length === 0 && (
            <p className="text-xs text-neutral-500 text-center mt-8">
              {searchQuery ? '无匹配对话' : '暂无对话'}
            </p>
          )}
          {filteredConversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => handleSelect(conv.id)}
              className={`relative flex items-center gap-2 px-3 min-h-[44px] rounded-lg mb-0.5 transition-colors ${
                conv.id === activeConversationId
                  ? 'bg-neutral-700 text-neutral-100'
                  : 'text-neutral-400 active:bg-neutral-700/50 active:text-neutral-200'
              }`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span className="flex-1 text-sm truncate">{conv.title}</span>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={(e) => handleExport(e, conv.id)}
                  className="w-8 h-8 flex items-center justify-center rounded text-neutral-500 active:text-blue-400"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" />
                  </svg>
                </button>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="w-8 h-8 flex items-center justify-center rounded text-neutral-500 active:text-red-400"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                  </svg>
                </button>
              </div>

              {exportMenuId === conv.id && (
                <div
                  className="absolute right-2 top-full mt-1 z-10 bg-neutral-700 rounded-lg shadow-lg border border-neutral-600 py-1 min-w-[120px]"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => doExport(conv.id, 'md')}
                    className="w-full px-3 py-2.5 text-sm text-neutral-200 active:bg-neutral-600 text-left"
                  >
                    导出 Markdown
                  </button>
                  <button
                    onClick={() => doExport(conv.id, 'json')}
                    className="w-full px-3 py-2.5 text-sm text-neutral-200 active:bg-neutral-600 text-left"
                  >
                    导出 JSON
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="shrink-0 border-t border-neutral-700 px-3 py-2">
          <button
            onClick={handleOpenSettings}
            className="w-full flex items-center gap-2 px-3 min-h-[44px] rounded-lg text-sm text-neutral-400 active:text-neutral-200 active:bg-neutral-600 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            设置
          </button>
        </div>
      </div>
    </div>
  );
}
