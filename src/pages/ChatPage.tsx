import { useRef, useCallback } from 'react';
import ChatNavbar from '@/components/chat/ChatNavbar';
import MessageList from '@/components/chat/MessageList';
import MessageInput from '@/components/chat/MessageInput';
import { useChatStore } from '@/stores';
import { chatCompletion } from '@/apis/chat';
import { createOpenAITextStream } from '@/apis/streaming';

export default function ChatPage() {
  const {
    messages,
    generating,
    settings,
    addMessage,
    appendContent,
    updateMessage,
    setGenerating,
    clearMessages,
  } = useChatStore();

  const abortRef = useRef<AbortController | null>(null);

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || generating) return;

      addMessage('user', text.trim());
      const aiId = addMessage('assistant', '');
      setGenerating(true);

      try {
        const [res, controller] = await chatCompletion({
          baseUrl: settings.apiBaseUrl,
          model: settings.model,
          messages: [
            ...useChatStore.getState().messages.slice(0, -1),
          ],
          systemPrompt: settings.systemPrompt,
          temperature: settings.temperature,
          maxTokens: settings.maxTokens,
          stream: settings.streamOutput,
        });

        abortRef.current = controller;

        if (!res.body) {
          updateMessage(aiId, { content: 'No response body', done: true, error: 'No response body' });
          setGenerating(false);
          return;
        }

        if (settings.streamOutput) {
          const stream = await createOpenAITextStream(res.body);
          for await (const update of stream) {
            if (update.error) {
              updateMessage(aiId, { error: update.error, done: true });
              break;
            }
            if (update.value) {
              appendContent(aiId, update.value);
            }
            if (update.done) {
              updateMessage(aiId, { done: true });
              break;
            }
          }
        } else {
          const data = await res.json();
          const content = data.choices?.[0]?.message?.content ?? '';
          updateMessage(aiId, { content, done: true });
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          updateMessage(aiId, { done: true });
        } else {
          const errMsg = err instanceof Error ? err.message : String(err);
          updateMessage(aiId, { content: `Error: ${errMsg}`, done: true, error: errMsg });
        }
      } finally {
        setGenerating(false);
        abortRef.current = null;
      }
    },
    [generating, settings, addMessage, appendContent, updateMessage, setGenerating]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setGenerating(false);
  }, [setGenerating]);

  return (
    <div className="flex flex-col h-full">
      <ChatNavbar
        model={settings.model}
        onClear={clearMessages}
      />
      <MessageList messages={messages} generating={generating} />
      <MessageInput
        onSend={handleSend}
        onStop={handleStop}
        generating={generating}
      />
    </div>
  );
}
