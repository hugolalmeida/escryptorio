import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  const resource = (await context.params).path.join("/");
  const allowed = request.method === "GET" ? /^(experiments|experiments\/[a-f0-9]{64}(\/result)?)$/ : /^(experiments|execute)$/;
  if (!allowed.test(resource) || request.nextUrl.search) return NextResponse.json({ detail: "Recurso de pesquisa inválido." }, { status: 404 });
  const host = request.headers.get("host") ?? "";
  const origin = request.headers.get("origin");
  if (!/^(127\.0\.0\.1|localhost)(:\d{1,5})?$/.test(host) || (request.method === "POST" &&
      (request.headers.get("x-cryptolab-research") !== "1" || (origin && origin !== `http://${host}`)))) {
    return NextResponse.json({ detail: "Solicitação local de pesquisa inválida." }, { status: 403 });
  }
  try {
    const base = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["127.0.0.1", "localhost"].includes(base.hostname) || base.protocol !== "http:" || base.username || base.password) throw new Error("Invalid backend");
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 16384) return NextResponse.json({ detail: "Solicitação muito grande." }, { status: 413 });
    const response = await fetch(new URL(`/api/v1/arena/${resource}`, base), { method: request.method, body,
      cache: "no-store", signal: AbortSignal.timeout(resource === "execute" ? 120000 : 20000),
      headers: { "Content-Type": "application/json", "X-CryptoLab-Research": "1" } });
    const data = await response.json();
    if (!response.ok) return NextResponse.json({ detail: response.status === 409 && typeof data.detail === "string" ? data.detail
      : response.status === 422 ? "Parâmetros inválidos. Confira os períodos e as premissas."
      : response.status === 429 ? "Pesquisa ocupada; aguarde e consulte novamente."
      : "Não foi possível consultar a Arena local." }, { status: response.status, headers: { "Cache-Control": "no-store" } });
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const timeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    return NextResponse.json({ detail: timeout ? "Tempo excedido; consulte o resultado persistido." : "Backend local indisponível." },
      { status: timeout ? 504 : 503, headers: { "Cache-Control": "no-store" } });
  }
}
export const GET = proxy;
export const POST = proxy;
