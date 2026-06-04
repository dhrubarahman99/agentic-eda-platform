import { create } from 'zustand';
import type { ChatMessage } from '../api/types';

interface ChatState {
  /** Messages keyed by sessionId — each session has its own history. */
  messagesBySession: Record<string, ChatMessage[]>;
  isThinking: boolean;

  getMessages: (sessionId: string | null) => ChatMessage[];
  addMessage: (sessionId: string, message: ChatMessage) => void;
  setThinking: (val: boolean) => void;
  clearSession: (sessionId: string) => void;
  clearAllSessions: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messagesBySession: {},
  isThinking: false,

  getMessages: (sessionId) => {
    if (!sessionId) return []
    return get().messagesBySession[sessionId] ?? []
  },

  addMessage: (sessionId, message) =>
    set((state) => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: [...(state.messagesBySession[sessionId] ?? []), message],
      },
    })),

  setThinking: (val) => set({ isThinking: val }),

  clearSession: (sessionId) =>
    set((state) => {
      const next = { ...state.messagesBySession }
      delete next[sessionId]
      return { messagesBySession: next }
    }),

  clearAllSessions: () => set({ messagesBySession: {} }),
}));
