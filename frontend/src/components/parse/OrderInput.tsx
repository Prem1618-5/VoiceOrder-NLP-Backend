import { useState, useCallback, type ChangeEvent, type FormEvent } from 'react';
import GradientBar from '@/components/ui/GradientBar';

/* ── Props ─────────────────────────────────────────────────────────────────── */

interface OrderInputProps {
  onParse: (text: string, menuId?: string) => void;
  isLoading: boolean;
}

/* ── Constants ─────────────────────────────────────────────────────────────── */

const MAX_CHARS = 500;

const EXAMPLE_PHRASES = [
  '3 medium margherita pizzas no onions',
  'a coke and garlic bread',
  'double smash burger extra cheese',
] as const;

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function OrderInput({ onParse, isLoading }: OrderInputProps) {
  const [text, setText] = useState('');
  const [menuId, setMenuId] = useState('default');

  const charCount = text.length;
  const isEmpty = text.trim().length === 0;
  const isDisabled = isLoading || isEmpty;

  const handleTextChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      if (value.length <= MAX_CHARS) {
        setText(value);
      }
    },
    [],
  );

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      if (!isDisabled) {
        onParse(text.trim(), menuId !== 'default' ? menuId : undefined);
      }
    },
    [text, menuId, isDisabled, onParse],
  );

  const fillExample = useCallback((phrase: string) => {
    setText(phrase);
  }, []);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* ── Textarea ──────────────────────────────────────────────────────── */}
      <div>
        <label
          htmlFor="order-text"
          className="block text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-2"
        >
          ORDER TEXT
        </label>

        <textarea
          id="order-text"
          rows={3}
          maxLength={MAX_CHARS}
          value={text}
          onChange={handleTextChange}
          placeholder="Type a food order…"
          className="form-input resize-y text-sm disabled:opacity-60"
          aria-describedby="char-count"
          disabled={isLoading}
        />

        {/* Character counter */}
        <p
          id="char-count"
          className="text-xs text-[#6B7280] text-right mt-1 font-mono tabular-nums"
          aria-live="polite"
        >
          {charCount}/{MAX_CHARS}
        </p>

        <GradientBar height={3} className="mt-1" />
      </div>

      {/* ── Menu ID ──────────────────────────────────────────────────────── */}
      <div>
        <label
          htmlFor="menu-id"
          className="block text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-2"
        >
          Menu ID
        </label>

        <select
          id="menu-id"
          value={menuId}
          onChange={(e) => setMenuId(e.target.value)}
          className="form-input text-sm disabled:opacity-60"
          disabled={isLoading}
        >
          <option value="default">default</option>
        </select>
      </div>

      {/* ── Parse button ─────────────────────────────────────────────────── */}
      <button
        type="submit"
        disabled={isDisabled}
        className="btn-primary w-full py-2.5"
      >
        {isLoading ? (
          <span className="inline-flex items-center gap-2">
            <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            Parsing…
          </span>
        ) : (
          'Parse →'
        )}
      </button>

      {/* ── Example phrases ──────────────────────────────────────────────── */}
      <div>
        <p className="text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-2">
          Example phrases:
        </p>
        <ul className="space-y-1.5" role="list">
          {EXAMPLE_PHRASES.map((phrase) => (
            <li key={phrase}>
              <button
                type="button"
                onClick={() => fillExample(phrase)}
                className="text-sm text-[#6B7280] italic hover:text-[#6366F1] transition-colors text-left cursor-pointer"
                aria-label={`Use example: ${phrase}`}
                disabled={isLoading}
              >
                • &ldquo;{phrase}&rdquo;
              </button>
            </li>
          ))}
        </ul>
      </div>
    </form>
  );
}
