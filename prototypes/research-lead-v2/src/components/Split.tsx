// The conversation / artifact split. Interaction after Open WebUI's
// ResizableSidePanel (pointer capture while dragging, arrow keys, width saved
// per browser) with AIA's defaults: conversation LEFT at 40 %, artifact RIGHT
// at 60 %, double-click resets, and focus modes that never overwrite the
// person's saved width.
import { useRef, useState, type ReactNode } from 'react';
import type { Mode } from '../model/types';
import { T } from '../model/terms';

const MIN = 28;
const MAX = 62;
const STEP = 2;

export function Split({ split, mode, onSplit, onCommit, left, right, rail }: {
  split: number; mode: Mode;
  onSplit: (v: number) => void; onCommit: (v: number) => void;
  left: ReactNode; right: ReactNode; rail: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState(false);
  const leftWidth = mode === 'artifact' ? null : mode === 'conversation' ? 68 : split;

  const fromPointer = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return split;
    return Math.max(MIN, Math.min(MAX, Math.round(((clientX - r.left) / r.width) * 1000) / 10));
  };

  return (
    <div className={'split split--' + mode} ref={box}>
      {mode === 'artifact' ? (
        <div className="split__rail">{rail}</div>
      ) : (
        <div className="split__left" style={{ width: leftWidth + '%' }}>{left}</div>
      )}
      {mode === 'normal' && (
        <div
          className={'split__handle' + (drag ? ' is-drag' : '')}
          role="separator"
          aria-orientation="vertical"
          aria-label={T.layout.resize}
          aria-valuemin={MIN} aria-valuemax={MAX} aria-valuenow={Math.round(split)}
          tabIndex={0}
          title={T.layout.resizeHint}
          onPointerDown={(e) => { (e.target as HTMLElement).setPointerCapture(e.pointerId); setDrag(true); }}
          onPointerMove={(e) => { if (drag) onSplit(fromPointer(e.clientX)); }}
          onPointerUp={(e) => { if (!drag) return; setDrag(false); onCommit(fromPointer(e.clientX)); }}
          onDoubleClick={() => onCommit(40)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') { e.preventDefault(); onCommit(Math.max(MIN, split - STEP)); }
            if (e.key === 'ArrowRight') { e.preventDefault(); onCommit(Math.min(MAX, split + STEP)); }
            if (e.key === 'Home' || e.key === 'Enter') { e.preventDefault(); onCommit(40); }
          }}
        />
      )}
      <div className="split__right">{right}</div>
    </div>
  );
}
