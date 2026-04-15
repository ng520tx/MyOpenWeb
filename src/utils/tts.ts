const SENTENCE_RE = /(?<=[。！？.!?\n])/;

let currentUtterances: SpeechSynthesisUtterance[] = [];
let enabled = false;
let lang = 'zh-CN';
let rate = 1.0;

export function configureTTS(opts: { enabled: boolean; lang: string; rate: number }) {
  enabled = opts.enabled;
  lang = opts.lang;
  rate = opts.rate;
}

export function stopTTS() {
  speechSynthesis.cancel();
  currentUtterances = [];
}

export function speakText(text: string) {
  if (!enabled || !text.trim()) return;
  if (!('speechSynthesis' in window)) return;

  const sentences = text.split(SENTENCE_RE).filter((s) => s.trim());
  currentUtterances = [];

  for (const sentence of sentences) {
    const u = new SpeechSynthesisUtterance(sentence);
    u.lang = lang;
    u.rate = rate;
    currentUtterances.push(u);
    speechSynthesis.speak(u);
  }
}

let accumulatedText = '';
let lastSpokenIndex = 0;

export function resetStreamTTS() {
  accumulatedText = '';
  lastSpokenIndex = 0;
  stopTTS();
}

export function feedStreamTTS(deltaText: string) {
  if (!enabled || !('speechSynthesis' in window)) return;

  accumulatedText += deltaText;

  const unspoken = accumulatedText.slice(lastSpokenIndex);
  const parts = unspoken.split(SENTENCE_RE);

  if (parts.length > 1) {
    for (let i = 0; i < parts.length - 1; i++) {
      const sentence = parts[i].trim();
      if (!sentence) continue;
      const u = new SpeechSynthesisUtterance(sentence);
      u.lang = lang;
      u.rate = rate;
      speechSynthesis.speak(u);
    }
    const spokenLength = parts.slice(0, -1).join('').length;
    lastSpokenIndex += spokenLength;
  }
}

export function flushStreamTTS() {
  if (!enabled || !('speechSynthesis' in window)) return;

  const remaining = accumulatedText.slice(lastSpokenIndex).trim();
  if (remaining) {
    const u = new SpeechSynthesisUtterance(remaining);
    u.lang = lang;
    u.rate = rate;
    speechSynthesis.speak(u);
  }
  accumulatedText = '';
  lastSpokenIndex = 0;
}
