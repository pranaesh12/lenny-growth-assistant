import MessageAvatar from "./MessageAvatar";
import MessageContent from "./MessageContent";

interface Props {
  role: "user" | "assistant";
  content: string;
}

export default function MessageBubble({
  role,
  content,
}: Props) {
  return (
    <div className="flex gap-4 py-6">
      <MessageAvatar role={role} />

      <div className="flex-1 rounded-xl border bg-white p-4 shadow-sm">
        <MessageContent content={content} />
      </div>
    </div>
  );
}