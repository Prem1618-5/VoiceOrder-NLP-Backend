import { useState, useCallback, type ReactNode } from 'react';
import CopyButton from '@/components/ui/CopyButton';

interface JsonViewerProps {
  data: unknown;
  className?: string;
}

/** Render a single JSON value with syntax-highlighting spans. */
function JsonValue({ value, indent }: { value: unknown; indent: number }): ReactNode {
  if (value === null) {
    return <span className="json-null">null</span>;
  }

  if (typeof value === 'boolean') {
    return <span className="json-boolean">{String(value)}</span>;
  }

  if (typeof value === 'number') {
    return <span className="json-number">{String(value)}</span>;
  }

  if (typeof value === 'string') {
    return <span className="json-string">&quot;{value}&quot;</span>;
  }

  if (Array.isArray(value)) {
    return <JsonArray data={value} indent={indent} />;
  }

  if (typeof value === 'object') {
    return <JsonObject data={value as Record<string, unknown>} indent={indent} />;
  }

  // Fallback for undefined, functions, symbols, etc.
  return <span className="json-null">{String(value)}</span>;
}

function JsonArray({ data, indent }: { data: unknown[]; indent: number }) {
  const [collapsed, setCollapsed] = useState(false);

  const toggle = useCallback(() => setCollapsed((c) => !c), []);
  const padding = '  '.repeat(indent);
  const innerPadding = '  '.repeat(indent + 1);

  if (data.length === 0) {
    return <span className="json-bracket">[]</span>;
  }

  return (
    <span>
      <span
        className="json-toggle"
        onClick={toggle}
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand array' : 'Collapse array'}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
          }
        }}
      >
        {collapsed ? '▶ ' : '▼ '}
      </span>
      <span className="json-bracket">[</span>
      {collapsed ? (
        <span className="json-null"> {data.length} items </span>
      ) : (
        <>
          {'\n'}
          {data.map((item, idx) => (
            <span key={idx}>
              {innerPadding}
              <JsonValue value={item} indent={indent + 1} />
              {idx < data.length - 1 ? ',' : ''}
              {'\n'}
            </span>
          ))}
          {padding}
        </>
      )}
      <span className="json-bracket">]</span>
    </span>
  );
}

function JsonObject({ data, indent }: { data: Record<string, unknown>; indent: number }) {
  const [collapsed, setCollapsed] = useState(false);

  const toggle = useCallback(() => setCollapsed((c) => !c), []);
  const entries = Object.entries(data);
  const padding = '  '.repeat(indent);
  const innerPadding = '  '.repeat(indent + 1);

  if (entries.length === 0) {
    return <span className="json-bracket">{'{}'}</span>;
  }

  return (
    <span>
      <span
        className="json-toggle"
        onClick={toggle}
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand object' : 'Collapse object'}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
          }
        }}
      >
        {collapsed ? '▶ ' : '▼ '}
      </span>
      <span className="json-bracket">{'{'}</span>
      {collapsed ? (
        <span className="json-null"> {entries.length} keys </span>
      ) : (
        <>
          {'\n'}
          {entries.map(([key, val], idx) => (
            <span key={key}>
              {innerPadding}
              <span className="json-key">&quot;{key}&quot;</span>
              {': '}
              <JsonValue value={val} indent={indent + 1} />
              {idx < entries.length - 1 ? ',' : ''}
              {'\n'}
            </span>
          ))}
          {padding}
        </>
      )}
      <span className="json-bracket">{'}'}</span>
    </span>
  );
}

export default function JsonViewer({ data, className = '' }: JsonViewerProps) {
  const jsonText = JSON.stringify(data, null, 2);

  return (
    <div className={`json-viewer relative ${className}`}>
      <div className="absolute top-2 right-2">
        <CopyButton text={jsonText} />
      </div>
      <pre className="whitespace-pre-wrap break-words m-0 font-mono">
        <JsonValue value={data} indent={0} />
      </pre>
    </div>
  );
}
