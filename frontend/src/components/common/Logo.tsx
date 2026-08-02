export default function Logo() {
    return (
        <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-black text-lg font-bold text-white">
                L
            </div>

            <div>
                <h1 className="text-sm font-bold">
                    Lenny Growth Assistant
                </h1>

                <p className="text-xs text-gray-500">
                    AI Research Assistant
                </p>
            </div>
        </div>
    );
}