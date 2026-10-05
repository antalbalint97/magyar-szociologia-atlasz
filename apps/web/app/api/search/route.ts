import { atlas } from "@/lib/atlas/server";
import { searchAtlas } from "@/lib/atlas/search";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams.get("q") ?? "";
  const hits = q.trim().length >= 2 ? searchAtlas(await atlas(), q, 10, 4) : [];
  return Response.json({ hits });
}
