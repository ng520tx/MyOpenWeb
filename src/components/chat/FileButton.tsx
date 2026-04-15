import { useRef, useCallback } from 'react';
import { useAppStore } from '@/stores';
import { MAX_FILE_SIZE, ACCEPTED_FILE_TYPES } from '@/constants';

export default function FileButton() {
  const inputRef = useRef<HTMLInputElement>(null);
  const addPendingFile = useAppStore((s) => s.addPendingFile);

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files) return;

      for (const file of Array.from(files)) {
        if (file.size > MAX_FILE_SIZE) {
          alert(`文件 "${file.name}" 超过 5MB 限制`);
          continue;
        }
        try {
          const content = await file.text();
          addPendingFile({
            name: file.name,
            size: file.size,
            type: file.type || 'text/plain',
            content,
          });
        } catch {
          alert(`无法读取文件 "${file.name}"`);
        }
      }
      e.target.value = '';
    },
    [addPendingFile]
  );

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_FILE_TYPES}
        onChange={handleChange}
        className="hidden"
      />
      <button
        onClick={handleClick}
        className="flex items-center justify-center w-9 h-9 rounded-xl bg-neutral-700 text-neutral-400 hover:text-neutral-200 active:bg-neutral-600 shrink-0 transition-colors"
        title="添加文件"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
      </button>
    </>
  );
}
