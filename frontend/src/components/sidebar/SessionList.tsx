import { useEffect } from "react";

import { useSessionApi } from "../../hooks/useSessionApi";
import { useSessionStore } from "../../stores/sessionStore";

import SessionItem from "./SessionItem";

export default function SessionList() {
    const {
        data: sessions,
        isLoading,
        isError,
    } = useSessionApi();

    const {
        activeSessionId,
        setActiveSession,
    } = useSessionStore();

    // Automatically select the first session
    useEffect(() => {
        if (
            sessions &&
            sessions.length > 0 &&
            !activeSessionId
        ) {
            setActiveSession(sessions[0].id);
        }
    }, [
        sessions,
        activeSessionId,
        setActiveSession,
    ]);

    if (isLoading) {
        return (
            <div className="p-4 text-sm text-gray-500">
                Loading sessions...
            </div>
        );
    }

    if (isError) {
        return (
            <div className="p-4 text-sm text-red-500">
                Failed to load sessions.
            </div>
        );
    }

    if (!sessions || sessions.length === 0) {
        return (
            <div className="p-4 text-sm text-gray-500">
                No conversations yet.
            </div>
        );
    }

    return (
        <div className="space-y-2 p-3">
            {sessions.map((session) => (
                <SessionItem
                    key={session.id}
                    session={session}
                />
            ))}
        </div>
    );
}