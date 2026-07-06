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
import { generateTitle, generateFollowUps } from '@/apis/tasks';

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
      const isFirstTurn = (store.getActiveConversation()?.messages.length ?? 0) === 0;

      const userId = store.addMessage('user', text.trim(), files);
      store.clearPendingFiles();

      const aiId = store.addMessage('assistant', '');
      store.setGenerating(true);
      resetStreamTTS();
      thinkingRef.current = false;
      const startedAt = Date.now();

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
            if (update.agentEvent) {
              useAppStore.getState().appendAgentEvent(aiId, update.agentEvent);
            }
            if (update.agent) {
              useAppStore.getState().updateMessage(aiId, { agent: update.agent });
            }
            if (update.sources) {
              useAppStore.getState().updateMessage(aiId, { sources: update.sources });
            }
            if (update.usage) {
              useAppStore.getState().updateMessage(aiId, { usage: update.usage });
            }
            if (update.done) {
              if (thinkBuf && !thinkingRef.current) {
                useAppStore.getState().appendContent(aiId, thinkBuf);
              }
              // 时间线只服务于生成过程，落库前清掉（完整步骤在 Agent 运行日志里）
              useAppStore.getState().updateMessage(aiId, {
                done: true,
                agentEvents: undefined,
                durationMs: Date.now() - startedAt,
              });
              break;
            }
          }
          flushStreamTTS();
        } else {
          const data = await res.json();
          const content = data.choices?.[0]?.message?.content ?? '';
          useAppStore.getState().updateMessage(aiId, {
            content,
            done: true,
            agent: data.agent,
            sources: data.sources,
            usage: data.usage,
            durationMs: Date.now() - startedAt,
          });
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

        // 异步增强（不阻塞主链路、失败静默）：LLM 标题替换截断标题 + 追问建议 chip。
        const finished = useAppStore.getState().getActiveConversation();
        const aiMessage = finished?.messages.find((m) => m.id === aiId);
        if (finished && aiMessage?.done && !aiMessage.error && aiMessage.content) {
          if (isFirstTurn) {
            const convId = finished.id;
            void generateTitle(settings.model, text.trim(), aiMessage.content).then((title) => {
              if (!title) return;
              useAppStore.getState().renameConversation(convId, title);
              const renamed = useAppStore.getState().conversations.find((c) => c.id === convId);
              if (renamed) void saveChat(renamed).catch(() => {});
            });
          }
          void generateFollowUps(settings.model, finished.messages.slice(-4)).then((followUps) => {
            if (followUps.length === 0) return;
            useAppStore.getState().updateMessage(aiId, { followUps });
          });
        }
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
      <MessageList messages={messages} generating={generating} onFollowUpClick={handleSend} />
      <MessageInput
        onSend={handleSend}
        onStop={handleStop}
        generating={generating}
      />
    </div>
  );
}
