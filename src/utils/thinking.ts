const THINK_OPEN = '<think>';
const THINK_CLOSE = '</think>';

/**
 * 从流式文本中过滤 <think>...</think> 块。
 * 返回可以安全输出的文本，以及需要保留到下一次调用的缓冲。
 */
export function filterThinking(
  buffer: string,
  inThinking: boolean
): { output: string; remaining: string; inThinking: boolean } {
  let output = '';
  let text = buffer;

  while (text.length > 0) {
    if (inThinking) {
      const closeIdx = text.indexOf(THINK_CLOSE);
      if (closeIdx >= 0) {
        inThinking = false;
        text = text.substring(closeIdx + THINK_CLOSE.length);
      } else {
        break;
      }
    } else {
      const openIdx = text.indexOf(THINK_OPEN);
      if (openIdx >= 0) {
        output += text.substring(0, openIdx);
        inThinking = true;
        text = text.substring(openIdx + THINK_OPEN.length);
      } else {
        output += text;
        text = '';
      }
    }
  }

  return { output, remaining: text, inThinking };
}
