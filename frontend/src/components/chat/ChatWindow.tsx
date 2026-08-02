import { useMessages } from "../../hooks/useMessages";
import { useSessionStore } from "../../stores/sessionStore";

import AssistantMessage from "../messages/AssistantMessage";
import UserMessage from "../messages/UserMessage";

export default function ChatWindow() {
    const activeSessionId = useSessionStore(
        (state) => state.activeSessionId,
    );

    const {
        data: messages = [],
        isLoading,
        isError,
    } = useMessages(activeSessionId ?? "");

    // No session selected
    if (!activeSessionId) {
        return (
            <div className="flex h-full items-center justify-center px-6">
                <div className="max-w-2xl text-center">
                    <h1 className="mb-4 text-5xl font-bold">
                        Welcome to Lenny Growth Assistant
                    </h1>

                    <p className="text-lg text-gray-500">
                        Select an existing conversation from the sidebar or create
                        a new chat to start asking questions about Lenny's Podcast.
                    </p>
                </div>
            </div>
        );
    }

    // Loading
    if (isLoading) {
        return (
            <div className="flex h-full items-center justify-center">
                <span className="text-lg text-gray-500">
                    Loading conversation...
                </span>
            </div>
        );
    }

    // Error
    if (isError) {
        return (
            <div className="flex h-full items-center justify-center">
                <span className="text-lg text-red-500">
                    Failed to load conversation.
                </span>
            </div>
        );
    }

    // New chat (no messages yet)
    if (messages.length === 0) {
        return (
            <div className="flex h-full items-center justify-center px-6">
                <div className="max-w-3xl text-center">
                    <h1 className="mb-6 text-5xl font-bold">
                        Ask anything about Lenny's Podcast
                    </h1>

                    <p className="mb-10 text-lg text-gray-500">
                        Search across hundreds of podcast conversations and get
                        answers about product management, startups, AI, growth,
                        leadership, hiring, pricing, strategy, and much more.
                    </p>

                    <div className="grid gap-4 text-left md:grid-cols-2">
                        <div className="rounded-xl border bg-white p-4 shadow-sm">
                            <h3 className="mb-2 font-semibold">
                                🚀 Product Management
                            </h3>
                            <p className="text-sm text-gray-600">
                                How do the best PMs prioritize features?
                            </p>
                        </div>

                        <div className="rounded-xl border bg-white p-4 shadow-sm">
                            <h3 className="mb-2 font-semibold">
                                📈 Growth
                            </h3>
                            <p className="text-sm text-gray-600">
                                What growth strategies were discussed by guests?
                            </p>
                        </div>

                        <div className="rounded-xl border bg-white p-4 shadow-sm">
                            <h3 className="mb-2 font-semibold">
                                🤖 AI
                            </h3>
                            <p className="text-sm text-gray-600">
                                What are founders saying about AI products?
                            </p>
                        </div>

                        <div className="rounded-xl border bg-white p-4 shadow-sm">
                            <h3 className="mb-2 font-semibold">
                                👥 Leadership
                            </h3>
                            <p className="text-sm text-gray-600">
                                How do successful leaders build great teams?
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Conversation
    return (
        <div className="mx-auto max-w-4xl space-y-6 px-8 py-10 pb-40">
            {messages.map((message) =>
                message.role === "user" ? (
                    <UserMessage
                        key={message.id}
                        content={message.content}
                    />
                ) : (
                    <AssistantMessage
                        key={message.id}
                        content={message.content}
                    />
                ),
            )}
        </div>
    );
}