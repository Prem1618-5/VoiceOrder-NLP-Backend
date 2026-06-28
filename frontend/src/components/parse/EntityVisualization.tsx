import { useMemo } from 'react';
import type { RawEntity } from '@/lib/api';

/* ── Props ─────────────────────────────────────────────────────────────────── */

interface EntityVisualizationProps {
  originalText: string;
  rawEntities: RawEntity[];
}

/* ── Entity colour map ─────────────────────────────────────────────────────── */

const ENTITY_COLORS: Record<
  RawEntity['label'],
  { bg: string; text: string; border: string; badgeBg: string }
> = {
  FOOD: {
    bg: '#EEF2FF',
    text: '#4338CA',
    border: '#C7D2FE',
    badgeBg: '#E0E7FF',
  },
  SIZE: {
    bg: '#FEF3C7',
    text: '#92400E',
    border: '#FDE68A',
    badgeBg: '#FDE68A',
  },
  MODIFIER: {
    bg: '#DCFCE7',
    text: '#166534',
    border: '#BBF7D0',
    badgeBg: '#BBF7D0',
  },
  CARDINAL: {
    bg: '#E0F2FE',
    text: '#075985',
    border: '#BAE6FD',
    badgeBg: '#BAE6FD',
  },
};

/* ── Span types ────────────────────────────────────────────────────────────── */

interface PlainSpan {
  kind: 'plain';
  text: string;
}

interface EntitySpan {
  kind: 'entity';
  text: string;
  label: RawEntity['label'];
  start: number;
  end: number;
  index: number; // entity index for stagger animation
}

type TextSpan = PlainSpan | EntitySpan;

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function EntityVisualization({
  originalText,
  rawEntities,
}: EntityVisualizationProps) {
  /* Build interleaved plain / entity spans, sorted by start offset. */
  const spans: TextSpan[] = useMemo(() => {
    if (rawEntities.length === 0) {
      return [{ kind: 'plain', text: originalText }];
    }

    // Sort entities by start position (stable)
    const sorted = [...rawEntities].sort((a, b) => a.start - b.start);

    const result: TextSpan[] = [];
    let cursor = 0;
    let entityIndex = 0;

    for (const entity of sorted) {
      // Plain text before this entity
      if (entity.start > cursor) {
        result.push({ kind: 'plain', text: originalText.slice(cursor, entity.start) });
      }

      result.push({
        kind: 'entity',
        text: originalText.slice(entity.start, entity.end),
        label: entity.label,
        start: entity.start,
        end: entity.end,
        index: entityIndex++,
      });

      cursor = entity.end;
    }

    // Trailing plain text
    if (cursor < originalText.length) {
      result.push({ kind: 'plain', text: originalText.slice(cursor) });
    }

    return result;
  }, [originalText, rawEntities]);

  return (
    <div>
      <h3 className="text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-3">
        ENTITY VISUALIZATION
      </h3>

      <p
        className="text-base leading-relaxed flex flex-wrap items-center gap-y-1"
        aria-label="Parsed order text with entity annotations"
      >
        {spans.map((span, i) => {
          if (span.kind === 'plain') {
            return (
              <span key={`plain-${i}`} className="text-[#111827]">
                {span.text}
              </span>
            );
          }

          const colors = ENTITY_COLORS[span.label];

          return (
            <span
              key={`entity-${span.start}-${span.end}`}
              className="entity-pill inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-sm font-medium border"
              style={{
                backgroundColor: colors.bg,
                color: colors.text,
                borderColor: colors.border,
                animationDelay: `${span.index * 30}ms`,
              }}
              title={`${span.label} · chars ${span.start}–${span.end}`}
              aria-label={`${span.label} entity: ${span.text}`}
            >
              {span.text}
              {/* Superscript label badge */}
              <sup
                className="ml-1 inline-flex items-center px-1 rounded font-bold uppercase leading-none select-none"
                style={{
                  fontSize: '10px',
                  backgroundColor: colors.badgeBg,
                  color: colors.text,
                }}
                aria-hidden="true"
              >
                {span.label}
              </sup>
            </span>
          );
        })}
      </p>
    </div>
  );
}
