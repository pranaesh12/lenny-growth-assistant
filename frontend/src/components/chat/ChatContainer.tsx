import ChatWindow from "./ChatWindow";
import ChatInput from "../input/ChatInput";

export default function ChatContainer() {
    return (
        <div className="flex h-full flex-col bg-gray-50">
            {/* Chat messages */}
            <div className="flex-1 overflow-y-auto">
                <ChatWindow />
            </div>

            {/* Input area */}
            <div className="sticky bottom-0 border-t border-gray-200 bg-white">
                <ChatInput />
            </div>
        </div>
    );
}