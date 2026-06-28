/* ── MessageBubble — Individual chat message ────────────────────────────── */

import type { ChatMessage } from '@/hooks/useSession';
import Badge from '@/components/ui/Badge';

interface MessageBubbleProps {
  message: ChatMessage;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="chat-bubble bg-[#EEF2FF] rounded-xl px-4 py-3 max-w-[75%] ml-auto"
          role="article"
          aria-label={`You said: ${message.text}`}
        >
          <p className="text-sm text-[#111827]">{message.text}</p>
          <p className="text-xs text-[#6B7280] mt-1.5 text-right">
            {formatTime(message.timestamp)}
          </p>
        </div>
      </div>
    );
  }

  // System message
  return (
    <div className="flex justify-start">
      <div
        className="chat-bubble bg-white border border-[#E2E8F0] border-l-[3px] border-l-[#6366F1] rounded-xl px-4 py-3 max-w-[75%]"
        role="article"
        aria-label={`System: ${message.text}`}
      >
        {/* Status badge */}
        <div className="flex items-center gap-2 mb-1.5">
          {message.contextApplied ? (
            <Badge variant="warning">↻ Updated</Badge>
          ) : (
            <Badge variant="success">✓ Added</Badge>
          )}
        </div>

        <p className="text-sm text-[#111827]">{message.text}</p>

        {/* Item list summary */}
        {message.items && message.items.length > 0 && (
          <ul className="mt-1.5 space-y-0.5" aria-label="Order items">
            {message.items.map((item, idx) => (
              <li
                key={`${item.name}-${idx}`}
                className="text-xs text-[#6B7280]"
              >
                • {item.name}
                {item.quantity > 1 && ` ×${item.quantity}`}
              </li>
            ))}
          </ul>
        )}

        {/* Footer: turn + timestamp */}
        <div className="flex items-center justify-between mt-2 gap-3">
          {message.turn !== undefined && (
            <span className="text-xs text-[#6B7280]">
              Turn {message.turn}
            </span>
          )}
          <span className="text-xs text-[#6B7280]">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
}
