import { NextResponse } from "next/server";
import { getProductsCount } from "@/lib/qdrant";

export async function GET() {
  try {
    const points = await getProductsCount();
    return NextResponse.json({ ok: true, points });
  } catch {
    return NextResponse.json({ ok: false }, { status: 503 });
  }
}
