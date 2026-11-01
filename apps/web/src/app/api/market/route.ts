import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const symbol = request.nextUrl.searchParams.get("symbol") ?? "BTCUSDT";
  const interval = request.nextUrl.searchParams.get("interval") ?? "60";
  if (!["BTCUSDT", "ETHUSDT"].includes(symbol) || !["15", "60", "240", "D"].includes(interval)) {
    return NextResponse.json({ detail: "Ativo ou período não suportado." }, { status: 400 });
  }
  try {
    const base = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["127.0.0.1", "localhost"].includes(base.hostname) || base.protocol !== "http:" || base.username || base.password) {
      throw new Error("Invalid local backend");
    }
    const upstream = await fetch(new URL(`/api/v1/market?symbol=${symbol}&interval=${interval}`, base), {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    if (!upstream.ok) {
      return NextResponse.json({ detail: upstream.status === 503
        ? "Sem coleta disponível. Verifique o backend e o worker local."
        : "Não foi possível consultar os dados. Tente atualizar novamente." }, { status: 503 });
    }
    const data = await upstream.json();
    if (data.symbol !== symbol || data.interval !== interval || data.source !== "Bybit" || data.category !== "spot" ||
      !Array.isArray(data.candles) || typeof data.source_time_ms !== "number") throw new Error("Invalid snapshot");
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Backend local indisponível. Inicie a API e o worker para receber dados da Bybit." },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
