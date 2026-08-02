import { useState } from "react";

import { useSendMessage } from "../../hooks/useSendMessage";
import { useSessionStore } from "../../stores/sessionStore";

import InputToolbar from "./InputToolbar";

export default function ChatInput() {
    const [value, setValue] = useState("");

    const activeSessionId = useSessionStore(
        (state) => state.activeSessionId,
    );

    const sendMessage = useSendMessage();

    function handleSend() {
    console.log("🚀 HANDLE SEND CALLED");

    const message = value.trim();

    if (!message) return;
    if (!activeSessionId) return;

    console.log("Sending:", message);

    // Clear input immediately (ChatGPT-like behavior)
    setValue("");

    sendMessage.mutate(
        {
            session_id: activeSessionId,
            message,
        },
        {
            onSuccess: () => {
                console.log("✅ Message sent successfully");
            },

            onError: (error) => {
    console.error("❌ Error:", error);
    setValue(message);
            },
        },
    );
}

    function handleKeyDown(
        event: React.KeyboardEvent<HTMLTextAreaElement>,
    ) {
        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {
            event.preventDefault();
            handleSend();
        }
    }

    return (
        <div className="border-t bg-white px-6 py-5">
            <div className="mx-auto max-w-4xl">
                <textarea
                    rows={3}
                    value={value}
                    onChange={(e) =>
                        setValue(e.target.value)
                    }
                    onKeyDown={handleKeyDown}
                    disabled={
                        sendMessage.isPending ||
                        !activeSessionId
                    }
                    placeholder={
                        activeSessionId
                            ? "Ask anything about Lenny's Podcast..."
                            : "Create or select a conversation to start chatting..."
                    }
                    className="
                        w-full
                        resize-none
                        rounded-xl
                        border
                        border-gray-300
                        p-4
                        text-base
                        outline-none
                        transition
                        focus:border-black
                        disabled:cursor-not-allowed
                        disabled:bg-gray-100
                    "
                />

                <div className="mt-3 flex items-center justify-between">
                    <InputToolbar />

                    <button
                        type="button"
                        onClick={handleSend}
                        disabled={
                            sendMessage.isPending ||
                            !activeSessionId
                        }
                        className="
                            rounded-lg
                            bg-black
                            px-6
                            py-2.5
                            text-sm
                            font-medium
                            text-white
                            transition
                            hover:bg-gray-800
                            disabled:cursor-not-allowed
                            disabled:opacity-50
                        "
                    >
                        {sendMessage.isPending
                            ? "Thinking..."
                            : "Send"}
                    </button>
                </div>

                <p className="mt-3 text-center text-xs text-gray-400">
                    Answers are generated from Lenny's Podcast knowledge base and
                    may occasionally be inaccurate.
                </p>
            </div>
        </div>
    );
}