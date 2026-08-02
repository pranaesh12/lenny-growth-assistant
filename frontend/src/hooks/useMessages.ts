import { useQuery } from "@tanstack/react-query";
import { MessageApi } from "../api/message";
import type { Message } from "../types/message";

export function useMessages(sessionId: string) {
    return useQuery<Message[]>({
        queryKey: ["messages", sessionId],

        enabled: !!sessionId,

        queryFn: async () => {
            const response = await MessageApi.list(sessionId);

            // Backend returns:
            // {
            //    messages: [...],
            //    count: number
            // }

            return response.data.messages;
        },
    });
}