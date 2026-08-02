import type { Session } from "../../types/session";
import { useSessionStore } from "../../stores/sessionStore";

interface Props {
    session: Session;
}

export default function SessionItem({ session }: Props) {
    const { activeSessionId, setActiveSession } = useSessionStore();

    const active = activeSessionId === session.id;

    console.log("Rendering SessionItem:", session.id);

    return (
        <button
            type="button"
            onClick={() => {
                alert("Clicked!");
                console.log("Clicked session:", session.id);
                setActiveSession(session.id);
            }}
            className={`w-full rounded-lg px-4 py-3 text-left transition ${
                active
                    ? "bg-blue-100 font-semibold"
                    : "hover:bg-gray-100"
            }`}
        >
            {session.title}
        </button>
    );
}