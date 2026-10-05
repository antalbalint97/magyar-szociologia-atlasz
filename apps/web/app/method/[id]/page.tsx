import type { Metadata } from "next";
import TermPage from "@/components/TermPage";
import { atlas } from "@/lib/atlas/server";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const n = (await atlas()).node((await params).id);
  return { title: n?.label ?? "Módszer" };
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <TermPage id={(await params).id} kind="method" />;
}
