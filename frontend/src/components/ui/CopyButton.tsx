import { useState, useCallback } from 'react';

interface CopyButtonProps {
  text: string;
  className?: string;
}

export default function CopyButton({ text, className = '' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Fallback: silently fail if clipboard API is unavailable
    }
  }, [text]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? 'Copied to clipboard' : 'Copy to clipboard'}
      className={`inline-flex items-center gap-1 text-[#6B7280] hover:text-[#111827] transition-colors ${className}`}
    >
      {copied ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-4 h-4"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
            clipRule="evenodd"
          />
        </svg>
      ) : (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-4 h-4"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M15.988 3.012A2.25 2.25 0 0 0 14.25 2h-4.5A2.25 2.25 0 0 0 7.5 4.25v1.5H4.25A2.25 2.25 0 0 0 2 8v7.75A2.25 2.25 0 0 0 4.25 18h5.5A2.25 2.25 0 0 0 12 15.75v-1.5h2.25A2.25 2.25 0 0 0 16.5 12V4.25a2.25 2.25 0 0 0-.512-1.238ZM12 15.75a.75.75 0 0 1-.75.75h-5.5a.75.75 0 0 1-.75-.75V8a.75.75 0 0 1 .75-.75H7.5v4.75A2.25 2.25 0 0 0 9.75 14.25H12v1.5Zm2.25-5.25a.75.75 0 0 1-.75.75h-3.75a.75.75 0 0 1-.75-.75v-6a.75.75 0 0 1 .75-.75h3.338l.462.513V10.5Z"
            clipRule="evenodd"
          />
        </svg>
      )}
      <span aria-live="polite" className="text-xs">
        {copied ? 'Copied!' : ''}
      </span>
    </button>
  );
}
