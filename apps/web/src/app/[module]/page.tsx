import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";

const modules: Record<string, { title: string; description: string; phase: string; items: string[] }> = {
  arena: { title: "Arena", description: "Compare hipóteses sob as mesmas condições de mercado.", phase: "Fase 5 · Planejada",
    items: ["Trend, RSI, Breakout e Buy & Hold com capital inicial e custos equivalentes.", "Retorno líquido, drawdown, profit factor, acerto, expectativa e número de trades.", "Comparação fora da amostra, com períodos de treino, validação e teste explícitos.", "Mack reservada como não validada; sem resultados ou sinais até sua especificação."] },
  backtesting: { title: "Backtesting", description: "Cada resultado deve ter dados, parâmetros e custos reproduzíveis.", phase: "Fase 4 · Planejada",
    items: ["Datasets imutáveis por SHA-256; coleta e versionamento inicial já disponíveis.", "Decisão no fechamento de t; execução permitida somente na abertura de t+1.", "Taxas e slippage em cada fill, gaps e regra conservadora para stop e alvo no mesmo candle.", "Treino, validação e teste cronológicos; sem ajuste de parâmetros na amostra de teste."] },
  signals: { title: "Sinais", description: "Planos explicáveis, com contexto e prazo de validade.", phase: "Fase 4 · Planejada",
    items: ["Ativo, timeframe, estratégia, entrada, stop, alvo e relação risco-retorno.", "Justificativa por condições verificáveis, invalidação e vencimento explícito.", "Recusa de dados antigos, lacunas no histórico e warm-up insuficiente.", "Nenhum sinal é gerado nesta etapa; indicadores do dashboard são descritivos."] },
  paper: { title: "Paper Trading", description: "Um livro de operações virtual, separado da conta da corretora.", phase: "Fase 5 · Planejada",
    items: ["Saldo virtual, fills e taxas persistidos com precisão decimal.", "PnL realizado e não realizado, regras de preenchimento e slippage auditáveis.", "Idempotência e reconciliação do livro de operações exclusivamente local.", "Nenhuma operação virtual está sendo executada nesta primeira entrega."] },
  wallet: { title: "Carteira Bybit", description: "Conexão privada somente leitura, ainda não configurada.", phase: "Fase 6 · Não conectada",
    items: ["Validar elegibilidade, tipo de conta e permissões efetivas antes de aceitar a chave.", "Rejeitar chaves com permissões de escrita, saque ou produtos não autorizados.", "Consultar saldo e ordens sem alterar o estado da conta.", "Credenciais apenas no backend; nunca no navegador, repositório ou logs."] },
  execution: { title: "Execução real desativada", description: "Nenhuma rota de envio de ordens ou cliente autenticado foi implementado.", phase: "Bloqueada por arquitetura",
    items: ["LIVE_TRADING_ENABLED=false. Outro valor impede a inicialização do backend e worker.", "Somente Spot. Margem, alavancagem e empréstimo proibidos.", "Execução futura exige aprovação humana, elegibilidade, permissões e limites confirmados.", "Antes de implementar: idempotência, stops, fills parciais, reconciliação, auditoria e kill switch."] },
  roadmap: { title: "Roteiro do projeto", description: "Da observação do mercado à pesquisa reproduzível.", phase: "Entrega inicial · Fases 1–3",
    items: ["Fase 1: arquitetura, regras de segurança e estrutura de processos — implementadas.", "Fase 2: design system e dashboard responsivo — implementados.", "Fase 3: dados públicos Bybit, persistência, candles e indicadores — implementados.", "Fase 4: estratégias, backtests, sinais e validação temporal — próxima etapa.", "Fase 5: Arena e paper trading — planejados.", "Fase 6: carteira e ordens somente leitura — planejadas.", "Fase 7: ampliar testes do motor, segurança e interface a cada entrega."] },
};

export default async function ModulePage({ params }: { params: Promise<{ module: string }> }) {
  const { module } = await params;
  const info = modules[module];
  if (!info) notFound();
  return <main id="main-content" className="page module-page"><Button variant="ghost" asChild><Link href="/"><ArrowLeft size={15} />Voltar ao dashboard</Link></Button><div className="page-heading"><div><h1>{info.title}</h1><p>{info.description}</p></div></div><section className="panel module-plan"><div className="panel-heading"><h2>Escopo e critérios</h2><span className="tag"><LockKeyhole size={12} />{info.phase}</span></div><ol>{info.items.map(item => <li key={item}>{item}</li>)}</ol><div className="module-foot"><span>Este módulo apresenta o escopo planejado. Não há resultados simulados.</span><Link href="/" className="text-link">Consultar mercado <ArrowRight size={14} /></Link></div></section></main>;
}
