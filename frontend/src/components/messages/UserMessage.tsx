import MessageBubble from "./MessageBubble";

interface Props {
  content: string;
}

export default function UserMessage({
  content,
}: Props) {
  return (
    <MessageBubble
      role="user"
      content={content}
    />
  );
}