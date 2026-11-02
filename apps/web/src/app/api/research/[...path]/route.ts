import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  const resource = (await context.params).path.join("/");
  const allowed = request.method === "GET" ? /^(runs|runs\/[a-f0-9]{64}|protocols\/[a-f0-9]{64})$/
    : /^(protocols|runs|runs\/[a-f0-9]{64}\/verify)$/;
  if (!allowed.test(resource) || request.nextUrl.search) return NextResponse.json({ detail: "Recurso de pesquisa inválido." }, { status: 404 });
  // Next's internal URL can use a different loopback hostname than the browser.
  // Compare Origin to the actual Host header, while allowing only local hosts.
  const host = request.headers.get("host") ?? "";
  const localHost = /^(127\.0\.0\.1|localhost)(:\d{1,5})?$/.test(host);
  const origin = request.headers.get("origin");
  if (!localHost || (request.method === "POST" && (request.headers.get("x-cryptolab-research") !== "1" ||
      (origin && origin !== `http://${host}`)))) {
    return NextResponse.json({ detail: "Solicitação local de pesquisa inválida." }, { status: 403 });
  }
  try {
    const base = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["127.0.0.1", "localhost"].includes(base.hostname) || base.protocol !== "http:" || base.username || base.password) throw new Error("Invalid backend");
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 8192) return NextResponse.json({ detail: "Solicitação muito grande." }, { status: 413 });
    const response = await fetch(new URL(`/api/v1/research/${resource}`, base), { method: request.method, body,
      cache: "no-store", signal: AbortSignal.timeout(120000), headers: { "Content-Type": "application/json", "X-CryptoLab-Research": "1" } });
    const data = await response.json();
    if (!response.ok) return NextResponse.json({ detail: response.status === 409 && typeof data.detail === "string" ? data.detail
      : response.status === 422 ? "Parâmetros inválidos. Confira limites, períodos e custos."
      : response.status === 429 ? "Pesquisa ocupada. Aguarde a execução atual." : "Não foi possível executar a pesquisa local." }, { status: response.status });
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Backend indisponível ou tempo excedido. Consulte as execuções antes de repetir." }, { status: 503 });
  }
}
export const GET = proxy;
export const POST = proxy;
