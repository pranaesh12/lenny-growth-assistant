import { Send } from "lucide-react";

export default function SendButton() {
  return (
    <button className="rounded-lg bg-black p-3 text-white hover:bg-gray-800">
      <Send size={18} />
    </button>
  );
}