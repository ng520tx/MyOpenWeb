import { create } from 'zustand';
import type { ChatMessage, Conversation, AppSettings, FileAttachment } from '@/types';
import { DEFAULT_SETTINGS, STORAGE_KEYS } from '@/constants';

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

// ─── persistence helpers ───────────────────────────────────

function loadJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw) as T;
  } catch { /* ignore */ }
  return fallback;
}

function saveJSON(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch { /* ignore */ }
}

function loadSettings(): AppSettings {
  return { ...DEFAULT_SETTINGS, ...loadJSON<Partial<AppSettings>>(STORAGE_KEYS.SETTINGS, {}) };
}

function loadConversations(): Conversation[] {
  return loadJSON<Conversation[]>(STORAGE_KEYS.CONVERSATIONS, []);
}

function loadActiveId(): string | null {
  return localStorage.getItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID) || null;
}

function stripFileContents(conversations: Conversation[]): Conversation[] {
  return conversations.map((c) => ({
    ...c,
    messages: c.messages.map((m) => {
      if (!m.files?.length) return m;
      return {
        ...m,
        files: m.files.map((f) => ({ ...f, content: '' })),
      };
    }),
  }));
}

// ─── store ─────────────────────────────────────────────────

interface AppState {
  conversations: Conversation[];
  activeConversationId: string | null;
  generating: boolean;
  settings: AppSettings;
  pendingFiles: FileAttachment[];
  sidebarOpen: boolean;
  settingsOpen: boolean;

  // derived selectors
  getActiveConversation: () => Conversation | undefined;
  getMessages: () => ChatMessage[];

  // conversation
  createConversation: () => string;
  switchConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;

  // messages
  addMessage: (role: ChatMessage['role'], content: string, files?: FileAttachment[]) => string;
  updateMessage: (id: string, partial: Partial<ChatMessage>) => void;
  appendContent: (id: string, text: string) => void;
  clearMessages: () => void;
  persistNow: () => void;

  // ui
  setGenerating: (v: boolean) => void;
  setSidebarOpen: (v: boolean) => void;
  setSettingsOpen: (v: boolean) => void;

  // settings
  updateSettings: (partial: Partial<AppSettings>) => void;

  // files
  addPendingFile: (file: FileAttachment) => void;
  removePendingFile: (name: string) => void;
  clearPendingFiles: () => void;
}

export const useAppStore = create<AppState>((set, get) => {
  const savedConversations = loadConversations();
  const savedActiveId = loadActiveId();

  function persist() {
    const { conversations, activeConversationId } = get();
    saveJSON(STORAGE_KEYS.CONVERSATIONS, stripFileContents(conversations));
    if (activeConversationId) {
      localStorage.setItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID, activeConversationId);
    } else {
      localStorage.removeItem(STORAGE_KEYS.ACTIVE_CONVERSATION_ID);
    }
  }

  function updateConversation(id: string, updater: (c: Conversation) => Conversation, shouldPersist = true) {
    set((s) => ({
      conversations: s.conversations.map((c) => (c.id === id ? updater(c) : c)),
    }));
    if (shouldPersist) persist();
  }

  return {
    conversations: savedConversations,
    activeConversationId: savedActiveId && savedConversations.some((c) => c.id === savedActiveId) ? savedActiveId : null,
    generating: false,
    settings: loadSettings(),
    pendingFiles: [],
    sidebarOpen: false,
    settingsOpen: false,

    getActiveConversation: () => {
      const s = get();
      return s.conversations.find((c) => c.id === s.activeConversationId);
    },

    getMessages: () => {
      const s = get();
      const conv = s.conversations.find((c) => c.id === s.activeConversationId);
      return conv ? conv.messages : [];
    },

    createConversation: () => {
      const id = generateId();
      const conv: Conversation = {
        id,
        title: '新对话',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      set((s) => ({
        conversations: [conv, ...s.conversations],
        activeConversationId: id,
        pendingFiles: [],
      }));
      persist();
      return id;
    },

    switchConversation: (id) => {
      set({ activeConversationId: id, pendingFiles: [] });
      persist();
    },

    deleteConversation: (id) => {
      set((s) => {
        const next = s.conversations.filter((c) => c.id !== id);
        const activeId = s.activeConversationId === id
          ? (next[0]?.id ?? null)
          : s.activeConversationId;
        return { conversations: next, activeConversationId: activeId };
      });
      persist();
    },

    renameConversation: (id, title) => {
      updateConversation(id, (c) => ({ ...c, title, updatedAt: Date.now() }));
    },

    addMessage: (role, content, files) => {
      let convId = get().activeConversationId;
      if (!convId) {
        convId = get().createConversation();
      }
      const msgId = generateId();
      const msg: ChatMessage = {
        id: msgId,
        role,
        content,
        timestamp: Date.now(),
        done: role === 'user',
        files,
      };
      updateConversation(convId, (c) => {
        const isFirstUserMsg = role === 'user' && c.messages.length === 0;
        return {
          ...c,
          messages: [...c.messages, msg],
          title: isFirstUserMsg ? content.slice(0, 30) || '新对话' : c.title,
          updatedAt: Date.now(),
        };
      }, role === 'user');
      return msgId;
    },

    updateMessage: (id, partial) => {
      const convId = get().activeConversationId;
      if (!convId) return;
      updateConversation(convId, (c) => ({
        ...c,
        messages: c.messages.map((m) => (m.id === id ? { ...m, ...partial } : m)),
        updatedAt: Date.now(),
      }));
    },

    appendContent: (id, text) => {
      const convId = get().activeConversationId;
      if (!convId) return;
      set((s) => ({
        conversations: s.conversations.map((c) =>
          c.id === convId
            ? {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === id ? { ...m, content: m.content + text } : m
                ),
              }
            : c
        ),
      }));
    },

    clearMessages: () => {
      get().createConversation();
    },

    persistNow: () => persist(),

    setGenerating: (v) => set({ generating: v }),
    setSidebarOpen: (v) => set({ sidebarOpen: v }),
    setSettingsOpen: (v) => set({ settingsOpen: v }),

    updateSettings: (partial) => {
      set((s) => {
        const next = { ...s.settings, ...partial };
        saveJSON(STORAGE_KEYS.SETTINGS, next);
        return { settings: next };
      });
    },

    addPendingFile: (file) => {
      set((s) => ({ pendingFiles: [...s.pendingFiles, file] }));
    },
    removePendingFile: (name) => {
      set((s) => ({ pendingFiles: s.pendingFiles.filter((f) => f.name !== name) }));
    },
    clearPendingFiles: () => set({ pendingFiles: [] }),
  };
});

/** @deprecated use useAppStore instead */
export const useChatStore = useAppStore;
