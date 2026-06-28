/* ── ChatWindow — Scrollable chat message container ─────────────────────── */

import { useEffect, useRef } from 'react';
import type { ChatMessage } from '@/hooks/useSession';
import MessageBubble from './MessageBubble';

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-[#6B7280] select-none">
      {/* Chat icon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-16 w-16 mb-4 opacity-40"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        />
      </svg>
      <p className="text-sm font-medium">Start a session to begin ordering</p>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div
      className="flex items-center gap-1.5 px-4 py-3"
      role="status"
      aria-label="System is typing"
    >
      <div className="flex items-center gap-1">
        <span className="block h-2 w-2 rounded-full bg-[#6B7280] animate-bounce [animation-delay:0ms]" />
        <span className="block h-2 w-2 rounded-full bg-[#6B7280] animate-bounce [animation-delay:150ms]" />
        <span className="block h-2 w-2 rounded-full bg-[#6B7280] animate-bounce [animation-delay:300ms]" />
      </div>
      <span className="sr-only">System is typing</span>
    </div>
  );
}

export default function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive or loading state changes
  useEffect(() => {
    const el = containerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages.length, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-4 py-4"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        <EmptyState />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
      role="log"
      aria-live="polite"
      aria-label="Chat messages"
    >
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}

      {isLoading && <TypingIndicator />}
    </div>
  );
}
