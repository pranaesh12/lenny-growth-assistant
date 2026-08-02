import { useMutation, useQueryClient } from "@tanstack/react-query";

import { SessionApi } from "../api/session";
import { useSessionStore } from "../stores/sessionStore";

export function useCreateSession() {
    const queryClient = useQueryClient();

    const setActiveSession = useSessionStore(
        (state) => state.setActiveSession,
    );

    return useMutation({
        mutationFn: SessionApi.create,

        onSuccess: (newSession) => {
            // Refresh the sidebar
            queryClient.invalidateQueries({
                queryKey: ["sessions"],
            });

            // Automatically open the newly created session
            setActiveSession(newSession.id);
        },
    });
}