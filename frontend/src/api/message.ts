import api from "./client";
import type { Message } from "../types/message";

interface MessageListResponse {
    messages: Message[];
    count: number;
}

export const MessageApi = {
    list(sessionId: string) {
        return api.get<MessageListResponse>(
            `/api/v1/sessions/${sessionId}/messages`,
        );
    },

    create(sessionId: string, content: string) {
        return api.post(
            `/api/v1/sessions/${sessionId}/messages`,
            {
                content,
            },
        );
    },
};