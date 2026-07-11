import { useEffect } from 'react';
import ChatPage from '@/pages/ChatPage';
import Sidebar from '@/components/sidebar/Sidebar';
import SettingsDrawer from '@/components/settings/SettingsDrawer';
import KnowledgeDrawer from '@/components/knowledge/KnowledgeDrawer';
import { useAppStore } from '@/stores';
import { fetchProviderConfig } from '@/apis/config';
import { fetchChats, saveChat } from '@/apis/chats';
import { mergeConversations } from '@/utils/conversations';

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
