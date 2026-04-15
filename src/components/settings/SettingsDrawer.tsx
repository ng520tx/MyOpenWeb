import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/stores';
import { fetchModels, type ModelInfo } from '@/apis/models';

export default function SettingsDrawer() {
  const { settings, settingsOpen, setSettingsOpen, updateSettings } = useAppStore();
  const backdropRef = useRef<HTMLDivElement>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

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
    setLoadingModels(true);
    fetchModels(settings.apiBaseUrl, settings.apiKey || undefined).then((list) => {
      if (!cancelled) {
        setModels(list);
        setLoadingModels(false);
      }
    });
    return () => { cancelled = true; };
  }, [settingsOpen, settings.apiBaseUrl, settings.apiKey]);

  const handleRefreshModels = useCallback(() => {
    setLoadingModels(true);
    fetchModels(settings.apiBaseUrl, settings.apiKey || undefined).then((list) => {
      setModels(list);
      setLoadingModels(false);
    });
  }, [settings.apiBaseUrl, settings.apiKey]);

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
            className="w-8 h-8 flex items-center justify-center rounded-lg text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18" /><path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
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
                  placeholder="qwen2.5:3b"
                  className="input-field flex-1"
                />
              )}
              <button
                onClick={handleRefreshModels}
                disabled={loadingModels}
                className="flex items-center justify-center w-9 h-9 rounded-lg bg-neutral-700 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-600 shrink-0 transition-colors disabled:opacity-40"
                title="刷新模型列表"
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
    <div className="flex items-center justify-between">
      <span className="text-sm text-neutral-200">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-[22px] rounded-full transition-colors ${checked ? 'bg-blue-600' : 'bg-neutral-600'}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-[18px] h-[18px] rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-[18px]' : ''}`}
        />
      </button>
    </div>
  );
}
