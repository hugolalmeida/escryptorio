import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  const { path } = await context.params;
  const resource = path.join("/");
  const readable = /^(jobs(\/[a-f0-9]{32})?|coverage|datasets(\/[a-f0-9]{64})?)$/.test(resource);
  const writable = /^(jobs|jobs\/[a-f0-9]{32}\/(pause|resume))$/.test(resource);
  if (!(request.method === "GET" ? readable : writable)) return NextResponse.json({ detail: "Recurso de pesquisa inválido." }, { status: 404 });
  if (request.method === "POST" && (request.headers.get("x-cryptolab-research") !== "1" ||
      (request.headers.get("origin") && request.headers.get("origin") !== request.nextUrl.origin))) {
    return NextResponse.json({ detail: "Solicitação local de pesquisa inválida." }, { status: 403 });
  }
  const allowed = new Set(["symbol", "interval", "start", "end", "offset", "limit"]);
  if ([...request.nextUrl.searchParams.keys()].some(key => !allowed.has(key))) {
    return NextResponse.json({ detail: "Parâmetro não suportado." }, { status: 400 });
  }
  try {
    const base = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["127.0.0.1", "localhost"].includes(base.hostname) || base.protocol !== "http:" || base.username || base.password) throw new Error("Invalid local backend");
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 4096) return NextResponse.json({ detail: "Solicitação muito grande." }, { status: 413 });
    const response = await fetch(new URL(`/api/v1/history/${resource}${request.nextUrl.search}`, base), {
      method: request.method, body, cache: "no-store", signal: AbortSignal.timeout(15000),
      headers: { "Content-Type": "application/json", "X-CryptoLab-Research": "1" },
    });
    if (!response.ok) {
      const detail = response.status === 422 ? "Período inválido. Use limites UTC alinhados ao timeframe e até 100.000 candles."
        : response.status === 404 ? "Coleta ou dataset não encontrado."
        : response.status === 409 ? "Dataset recusado: hash, integridade ou recorte inválido."
        : "Não foi possível consultar a pesquisa. Verifique o backend local.";
      return NextResponse.json({ detail }, { status: response.status, headers: { "Cache-Control": "no-store" } });
    }
    return NextResponse.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Backend local indisponível. Inicie a API e o worker histórico." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export const GET = proxy;
export const POST = proxy;
