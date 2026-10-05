// Node glyphs: one shape per kind, so the graph never relies on colour alone.
import type { Kind } from "./vocab.ts";

export function shapePath(kind: Kind, r: number): string {
  const f = (n: number) => +n.toFixed(2);
  switch (kind) {
    case "person":
      return `M ${f(-r)} 0 A ${f(r)} ${f(r)} 0 1 0 ${f(r)} 0 A ${f(r)} ${f(r)} 0 1 0 ${f(-r)} 0 Z`;
    case "project": {
      const s = r * 0.9;
      return `M ${f(-s)} ${f(-s)} H ${f(s)} V ${f(s)} H ${f(-s)} Z`;
    }
    case "unit": {
      const pts = Array.from({ length: 6 }, (_, i) => {
        const a = (Math.PI / 3) * i;
        return `${f(r * 1.08 * Math.cos(a))} ${f(r * 1.08 * Math.sin(a))}`;
      });
      return `M ${pts.join(" L ")} Z`;
    }
    case "topic": {
      const s = r * 1.25;
      return `M 0 ${f(-s)} L ${f(s)} 0 L 0 ${f(s)} L ${f(-s)} 0 Z`;
    }
    case "method": {
      const s = r * 1.3;
      return `M 0 ${f(-s)} L ${f(s * 0.92)} ${f(s * 0.62)} L ${f(-s * 0.92)} ${f(s * 0.62)} Z`;
    }
  }
}

export const KIND_COLOR: Record<Kind, string> = {
  person: "var(--n-person)",
  project: "var(--n-project)",
  unit: "var(--n-unit)",
  topic: "var(--n-topic)",
  method: "var(--n-topic)",
};
