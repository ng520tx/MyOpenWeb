import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/stores';
import {
  bindKnowledgeFile,
  createKnowledge,
  deleteKnowledge,
  fetchKnowledgeDetail,
  fetchKnowledgeList,
  indexKnowledge,
  unbindKnowledgeFile,
} from '@/apis/knowledge';
import { reextractFile, uploadFile } from '@/apis/files';
import type { IndexResult, KnowledgeBase, KnowledgeDetail } from '@/types';

const ACCEPTED =
  '.txt,.md,.markdown,.json,.csv,.log,.pdf,.docx,.html,.xml,.yaml,.yml,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp';

export default function KnowledgeDrawer() {
  const knowledgeOpen = useAppStore((s) => s.knowledgeOpen);
  const setKnowledgeOpen = useAppStore((s) => s.setKnowledgeOpen);
  const activeKnowledgeId = useAppStore((s) => s.activeKnowledgeId);
  const setActiveKnowledgeId = useAppStore((s) => s.setActiveKnowledgeId);

  const backdropRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [list, setList] = useState<KnowledgeBase[]>([]);
  const [listState, setListState] = useState<'idle' | 'loading' | 'error'>('idle');
  const [newName, setNewName] = useState('');

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<KnowledgeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null);
  const [reextractingId, setReextractingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    setListState('loading');
    try {
      setList(await fetchKnowledgeList());
      setListState('idle');
    } catch {
      setListState('error');
    }
  }, []);

  const refreshDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    try {
      setDetail(await fetchKnowledgeDetail(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!knowledgeOpen) return;
    void refreshList();
  }, [knowledgeOpen, refreshList]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setKnowledgeOpen(false);
    };
    if (knowledgeOpen) window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [knowledgeOpen, setKnowledgeOpen]);

  useEffect(() => {
    if (selectedId) {
      setIndexResult(null);
      setError(null);
      void refreshDetail(selectedId);
    } else {
      setDetail(null);
    }
  }, [selectedId, refreshDetail]);

  const handleCreate = useCallback(() => {
    const name = newName.trim();
    if (!name) return;
    void (async () => {
      try {
        const created = await createKnowledge(name);
        setNewName('');
        await refreshList();
        setSelectedId(created.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [newName, refreshList]);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || !selectedId) return;
      setUploading(true);
      setError(null);
      try {
        for (const file of Array.from(files)) {
          const record = await uploadFile(file);
          await bindKnowledgeFile(selectedId, record.id);
        }
        await refreshDetail(selectedId);
        await refreshList();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setUploading(false);
        e.target.value = '';
      }
    },
    [selectedId, refreshDetail, refreshList]
  );

  const handleUnbind = useCallback(
    (fileId: string) => {
      if (!selectedId) return;
      void (async () => {
        try {
          const updated = await unbindKnowledgeFile(selectedId, fileId);
          setDetail(updated);
          await refreshList();
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })();
    },
    [selectedId, refreshList]
  );

  const handleReextract = useCallback(
    (fileId: string) => {
      if (!selectedId) return;
      setReextractingId(fileId);
      setError(null);
      void (async () => {
        try {
          await reextractFile(fileId);
          await refreshDetail(selectedId);
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          setReextractingId(null);
        }
      })();
    },
    [selectedId, refreshDetail]
  );

  const handleIndex = useCallback(() => {
    if (!selectedId) return;
    setIndexing(true);
    setError(null);
    setIndexResult(null);
    void (async () => {
      try {
        const result = await indexKnowledge(selectedId);
        setIndexResult(result);
        await refreshDetail(selectedId);
        await refreshList();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setIndexing(false);
      }
    })();
  }, [selectedId, refreshDetail, refreshList]);

  const handleDelete = useCallback(
    (id: string) => {
      void (async () => {
        try {
          await deleteKnowledge(id);
          if (activeKnowledgeId === id) setActiveKnowledgeId(null);
          if (selectedId === id) setSelectedId(null);
          await refreshList();
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })();
    },
    [activeKnowledgeId, selectedId, setActiveKnowledgeId, refreshList]
  );

  const handleBackdrop = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === backdropRef.current) setKnowledgeOpen(false);
    },
    [setKnowledgeOpen]
  );

  if (!knowledgeOpen) return null;

  return (
    <div ref={backdropRef} onClick={handleBackdrop} className="fixed inset-0 z-50 bg-black/50">
      <div className="absolute right-0 top-0 bottom-0 w-[340px] max-w-[88vw] bg-neutral-800 shadow-xl flex flex-col animate-slide-in-right">
        <div className="flex items-center justify-between px-4 h-12 border-b border-neutral-700 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {selectedId && (
              <button
                onClick={() => setSelectedId(null)}
                className="w-8 h-8 flex items-center justify-center rounded-lg text-neutral-400 active:text-neutral-100 active:bg-neutral-600"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m15 18-6-6 6-6" />
                </svg>
              </button>
            )}
            <span className="text-sm font-semibold truncate">{selectedId ? detail?.name ?? '知识库' : '知识库'}</span>
          </div>
          <button
            onClick={() => setKnowledgeOpen(false)}
            className="w-10 h-10 flex items-center justify-center rounded-lg text-neutral-400 active:text-neutral-100 active:bg-neutral-600"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18" /><path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-700/70 bg-red-950/30 px-3 py-2 text-xs text-red-300 break-all">{error}</div>
          )}

          {!selectedId ? (
            <>
              <div className="rounded-xl border border-neutral-700 bg-neutral-900/50 p-3 space-y-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); }}
                  placeholder="新建知识库名称，如：运维手册"
                  className="input-field"
                />
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim()}
                  className="w-full min-h-[44px] rounded-lg bg-primary-600 text-sm font-medium text-white active:bg-primary-700 transition-colors disabled:opacity-50"
                >
                  新建知识库
                </button>
              </div>

              <button
                onClick={() => setActiveKnowledgeId(null)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-xs ${
                  activeKnowledgeId === null
                    ? 'border-blue-700/70 bg-blue-950/30 text-blue-200'
                    : 'border-neutral-700 bg-neutral-900/40 text-neutral-400'
                }`}
              >
                {activeKnowledgeId === null ? '当前：不使用知识库（普通聊天）' : '点此切回普通聊天（不使用知识库）'}
              </button>

              {listState === 'loading' && <p className="text-xs text-neutral-500">加载中...</p>}
              {listState === 'error' && <p className="text-xs text-red-400">知识库列表加载失败，请确认后端已启动</p>}

              {list.length === 0 && listState === 'idle' && (
                <p className="text-xs text-neutral-500">还没有知识库。新建一个，上传运维文档/接口文档/故障案例试试。</p>
              )}

              <div className="space-y-2">
                {list.map((kb) => (
                  <div
                    key={kb.id}
                    className={`rounded-xl border p-3 ${
                      activeKnowledgeId === kb.id ? 'border-blue-700/70 bg-blue-950/20' : 'border-neutral-700 bg-neutral-900/40'
                    }`}
                  >
                    <button onClick={() => setSelectedId(kb.id)} className="block w-full text-left">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-neutral-100 truncate">{kb.name}</span>
                        {activeKnowledgeId === kb.id && (
                          <span className="text-[11px] text-blue-300 bg-blue-950/70 border border-blue-800/60 rounded-full px-2 py-0.5 shrink-0">使用中</span>
                        )}
                      </div>
                      <div className="mt-1 text-[11px] text-neutral-500">
                        {kb.file_count} 个文件 · {kb.chunk_count} 个分块{kb.chunk_count === 0 ? ' · 未建索引' : ''}
                      </div>
                    </button>
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        onClick={() => setActiveKnowledgeId(activeKnowledgeId === kb.id ? null : kb.id)}
                        disabled={kb.chunk_count === 0 && activeKnowledgeId !== kb.id}
                        className={`flex-1 rounded-lg px-2 py-1.5 text-xs ${
                          activeKnowledgeId === kb.id
                            ? 'bg-blue-900/40 text-blue-200'
                            : 'bg-neutral-700 text-neutral-200 active:bg-neutral-600 disabled:opacity-40'
                        }`}
                      >
                        {activeKnowledgeId === kb.id ? '取消使用' : '聊天使用'}
                      </button>
                      <button
                        onClick={() => setSelectedId(kb.id)}
                        className="flex-1 rounded-lg bg-neutral-700 px-2 py-1.5 text-xs text-neutral-200 active:bg-neutral-600"
                      >
                        管理
                      </button>
                      <button
                        onClick={() => handleDelete(kb.id)}
                        className="rounded-lg px-2 py-1.5 text-xs text-red-300 active:bg-red-950/50"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ACCEPTED}
                onChange={handleUpload}
                className="hidden"
              />

              <div className="rounded-xl border border-neutral-700 bg-neutral-900/50 p-3 space-y-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="w-full min-h-[44px] rounded-lg bg-primary-600 text-sm font-medium text-white active:bg-primary-700 transition-colors disabled:opacity-50"
                >
                  {uploading ? '上传中...' : '上传文件（txt / md / pdf / docx 等）'}
                </button>
                <button
                  onClick={handleIndex}
                  disabled={indexing || detailLoading || (detail?.files.length ?? 0) === 0}
                  className="w-full min-h-[44px] rounded-lg border border-neutral-600 text-sm font-medium text-neutral-100 active:bg-neutral-700 transition-colors disabled:opacity-50"
                >
                  {indexing ? '建立索引中...' : '建立 / 重建索引'}
                </button>
                {indexResult && (
                  <p className="text-xs text-emerald-400">
                    索引完成：{indexResult.files} 个文件，{indexResult.chunks} 个分块（embedding：{indexResult.embedding_model}）
                  </p>
                )}
                <p className="text-[11px] leading-relaxed text-neutral-500">
                  上传后会自动抽取文本。点击"建立索引"会对文件切片并向量化，之后才能在聊天中检索。索引使用设置里配置的 embedding 模型。
                </p>
              </div>

              {detailLoading && <p className="text-xs text-neutral-500">加载中...</p>}

              {detail && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-neutral-400">文件（{detail.files.length}）· 分块 {detail.chunk_count}</span>
                    <button
                      onClick={() => setActiveKnowledgeId(activeKnowledgeId === detail.id ? null : detail.id)}
                      disabled={detail.chunk_count === 0 && activeKnowledgeId !== detail.id}
                      className={`rounded-lg px-2.5 py-1 text-xs ${
                        activeKnowledgeId === detail.id
                          ? 'bg-blue-900/40 text-blue-200'
                          : 'bg-neutral-700 text-neutral-200 active:bg-neutral-600 disabled:opacity-40'
                      }`}
                    >
                      {activeKnowledgeId === detail.id ? '聊天使用中' : '设为聊天知识库'}
                    </button>
                  </div>

                  {detail.files.length === 0 ? (
                    <p className="text-xs text-neutral-500">还没有文件，先上传文档。</p>
                  ) : (
                    detail.files.map((file) => (
                      <div key={file.id} className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs text-neutral-200 truncate">{file.filename}</span>
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => handleReextract(file.id)}
                              disabled={reextractingId === file.id}
                              className="rounded px-2 py-1 text-[11px] text-neutral-300 active:bg-neutral-700 disabled:opacity-50"
                            >
                              {reextractingId === file.id ? '抽取中...' : '重新抽取'}
                            </button>
                            <button
                              onClick={() => handleUnbind(file.id)}
                              className="rounded px-2 py-1 text-[11px] text-red-300 active:bg-red-950/50"
                            >
                              移除
                            </button>
                          </div>
                        </div>
                        <p className="mt-1 text-[11px] text-neutral-500">
                          {file.text_length} 字{file.text_length === 0 ? '（未抽取到文本）' : ''}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
