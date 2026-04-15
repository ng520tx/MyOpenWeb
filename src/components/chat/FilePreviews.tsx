import { useAppStore } from '@/stores';

export default function FilePreviews() {
  const { pendingFiles, removePendingFile } = useAppStore();

  if (pendingFiles.length === 0) return null;

  return (
    <div className="flex gap-2 px-3 py-1.5 overflow-x-auto shrink-0 border-t border-neutral-700 bg-neutral-800">
      {pendingFiles.map((f) => (
        <div
          key={f.name}
          className="flex items-center gap-1.5 pl-2.5 pr-1 py-1 rounded-lg bg-neutral-700 text-xs text-neutral-300 shrink-0 max-w-[180px]"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" strokeLinejoin="round" />
            <polyline points="14 2 14 8 20 8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="truncate">{f.name}</span>
          <button
            onClick={() => removePendingFile(f.name)}
            className="w-5 h-5 flex items-center justify-center rounded text-neutral-500 hover:text-red-400 shrink-0"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18" /><path d="m6 6 12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
