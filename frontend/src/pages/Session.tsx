import { useState, type FormEvent } from 'react';
import { useSession } from '@/hooks/useSession';
import SessionHeader from '@/components/session/SessionHeader';
import ChatWindow from '@/components/session/ChatWindow';
import OrderAccumulator from '@/components/session/OrderAccumulator';
import GradientBar from '@/components/ui/GradientBar';

export default function Session() {
  const session = useSession();
  const [inputText, setInputText] = useState('');

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = inputText.trim();
    if (!text || !session.sessionId) return;
    setInputText('');
    try {
      await session.send(text);
    } catch {
      // Error is already set in the hook
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Session Context Bar */}
      {session.status !== 'idle' && session.sessionId && (
        <SessionHeader
          sessionId={session.sessionId}
          turn={session.turn}
          expiresAt={session.expiresAt}
          status={session.status}
          onClose={async () => {
            await session.close();
          }}
        />
      )}

      {session.error && (
        <div className="mx-4 mt-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {session.error}
        </div>
      )}

      {/* Main 3-column layout */}
      <div className="flex-1 flex gap-4 mt-4 min-h-0">
        {/* Controls (left) */}
        <div className="w-[200px] shrink-0 hidden lg:block">
          <div className="glass-card p-4 space-y-4">
            <button
              onClick={async () => {
                session.reset();
                await session.start();
              }}
              disabled={session.isLoading}
              className="btn-primary w-full py-2.5"
            >
              {session.status === 'idle' ? 'Start New Session' : 'New Session'}
            </button>

            {session.status !== 'idle' && (
              <>
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">
                    Status
                  </p>
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        session.status === 'active'
                          ? 'bg-[#16A34A]'
                          : 'bg-[#6B7280]'
                      }`}
                    />
                    <span className="text-sm text-[#111827] capitalize">
                      {session.status}
                    </span>
                  </div>
                  <p className="text-sm text-[#6B7280]">
                    Turn {session.turn} / ∞
                  </p>
                  {session.expiresAt && (
                    <p className="text-sm text-[#6B7280]">
                      Expires in{' '}
                      {Math.max(
                        0,
                        Math.round(
                          (session.expiresAt.getTime() - Date.now()) / 60000,
                        ),
                      )}{' '}
                      min
                    </p>
                  )}
                </div>

                {session.status === 'active' && (
                  <button
                    onClick={() => session.close()}
                    disabled={session.isLoading}
                    className="w-full border border-[#DC2626] text-[#DC2626] rounded-lg py-2
                               text-sm font-medium hover:bg-red-50 transition-colors
                               disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Close & Confirm
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Chat Window (center) */}
        <div className="flex-1 flex flex-col glass-card p-0 overflow-hidden min-h-0">
          {session.status === 'idle' ? (
            /* Pre-session state */
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
              <div className="text-5xl mb-4">💬</div>
              <h3 className="text-lg font-semibold text-[#111827] mb-2">
                Start a session to order
              </h3>
              <p className="text-sm text-[#6B7280] mb-6 max-w-sm">
                Multi-turn conversations let you build an order naturally, one
                step at a time. Context is preserved across turns.
              </p>
              <button
                onClick={() => session.start()}
                disabled={session.isLoading}
                className="btn-primary px-8 py-3"
              >
                {session.isLoading ? 'Starting...' : 'Start Session'}
              </button>
            </div>
          ) : (
            <>
              {/* Messages */}
              <ChatWindow
                messages={session.messages}
                isLoading={session.isLoading}
              />

              {/* Input (sticky bottom) */}
              {session.status === 'active' && (
                <div className="border-t border-[rgba(99,102,241,0.08)] bg-[rgba(255,255,255,0.4)]">
                  <GradientBar height={3} />
                  <form
                    onSubmit={handleSend}
                    className="flex items-center px-4 py-3"
                  >
                    <input
                      type="text"
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      placeholder="Add to your order..."
                      disabled={session.isLoading}
                      className="form-input flex-1 disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={session.isLoading || !inputText.trim()}
                      className="btn-primary ml-3 px-4 py-2"
                    >
                      Send
                    </button>
                  </form>
                </div>
              )}

              {session.status === 'closed' && (
                <div className="border-t border-[rgba(99,102,241,0.08)] px-4 py-3 bg-[rgba(255,255,255,0.6)] text-center">
                  <p className="text-sm text-[#6B7280]">
                    Session closed. Order has been confirmed and saved.
                  </p>
                  <button
                    onClick={() => {
                      session.reset();
                    }}
                    className="mt-2 text-sm text-[#6366F1] hover:underline font-medium"
                  >
                    Start a new session →
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Live Order Panel (right) */}
        <div className="w-[280px] shrink-0 hidden lg:block">
          <OrderAccumulator
            items={session.currentOrder?.items ?? []}
            totalPrice={session.currentOrder?.total_price ?? 0}
          />
        </div>
      </div>

      {/* Mobile: bottom drawer for order (simplified) */}
      {session.status !== 'idle' && session.currentOrder && (
        <div className="lg:hidden mt-4">
          <OrderAccumulator
            items={session.currentOrder.items}
            totalPrice={session.currentOrder.total_price}
          />
        </div>
      )}

      {/* Mobile: Start button when idle */}
      {session.status === 'idle' && (
        <div className="lg:hidden mt-4">
          <button
            onClick={() => session.start()}
            disabled={session.isLoading}
            className="btn-primary w-full py-3"
          >
            {session.isLoading ? 'Starting...' : 'Start New Session'}
          </button>
        </div>
      )}
    </div>
  );
}
