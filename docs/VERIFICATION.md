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

## Fase 2.2 · Evidência adicional em 02/11/2026

A auditoria inicial executou a suíte anterior: 71 testes Python passaram. Depois da implementação, `.venv/Scripts/python -m pytest backend/tests -q` passou com **95 testes**, incluindo 24 casos/parametrizações novos. Aviso Starlette/httpx preexistente permanece. `npm run typecheck`, `npm run build` e `pip check` passaram. O Playwright completo, com smoke de backtesting real habilitado, teve **48 testes aprovados e 6 ignorados** (smokes reais anteriores de dashboard e histórico não foram habilitados nesta execução). O smoke real novo passou nos três tamanhos; os testes de regressão offline de dashboard e histórico passaram. Usou-se runner Playwright local, pois Playwright MCP não estava disponível. Sandbox recusou spawn do Chromium com EPERM; a execução foi repetida com permissão para iniciar o processo local.

Foram testados matemática independente dos fills e custos, stops simultâneos conservadores, gaps, Buy & Hold, posição aberta, métricas indefinidas, drawdown, profit factor, arredondamento, risco, saldo, mínimos, warm-up, candles inválidos, causalidade de prefixo das quatro estratégias, alteração futura, resistência prévia, recuperação RSI, persistência, triggers, adulteração, execução cronológica e proteção API. Fixtures são exclusivamente sintéticas e a fixture de teste bloqueia rede. O cenário real usou dataset previamente aprovado e não fez coleta. Os 12 resultados reais (quatro estratégias por três janelas) foram reexecutados com hash idêntico; resultados fora da amostra e premissas em [BACKTESTING.md](BACKTESTING.md).

Na primeira execução real da interface, o proxy rejeitou a origem local porque o hostname interno do Next diferia do endereço do navegador. A validação passou a comparar `Origin` ao `Host` efetivo e a restringir ambos a loopback; o teste também rejeita origem externa. Dois testes sintéticos inicialmente selecionaram o anunciador de rota do Next como alerta; o seletor foi restringido ao alerta da aplicação. Desktop, tablet e celular foram revisados com capturas reais em `artifacts/backtest-{desktop,tablet,mobile}.png`; tabelas possuem rolagem interna e a página não transborda horizontalmente.

Após a suíte completa, foi adicionada a retomada do protocolo a partir de uma execução anterior. Uma primeira tentativa de ler execução e protocolo em paralelo disputou o limitador local; as leituras passaram a ser sequenciais. A suíte específica de Backtesting foi repetida na versão final: **15 passaram**, incluindo reabrir a página, restaurar o protocolo e executar validação com dados reais nas três resoluções. Build e typecheck foram repetidos após o ajuste.

## Ajuste de fingerprint pré-Fase 2.3

Em 02/11/2026, a suíte Python completa passou com **100 testes**, incluindo cinco novos testes de fingerprint: adição de módulo independente, migration e dependência não relevante; mudança em trecho não usado de serviço/configuração; alteração matemática recusada até reiniciar e exigindo outro protocolo; versão de runtime alterada; leitura, imutabilidade, replay legado auditado e recusa de hash ou esquema desconhecido. Não foi alterado o modelo financeiro. A suíte direcionada de backtest/fingerprint passou com 29 testes. O aviso Starlette/httpx preexistente permanece.

Além das fixtures sintéticas, os **12 resultados reais legados** registrados na Fase 2.2 foram reexecutados pelo novo código, sem rede, e todos reproduziram exatamente seus hashes originais. A ponte de compatibilidade cobre somente o fingerprint antigo e o runtime identificados em [BACKTESTING.md](BACKTESTING.md). Nenhuma alteração em resultados ou protocolos existentes foi feita, e não foi criada Arena.

## Fase 2.3A · Arena histórica

Auditoria inicial: Git limpo; **39 testes relevantes** de backtest, fingerprint e segurança passaram. Na entrega, `.venv/Scripts/python -m pytest backend/tests -q` passou com **109 testes**, incluindo nove testes novos da Arena; após acrescentar a guarda de leitura de credenciais, o teste de API afetado passou novamente. O aviso Starlette/httpx existente permanece. `npm run build` e `npm run typecheck` passaram. A regressão Playwright de interface não alterada teve **45 aprovados e 9 ignorados**, correspondentes aos três smoke tests reais opcionais em cada resolução; usou Chromium local em porta alternativa.

As fixtures sintéticas verificam isolamento de capital, condições comuns, janela cronológica, desempate e ordenação Decimal de alta precisão, parâmetros diferentes por estratégia, recusa de protocolos incompatíveis, idempotência, triggers e adulteração de resultados/protocolos vinculados, compatibilidade legada, origem/Host/rotas, ausência de leitura de credenciais, e invariância do treino quando candles futuros mudam. A rede é bloqueada na suíte Python. As regras financeiras e o fingerprint `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62` permaneceram inalterados.

O ensaio offline real usou BTCUSDT 1h já aprovado. O resultado foi reexecutado com o mesmo hash e os quatro protocolos legados existentes foram aceitos em outra competição, preservando os IDs. Dados, hashes, custos e advertências de amostra pequena em [ARENA.md](ARENA.md). Sem download, conta privada ou ordens reais; não foi implementado frontend ou paper contínuo.

## Fase 2.3B · Interface da Arena

Em 02/11/2026, a aplicação recebeu a página `/arena` e proxy Next específico, sem alterações no backend financeiro, fingerprint ou datasets. `npm run typecheck` e `npm run build` passaram; `.venv/Scripts/python -m pytest backend/tests -q` teve **109 testes aprovados**, com o aviso Starlette/httpx já existente. A regressão Playwright completa teve **72 aprovados e 9 ignorados**: os testes opcionais reais anteriores de dashboard, histórico e backtesting não foram habilitados. Os novos testes da Arena incluem o smoke real em desktop 1440×1000, tablet 820×1180 e celular 390×844, com API própria em loopback e dataset BTCUSDT aprovado já no banco. Não se chamou a Bybit nem conta privada. Usou-se o runner Playwright local; Playwright MCP não estava disponível.

Os cenários sintéticos isolados cobrem seleção de dados, parâmetros das quatro estratégias, congelamento, execução, empate preservado, métricas indefinidas, aviso de amostra, curvas e legenda, troca rápida de janelas, histórico sem POST, restauração de configuração, 409, 429, backend indisponível, catálogo vazio e timeout. No timeout, os testes verificam consulta imediata, bloqueio enquanto ocupado, recuperação de resultado persistido e ausência de reexecução automática. O smoke real conferiu curvas, integridade visual, ausência de overflow da página, rejeição de origem externa e inexistência de rota de ordem.

Em 03/11/2026, a suíte específica da Arena foi repetida após o tratamento adicional de resposta inválida e erro HTTP 500 na execução: **33 testes passaram**, incluindo os três smoke tests reais locais. Esses casos também exigem consultar o resultado antes de liberar outra tentativa; nenhum POST é repetido automaticamente. Build e typecheck passaram após os ajustes.

Capturas reais abertas e revisadas: [desktop](../artifacts/arena-desktop.png), [tablet](../artifacts/arena-tablet.png) e [celular](../artifacts/arena-mobile.png). São artefatos locais ignorados pelo Git; tabelas largas têm rolagem interna. Não houve instalação das referências visuais nem criação de paper trading, conta privada ou execução real. O processamento continua síncrono, sem progresso percentual; limitações de concorrência e proposta para 2.3C em [ARENA.md](ARENA.md).

## Fase 2.3C1 · Fundação paper

Em 07/11/2026, a auditoria inicial encontrou Git limpo e **38 testes relevantes** de backtest, fingerprint e Arena aprovados. Na entrega, `.venv/Scripts/python -m pytest backend/tests -q` passou com **124 testes**, incluindo **15 casos do ledger** com fixtures sintéticas isoladas. O aviso preexistente Starlette/httpx permanece. `npm run build` e `npm run typecheck` passaram; a regressão de interface existente teve **75 testes Playwright aprovados e 12 smoke tests opcionais ignorados**. Não foi alterado frontend.

Os testes do ledger verificam saldos, custo de aquisição, PnL, taxas, marcação e estado pausado; idempotência e isolamento; tentativas concorrentes com saldo limitado; entrada sem float, precisão e arredondamento independentes do contexto; recusa de short/margem, referências inválidas e sequência temporal regressiva; rollback forçado entre evento e checkpoint, retomada, triggers e adulteração de eventos, metadata e checkpoint. A CLI foi exercitada em banco temporário, com teste da recusa de `LIVE_TRADING_ENABLED=true`. Testes Python bloqueiam rede. A execução do app não fornece dados sintéticos.

Após adicionar o módulo e a migration, o fingerprint financeiro permaneceu `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62` e **12 de 12 replays legados reais** foram verificados com hashes idênticos. A cadeia SHA-256 e o checkpoint detectam corrupção, mas não constituem assinatura contra quem possa reescrever toda a base; limitações e comandos em [PAPER.md](PAPER.md). Nenhum worker contínuo, conta privada, credencial ou ordem real foi implementado.

## Fase 2.3C2A · Monitor de candles e sinais

O Git estava limpo no início. Em 07/11/2026, a suíte Python completa passou com **150 testes**, incluindo **26 casos do monitor**. O aviso preexistente Starlette/httpx permanece. Build e typecheck passaram; a regressão Playwright existente teve **75 aprovados e 12 smoke tests opcionais ignorados**, sem mudanças no frontend. O fingerprint financeiro permaneceu `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`, e **12 de 12 replays legados reais** mantiveram os hashes.

As fixtures sintéticas, isoladas e sem rede, cobrem as quatro estratégias e prefixos causais, candles abertos, contiguidade, warm-up, dados obsoletos e relógio futuro, hash de snapshot/dataset, conflito e imutabilidade, idempotência por bot/configuração/candle, concorrência, reinício, lacunas perdidas, troca de snapshot ou janela durante avaliação, arredondamento, CLI e recusa de `LIVE_TRADING_ENABLED=true`. Um teste compara eventos e saldo paper antes/depois da avaliação concorrente. No banco local real, o `--once` retornou `STALE_SNAPSHOT`; o conteúdo das três tabelas paper permaneceu idêntico. Nenhum snapshot novo foi coletado nem sinal obsoleto emitido. Detalhes e comando em [MONITOR.md](MONITOR.md).

Novos arquivos: `backend/cryptolab/engine/{contracts,strategies,backtest}.py`, `backend/cryptolab/research/{__init__,service,api,cli}.py`, `backend/cryptolab/migrations/003_research.sql`, `backend/tests/test_backtest.py`, `apps/web/src/app/backtesting/page.tsx`, `apps/web/src/app/api/research/[...path]/route.ts`, `apps/web/src/components/{backtesting,equity-chart}.tsx`, `apps/web/src/lib/research.ts`, `tests/ui/backtesting.spec.ts`, `docs/BACKTESTING.md`, `docs/backtest-example.json`. Alterados: `AGENTS.md`, `README.md`, `backend/cryptolab/api.py`, `backend/tests/test_api_storage.py`, CSS e navegação/roadmap do frontend, `docs/ARCHITECTURE.md`, `docs/PHASE_2_2.md` e este arquivo. Sem novas dependências. Nenhuma ordem real, conta privada, margem, futuros ou alavancagem foi adicionada.

## Hardening 2.3C2B1 · 08/11/2026

O Git estava limpo na auditoria do commit `0ad94f1`. Antes da mudança, os 20 testes existentes do planejador passaram. Depois do ajuste, `.venv/Scripts/python -m pytest backend/tests -q` passou com **192 testes**, incluindo cenários sintéticos de venda redutora com exposição acima do limite, compra incompatível e dimensionamento pós-custos, HOLD com excesso, marcação obsoleta, Buy & Hold sem stop, vínculos conflitantes e comparação integral das três tabelas do ledger. A regressão direcionada de backtest e fingerprint teve **29 testes aprovados**. O aviso de depreciação Starlette/httpx permanece.

`npm run typecheck` e `npm run build` passaram. A regressão Playwright teve **75 aprovados e 12 smoke tests opcionais ignorados**, usando Chromium local. Em cópia temporária do banco local, **38 de 38 replays históricos**, incluindo **14 de 14 legados**, mantiveram os IDs originais. O fingerprint financeiro permaneceu `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`; não houve alteração do motor financeiro nem de protocolos existentes. Os testes do planejador usam banco isolado, bloqueiam rede e verificam que a consulta não modifica `paper_wallets`, `paper_events` ou `paper_heads`.

O planejador é versionado como `cryptolab-paper-planner/2`, continua somente leitura e não cria fills nem ordens. A política sem stop para Buy & Hold foi especificada, mas a entrada permanece bloqueada até implementação futura. Os testes de vínculos demonstram uma limitação real: arquivos de risco divergentes podem gerar propostas alternativas com a mesma chave de decisão, pois vínculos e decisões ainda não são persistidos. O desenho de unicidade e marcação verificável para a próxima fase está em [PAPER_PLANNER.md](PAPER_PLANNER.md); não autoriza executor nem escrita no ledger nesta fase. Não foram acessadas contas privadas.
