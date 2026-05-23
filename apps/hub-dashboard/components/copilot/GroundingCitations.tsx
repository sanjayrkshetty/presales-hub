"use client";

interface GroundingEntry { source: string; score: number; content: string; }

interface Props { sources: GroundingEntry[]; }

export function GroundingCitations({ sources }: Props) {
  if (!sources?.length) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">Sources</p>
      <div className="flex flex-col gap-1">
        {sources.map((s, i) => (
          <div key={i} className="panel-sm p-2 flex items-start gap-2">
            <span className="text-2xs font-mono text-accent flex-shrink-0 w-8">
              {Math.round(s.score * 100)}%
            </span>
            <div className="flex flex-col gap-0.5 min-w-0">
              <p className="text-2xs font-sans text-text-primary truncate">{s.source}</p>
              {s.content && (
                <p className="text-2xs font-sans text-text-muted line-clamp-2">{s.content}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
