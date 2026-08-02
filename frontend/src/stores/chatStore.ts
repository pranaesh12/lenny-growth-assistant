import { create } from "zustand";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

interface ChatStore {
  messages: ChatMessage[];
  isTyping: boolean;

  addMessage: (message: ChatMessage) => void;

  clearMessages: () => void;

  setTyping: (typing: boolean) => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],

  isTyping: false,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  clearMessages: () =>
    set({
      messages: [],
    }),

  setTyping: (typing) =>
    set({
      isTyping: typing,
    }),
}));