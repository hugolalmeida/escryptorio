# Evidências de verificação

Data: 01/11/2026. Ambiente Windows, Node v22.13.0, npm 11.0.0 e Python 3.10.11. Versões exatas de dependências em `package-lock.json` e `backend/requirements.lock.txt`.

## Resultado final

| Verificação | Resultado |
| --- | --- |
| `npm run build` | Passou: Next.js 16.4.3, compilação e checagem TypeScript. |
| `npm run typecheck` | Passou. |
| `python -m pytest backend/tests -q` na venv | **28 passaram**. |
| `python -m pip check` na venv | Sem dependências quebradas. |
| `CRYPTOLAB_LIVE_SMOKE=1 npm run test:ui` | **21 passaram**, Chromium, 1440×1000, 820×1180 e 390×844. |
| `python -m cryptolab.worker --once` na venv | Oito snapshots reais coletados e persistidos, saída 0. |
| `scripts/dev.ps1 -SkipInstall` | API, worker e Next iniciaram; dashboard e proxy HTTP 200, ETHUSDT real e `stale=false`. |
| Encerramento de `dev.ps1` | Ctrl+C; portas 8000 e 3100 sem listeners após encerramento. |

O serviço real foi verificado em toda a cadeia Bybit → worker → SQLite → FastAPI → Next → canvas. Os smoke tests verificaram BTCUSDT e ETHUSDT em todos os quatro intervalos, preço positivo, mercado Spot, 300 candles, histórico fechado, timestamps frescos e `live_trading_enabled=false`. Não foram enviadas ordens ou usadas credenciais privadas.

O Playwright MCP não está disponível na sessão. Foi usado o runner oficial Playwright com Chromium local; nenhuma inspeção é atribuída a MCP. As capturas finais de dados reais foram abertas e inspecionadas visualmente:

- [Desktop](../artifacts/dashboard-desktop.png)
- [Tablet](../artifacts/dashboard-tablet.png)
- [Celular](../artifacts/dashboard-mobile.png)

As capturas e o relatório HTML em `playwright-report/index.html` são artefatos locais ignorados pelo Git, gerados novamente no smoke real. A revisão visual confirmou composição, legibilidade, gráfico, estado de coleta e navegação. Textos auxiliares foram ampliados após a primeira inspeção.

## Cobertura relevante

Python: SMA/EMA de referência; RSI Wilder de referência; ATR com gap; warm-up; série constante; extremos; contexto Decimal independente; invariância de prefixo; candle aberto excluído; ordenação e gaps; OHLC inválido e não finitos; hash por conteúdo e dataset somente fechado; migrations idempotentes; precisão na persistência; freshness e relógio futuro; validação de símbolo/período/Host; ausência de rotas de ordem; recusa de flag live; falhas/rate limit/resposta de mercado errado; retenção de snapshot após erro; cliente sem credenciais e somente categoria Spot.

Playwright: seis cenários independentes com fixtures sintéticas de teste, repetidos em três tamanhos, mais um smoke real por tamanho. Exercita troca de ativo e período, linha/candles, médias, atualizar, erro inicial, snapshot antigo, falha após sucesso sem alterar horário original, navegação, bloqueio de execução, link de pular conteúdo e Escape no menu móvel. Sem erros JavaScript e sem overflow horizontal da página nos cenários de mercado e erro. A tabela tem rolagem interna intencional.

Na primeira execução, a porta 3000 já pertencia a outro projeto. A configuração foi corrigida para 3100, com servidor exclusivo nos testes e preflight de portas no script. Um controle somente com ícone perdeu o nome no celular e recebeu `aria-label`; o seletor de alertas foi restringido para não confundir o anúncio de rotas do Next. As verificações finais passaram após essas correções.

## Limites da evidência

Há um aviso de depreciação do Starlette ao usar TestClient com httpx 0.28.1; os testes passam, mas a migração do cliente de teste deve ser avaliada na próxima atualização de dependências. Não foi suprimido.

Não foram validados backtests, métricas da Arena, operações paper ou conta privada, porque esses módulos ainda não foram implementados. Freqtrade teve compatibilidade e manutenção avaliadas documentalmente, sem instalação ou integração funcional. Não há teste de execução real, nem capacidade de executá-la. Acesso público à API não comprova elegibilidade de conta.

Os processos de teste foram encerrados. Para usar a aplicação, iniciar pelo README. As exclusões legadas preexistentes foram preservadas; nenhuma alteração foi commitada ou publicada.

## Fase 2.1 · Evidência adicional em 01/11/2026

O registro anterior descreve a entrega inicial, posteriormente commitada em `3545b76`. A Fase 2.1 foi implementada sobre ela, sem reconstrução de frontend/backend e sem novas dependências de runtime.

| Verificação | Resultado |
| --- | --- |
| `.venv/Scripts/python -m pytest backend/tests -q` | **71 passaram**: 28 anteriores e 43 novos casos/parametrizações de histórico. |
| `npm run build` | Passou com `/history` e proxy histórico, incluindo TypeScript. Um EPERM do sandbox na criação de subprocesso exigiu repetir a compilação com permissão de execução; não houve mudança de proteção do app. |
| Playwright com smoke dashboard e histórico | **39 passaram**, Chromium desktop 1440×1000, tablet 820×1180 e celular 390×844. |
| CLI pública real BTCUSDT 1h | 1.464 candles, duas páginas, período UTC 01/09–01/11/2026, 100% de cobertura, zero lacunas, dataset aprovado por SHA-256. |
| CLI pública real ETHUSDT 15m | 2.976 candles, três páginas, UTC 01/10–01/11/2026, 100%, zero lacunas. |
| CLI pública real BTCUSDT 4h | 366 candles, UTC 01/09–01/11/2026, 100%, zero lacunas. |
| CLI pública real ETHUSDT 1d | 669 candles, UTC 01/01/2025–01/11/2026, 100%, zero lacunas. |
| Repetição BTCUSDT 1h | Mesmo job/hash, nenhuma nova página/tentativa ou acesso à rede. |
| Reader/CLI offline | Recorte BTCUSDT de três candles verificado contra hash completo, sem rede. |
| Proxy → API → fila → worker histórico | Recorte BTCUSDT de 24 candles aprovado usando arquivo validado, zero novas páginas de rede. |

Total real persistido: **5.475 candles únicos**, quatro faixas completas e um quinto dataset de 24 candles reutilizados. Hashes, exemplos e limitações em [HISTORY.md](HISTORY.md).

Os novos testes cobrem paginação acima de 1.000 candles, quatro timeframes, ordenação, duplicatas iguais/conflitantes, gaps, respostas vazias, exclusão de candle aberto, alinhamento, não finitos, precisão e normalização Decimal sem arredondamento, backoff limitado, preservação após erro, Ctrl+C e retomada, idempotência, períodos sobrepostos, leases concorrentes/expirados, pausa entre páginas, rollback integral de página em conflito, hash e triggers de imutabilidade, adulteração externa, recortes, origem HTTP e coexistência com snapshots. As fixtures são sintéticas e identificadas; testes Python bloqueiam rede por fixture autouse.

Os testes de interface cobrem formulário UTC, seleção de ativo/timeframe, solicitação, fila, pausa/retomada, gaps, catálogo, prévia e hash completo, recusa de hash inválido, período desalinhado, indisponibilidade da API e ausência de overflow da página. Os testes anteriores do dashboard continuam passando, incluindo seus oito snapshots reais e bloqueio de execução. A execução final não precisou alterar Host, CORS, flag live ou permissões de conta.

As portas padrão 8000/3100 tinham instâncias existentes. Foram preservadas; o backend de QA usou 18000 e o servidor exclusivo Playwright 13100, ambos em loopback. O coletor público do dashboard permaneceu atualizando durante os testes. Apenas processos iniciados para esta validação são encerrados na entrega. Para usar a nova fase nas portas padrão, reiniciar a instância anterior para carregar as novas rotas e iniciar o worker histórico.

Capturas reais abertas e avaliadas:

- [Histórico desktop](../artifacts/history-desktop.png)
- [Histórico tablet](../artifacts/history-tablet.png)
- [Histórico celular](../artifacts/history-mobile.png)

Os artefatos são locais/ignorados pelo Git; o relatório HTML é regenerado a cada suíte. O Playwright MCP segue indisponível; usamos o runner oficial local. O aviso Starlette/httpx já registrado continua presente, sem impedir os testes.

Sem estratégias, backtests, paper trading, credenciais privadas, ordens ou integrações de margem/futuros. Nenhuma publicação foi realizada. Plano da próxima etapa em [PHASE_2_2.md](PHASE_2_2.md).
