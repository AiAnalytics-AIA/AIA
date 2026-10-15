"use client";

// A model's long text, laid out as it was written (lib/result-reading.ts textBlocks): headings,
// paragraphs and lists. Every word is kept; only line markers and bold markers become layout.

import { inlineRuns, textBlocks } from "@/lib/result-reading";

function Runs({ text }: { text: string }) {
  return <>{inlineRuns(text).map((run, i) => (run.bold ? <strong key={i}>{run.text}</strong> : <span key={i}>{run.text}</span>))}</>;
}

export function FormattedText({ text, className = "" }: { text: string | null | undefined; className?: string }) {
  const blocks = textBlocks(text);
  if (!blocks.length) return null;
  return (
    <div className={`flex flex-col gap-2 text-sm leading-6 ${className}`}>
      {blocks.map((block, i) => {
        if (block.kind === "heading") return <p key={i} className="font-semibold"><Runs text={block.text} /></p>;
        if (block.kind === "paragraph") return <p key={i}><Runs text={block.text} /></p>;
        const items = block.items.map((item, j) => <li key={j}><Runs text={item} /></li>);
        return block.ordered
          ? <ol key={i} start={block.start} className="list-decimal space-y-1 pl-5">{items}</ol>
          : <ul key={i} className="list-disc space-y-1 pl-5">{items}</ul>;
      })}
    </div>
  );
}
