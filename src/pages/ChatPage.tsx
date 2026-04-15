import { useRef, useCallback, useEffect } from 'react';
import ChatNavbar from '@/components/chat/ChatNavbar';
import MessageList from '@/components/chat/MessageList';
import MessageInput from '@/components/chat/MessageInput';
import { useAppStore } from '@/stores';
import { chatCompletion } from '@/apis/chat';
import { createOpenAITextStream } from '@/apis/streaming';
import { configureTTS, resetStreamTTS, feedStreamTTS, flushStreamTTS, stopTTS } from '@/utils/tts';

export default function ChatPage() {
  const generating = useAppStore((s) => s.generating);
  const settings = useAppStore((s) => s.settings);
  const pendingFiles = useAppStore((s) => s.pendingFiles);
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const conversations = useAppStore((s) => s.conversations);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConv?.messages ?? [];

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    configureTTS({
      enabled: settings.ttsEnabled,
      lang: settings.ttsLang,
      rate: settings.ttsRate,
    });
  }, [settings.ttsEnabled, settings.ttsLang, settings.ttsRate]);

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || useAppStore.getState().generating) return;

      const store = useAppStore.getState();
      const files = store.pendingFiles.length > 0 ? [...store.pendingFiles] : undefined;

      store.addMessage('user', text.trim(), files);
      store.clearPendingFiles();

      const aiId = store.addMessage('assistant', '');
      store.setGenerating(true);
      resetStreamTTS();

      try {
        const currentMessages = useAppStore.getState().getMessages();
        const [res, controller] = await chatCompletion({
          baseUrl: settings.apiBaseUrl,
          apiKey: settings.apiKey || undefined,
          model: settings.model,
          messages: currentMessages.slice(0, -1),
          systemPrompt: settings.systemPrompt,
          temperature: settings.temperature,
          maxTokens: settings.maxTokens,
          stream: settings.streamOutput,
          files,
        });

        abortRef.current = controller;

        if (!res.body) {
          useAppStore.getState().updateMessage(aiId, { content: 'No response body', done: true, error: 'No response body' });
          useAppStore.getState().setGenerating(false);
          return;
        }

        if (settings.streamOutput) {
          const stream = await createOpenAITextStream(res.body);
          for await (const update of stream) {
            if (update.error) {
              useAppStore.getState().updateMessage(aiId, { error: update.error, done: true });
              break;
            }
            if (update.value) {
              useAppStore.getState().appendContent(aiId, update.value);
              feedStreamTTS(update.value);
            }
            if (update.done) {
              useAppStore.getState().updateMessage(aiId, { done: true });
              break;
            }
          }
          flushStreamTTS();
        } else {
          const data = await res.json();
          const content = data.choices?.[0]?.message?.content ?? '';
          useAppStore.getState().updateMessage(aiId, { content, done: true });
          flushStreamTTS();
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          useAppStore.getState().updateMessage(aiId, { done: true });
        } else {
          const errMsg = err instanceof Error ? err.message : String(err);
          useAppStore.getState().updateMessage(aiId, { content: `Error: ${errMsg}`, done: true, error: errMsg });
        }
      } finally {
        useAppStore.getState().setGenerating(false);
        useAppStore.getState().persistNow();
        abortRef.current = null;
      }
    },
    [settings]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    useAppStore.getState().setGenerating(false);
    useAppStore.getState().persistNow();
    stopTTS();
  }, []);

  return (
    <div className="flex flex-col h-full">
      <ChatNavbar />
      <MessageList messages={messages} generating={generating} />
      <MessageInput
        onSend={handleSend}
        onStop={handleStop}
        generating={generating}
      />
    </div>
  );
}
