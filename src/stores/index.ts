import { create } from 'zustand';
import type { ChatMessage, AppSettings } from '@/types';
import { DEFAULT_SETTINGS } from '@/constants';

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

interface ChatState {
  messages: ChatMessage[];
  generating: boolean;
  settings: AppSettings;

  addMessage: (role: ChatMessage['role'], content: string) => string;
  updateMessage: (id: string, partial: Partial<ChatMessage>) => void;
  appendContent: (id: string, text: string) => void;
  clearMessages: () => void;
  setGenerating: (v: boolean) => void;
  updateSettings: (partial: Partial<AppSettings>) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  generating: false,
  settings: loadSettings(),

  addMessage: (role, content) => {
    const id = generateId();
    const msg: ChatMessage = {
      id,
      role,
      content,
      timestamp: Date.now(),
      done: role === 'user',
    };
    set((s) => ({ messages: [...s.messages, msg] }));
    return id;
  },

  updateMessage: (id, partial) => {
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...partial } : m)),
    }));
  },

  appendContent: (id, text) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + text } : m
      ),
    }));
  },

  clearMessages: () => set({ messages: [] }),

  setGenerating: (v) => set({ generating: v }),

  updateSettings: (partial) => {
    set((s) => {
      const next = { ...s.settings, ...partial };
      saveSettings(next);
      return { settings: next };
    });
  },
}));

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem('app-settings');
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULT_SETTINGS };
}

function saveSettings(s: AppSettings) {
  try {
    localStorage.setItem('app-settings', JSON.stringify(s));
  } catch { /* ignore */ }
}
