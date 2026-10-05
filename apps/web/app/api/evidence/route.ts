// Evidence for drawn graph edges: the relations they merge and the claims behind them.
// Returns public source URLs and snippets only; never file-system paths.
import { graph } from "@/lib/graph";
import { atlas } from "@/lib/atlas/server";

export async function GET(req: Request) {
  const ids = (new URL(req.url).searchParams.get("rel") ?? "").split(",").filter(Boolean).slice(0, 12);
  const a = await atlas();
  const relations = ids.map((id) => a.edgeById.get(id)).filter((e) => e !== undefined);
  const evidence = await graph().evidence([...new Set(relations.flatMap((e) => e.claimIds))]);
  return Response.json({
    relations: relations.map((e) => ({
      id: e.id, type: e.type, status: e.status, derivationMethod: e.derivationMethod, qualifiers: e.qualifiers,
    })),
    evidence: evidence.map((ev) => ({ ...ev, url: ev.url.startsWith("repo://") ? ev.url.slice(7) : ev.url })),
  });
}
