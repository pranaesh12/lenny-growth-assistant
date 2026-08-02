import api from "./client";

export const ChatApi = {
    sendMessage(data: {
        session_id: string;
        message: string;
    }) {
        return api.post("/api/v1/chat", data);
    },
};