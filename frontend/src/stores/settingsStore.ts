import { create } from "zustand";

interface Settings {
  provider: string;
  model: string;
  temperature: number;
  topK: number;
}

interface SettingsStore {
  settings: Settings;

  updateSettings: (settings: Settings) => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  settings: {
    provider: "openai",
    model: "gpt-5",
    temperature: 0.7,
    topK: 5,
  },

  updateSettings: (settings) =>
    set({
      settings,
    }),
}));