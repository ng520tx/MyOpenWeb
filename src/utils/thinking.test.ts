import { describe, expect, it } from 'vitest';
import { filterThinking } from './thinking';

describe('filterThinking', () => {
  it('passes through plain text untouched', () => {
    const result = filterThinking('你好，世界', false);
    expect(result).toEqual({ output: '你好，世界', remaining: '', inThinking: false });
  });

  it('strips a complete <think> block', () => {
    const result = filterThinking('<think>推理过程</think>答案', false);
    expect(result.output).toBe('答案');
    expect(result.inThinking).toBe(false);
  });

  it('keeps swallowing text while a think block is open across chunks', () => {
    const first = filterThinking('前文<think>开始推理', false);
    expect(first.output).toBe('前文');
    expect(first.inThinking).toBe(true);

    const second = filterThinking(first.remaining + '还在推理', first.inThinking);
    expect(second.output).toBe('');
    expect(second.inThinking).toBe(true);

    const third = filterThinking(second.remaining + '</think>结论', second.inThinking);
    expect(third.output).toBe('结论');
    expect(third.inThinking).toBe(false);
  });

  it('handles multiple think blocks in one buffer', () => {
    const result = filterThinking('A<think>x</think>B<think>y</think>C', false);
    expect(result.output).toBe('ABC');
    expect(result.inThinking).toBe(false);
  });

  it('resumes from inThinking=true and drops content up to the close tag', () => {
    const result = filterThinking('隐藏内容</think>可见内容', true);
    expect(result.output).toBe('可见内容');
    expect(result.inThinking).toBe(false);
  });
});
