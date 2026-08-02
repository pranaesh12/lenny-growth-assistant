import SidebarHeader from "./SidebarHeader";
import SessionList from "./SessionList";

export default function Sidebar() {
    return (
        <aside
            className="
                flex
                h-screen
                w-72
                flex-col
                border-r
                bg-white
            "
        >
            <SidebarHeader />

            <div className="flex-1 overflow-auto">
                <SessionList />
            </div>
        </aside>
    );
}