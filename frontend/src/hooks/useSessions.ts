import { useSessionStore } from "../stores/sessionStore";

export function useSessions() {
  return useSessionStore();
}