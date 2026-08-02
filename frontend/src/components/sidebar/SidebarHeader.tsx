import { Plus } from "lucide-react";

import Logo from "../common/Logo";

import { useCreateSession } from "../../hooks/useCreateSession";

export default function SidebarHeader() {
    const createSession = useCreateSession();

    const handleNewChat = () => {
        createSession.mutate({
            title: "New Chat",
        });
    };

    return (
        <div className="border-b p-4">
            <Logo />

            <button
                type="button"
                onClick={handleNewChat}
                disabled={createSession.isPending}
                className="
                    mt-4
                    flex
                    w-full
                    items-center
                    justify-center
                    gap-2
                    rounded-lg
                    bg-black
                    px-4
                    py-2
                    text-sm
                    font-medium
                    text-white
                    transition
                    hover:bg-gray-800
                    disabled:cursor-not-allowed
                    disabled:opacity-50
                "
            >
                <Plus size={18} />

                {createSession.isPending
                    ? "Creating..."
                    : "New Chat"}
            </button>
        </div>
    );
}