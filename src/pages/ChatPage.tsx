import { useRef, useCallback, useEffect } from 'react';
import ChatNavbar from '@/components/chat/ChatNavbar';
import MessageList from '@/components/chat/MessageList';
import MessageInput from '@/components/chat/MessageInput';
import { useAppStore } from '@/stores';
import { chatCompletion } from '@/apis/chat';
import { createOpenAITextStream } from '@/apis/streaming';
import { configureTTS, resetStreamTTS, feedStreamTTS, flushStreamTTS, stopTTS } from '@/utils/tts';
import { filterThinking } from '@/utils/thinking';
import { syncProviderConfig } from '@/apis/config';
import { saveChat } from '@/apis/chats';

export default function ChatPage() {
  const generating = useAppStore((s) => s.generating);
  const settings = useAppStore((s) => s.settings);
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const conversations = useAppStore((s) => s.conversations);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConv?.messages ?? [];

  const abortRef = useRef<AbortController | null>(null);
  const thinkingRef = useRef(false);

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

      const userId = store.addMessage('user', text.trim(), files);
      store.clearPendingFiles();

      const aiId = store.addMessage('assistant', '');
      store.setGenerating(true);
      resetStreamTTS();
      thinkingRef.current = false;

      try {
        const currentMessages = useAppStore.getState().getMessages();
        await syncProviderConfig(settings);
        const [res, controller] = await chatCompletion({
          model: settings.model,
          messages: currentMessages.slice(0, -1),
          systemPrompt: settings.systemPrompt,
          temperature: settings.temperature,
          maxTokens: settings.maxTokens,
          stream: settings.streamOutput,
          files,
          agentEnabled: settings.agentEnabled,
          knowledgeId: useAppStore.getState().activeKnowledgeId,
          metadata: {
            conversation_id: useAppStore.getState().activeConversationId,
            user_message_id: userId,
            assistant_message_id: aiId,
          },
        });

        abortRef.current = controller;

        if (!res.body) {
          useAppStore.getState().updateMessage(aiId, { content: 'No response body', done: true, error: 'No response body' });
          useAppStore.getState().setGenerating(false);
          return;
        }

        if (settings.streamOutput) {
          const stream = await createOpenAITextStream(res.body);
          let thinkBuf = '';
          for await (const update of stream) {
            if (update.error) {
              useAppStore.getState().updateMessage(aiId, { error: update.error, done: true });
              break;
            }
            if (update.value) {
              thinkBuf += update.value;
              const result = filterThinking(thinkBuf, thinkingRef.current);
              thinkingRef.current = result.inThinking;
              thinkBuf = result.remaining;
              if (result.output) {
                useAppStore.getState().appendContent(aiId, result.output);
                feedStreamTTS(result.output);
              }
            }
            if (update.agent) {
              useAppStore.getState().updateMessage(aiId, { agent: update.agent });
            }
            if (update.sources) {
              useAppStore.getState().updateMessage(aiId, { sources: update.sources });
            }
            if (update.done) {
              if (thinkBuf && !thinkingRef.current) {
                useAppStore.getState().appendContent(aiId, thinkBuf);
              }
              useAppStore.getState().updateMessage(aiId, { done: true });
              break;
            }
          }
          flushStreamTTS();
        } else {
          const data = await res.json();
          const content = data.choices?.[0]?.message?.content ?? '';
          useAppStore.getState().updateMessage(aiId, { content, done: true, agent: data.agent, sources: data.sources });
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
        const activeConversation = useAppStore.getState().getActiveConversation();
        if (activeConversation) {
          try {
            await saveChat(activeConversation);
          } catch {
            // Keep the local cache authoritative when the backend is temporarily unavailable.
          }
        }
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
