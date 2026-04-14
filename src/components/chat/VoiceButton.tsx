import { useState, useRef, useCallback } from 'react';

interface VoiceButtonProps {
  onResult: (transcript: string) => void;
}

export default function VoiceButton({ onResult }: VoiceButtonProps) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const toggle = useCallback(() => {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      // TODO: 通过 moaBridge 调用原生 ASR
      console.warn('SpeechRecognition not supported');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      const transcript = e.results[0]?.[0]?.transcript ?? '';
      if (transcript) onResult(transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, [listening, onResult]);

  return (
    <button
      onClick={toggle}
      className={`flex items-center justify-center w-9 h-9 rounded-xl shrink-0 transition-colors ${
        listening
          ? 'bg-red-600 text-white animate-pulse'
          : 'bg-neutral-700 text-neutral-400 hover:text-neutral-200 active:bg-neutral-600'
      }`}
      title={listening ? '停止录音' : '语音输入'}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" x2="12" y1="19" y2="22" />
      </svg>
    </button>
  );
}
