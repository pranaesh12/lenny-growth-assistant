import { useMessages } from "./useMessages";
import { useSendMessage } from "./useSendMessage";

export function useChatConversation(
    sessionId: string,
) {

    const messages =
        useMessages(sessionId);

    const sendMessage =
        useSendMessage();

    return {

        messages,

        sendMessage,

    };

}