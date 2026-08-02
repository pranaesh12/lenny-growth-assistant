import {
    useMutation,
    useQueryClient,
} from "@tanstack/react-query";

import { ChatApi } from "../api/chat";

export function useSendMessage() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ChatApi.sendMessage,

        onSuccess: (_, variables) => {
            // Refresh the conversation
            queryClient.invalidateQueries({
                queryKey: [
                    "messages",
                    variables.session_id,
                ],
            });

            // Refresh the session list
            // (useful if backend sorts by latest activity)
            queryClient.invalidateQueries({
                queryKey: ["sessions"],
            });
        },
    });
}