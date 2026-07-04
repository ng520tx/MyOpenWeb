import { useEffect } from 'react';
import ChatPage from '@/pages/ChatPage';
import Sidebar from '@/components/sidebar/Sidebar';
import SettingsDrawer from '@/components/settings/SettingsDrawer';
import KnowledgeDrawer from '@/components/knowledge/KnowledgeDrawer';
import { useAppStore } from '@/stores';
import { fetchProviderConfig } from '@/apis/config';
import { fetchChats, saveChat } from '@/apis/chats';
import type { Conversation } from '@/types';

function mergeConversations(localConversations: Conversation[], remoteConversations: Conversation[]) {
  const remoteById = new Map(remoteConversations.map((conversation) => [conversation.id, conversation]));
  const merged: Conversation[] = [];
  const uploads: Conversation[] = [];

  for (const localConversation of localConversations) {
    const remoteConversation = remoteById.get(localConversation.id);
    if (!remoteConversation || localConversation.updatedAt >= remoteConversation.updatedAt) {
      merged.push(localConversation);
      uploads.push(localConversation);
    } else {
      merged.push(remoteConversation);
    }
    remoteById.delete(localConversation.id);
  }

  merged.push(...remoteById.values());
  merged.sort((a, b) => b.updatedAt - a.updatedAt);
  return { merged, uploads };
}

export default function App() {
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const store = useAppStore.getState();

      const providerConfig = await fetchProviderConfig();
      if (providerConfig && !cancelled) {
        store.updateSettings({
          providerType: providerConfig.providerType,
          apiBaseUrl: providerConfig.apiBaseUrl,
          apiKey: providerConfig.apiKey,
          embeddingModel: providerConfig.embeddingModel,
          ocrEnabled: providerConfig.ocrEnabled,
          ocrBaseUrl: providerConfig.ocrBaseUrl,
          ocrMode: providerConfig.ocrMode,
        });
      }

      const remoteConversations = await fetchChats();
      if (cancelled) return;

      const { merged, uploads } = mergeConversations(
        useAppStore.getState().conversations,
        remoteConversations
      );

      store.hydrateConversations(merged);
      await Promise.allSettled(uploads.map((conversation) => saveChat(conversation)));
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="h-full bg-neutral-900 text-neutral-100">
      <ChatPage />
      <Sidebar />
      <SettingsDrawer />
      <KnowledgeDrawer />
    </div>
  );
}
