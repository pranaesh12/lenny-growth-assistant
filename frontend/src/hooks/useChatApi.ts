import { useMutation } from "@tanstack/react-query";

import { ChatApi } from "../api/chat";

export function useChatApi() {
    return useMutation({
        mutationFn: ChatApi.sendMessage,
    });
}