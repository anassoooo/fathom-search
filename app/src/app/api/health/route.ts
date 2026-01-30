import { NextResponse } from "next/server";
import { qdrant, COLLECTION } from "@/lib/qdrant";

export async function GET() {
  const info = await qdrant.getCollection(COLLECTION);
  return NextResponse.json({ ok: true, collection: COLLECTION, points: info.points_count });
}

