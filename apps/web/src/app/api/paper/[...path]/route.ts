import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };
export async function GET(request: NextRequest, context: Context) {
  const path = (await context.params).path.join("/");
  if (!/^(overview|signals|decisions|wallets\/[a-f0-9]{32}(\/(events|fills|equity))?)$/.test(path))
    return NextResponse.json({ detail: "Recurso inválido." }, { status: 404 });
  const host = request.headers.get("host") ?? "";
  if (!/^(127\.0\.0\.1|localhost)(:\d{1,5})?$/.test(host)) return NextResponse.json({ detail: "Somente acesso local." }, { status: 403 });
  const query = request.nextUrl.searchParams;
  const allowed = path.endsWith("/fills") || path.endsWith("/events") ? ["limit", "offset"] : ["signals", "decisions"].includes(path) ? ["limit"] : [];
  if (Array.from(query.keys()).some(k => !allowed.includes(k) || query.getAll(k).length !== 1 || !/^\d{1,7}$/.test(query.get(k) ?? "")))
    return NextResponse.json({ detail: "Parâmetros inválidos." }, { status: 400 });
  try {
    const base = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["localhost", "127.0.0.1"].includes(base.hostname) || base.protocol !== "http:" || base.username || base.password) throw new Error("invalid backend");
    const url = new URL(`/api/v1/paper/${path}`, base); url.search = request.nextUrl.search;
    const response = await fetch(url, { cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15000) });
    if (!response.ok) return NextResponse.json({ detail: "Dados paper indisponíveis ou falha de integridade." }, { status: response.status, headers: { "Cache-Control": "no-store" } });
    return NextResponse.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Backend local indisponível." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
