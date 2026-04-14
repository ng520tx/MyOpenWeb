import { useCallback } from 'react';

export default function FileButton() {
  const handleClick = useCallback(() => {
    // TODO: 第二阶段实现文件选择
    // 1. Web: 打开 <input type="file">
    // 2. Android: 通过 moaBridge 调用原生文件选择
    console.log('File button clicked - to be implemented');
  }, []);

  return (
    <button
      onClick={handleClick}
      className="flex items-center justify-center w-9 h-9 rounded-xl bg-neutral-700 text-neutral-400 hover:text-neutral-200 active:bg-neutral-600 shrink-0 transition-colors"
      title="添加文件"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
      </svg>
    </button>
  );
}
