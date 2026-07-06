import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/stores';
import { fetchModels, type ModelInfo } from '@/apis/models';
import { syncProviderConfig, verifyProviderConfig, type ProviderVerifyResult } from '@/apis/config';
import { createMemory, deleteMemory, fetchMemories, updateMemory } from '@/apis/memories';
import type { AppSettings, MemoryCategory, MemoryItem } from '@/types';

export default function SettingsDrawer() {
  const { settings, settingsOpen, setSettingsOpen, updateSettings } = useAppStore();
  const backdropRef = useRef<HTMLDivElement>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ProviderVerifyResult | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [memoryContent, setMemoryContent] = useState('');
  const [memoryCategory, setMemoryCategory] = useState<MemoryCategory>('fact');
  const [memoryState, setMemoryState] = useState<'idle' | 'loading' | 'saving' | 'error'>('idle');

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSettingsOpen(false);
    };
    if (settingsOpen) window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [settingsOpen, setSettingsOpen]);

  useEffect(() => {
    if (!settingsOpen) return;
    let cancelled = false;
    void (async () => {
      setLoadingModels(true);
      try {
        await syncProviderConfig(settings);
        const list = await fetchModels();
        if (!cancelled) {
          setModels(list);
          setSaveState('saved');
        }
      } catch {
        if (!cancelled) {
          setSaveState('error');
          setModels([]);
        }
      } finally {
        if (!cancelled) {
          setLoadingModels(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [settingsOpen, settings.providerType, settings.apiBaseUrl, settings.apiKey]);

  useEffect(() => {
    setVerifyResult(null);
  }, [settings.providerType, settings.apiBaseUrl, settings.apiKey]);

  useEffect(() => {
    if (!settingsOpen) return;
    let cancelled = false;
    void (async () => {
      setMemoryState('loading');
      try {
        const list = await fetchMemories();
        if (!cancelled) {
          setMemories(list);
          setMemoryState('idle');
        }
      } catch {
        if (!cancelled) {
          setMemoryState('error');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [settingsOpen]);

  const handleRefreshModels = useCallback(() => {
    void (async () => {
      setLoadingModels(true);
      try {
        await syncProviderConfig(settings);
        const list = await fetchModels();
        setModels(list);
        setSaveState('saved');
      } catch {
        setSaveState('error');
        setModels([]);
      } finally {
        setLoadingModels(false);
      }
    })();
  }, [settings]);

  const handleSaveProvider = useCallback(() => {
    void (async () => {
      setSaveState('saving');
      try {
        await syncProviderConfig(settings);
        setSaveState('saved');
      } catch {
        setSaveState('error');
      }
    })();
  }, [settings]);

  const handleVerifyProvider = useCallback(() => {
    void (async () => {
      setVerifying(true);
      try {
        const result = await verifyProviderConfig(settings);
        setVerifyResult(result);
        if (result.ok) {
          setModels(result.models);
        }
      } catch (error) {
        setVerifyResult({
          ok: false,
          provider_type: settings.providerType,
          configured_base_url: settings.apiBaseUrl,
          models_count: 0,
          models: [],
          error: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setVerifying(false);
      }
    })();
  }, [settings]);

  const handleCreateMemory = useCallback(() => {
    const content = memoryContent.trim();
    if (!content) return;

    void (async () => {
      setMemoryState('saving');
      try {
        const created = await createMemory({ content, category: memoryCategory, enabled: true });
        setMemories((current) => [created, ...current]);
        setMemoryContent('');
        setMemoryState('idle');
      } catch {
        setMemoryState('error');
      }
    })();
  }, [memoryCategory, memoryContent]);

  const handleToggleMemory = useCallback((memory: MemoryItem) => {
    void (async () => {
      try {
        const updated = await updateMemory(memory.id, { enabled: !memory.enabled });
        setMemories((current) => current.map((item) => (item.id === memory.id ? updated : item)));
      } catch {
        setMemoryState('error');
      }
    })();
  }, []);

  const handleDeleteMemory = useCallback((memory: MemoryItem) => {
    void (async () => {
      try {
        await deleteMemory(memory.id);
        setMemories((current) => current.filter((item) => item.id !== memory.id));
      } catch {
        setMemoryState('error');
      }
    })();
  }, []);

  const handleBackdrop = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === backdropRef.current) setSettingsOpen(false);
    },
    [setSettingsOpen]
  );

  if (!settingsOpen) return null;

  const modelInList = models.some((m) => m.id === settings.model);

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdrop}
      className="fixed inset-0 z-50 bg-black/50"
    >
      <div className="absolute right-0 top-0 bottom-0 w-[320px] max-w-[85vw] bg-neutral-800 shadow-xl flex flex-col animate-slide-in-right">
        <div className="flex items-center justify-between px-4 h-12 border-b border-neutral-700 shrink-0">
          <span className="text-sm font-semibold">设置</span>
          <button
            onClick={() => setSettingsOpen(false)}
            className="w-10 h-10 flex items-center justify-center rounded-lg text-neutral-400 active:text-neutral-100 active:bg-neutral-600"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18" /><path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
          <Field label="Provider">
            <select
              value={settings.providerType}
              onChange={(e) => updateSettings({ providerType: e.target.value as typeof settings.providerType })}
              className="input-field"
            >
              <option value="ollama">Ollama</option>
              <option value="openai">OpenAI Compatible</option>
            </select>
          </Field>

          <Field label="API 地址">
            <input
              type="text"
              value={settings.apiBaseUrl}
              onChange={(e) => updateSettings({ apiBaseUrl: e.target.value })}
              placeholder="http://localhost:11434/v1"
              className="input-field"
            />
          </Field>

          <Field label="API Key（可选）">
            <input
              type="password"
              value={settings.apiKey}
              onChange={(e) => updateSettings({ apiKey: e.target.value })}
              placeholder="sk-..."
              className="input-field"
            />
          </Field>

          <div className="rounded-xl border border-neutral-700 bg-neutral-900/50 p-3 space-y-2">
            <button
              onClick={handleSaveProvider}
              disabled={saveState === 'saving'}
              className="w-full min-h-[44px] rounded-lg bg-primary-600 text-sm font-medium text-white active:bg-primary-700 transition-colors disabled:opacity-50"
            >
              {saveState === 'saving' ? '保存中...' : '保存连接配置到后端'}
            </button>
            {saveState === 'saved' && (
              <p className="text-xs text-emerald-400">连接配置已同步到本地后端</p>
            )}
            {saveState === 'error' && (
              <p className="text-xs text-red-400">连接配置同步失败，请确认后端已启动</p>
            )}
            <button
              onClick={handleVerifyProvider}
              disabled={verifying}
              className="w-full min-h-[44px] rounded-lg border border-neutral-600 text-sm font-medium text-neutral-100 active:bg-neutral-700 transition-colors disabled:opacity-50"
            >
              {verifying ? '测试中...' : '测试连接'}
            </button>
            {verifyResult && (
              <div
                className={`rounded-lg border px-3 py-2 text-xs ${
                  verifyResult.ok
                    ? 'border-emerald-700/70 bg-emerald-950/30 text-emerald-300'
                    : 'border-red-700/70 bg-red-950/30 text-red-300'
                }`}
              >
                {verifyResult.ok ? (
                  <div className="space-y-1">
                    <p>连接成功，发现 {verifyResult.models_count} 个模型</p>
                    {verifyResult.resolved_base_url && (
                      <p className="break-all text-emerald-200/80">实际地址：{verifyResult.resolved_base_url}</p>
                    )}
                  </div>
                ) : (
                  <p className="break-all">连接失败：{verifyResult.error || '未知错误'}</p>
                )}
              </div>
            )}
          </div>

          <Field label="模型">
            <div className="flex gap-2">
              {models.length > 0 ? (
                <select
                  value={modelInList ? settings.model : '__custom__'}
                  onChange={(e) => {
                    if (e.target.value !== '__custom__') {
                      updateSettings({ model: e.target.value });
                    }
                  }}
                  className="input-field flex-1"
                >
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>{m.id}</option>
                  ))}
                  {!modelInList && (
                    <option value="__custom__">{settings.model}（自定义）</option>
                  )}
                </select>
              ) : (
                <input
                  type="text"
                  value={settings.model}
                  onChange={(e) => updateSettings({ model: e.target.value })}
                  placeholder="qwen3.5:4b"
                  className="input-field flex-1"
                />
              )}
              <button
                onClick={handleRefreshModels}
                disabled={loadingModels}
                className="flex items-center justify-center w-11 h-11 rounded-lg bg-neutral-700 text-neutral-400 active:text-neutral-200 active:bg-neutral-600 shrink-0 transition-colors disabled:opacity-40"
              >
                <svg
                  width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  className={loadingModels ? 'animate-spin' : ''}
                >
                  <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
                  <path d="M21 3v5h-5" />
                </svg>
              </button>
            </div>
            {loadingModels && <span className="text-xs text-neutral-500 mt-1 block">加载中...</span>}
            {!loadingModels && models.length > 0 && (
              <span className="text-xs text-neutral-500 mt-1 block">已发现 {models.length} 个模型</span>
            )}
          </Field>

          <div className="border-t border-neutral-700 pt-4">
            <span className="text-xs text-neutral-400 font-medium uppercase tracking-wider">知识库 / RAG</span>
          </div>

          <Field label="Embedding 模型（用于知识库向量化）">
            <input
              type="text"
              value={settings.embeddingModel}
              onChange={(e) => updateSettings({ embeddingModel: e.target.value })}
              placeholder="bge-m3"
              className="input-field"
            />
            <span className="text-xs text-neutral-500 mt-1 block leading-relaxed">
              Ollama 需先执行 <code className="text-neutral-300">ollama pull {settings.embeddingModel || 'bge-m3'}</code>。修改后点上方"保存连接配置到后端"生效。
            </span>
          </Field>

          <Field label="检索模式">
            <select
              value={settings.retrievalMode}
              onChange={(e) => updateSettings({ retrievalMode: e.target.value === 'vector' ? 'vector' : 'hybrid' })}
              className="input-field"
            >
              <option value="hybrid">混合检索（BM25 + 向量 RRF 融合）</option>
              <option value="vector">纯向量（余弦相似度）</option>
            </select>
            <span className="text-xs text-neutral-500 mt-1 block leading-relaxed">
              混合检索对术语、编号、命令类问题召回更稳。修改后点上方"保存连接配置到后端"生效，需重建索引以生成 BM25 词表。
            </span>
          </Field>

          <Toggle
            label="Rerank 重排序（bge-reranker）"
            checked={settings.rerankEnabled}
            onChange={(v) => updateSettings({ rerankEnabled: v })}
          />

          {settings.rerankEnabled && (
            <Field label="Rerank 模型">
              <input
                type="text"
                value={settings.rerankModel}
                onChange={(e) => updateSettings({ rerankModel: e.target.value })}
                placeholder="BAAI/bge-reranker-base"
                className="input-field"
              />
              <span className="text-xs text-neutral-500 mt-1 block leading-relaxed">
                需安装可选依赖：<code className="text-neutral-300">pip install -r server/rerank/requirements.txt</code>。未安装时自动回退为不重排。
              </span>
            </Field>
          )}

          <Toggle
            label="多轮检索改写（Query Rewrite）"
            checked={settings.queryRewriteEnabled}
            onChange={(v) => updateSettings({ queryRewriteEnabled: v })}
          />
          <span className="text-xs text-neutral-500 -mt-2 block leading-relaxed">
            多轮追问时用模型把&quot;它的端口是多少&quot;这类省略主语的问题补全后再检索，失败自动回退原问题。
          </span>

          <Toggle
            label="检索自纠错（Agentic Retrieval）"
            checked={settings.agenticRetrievalEnabled}
            onChange={(v) => updateSettings({ agenticRetrievalEnabled: v })}
          />
          <span className="text-xs text-neutral-500 -mt-2 block leading-relaxed">
            检索后先让模型评估资料是否足以回答（Grader），不足时按缺失信息补检索一轮再合并。会增加一次模型调用的延迟；评估失败自动沿用首轮结果。
          </span>

          <Toggle
            label="OCR 文档解析（扫描件 / 表格 / 图片）"
            checked={settings.ocrEnabled}
            onChange={(v) => updateSettings({ ocrEnabled: v })}
          />

          {settings.ocrEnabled && (
            <>
              <Field label="OCR 服务地址">
                <input
                  type="text"
                  value={settings.ocrBaseUrl}
                  onChange={(e) => updateSettings({ ocrBaseUrl: e.target.value })}
                  placeholder="http://localhost:8118"
                  className="input-field"
                />
              </Field>
              <Field label="OCR 触发模式">
                <select
                  value={settings.ocrMode}
                  onChange={(e) => updateSettings({ ocrMode: e.target.value === 'always' ? 'always' : 'auto' })}
                  className="input-field"
                >
                  <option value="auto">auto（仅扫描件 / 抽不出文字时）</option>
                  <option value="always">always（PDF / 图片都走 OCR）</option>
                </select>
                <span className="text-xs text-neutral-500 mt-1 block leading-relaxed">
                  需单独启动 PaddleOCR (PP-StructureV3) 服务，见 <code className="text-neutral-300">scripts/ocr-server.ps1</code>。修改后点上方"保存连接配置到后端"生效；已上传文件可在知识库内重新抽取。
                </span>
              </Field>
            </>
          )}

          <div className="border-t border-neutral-700 pt-4">
            <span className="text-xs text-neutral-400 font-medium uppercase tracking-wider">Agent</span>
          </div>

          <Toggle
            label="Agent 模式"
            checked={settings.agentEnabled}
            onChange={(v) => updateSettings({ agentEnabled: v })}
          />

          {settings.agentEnabled && (
            <>
              <div className="rounded-xl border border-blue-800/60 bg-blue-950/30 px-3 py-2 text-xs text-blue-200 leading-relaxed">
                Agent 工具：当前时间、计算器、日志分析、Git diff 摘要、工单总结、测试用例生成、知识库检索。后端白名单执行，不会运行系统命令。
              </div>
              <Field label="工具调用协议">
                <select
                  value={settings.agentToolProtocol}
                  onChange={(e) => updateSettings({ agentToolProtocol: e.target.value as AppSettings['agentToolProtocol'] })}
                  className="input-field"
                >
                  <option value="prompt">Prompt JSON（兼容任意模型）</option>
                  <option value="native">原生 Function Calling（需模型支持 tools）</option>
                </select>
                <span className="text-xs text-neutral-500 mt-1 block leading-relaxed">
                  Prompt 协议靠系统提示词约定 JSON 输出，任何模型可用；原生协议走模型 tools 接口（如 qwen2.5），格式更稳但依赖模型支持。
                </span>
              </Field>
            </>
          )}

          <div className="border-t border-neutral-700 pt-4">
            <span className="text-xs text-neutral-400 font-medium uppercase tracking-wider">Memory</span>
          </div>

          <div className="rounded-xl border border-neutral-700 bg-neutral-900/50 p-3 space-y-3">
            <div className="flex gap-2">
              <select
                value={memoryCategory}
                onChange={(e) => setMemoryCategory(e.target.value as MemoryCategory)}
                className="input-field w-[116px] shrink-0"
              >
                <option value="fact">事实</option>
                <option value="preference">偏好</option>
                <option value="profile">个人</option>
                <option value="project">项目</option>
              </select>
              <button
                onClick={handleCreateMemory}
                disabled={memoryState === 'saving' || !memoryContent.trim()}
                className="min-h-[44px] rounded-lg bg-blue-600 px-3 text-sm font-medium text-white active:bg-blue-700 disabled:opacity-50"
              >
                添加
              </button>
            </div>
            <textarea
              value={memoryContent}
              onChange={(e) => setMemoryContent(e.target.value)}
              placeholder="例如：我正在开发 MyOpenWeb，目标是学习 AI Agent。"
              rows={3}
              className="input-field resize-none"
            />
            {memoryState === 'loading' && <p className="text-xs text-neutral-500">加载记忆中...</p>}
            {memoryState === 'error' && <p className="text-xs text-red-400">Memory 操作失败，请确认后端已启动</p>}
            {memories.length > 0 ? (
              <div className="space-y-2">
                {memories.map((memory) => (
                  <div key={memory.id} className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-2">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="text-[11px] uppercase tracking-wide text-neutral-500">{memory.category}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleToggleMemory(memory)}
                          className={`rounded px-2 py-1 text-[11px] ${memory.enabled ? 'bg-emerald-900/40 text-emerald-300' : 'bg-neutral-800 text-neutral-500'}`}
                        >
                          {memory.enabled ? '启用' : '停用'}
                        </button>
                        <button
                          onClick={() => handleDeleteMemory(memory)}
                          className="rounded px-2 py-1 text-[11px] text-red-300 active:bg-red-950/50"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                    <p className="text-xs leading-relaxed text-neutral-300">{memory.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              memoryState !== 'loading' && (
                <p className="text-xs text-neutral-500">还没有长期记忆。添加后，Agent 会在请求时自动参考。</p>
              )
            )}
          </div>

          <Field label="系统提示词">
            <textarea
              value={settings.systemPrompt}
              onChange={(e) => updateSettings({ systemPrompt: e.target.value })}
              rows={3}
              className="input-field resize-none"
            />
          </Field>

          <Field label={`温度：${settings.temperature.toFixed(1)}`}>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={settings.temperature}
              onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </Field>

          <Field label={`最大 Tokens：${settings.maxTokens}`}>
            <input
              type="range"
              min="256"
              max="16384"
              step="256"
              value={settings.maxTokens}
              onChange={(e) => updateSettings({ maxTokens: parseInt(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </Field>

          <Toggle
            label="流式输出"
            checked={settings.streamOutput}
            onChange={(v) => updateSettings({ streamOutput: v })}
          />

          <div className="border-t border-neutral-700 pt-4">
            <span className="text-xs text-neutral-400 font-medium uppercase tracking-wider">语音</span>
          </div>

          <Toggle
            label="TTS 自动朗读"
            checked={settings.ttsEnabled}
            onChange={(v) => updateSettings({ ttsEnabled: v })}
          />

          {settings.ttsEnabled && (
            <>
              <Field label="朗读语言">
                <select
                  value={settings.ttsLang}
                  onChange={(e) => updateSettings({ ttsLang: e.target.value })}
                  className="input-field"
                >
                  <option value="zh-CN">中文</option>
                  <option value="en-US">English</option>
                  <option value="ja-JP">日本語</option>
                </select>
              </Field>
              <Field label={`朗读速度：${settings.ttsRate.toFixed(1)}x`}>
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={settings.ttsRate}
                  onChange={(e) => updateSettings({ ttsRate: parseFloat(e.target.value) })}
                  className="w-full accent-blue-500"
                />
              </Field>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-neutral-400 mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      className="flex items-center justify-between min-h-[44px] py-1"
      onClick={() => onChange(!checked)}
    >
      <span className="text-sm text-neutral-200">{label}</span>
      <div
        className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${checked ? 'bg-blue-600' : 'bg-neutral-600'}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : ''}`}
        />
      </div>
    </div>
  );
}
