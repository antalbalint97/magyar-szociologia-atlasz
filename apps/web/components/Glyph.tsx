import { KIND_COLOR, shapePath } from "@/lib/atlas/shapes";
import { KIND_LABEL, type Kind } from "@/lib/atlas/vocab";

export function Glyph({ kind, size = 12 }: { kind: Kind; size?: number }) {
  const r = size * 0.36;
  return (
    <svg width={size} height={size} viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`} aria-hidden="true">
      <path d={shapePath(kind, r)} fill={KIND_COLOR[kind]} />
    </svg>
  );
}

export function KindLabel({ kind, text }: { kind: Kind; text?: string }) {
  return (
    <span className="kind">
      <Glyph kind={kind} />
      {text ?? KIND_LABEL[kind]}
    </span>
  );
}
