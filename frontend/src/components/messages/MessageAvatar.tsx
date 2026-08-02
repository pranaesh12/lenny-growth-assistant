interface MessageAvatarProps {
  role: "user" | "assistant";
}

export default function MessageAvatar({
  role,
}: MessageAvatarProps) {
  return (
    <div
      className={`flex h-10 w-10 items-center justify-center rounded-full font-semibold ${
        role === "assistant"
          ? "bg-black text-white"
          : "bg-blue-600 text-white"
      }`}
    >
      {role === "assistant" ? "L" : "U"}
    </div>
  );
}