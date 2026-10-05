import type { Metadata } from "next";
import Link from "next/link";
import { atlas } from "@/lib/atlas/server";
import type { Atlas, Node } from "@/lib/atlas/atlas";
import { UNIT_TYPE_LABEL } from "@/lib/atlas/vocab";

export const metadata: Metadata = { title: "Intézmények" };

function counts(a: Atlas, id: string) {
  const tree = a.unitTree(id);
  const people = new Set(tree.flatMap((u) => a.in(u, ["AFFILIATED_WITH", "MEMBER_OF", "LEADS"]).map((e) => e.source))).size;
  const projects = tree.flatMap((u) => a.in(u, ["HOSTED_BY"])).length;
  return { people, projects };
}

function Tree({ a, node, depth }: { a: Atlas; node: Node; depth: number }) {
  const kids = a.in(node.id, ["PART_OF"]).map((e) => a.node(e.source)!)
    .sort((x, y) => Number(a.isRegistryOnly(x.id)) - Number(a.isRegistryOnly(y.id)) || x.label.localeCompare(y.label, "hu"));
  const c = counts(a, node.id);
  const reg = a.isRegistryOnly(node.id);
  const type = (node.fields.unit_type ?? node.fields.institution_type) as string | undefined;
  return (
    <li style={{ paddingLeft: depth ? 18 : 0, borderLeft: depth ? "1px solid var(--rule)" : undefined, listStyle: "none" }}>
      <div style={{ padding: "6px 0" }}>
        <Link href={`/institution/${node.id}`} style={{ fontFamily: "var(--serif)", fontWeight: depth < 2 ? 600 : 500, fontSize: depth ? "1rem" : "1.15rem", color: reg ? "var(--muted)" : "var(--ink)" }}>
          {node.label}
        </Link>
        <span className="muted small">
          {type ? ` · ${UNIT_TYPE_LABEL[type] ?? type}` : ""}
          {reg ? " · csak nyilvántartásban" : ` · ${c.people} munkatárs · ${c.projects} projekt`}
        </span>
      </div>
      {kids.length > 0 && <ul style={{ margin: 0, padding: 0 }}>{kids.map((k) => <Tree key={k.id} a={a} node={k} depth={depth + 1} />)}</ul>}
    </li>
  );
}

export default async function Institutions() {
  const a = await atlas();
  const roots = a.ofKind("unit").filter((u) => !a.out(u.id, ["PART_OF"]).length);
  const covered = roots.filter((r) => !a.isRegistryOnly(r.id));
  const registry = roots.filter((r) => a.isRegistryOnly(r.id)).sort((x, y) => x.label.localeCompare(y.label, "hu"));
  return (
    <div className="wrap page">
      <div className="eyebrow">Intézmények</div>
      <h1>Intézmények és egységek</h1>
      <p className="lede" style={{ marginTop: 8 }}>
        A jelenlegi pilot a TK négy intézeti honlapját dolgozza fel. A többi intézmény az atlasz nyilvántartásában már szerepel
        (a későbbi bővítéshez), de kutatók és projektek még nem tartoznak hozzájuk.
      </p>
      <section className="section">
        <header><h2>Feldolgozott források</h2></header>
        <ul style={{ margin: 0, padding: 0 }}>{covered.map((r) => <Tree key={r.id} a={a} node={r} depth={0} />)}</ul>
      </section>
      <section className="section">
        <header><h2>Csak nyilvántartásban</h2><span className="aside">a következő mérföldkövekben bővül</span></header>
        <ul style={{ margin: 0, padding: 0 }}>{registry.map((r) => <Tree key={r.id} a={a} node={r} depth={0} />)}</ul>
      </section>
    </div>
  );
}
