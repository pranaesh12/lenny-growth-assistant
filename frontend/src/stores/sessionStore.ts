import { create } from "zustand";
import type { Session } from "../types/session";

interface SessionStore {
    sessions: Session[];

    activeSessionId: string | null;

    setSessions: (sessions: Session[]) => void;

    setActiveSession: (id: string) => void;
}

export const useSessionStore =
    create<SessionStore>((set) => ({
        sessions: [],

        activeSessionId: null,

        setSessions: (sessions) =>
            set({
                sessions,
            }),

        setActiveSession: (id) =>
            set({
                activeSessionId: id,
            }),
    }));