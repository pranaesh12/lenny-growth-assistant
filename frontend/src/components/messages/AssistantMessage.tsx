import MessageBubble from "./MessageBubble";

interface Props {
  content: string;
}

export default function AssistantMessage({
  content,
}: Props) {
  return (
    <MessageBubble
      role="assistant"
      content={content}
    />
  );
}