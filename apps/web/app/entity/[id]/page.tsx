// Stable URL kept from the first explorer: canonical entities redirect to their typed page;
// PersonMention / ProjectMention records are shown here, as source evidence, never as identities.
import { notFound, permanentRedirect } from "next/navigation";
import MentionView from "@/components/MentionView";
import { graph } from "@/lib/graph";
import { atlas } from "@/lib/atlas/server";
import { hrefFor } from "@/lib/atlas/vocab";

export default async function EntityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const g = graph();
  const mention = id.startsWith("pmn_") || id.startsWith("pjm_") ? await g.mention(id) : null;
  if (mention) return <div className="wrap page"><MentionView m={mention} g={g} /></div>;
  const n = (await atlas()).node(id);
  if (!n) notFound();
  permanentRedirect(hrefFor(n.id, n.type));
}
