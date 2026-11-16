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

## Fase 2.3C2B2A · Vínculos e decisões · 08/11/2026

A auditoria encontrou o Git limpo e **62 testes direcionados anteriores aprovados**. Após a implementação, `.venv/Scripts/python -m pytest backend/tests -q` passou com **216 testes**, incluindo testes da migration, vínculos, decisões, SHA-256, projeções e checkpoints, mercado obsoleto, carteira pausada, sinal legado ou histórico, HOLD, mudança de snapshot ou ledger, expiração e relógio regressivo. Os cenários usam fixtures sintéticas isoladas com rede bloqueada. O aviso preexistente Starlette/httpx permanece.

Os testes exercitaram concorrência entre três processos, duas ativações simultâneas, idempotência, rejeição de decisão conflitante pela constraint SQLite, desativação auditável, falha e rollback, encerramento abrupto real do processo antes do commit e retomada após reinício. Verificaram a imutabilidade SQL, adulteração e o conteúdo integral de `paper_wallets`, `paper_events` e `paper_heads` antes/depois das operações. Um ensaio sintético adicional registrou vínculo e decisão BUY, confirmou o mesmo ID na repetição, obteve `DECISION_CONFLICT` para outra política no mesmo candle e confirmou ledger inalterado e `execution_enabled=false`.

`npm run typecheck` e `npm run build` passaram; a regressão Playwright teve **75 aprovados e 12 smoke tests opcionais ignorados**, usando Chromium local. Em cópia temporária do banco local, **38 de 38 replays históricos**, incluindo **14 de 14 legados**, reproduziram seus IDs. O fingerprint financeiro permaneceu `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`.

A migration 008 cria somente tabelas de vínculo/decisão, eventos, projeções e checkpoint de relógio; não altera dados do ledger, monitor ou backtesting. O planner passou para `cryptolab-paper-planner/3` para incluir hash do snapshot integral. Como decisões e vínculos agora são persistidos, a limitação de unicidade descrita na seção anterior é resolvida para **decisões registradas**; consultas isoladas ao planner continuam sem persistência. Expiração observada é persistida e retrocessos do relógio são recusados, mas retrocessos nunca observados enquanto o processo estava desligado exigem relógio confiável. Não há executor, fills, ordens, acesso privado ou consumo de decisões. Detalhes em [PAPER_BINDINGS.md](PAPER_BINDINGS.md).

## Fase 2.3C2B2A.1 · Recuperação idempotente · 08/11/2026

A auditoria encontrou o Git limpo e a suíte Python anterior passou com **216 testes**. Após a alteração, `.venv/Scripts/python -m pytest backend/tests -q` passou com **223 testes**; a suíte específica de decisões também passou. Permanece o aviso de depreciação Starlette/httpx. `npm run typecheck` e `npm run build` passaram; Playwright teve **75 aprovados e 12 smoke tests opcionais ignorados**, em Chromium local.

O teste sintético encerrou um processo após o commit sem entregar resposta, atualizou o ticker no mesmo candle e recuperou o ID original usando dois processos concorrentes, sem recalcular o preço. Outros casos cobriram alteração de ledger, pausa, vínculo desativado, invalidação, expiração, conflito por hash ou sinal diferente, adulteração de payload/checkpoint, crash antes do commit e relógio regressivo. O conteúdo das três tabelas financeiras foi comparado antes e depois das recuperações. Em ensaio sintético adicional, o processo saiu com código 74 após o commit; o ID salvo e recuperado foi `5a175817dd57d9ac2c2000d7e9f9375b4a21346508c128b90ef5ffe90aae6345`, a tentativa com outro hash retornou `DECISION_CONFLICT` e o ledger permaneceu igual.

Em cópia temporária do banco local, **38 de 38 replays históricos**, incluindo **14 de 14 legados**, mantiveram os IDs. O fingerprint financeiro permaneceu `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. O recibo recuperado informa estado e metadados atuais, mas não aprova operação e exige revalidação futura. Não houve alteração de migrations, tabelas financeiras, motor, sinais ou resultados históricos; não foram criados fills, ordens, execução ou acesso privado. A limitação anterior de relógio não observado durante desligamento permanece; política e contrato em [PAPER_BINDINGS.md](PAPER_BINDINGS.md).

## Fase 2.3C2B2B · Simulação exclusivamente virtual · 08/11/2026

A auditoria inicial encontrou Git limpo e **93 testes direcionados aprovados**. Antes dos fills, a Etapa A foi validada com **56 testes** de marcação, proveniência, decisão, ledger, concorrência e regressão. Após a Etapa B, `.venv/Scripts/python -m pytest backend/tests -q` passou com **261 testes**, incluindo falha na gravação da evidência de marcação, ausência de preço público, bloqueio de Buy & Hold e ausência de acesso a credenciais privadas ou rede. O aviso Starlette/httpx preexistente permanece. `npm run typecheck` e `npm run build` passaram; Playwright teve **75 aprovados e 12 smoke tests opcionais ignorados**.

Os testes sintéticos, em bancos temporários e com rede bloqueada, cobrem BUY/SELL, HOLD, posição e marcação, configuração, sinais, relógio, expiração, dados obsoletos ou futuros, lacunas, limites, custos, arredondamento, float rejeitado, stop/target informativos, venda parcial, integridade, concorrência em três processos, conflito de chave, crash real antes e depois do commit, retomada, rollback do fill ou da marca quando o sidecar falha, e reconciliação. Os cálculos de saldo e PnL foram comparados com fórmulas independentes. As tabelas financeiras do banco local real não foram usadas para simular operações.

Em um ensaio **sintético** separado, capital inicial `1000` resultou em compra de `1.708` unidades a `180.09`, fee `0.30759372`, slippage `0.15372` e saldo `692.09868628`. A marca sintética teve preço `150` e snapshot SHA-256 `df8e0d4629dca132af84b89143f8d58867072f54e79461b1d266a962cfcfa6b1`. A venda virtual a `149.92` teve fee `0.25606336`, slippage `0.13664`, saldo final `947.90598292`, posição `0` e PnL realizado `-52.09401708`. A repetição retornou o mesmo fill, outra chave gerou `EXECUTION_CONFLICT`, e a reconciliação encontrou uma marca e duas execuções íntegras. Esses valores são fixtures, não preços ou operações reais.

Em cópia temporária do banco local, **38 de 38 replays históricos**, incluindo **14 de 14 legados**, mantiveram seus IDs. O fingerprint financeiro permaneceu `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`; migrations 001–008 e o motor não foram alterados. A migration 009 acrescenta sidecars e constraints. `PAPER_SIMULATION_ENABLED` permanece desabilitado por padrão, e o comando mutável também exige `--paper`; `LIVE_TRADING_ENABLED` permanece `false`. Não há conta privada, ordem real ou worker executor. Limitações de liquidez, relógio, Buy & Hold e proteção hipotética em [PAPER_EXECUTION.md](PAPER_EXECUTION.md).

## Fase 2.3C2B2C · Validação operacional isolada · 09/11/2026

O Git estava limpo no commit-base `6d86bbe44b4338766285a1ae5307e8ece051715d`; **84 testes pertinentes** passaram antes das mudanças. A suíte completa passou com **266 testes** e o aviso preexistente Starlette/httpx; os cinco testes novos do diagnóstico também passaram isoladamente. Typecheck e build passaram; Playwright teve **75 aprovados e 12 opcionais ignorados**. A primeira tentativa Playwright no sandbox retornou `spawn EPERM`; a repetição fora da restrição de processos passou. Não houve alteração no frontend.

A coleta Bybit pública passou fora da restrição de rede do sandbox, com oito snapshots em banco novo. Monitor retornou sinal atual íntegro e idempotente; planner retornou HOLD, decisão informativa foi persistida e a reconciliação permaneceu válida, sem marcas ou execuções. Após envelhecer o snapshot, o monitor retornou `STALE_SNAPSHOT`. Os detalhes, hashes, caminho do banco e distinção entre dados públicos e testes sintéticos estão em [PAPER_OPERATIONAL_VALIDATION.md](PAPER_OPERATIONAL_VALIDATION.md). **NO_ELIGIBLE_TRADE** não valida ciclo de fill com dados públicos.

Em cópia temporária feita via backup SQLite de origem somente leitura, **38 de 38 replays**, incluindo **14 legados**, tiveram IDs idênticos e fingerprint `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Após imprimir o resultado, a limpeza automática da cópia temporária falhou por bloqueio de arquivo Windows, fazendo esse processo sair com código 1; o banco original não foi alterado. Não houve ordens reais, conta privada ou fill paper neste ensaio.

## Fase 2.3C3A · Dashboard paper somente leitura · 13/11/2026

O Git estava limpo no commit-base `a4c8aec3602c6d67dc1a37e0c18769da4255c570`; **86 testes relevantes** passaram antes da implementação. A suíte completa passou com **273 testes** e o aviso preexistente Starlette/httpx. Typecheck e build passaram. Playwright completo teve **81 aprovados e 12 opcionais ignorados**; após o último ajuste visual, os seis testes paper passaram novamente em desktop, tablet e celular. A primeira execução foi iniciada durante o build e não encontrou artefatos completos; a seguinte identificou um seletor de alerta ambíguo no teste, corrigido antes da execução aprovada.

Os testes sintéticos com banco isolado conferem carteira sem posição, posição sem marca verificável, venda parcial, custo contábil e PnL realizado, paginação, fill legado, fill com evidência, decisão expirada derivada sem evento, checkpoint adulterado, sidecar obrigatório ausente, banco ausente sem criação, validação de rotas e comparação das tabelas financeiras antes e depois dos GETs. A interface testada usa respostas sintéticas interceptadas. Em leitura adicional do banco fictício preservado da fase anterior, overview, sinais e decisões retornaram 200, com saldo fictício 1000 e zero fills.

Em cópia temporária criada por backup SQLite de origem somente leitura, **38 de 38 replays históricos**, incluindo **14 legados**, mantiveram seus IDs; fingerprint financeiro `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Nenhum motor ou migration foi alterado. Limites da verificação, paginação e curva de observações em [PAPER_DASHBOARD.md](PAPER_DASHBOARD.md). Nenhuma ordem ou operação foi criada pelas consultas.

## Fase 2.3C3A.1 · Hardening e fluxo assistido · 14/11/2026

O Git iniciou limpo em `d7ec4f11c3032bebbd938e1b5d1289b9dd9c00bd`; sete testes do dashboard passaram na linha de base. O ZIP fornecido foi lido sem extrair ou executar scripts; não havia arquivo de licença identificado. Seis workflows locais de redação própria e suas limitações estão em [AI_DEVELOPMENT_WORKFLOW.md](AI_DEVELOPMENT_WORKFLOW.md). Uma verificação documental confirmou nomes e frontmatter das seis skills; ela não é teste financeiro.

A suíte final `.venv/Scripts/python -m pytest backend/tests -q` passou com **277 testes**, com o aviso preexistente Starlette/httpx; typecheck e build passaram. A suíte Playwright completa passou com **87 testes e 12 opcionais ignorados**; após acréscimo do cenário de refresh concorrente e ajuste de apresentação, os **15 testes paper** passaram em desktop, tablet e mobile. As fixtures são sintéticas e não são fallback do aplicativo.

Os testes novos verificam, usando Decimal e marcações sintéticas com sidecar, patrimônio, exposição, custo médio, PnL e taxas já incluídas, dados obsoletos, marca anterior a fill, agregação com dados incompletos e evidência adulterada. Compararam tabelas financeiras antes/depois dos GETs. Os testes de interface cobrem falha de detalhes, recuperação, troca rápida e refresh concorrente. A verificação de `WALLETS_VERIFIED` permanece limitada aos ledgers consultados.

Em backup SQLite temporário de origem somente leitura, **38 de 38 replays**, incluindo **14 legados**, mantiveram os IDs; o fingerprint permanece `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Não foram alterados motor financeiro, migrations, eventos históricos ou rotas mutáveis. Medição pós-mudança do overview em uma carteira fictícia e limitações em [PAPER_DASHBOARD.md](PAPER_DASHBOARD.md); não há comparação antes/depois ou ganho comprovado.

## Fase 2.3C3B · Observabilidade operacional · 14/11/2026

O repositório estava limpo em `c2340077d9c9004e8e66ecf51a3029f7b54ea134`; **26 testes relevantes** passaram antes das mudanças. A suíte Python completa passou com **283 testes** e o aviso preexistente Starlette/httpx. Em seguida foi acrescentado um caso de evidência ausente; os **7 testes da API operacional** passaram isoladamente com esse caso. Typecheck e build passaram. Playwright completo passou com **99 aprovados e 12 opcionais ignorados**; após links locais de navegação, **24 testes paper** passaram em desktop, tablet e celular. Testes de UI usam exclusivamente dados sintéticos interceptados.

A API usa transação somente leitura e IDs estáveis para alertas derivados; testes comparam tabelas financeiras, monitor e coleta antes e depois dos GETs. Os cenários verificados incluem ausência, frescor, obsolescência, timestamp futuro, erro de coleta, ledger e dataset adulterados, checkpoint sem sinal, decisão expirada e evidência ausente. A interface separa sinais e decisões e mantém a carteira selecionada identificável em erro. O resumo financeiro é ocultado quando a observação operacional é indisponível ou aponta integridade degradada. A ausência de heartbeat é apresentada como UNKNOWN.

Em cópia temporária aberta a partir do banco histórico em modo somente leitura, **38 de 38 replays**, incluindo **14 legados**, mantiveram seus IDs. O fingerprint financeiro permanece `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. A nova consulta foi medida em banco sintético vazio, dez chamadas locais, mediana 27,36 ms e máximo 378,46 ms; sem baseline comparável ou afirmação de ganho. Limites, estados e alertas em [PAPER_OPERATIONS.md](PAPER_OPERATIONS.md). Não foram alterados motor, migrations, contratos de execução ou tabelas financeiras.

## Fase 2.3C3C · Estudo documental de pesquisa com IA · 14/11/2026

O Git iniciou limpo na branch `main` em `9842db0a3d5b6a52b143be056898f99ded459b56`. Foram consultados documentos e contratos do projeto e as páginas públicas dos três repositórios de referência e licenças; a API GitHub de metadados não ficou acessível e os SHAs externos não foram fixados. Não foram instaladas dependências, executados scripts externos, chamadas de modelos, acessadas contas privadas ou implementadas capacidades de agentes.

A checagem documental final percorreu **16 arquivos Markdown** e verificou **42 links locais**, sem caminhos ausentes; uma busca limitada de padrões de segredos não encontrou ocorrências e `git diff --check` passou. Essa busca não equivale a uma auditoria completa de segredos. O cálculo local de `replay_fingerprint()` retornou `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Alterações desta fase são apenas documentação e handoff; não houve alteração de engine, ledger, rotas, dependências ou migrations. Não executamos as suítes Python/Playwright nem replays nesta fase documental: os **38 replays / 14 legados** acima pertencem à fase anterior e não são revalidação atual.

O estudo e os ADRs em [AI_RESEARCH_ARCHITECTURE.md](AI_RESEARCH_ARCHITECTURE.md) são propostas não implementadas. Referências à segurança descrevem controles a validar no futuro, não garantias do sistema existente.
# Verificação 2.3D1 — evidência determinística

Referência inicial `6faa148dbd217b9df2362d0ba3f493b7f7f6e628`. Baseline `.venv/Scripts/python -m pytest backend/tests -q`: **284 aprovados**, um aviso preexistente Starlette/httpx. Após a implementação, a suíte completa registrou **295 aprovados**, mesmo aviso; os 11 testes da evidência passaram também isoladamente após o reforço de validação. Incluem fixture sintética, comparação do dump do SQLite isolado antes/depois, identidade, fronteira temporal, adulteração, campos desconhecidos, origem e manifesto. Não demonstram exaustivamente todos os casos adversariais da especificação, nem proteção contra alteração concorrente maliciosa do diretório de exportação.

O fingerprint financeiro calculado foi `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Em backup temporário criado a partir do banco em modo somente leitura, **38/38 replays**, incluindo **14 legados**, mantiveram os IDs. O processo de replay terminou com código 1 após imprimir o resultado porque a limpeza automática encontrou arquivo bloqueado no Windows; a cópia temporária foi removida após o encerramento. A CLI `build` e `verify` foi executada com dataset histórico local e bundle temporário: ambas saíram com código 0 e `UNVERIFIED_POINT_IN_TIME`. A consulta local registrou cinco datasets, máximo de 2.976 candles. Não houve comparação antes/depois das tabelas do banco real: a garantia de ausência de mutação foi testada em banco sintético isolado e a origem real foi aberta em modo somente leitura.

Nenhum frontend foi alterado, portanto build, typecheck e Playwright não foram repetidos nesta fase backend/documentação. Não foram exercitados todos os cenários adversariais solicitados, benchmark no limite de 100.000 candles, teste formal de corrida de symlink nem prova de autenticidade da fonte. Não há garantia PIT nem validação de teses, IA, ordens ou operações paper. Ver [implementação](AI_EVIDENCE_IMPLEMENTATION.md).
# Verificação 2.3D2 — claims e backtest congelado

Baseline `c97f00ab61a61616c6a0fbb834c8e36fc88dcfc9`: 11 testes de evidência aprovados. A suíte completa `.venv/Scripts/python -m pytest backend/tests -q` teve **320 aprovados** e um aviso Starlette/httpx preexistente; após o último ajuste das dimensões de validação foram executados **36 testes direcionados**, todos aprovados. Os testes cobrem tipos inválidos/NULL no SQLite, limite de profundidade, contratos fechados, valor, unidade, referência, PIT, métricas e adulteração de bundle.

Fingerprint financeiro `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Em backup SQLite temporário criado de origem somente leitura, **38/38 replays** reproduziram os IDs, dos quais 14 eram legados. O processo terminou com código zero e a cópia foi removida depois de fechar as conexões. `build-backtest` e `verify` foram exercitados com resultado local existente, sem rede e com saída temporária; ambos terminaram com código zero e PIT desconhecido. A comparação integral antes/depois de banco foi feita em fixture sintética isolada; o banco real foi aberto em leitura, mas suas tabelas não foram comparadas integralmente.

O conjunto adversarial não é exaustivo: não há benchmark de 100.000 candles, teste formal de corrida com substituição concorrente de symlinks, verificação de assinatura externa ou recálculo independente de métricas. O bundle v1 foi testado com fixtures sintéticas; não houve ensaio com bundle v1 exportado na fase anterior. A nova limitação de profundidade também pode rejeitar um v1 anteriormente aceito com estrutura excepcionalmente profunda; compatibilidade universal não foi comprovada. Sem alteração frontend, build e Playwright não foram repetidos. Mais detalhes em [AI_CLAIM_VALIDATION.md](AI_CLAIM_VALIDATION.md).
# Verificação 2.3D2.H1 — hardening de evidências

Referência inicial `2816d67c9ee919f098244d4952447ae4f7f1de2c`: baseline dos quatro arquivos de evidências com **36 aprovados**. A suíte completa `.venv/Scripts/python -m pytest backend/tests -q` registrou **346 aprovados**, um aviso Starlette/httpx preexistente; depois foram acrescentados casos independentes aos testes novos. A execução direcionada dos cinco arquivos de evidências teve **70 aprovados e um ignorado**, e a última execução de `test_evidence_h1.py` teve **34 aprovados e um ignorado**. O Windows recusou a criação do symlink para o teste, que não comprova o comportamento real de links neste ambiente.

O v1 original `c97f00a` gerou fixtures sintéticas com IDs e bytes fixos. O código `2816d67` rejeitou fixture sintética de 70 níveis; o código atual a aceita, preservando seu hash. O v1 atual tem limite 256, portanto não se declara compatibilidade universal. A CLI seleciona a versão pelo manifesto estrito; foram testados v1, v2, troca de versão, arquivo adicional, argumentos inválidos e falha simulada de fsync. Ver matriz e casos não testados em [AI_EVIDENCE_HARDENING.md](AI_EVIDENCE_HARDENING.md).

Fingerprint financeiro: `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Em backup temporário de origem SQLite somente leitura, **38/38 replays**, incluindo **14 legados**, preservaram IDs; comando e limpeza terminaram com código zero. As comparações de estado financeiro antes/depois são de banco sintético; não se comparou integralmente o banco pessoal. Sem mudanças frontend, build, typecheck e Playwright não foram repetidos.

Não foram comprovados: ausência de corridas com processo hostil que controla o mesmo diretório, autenticidade externa por SHA, compatibilidade com bundle real não localizado, desempenho no limite de 100.000 candles ou cobertura adversarial integral. Não houve alterações de engine, estratégias, migrations, ledger, ordens ou integração de IA.

# Verificação 2.3D3A · contexto e mock supervisionado · 15/11/2026

## Baseline e comandos executados

Branch main, HEAD inicial `22f59e8dc01e1febd358a7dce3c332f4dd7d8cbc`, árvore limpa e diff vazio contra a referência solicitada. Foram executados `git status -sb`, `git rev-parse HEAD`, `git log -5 --oneline` e `git diff 22f59e8dc01e1febd358a7dce3c332f4dd7d8cbc --stat`. A identidade restrita recusou Git por proprietário divergente e a venv por acesso ao Python base. As verificações foram repetidas com a identidade proprietária, sem mudar configuração global do Git.

| Execução | Resultado realmente observado |
| --- | --- |
| `.venv/Scripts/python -m pytest backend/tests -q` inicial | 354 passed, 1 skipped, 1 warning, 96,91 s |
| `pytest backend/tests/test_ai_boundary.py -q` primeira execução | 51 passed e 17 failed, 47,95 s. Fixtures passavam ambiente vazio no Windows, resultando em WORKER_UNAVAILABLE |
| Mesmo arquivo após SystemRoot explícito nas fixtures | 68 passed, 42,86 s |
| Mesmo arquivo após testes adicionais de minimização/contabilidade | 71 passed, 44,58 s |
| `.venv/Scripts/python -m pytest backend/tests -q` após implementação | 427 passed, 1 skipped, 1 warning, 148,27 s |
| Execução final direcionada abaixo, após reforço do gateway | 143 passed, 1 skipped, 1 warning, 60,14 s |
| `pytest backend/tests/test_evidence_h1.py -k symlink -q -rs` | 1 skipped, 34 deselected, 0,73 s. Windows recusou criação de symlink |
| Compilação `compile()` dos fontes novos e teste, links locais dos três documentos | COMPILE_AND_DOCUMENT_LINKS_OK |
| Backup SQLite temporário, replay e fluxo offline | 38/38 IDs idênticos, 14 legados, VALIDATED_MOCK / NOT_SANDBOXED, limpeza OK, saída 0, 6,53 s |

A execução final direcionada utilizou a venv com `-m pytest` e estes arquivos, todos com `-q`.

```powershell
.venv/Scripts/python -m pytest backend/tests/test_ai_boundary.py backend/tests/test_evidence.py backend/tests/test_evidence_backtest.py backend/tests/test_evidence_claims.py backend/tests/test_evidence_hardening.py backend/tests/test_evidence_h1.py -q
```

O aviso Starlette/httpx é preexistente. A suíte completa foi iniciada antes do último reforço de validação do envelope confiável no gateway. O comando direcionado final executou esse reforço e os 73 casos da fronteira. O baseline inicial foi combinado com consultas Windows, e o processo composto terminou com código 1 por argumento inválido em Get-WindowsOptionalFeature após o pytest aprovado. Consultas individuais posteriores registraram QUERY_UNAVAILABLE. A suíte completa final e a execução direcionada terminaram com código 0.

## Integridade e fluxo offline

Fingerprint recalculado por `replay_fingerprint()` e preservado.

```text
e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62
```

Um script local via stdin para `.venv/Scripts/python -` abriu `data/cryptolab.sqlite3` usando URI `mode=ro`, executou query_only e `Connection.backup` para diretório temporário. Na cópia, enumerou research_runs e chamou ResearchService.verify para cada um, exigindo identical=True. Identificou 14 legados por fingerprint do manifesto diferente do atual. Os 38 IDs foram preservados. As conexões foram fechadas e o diretório removido antes da saída 0.

Na mesma cópia, o script congelou um resultado existente, criou bundle v2 temporário com claim net_return_pct do valor persistido e as-of no fim do dataset, construiu contexto e executou DEVELOPMENT_MOCK. Retornou VALIDATED_MOCK, NOT_SANDBOXED e context hash `56f3a8a824ace36f9694dc56ec2044465966e158f1081febe3c63c9226747b22`. Esse hash identifica esse conteúdo específico do ensaio. A captura completa foi descartada após a verificação. A origem foi aberta somente para leitura, e a comparação integral antes/depois foi realizada na fixture sintética.

O teste sintético compara todos os objetos e linhas representados por iterdump e os bytes originais do bundle. Inclui historical_datasets, research_protocols/runs, arena_experiments/results, paper_wallets/events/heads, paper_bindings e tabelas associadas, paper_decisions e tabelas associadas, paper_mark_evidence, paper_execution_evidence, monitor_signals/runtime/leases e collection_status. Muitas tabelas financeiras/monitor estão vazias nessa fixture. O teste preserva também os candles e dados de coleta existentes no banco sintético.

## Relatório de entrega

| Item | Estado e resultado |
| --- | --- |
| 1. HEAD inicial | TESTED — 22f59e8dc01e1febd358a7dce3c332f4dd7d8cbc |
| 2. HEAD final | DOCUMENTED — informado na resposta final e identificável pelo commit `feat: add isolated research context foundation` |
| 3. Arquitetura | IMPLEMENTED, TESTED — builder confiável → envelope mínimo → subprocesso mock → gateway externo |
| 4. Arquivos criados | IMPLEMENTED — ai_boundary/{__init__,contracts,context,gateway,mock_worker,runtime,cli}.py, backend/tests/test_ai_boundary.py e três docs AI_RESEARCH_CONTEXT/ISOLATION/BUDGET.md |
| 5. Arquivos modificados | DOCUMENTED — AI_RESEARCH_ARCHITECTURE, AI_RESEARCH_ROADMAP, AI_THREAT_MODEL, ARCHITECTURE, VERIFICATION, adr/004-isolamento e .ai/SESSION_HANDOFF.md |
| 6. Contrato | IMPLEMENTED, TESTED — Context v1 estrito, fechado, imutável, até 32.768 bytes |
| 7. Autorizados | IMPLEMENTED, TESTED — escopo, tempo, hashes, claims reconciliadas, unidades, métodos, fontes, limitações e incerteza |
| 8. Excluídos | IMPLEMENTED, TESTED no payload — candles, fonte bruta, ledger, caminhos, ambiente, credenciais e warnings livres |
| 9. Content hash | TESTED — contexto reproduzível entre capturas, novo domínio, hash do ensaio acima |
| 10. Mock | IMPLEMENTED, TESTED — stdlib determinística, operação única DESCRIBE_VERIFIED_CONTEXT |
| 11. Gateway | IMPLEMENTED, TESTED — reconstrução externa e reconciliação integral, inclusive envelope e uso |
| 12. Budget | IMPLEMENTED, TESTED — reservas por tentativa, falhas contabilizadas, sessão efêmera com lock |
| 13. Tokens | IMPLEMENTED, TESTED — ceil(bytes/4), estimativa simulada, 16.384 por entrada/saída por tentativa |
| 14. Bytes | IMPLEMENTED, TESTED — entrada até 65.536, stdout/stderr até 65.536 cada |
| 15. Processos e tempo | IMPLEMENTED, TESTED — 5 s e concorrência padrão 1 por sessão. Memória/CPU/descendentes DEFERRED |
| 16. Windows | TESTED — Home 10.0.26200 x64, Python 3.10.11, hipervisor reportado inativo |
| 17. Alternativas | DOCUMENTED — subprocesso, Restricted Token/ACL/Job, AppContainer, Sandbox/VM e Docker |
| 18. Controles concretos | IMPLEMENTED, TESTED — comando fixo, ambiente mínimo, cotas, timeout, cancelamento e espera do filho direto |
| 19. Indisponíveis no produto | DEFERRED — launcher restrito, ACL dedicada, limites de memória e egress. APIs Win32 presentes, contenção NOT_VERIFIED |
| 20. Exfiltração | TESTED — canários sintéticos e operações proibidas por contrato. Bloqueio real de FS/rede NOT_VERIFIED |
| 21. Adversariais | TESTED — JSON inválido/duplicado, IDs, hashes, métricas, unidade, fonte, janela, campos, PIT, uso, saída excessiva, timeout e exit code |
| 22. Causalidade | TESTED — dataset posterior recusado, PIT desconhecido preservado, claim causal excluída e limitações obrigatórias |
| 23. Não mutação | TESTED — SQLite sintético integral e bytes do bundle antes/depois. Banco pessoal integral NOT_VERIFIED |
| 24. Fingerprint | TESTED — valor e3adfd0e…ecc3f62 preservado, valor completo acima |
| 25. Replays | TESTED — 38/38, 14 legados, backup temporário removido e saída 0 |
| 26. Python | TESTED — 427 aprovados/1 skip, regressão direcionada final 143/1 skip |
| 27. Limitações | DOCUMENTED — v1 adiado no builder, warnings livres suprimidos, schema de saída limitado ao mock |
| 28. Riscos | DOCUMENTED — permissões do usuário, memória/CPU/disco sem quotas de SO, rede sem contenção, corridas e autenticidade desconhecida |
| 29. Gate D3B | DOCUMENTED — NOT_READY por fronteiras críticas de SO ainda sem implementação comprovada |
| 30. Decisões humanas | PROPOSED — mecanismo de isolamento, política de privacidade/retenção, fornecedor/orçamento futuro e aceitação explícita dos riscos |

## Escopo e verificações restantes

Arquivos financeiros, motor, estratégias, simulador, migrations, rotas, frontend, dependências e dados históricos têm zero alterações neste diff. As flags existentes continuam sob os contratos anteriores, exercitados pela suíte. Playwright, build e typecheck foram dispensados nesta entrega restrita a backend/documentação. A verificação de performance é limitada ao tempo observado das execuções, sem benchmark de limite máximo. Negação de execução financeira pelo SO e resistência de uma LLM a prompt injection permanecem NOT_VERIFIED. O mock e seu gateway não oferecem caminho de ação financeira. O isolamento forte e a fase D3B ficam DEFERRED.

# Verificação 2.3D3A.1 · PoC Windows · 15/11/2026

Baseline Git conferido na main em `775e9c553d6ba346f23fceb1348345fc7eb30035`, árvore limpa. Os números 427/143 da 2.3D3A foram tratados como histórico documental. A PoC acrescenta somente três módulos experimentais, testes e documentação, com modos de produção preservados.

| Comando ou ensaio | Resultado atual |
| --- | --- |
| `.venv/Scripts/python -m pytest backend/tests -q` após implementação inicial | 454 passed, 1 skipped, 1 warning, 150,25 s, saída 0 |
| Execução direcionada com sete arquivos abaixo, após ambiente e CLI corrigidos | 171 passed, 1 skipped, 1 warning, 75,02 s, saída 0 |
| `.venv/Scripts/python -m pytest backend/tests -q` repetido após revisão | 455 passed, 1 skipped, 1 warning, 148,32 s, saída 0 |
| Testes Windows finais após bloqueio de reuso e propagação de rollback incompleto | Resultado final registrado em AI_ISOLATION_TEST_RESULTS.md |
| CLI `.venv/Scripts/python -m cryptolab.research.ai_boundary.isolation_poc --suite` | PARTIAL_POC, cleanup COMPLETE, canários intactos, saída 0 |
| Repetição final do agregador via stdin | MEMORY_LIMIT/PROCESS_LIMIT/ROLLBACK ENFORCED_AND_TESTED, FS/rede NOT_VERIFIED, saída 0 |
| Replay em backup SQLite temporário | 38/38 IDs preservados, 14 legados, limpeza COMPLETE, saída 0, 5,17 s |
| Sintaxe e links | Quatro fontes/teste compilados por compile(), dois links locais dos três documentos novos conferidos |

```powershell
.venv/Scripts/python -m pytest backend/tests/test_windows_isolation.py backend/tests/test_ai_boundary.py backend/tests/test_evidence.py backend/tests/test_evidence_backtest.py backend/tests/test_evidence_claims.py backend/tests/test_evidence_hardening.py backend/tests/test_evidence_h1.py -q -rs
```

A suíte completa repetida foi iniciada antes do reforço final que invalida uma instância após rollback nativo incompleto. Esse reforço e sua propagação após remover a árvore foram verificados em execução posterior do arquivo Windows. O skip continua sendo test_evidence_h1.py, linha 133, porque o Windows recusa criação de symlink. O aviso Starlette/httpx é preexistente.

O token consultado é primário, UAC limitado e não elevado. A venv e o Git foram executados pela identidade proprietária, fora da restrição da ferramenta, enquanto a PoC recusa TokenIsElevated=True. A configuração de Job foi aplicada e relida antes do lançamento suspenso. VirtualAlloc de 96 MiB foi negado com erro 1455 sob limite de processo de 64 MiB e aceito sob limite de 192 MiB. O Job agregado foi testado separadamente. A tentativa de descendente recebeu erro 1816 no limite de um. O teste positivo permitiu dois processos e verificou sua saída após término do Job. A morte do helper supervisor fechou o último handle não herdado do Job e ambos os handles de processo sinalizaram término.

Restricted Token com SID Restricted Code criou processo, mas o runtime retornou 0xC0000022 antes do probe. AppContainer sem perfil retornou erro 203 em CreateProcessW, sem fallback. As tentativas de arquivos e rede ficam NOT_VERIFIED. Canários sintéticos e a base fictícia permaneceram intactos. O listener de loopback é local e efêmero, com controles positivos do supervisor e JOB_ONLY. Egress externo, DNS, IPC, CPU e disco não foram comprovados, com CPU/disco DEFERRED.

A revisão encontrou cache incidental em diretório relativo `%SystemDrive%` no workspace. Os metadados foram conferidos, SystemDrive foi incluído no ambiente mínimo e cwd do helper foi fixado na árvore sintética. O artefato próprio foi removido por caminho literal com checagem de contenção. As verificações finais conferem sua ausência. Nenhum arquivo de cache ou banco sintético entra no commit.

Fingerprint financeiro recalculado e preservado em `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. A origem do replay foi aberta em mode=ro/query_only e a execução ocorreu na cópia temporária, com todas as conexões fechadas antes da remoção. A comparação integral de não mutação foi exercitada em banco sintético, com várias tabelas financeiras vazias, e nos bytes do bundle.

A revisão do diff confirma escopo em ai_boundary, testes e documentação. Zero alterações de engine, estratégias, migrations, ledger, rotas, dependências ou frontend. Playwright, build e typecheck ficaram dispensados pelo escopo backend/documentação. Zero regras de firewall, perfis AppContainer, contas, serviços ou ACLs externas foram criados pela implementação. DACLs foram aplicadas exclusivamente à raiz temporária da instância e seus descendentes.

Readiness PARTIAL_POC. ISOLATED_RESEARCH permanece indisponível. A próxima etapa mínima proposta é revisar autorização e rollback de perfil AppContainer descartável e compatibilidade do runtime para testar negação real de arquivos e loopback. Capacidades, hipóteses, tentativas falhas, rollback e relatório de 30 itens em [AI_ISOLATION_TEST_RESULTS.md](AI_ISOLATION_TEST_RESULTS.md), [AI_WINDOWS_ISOLATION_POC.md](AI_WINDOWS_ISOLATION_POC.md) e [WINDOWS_ISOLATION_CAPABILITIES.md](WINDOWS_ISOLATION_CAPABILITIES.md).

A última execução `.venv/Scripts/python -m pytest backend/tests/test_windows_isolation.py -q`, posterior ao bloqueio persistente de reuso após rollback incompleto, terminou com 28 passed, um aviso Starlette/httpx, em 11,79 s e saída 0. A suíte completa repetida teve 455 passed/1 skipped em 148,32 s. A execução direcionada teve 171 passed/1 skipped em 75,02 s. O skip é a criação de symlink recusada pelo Windows. O teste final confirma propagação de ROLLBACK_INCOMPLETE mesmo após remover a árvore sintética.


# Prepara??o AppContainer ? 2.3D3A.2

Etapa n?o persistente conclu?da como PREPARATION_COMPLETE_AWAITING_APPROVAL. DACLs sint?ticas s?o capturadas antes das altera??es e conferidas ap?s aplica??o. Lifecycle e evid?ncia fechada foram preparados com testes mockados. Perfil real permanece NOT_AUTHORIZED, sem adapter nativo ou execu??o de CreateAppContainerProfile. Erro 203 e runtime 0xC0000022 foram reproduzidos, com causas espec?ficas ainda n?o confirmadas. Plano e testes em [AI_APPCONTAINER_APPROVAL_PLAN.md](AI_APPCONTAINER_APPROVAL_PLAN.md), [AI_APPCONTAINER_COMPATIBILITY.md](AI_APPCONTAINER_COMPATIBILITY.md) e [AI_ISOLATION_COMPATIBILITY_TESTS.md](AI_ISOLATION_COMPATIBILITY_TESTS.md). ISOLATED_RESEARCH permanece indispon?vel.


Baseline `.venv/Scripts/python -m pytest backend/tests -q` antes das altera??es teve 455 passed/1 skipped em 158,26 s, sa?da 0. Su?te posterior teve 470 passed/1 skipped em 145,99 s, sa?da 0. O skip de symlink e o aviso Starlette/httpx s?o preexistentes. A captura de ACLs em duas passagens foi ajustada ap?s iniciar essa su?te e foi verificada posteriormente no arquivo Windows junto aos testes de perfil. Diagn?stico e replays via stdin terminaram com sa?da 0 e REPLAY_CLEANUP_COMPLETE. `git diff --check` passou e o artefato %SystemDrive% permaneceu ausente.

Execu??o direcionada final: Windows isolation + profile_plan, 43 passed, um aviso preexistente, 13,66 s, sa?da 0. Nenhum perfil real foi criado.


# Native lifecycle preparation 2.3D3A.3

PREPARATION_COMPLETE_AWAITING_APPROVAL. Native read-only adapter and blocked mutation interfaces prepared. ProfileLifecycle supports an optional durable journal for synthetic tests. Recovery is inspection-only and uncertain ownership requires manual review. Reserved profile was absent in inspected storage/registry locations. No profile creation/deletion executed. See [native lifecycle](AI_APPCONTAINER_NATIVE_LIFECYCLE.md), [recovery](AI_APPCONTAINER_RECOVERY.md) and [authorized test plan](AI_APPCONTAINER_AUTHORIZED_TEST_PLAN.md). Filesystem/network enforcement remains NOT_VERIFIED; ISOLATED_RESEARCH remains unavailable.


# Verification 2.3D3A.3

Baseline d50f93291477581a37b9cd2be3c1dfe1a1fc696e, main clean. `.venv/Scripts/python -m pytest backend/tests -q` completed with 480 passed, 1 skipped, one preexisting Starlette/httpx warning in 147.62 s, exit 0. The skip is the existing Windows symlink permission test. Initial journal/profile tests passed 25 cases in 0.53 s. Windows/profile/journal tests passed 53 cases in 15.01 s. Final SID-schema/read-back fault checks were added afterwards and verified in a subsequent targeted run recorded below.

The first native read-only folder query returned HRESULT 0x80070002. The adapter now treats only FILE_NOT_FOUND/PATH_NOT_FOUND as absent storage and propagates other errors. Reinspection returned ABSENT_IN_INSPECTED_LOCATIONS for the exact reserved name, folder_present=False and mapping_present=False. No mutation API was invoked. This limited absence observation does not establish ownership or universal absence of residual state.

A script via `.venv/Scripts/python -` opened the source database with mode=ro/query_only and backed it up to a temporary directory. All 38 replays, including 14 legacy runs, preserved IDs. Connections closed and cleanup completed with exit 0 and REPLAY_CLEANUP_COMPLETE. Fingerprint e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62 was preserved. Existing synthetic database/bundle nonmutation tests were included in the full suite. Playwright/build/typecheck were omitted because the diff is backend/documentation only.

Financial modules, migrations, endpoints, credentials and LLM integrations have zero changes. Real profiles/journals for profiles were not created. Native mutation methods remain blocked; profile storage and registry inspection was read-only. Journals in pytest were temporary synthetic artifacts. Windows Job and developer mock contracts remain intact. CPU/disk, network/filesystem enforcement and automatic real recovery remain unverified/deferred.

Final targeted command `.venv/Scripts/python -m pytest backend/tests/test_profile_journal.py backend/tests/test_profile_plan.py backend/tests/test_windows_isolation.py -q`: 55 passed, one preexisting warning, 12.46 s, exit0. No real profile creation/deletion.


# Runner preparation 2.3D3A.4

PREPARATION_COMPLETE_AWAITING_APPROVAL. Closed runner policy/request and read-only approval manifest prepared. Native Win32 mutation bodies are disconnected from the operational adapter and exercised only through a synthetic API seam. execute_authorized_test always refuses. Mock end-to-end now binds operation/request to the durable journal, confirms runtime identity, runs fixture probes/gateway, stops resources and verifies profile/tree removal before CLEANED. Unexpected returned SID goes to manual review without deletion. See [runner](AI_APPCONTAINER_AUTHORIZED_TEST_RUNNER.md) and [approval manifest](AI_APPCONTAINER_APPROVAL_MANIFEST.md). Real filesystem/network containment remains NOT_VERIFIED.


# Verification 2.3D3A.4

Initial HEAD 1fd80d2be38282c9718fdefcfc5ee78b74db48ad, main clean. Full `.venv/Scripts/python -m pytest backend/tests -q` completed with 499 passed, 1 skipped, one preexisting Starlette/httpx warning, 141.40 s, exit0. The skip is the existing symlink creation test refused by Windows. The full run preceded final strict integer checks and two additional manifest/policy failure cases, verified by the subsequent targeted run. Initial runner/profile/journal tests passed44 in2.50s, exit0.

Read-only prepare_authorized_test produced profile absence in inspected locations, empty capabilities, policy hash489b6c6abe0719cd8cc78a8cf18fbe1159235ed5be69dc72312f5359fc62258b and the proposed operation in the approval manifest. No real profile create/delete APIs were called. Native call bodies were exercised against FakeUserenv only. The initial request-manifest write uses exclusive creation, flush/fsync/read-back before any profile call. Partial or preexisting operation manifest blocks reuse and requires review.

Replay verification used `.venv/Scripts/python -` with mode=ro/query_only origin and SQLite backup to a temporary directory. All38 IDs,14 legacy, preserved. Connections closed, cleanup completed with REPLAY_CLEANUP_COMPLETE and exit0. Fingerprint e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62 preserved. Existing synthetic nonmutation tests were included. No financial module, migration, ledger, frontend, dependency or HTTP route changed. Playwright/build/typecheck omitted for backend/documentation scope. Filesystem/network proof, native runtime compatibility and real rollback remain NOT_VERIFIED. Profile storage and registry inspection was read-only; test journals were temporary synthetic data.


Final targeted command `.venv/Scripts/python -m pytest backend/tests/test_authorized_runner.py backend/tests/test_profile_plan.py backend/tests/test_profile_journal.py backend/tests/test_windows_isolation.py backend/tests/test_ai_boundary.py -q` completed with147 passed, one preexisting warning,58.82s,exit0. A final explicit tree-absence confirmation guard and regression case followed; `test_authorized_runner.py -q` then passed20 tests in1.51s,exit0. A callback returning False cannot publish CLEANED. These final changes were verified by the targeted commands; the earlier full-suite count remains499/1skip.
# Verification 2.3D3A.4-GATE · 15/11/2026

Baseline: `main`, `ffeaf0674a67d3114cffe9b85cc177a27259564c`, clean; `git status -sb`, `git rev-parse HEAD`, `git log -5 --oneline` and diff against the mandatory baseline executed, exit 0. Current gate **PREFLIGHT_PARTIAL / NOT_AUTHORIZED**. [Final preflight and 22-item report](AI_APPCONTAINER_FINAL_PREFLIGHT.md), [rollback verification](AI_APPCONTAINER_ROLLBACK_VERIFICATION.md).

Final targeted command (exit 0):

```text
.venv/Scripts/python -m pytest backend/tests/test_appcontainer_preflight.py backend/tests/test_authorized_runner.py backend/tests/test_profile_plan.py backend/tests/test_profile_journal.py backend/tests/test_windows_isolation.py backend/tests/test_ai_boundary.py -q
217 passed, 1 warning in 75.75s
```

Earlier executed checks: profile/runner/journal 47 passed in 4.17s, exit 0; initial new preflight 52 passed/1 failed in 6.04s, exit 1 (retry was correctly refused with FileExistsError but the test expected only EvidenceError); corrected expanded subset 112 passed in 9.58s, exit 0; targeted 213 passed in 67.82s and then 216 passed in 66.53s, exit 0. Full suite before the final four regression cases: 567 passed/1 skipped/1 warning in 152.69s, exit 0. The final full-suite result is recorded after completion below. Warning is the preexisting Starlette/httpx deprecation; no installation performed.

Native read-only diagnostic through `.venv/Scripts/python -`, exit 0: token_type=1, elevated=False, elevation_type=3, appcontainer=False, pointer_bytes=8, five privileges present/one enabled. Discovery creates/releases an ephemeral restricted token, without profile creation or account changes. Exact reserved profile inspection: folder_present=False, mapping_present=False, ABSENT_IN_INSPECTED_LOCATIONS. Measured policy hash remains `489b6c6abe0719cd8cc78a8cf18fbe1159235ed5be69dc72312f5359fc62258b`, matching the approval manifest. No real Create/DeleteAppContainerProfile API called. Actual Win32 DACL read-back on disposable root/children/temp/manifest, permissive ACL rejection and junction rejection passed. Worker AppContainer access-denial tests NOT_EXECUTED. Mock receipts and injected API responses are TESTED_MOCK, not OS enforcement.

Replay command `.venv/Scripts/python -` used `sqlite3.connect(source_uri + '?mode=ro', uri=True)`, PRAGMA query_only=ON, SQLite backup into TemporaryDirectory, HistoryStore/ResearchService only on the copy, no migrations, all connections closed and temporary backup removed. Final exit 0 with output:

```text
fingerprint=e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62
replays=38 total=38 legacy=14
REPLAY_CLEANUP_COMPLETE
```

The first replay script exited 1 before replay because store.connect() is a context manager and was incorrectly wrapped in closing(); the corrected `with store.connect()` run above completed. Origin was read-only in both attempts; failed attempt did not run migrations or financial mutations.

No financial engine, strategy, ledger, wallet, migration, frontend, dependency or route changed. LIVE_TRADING_ENABLED=false and PAPER_SIMULATION_ENABLED=false defaults preserved. No LLM, private API, credentials, firewall/registry writes, account/service/global Windows changes. Only own disposable ACLs, benign Job/process controls and ephemeral listener used in tests. No real profile/operational journal created/deleted. Pytest may retain recent synthetic fixtures in TEMP; no blanket TEMP cleanup was attempted. The proposed persistent journal root and workspace `%SystemDrive%` artifact both absent on explicit checks. New reports validated as UTF-8 without replacement characters. Frontend build/typecheck/Playwright not repeated for this backend/documentation-only diff. Final staged whitespace/scope checks and commit recorded in Git; no push/PR.
# Final full-suite result · 2.3D3A.4-GATE

`.venv/Scripts/python -m pytest backend/tests -q -rs`: **571 passed, 1 skipped, 1 warning in 160.25s**, exit 0, after all code changes. Skip: `backend/tests/test_evidence_h1.py:133`, Windows does not permit symlink creation in this environment. Warning: preexisting Starlette/httpx deprecation. Final targeted result: **217 passed**, exit 0. No code changes followed these final runs; remaining edits were documentation only.
# Verification · 2.3D3A.4-BRIDGE · 15/11/2026

Baseline main clean `4a3bac1eaafabdb0bcc5497496682e7403805dbe`; status/HEAD/log inspected, exit 0. Implementation and 14-item delivery report: [native bridge](AI_APPCONTAINER_NATIVE_BRIDGE.md); [OS receipts](AI_APPCONTAINER_OS_RECEIPTS.md). No real AppContainer profile mutation. Native facade tested only with injected FakeUserenv bindings; no normal code path constructs/connects it. execute_authorized_test remains blocked.

Executed targeted command:

```text
.venv/Scripts/python -m pytest backend/tests/test_native_bridge_receipts.py backend/tests/test_appcontainer_preflight.py backend/tests/test_authorized_runner.py backend/tests/test_profile_journal.py backend/tests/test_profile_plan.py backend/tests/test_windows_isolation.py backend/tests/test_ai_boundary.py -q
```

Before the final False/None refinement: 248 passed/1 warning in102.29s,exit0; then249 passed/1 warning in111.39s,exit0 including the DLL facade test. New bridge/receipts file separately passed25 in19.41s and32 in29.38s,exit0. Initial compatibility files passed75/1 warning in20.51s,exit0. Journal/preflight subset passed81 in9.83s,exit0.

Full `.venv/Scripts/python -m pytest backend/tests -q -rs` passed602/1skip/1warning in182.37s,exit0; after the facade test,603/1skip/1warning in193.82s,exit0. Final full/targeted commands after the final False/None refinement are recorded below when completed. Preexisting skip: test_evidence_h1.py:133, Windows does not permit symlink creation. Preexisting Starlette/httpx deprecation warning; no dependency installation. Build/typecheck/Playwright omitted because this is backend/native infrastructure and documentation only.

Intermediate failures are preserved here: first journal subset had80 passed/1 failed in11.39s,exit1, because an extra pre-publication read changed the legacy read-back injection point; fixed while retaining the extra protected-native verification. First receipts run had21 passed/3 failed in19.09s,exit1: metadata-only handle did not block data write, a weak attribute-only deny fixture did not deny the query, and the substitution attack was refused earlier by Windows than its expected exception. Requesting GENERIC_READ and denying GR in the synthetic fixture corrected the sharing/access checks. That change initially caused sharing violations with the still-open exclusive CRT writer:9 passed/16 failed in7.77s,exit1. Fixed by capturing File ID from the original writer handle, verifying ACL before content and pinning the file only after writer close, then comparing IDs through publication. Subsequent25/32-file and248/249 targeted runs passed. No profile API in these failures used real Windows Create/Delete.

Real nonpersistent tests cover live/signalled/error process, exact Job membership, ActiveProcesses/PIDs, known-handle/CRT closure, denied/failing Win32 queries, present/absent/inaccessible/recreated directory, junction, foreign/stale/copied receipt, pinning/share denial and publication identity faults. Failed query is NONE, observed contrary condition is False, verified property is True. Real resource receipts leave ownership_confirmed/delete_succeeded=None for uncreated profiles. A real resources-complete fixture still cannot publish CLEANED. Fake profile lifecycle remains TESTED_MOCK even when its other resources are real.

Replay/diagnostic script through `.venv/Scripts/python -`,exit0: source SQLite mode=ro and PRAGMA query_only=ON, backup in TemporaryDirectory, ResearchService verification only on the copy, no migrations, connections closed and copy removed. Output: fingerprint `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`, replays38/38,legacy14,REPLAY_CLEANUP_COMPLETE. Read-only exact-profile inspection: folder_present=False,mapping_present=False,ABSENT_IN_INSPECTED_LOCATIONS. Discovery: primary token1,elevated=False,elevation_type3,not AppContainer,64-bit,5 privileges present/1 enabled; ephemeral restricted token created/released. No UAC elevation, account/service/global Windows change, firewall or registry write.

No financial module, ledger, wallet, strategy, order/fill, migration, private API, credential, LLM, frontend or dependency changed. Live/paper disabled defaults preserved. ACL writes confined to disposable test trees. No operational LOCALAPPDATA journal, real profile, permanent Job or service created/deleted. Pytest may retain recent synthetic fixtures in TEMP; no blanket cleanup attempted. Known process/Job/tree resources are the existing benign PoC's own fixtures. Residual same-user/SYSTEM, replace-gap, handle-duplicate and point-in-time limitations in the bridge/receipts documents; no ISOLATION_VERIFIED claim. Final Git scope/whitespace/link checks and local commit follow; no push/PR.
# Final results · 2.3D3A.4-BRIDGE

After all code changes: `.venv/Scripts/python -m pytest backend/tests -q -rs` completed **603 passed,1 skipped,1 warning in187.20s,exit0**. Final seven-file targeted command above completed **249 passed,1 warning in108.20s,exit0**. Skip and warning are the existing Windows symlink-permission case and Starlette/httpx deprecation. No code changes followed these runs. Fingerprint and38/38 replays14legacy preserved as recorded above. Gate **BRIDGE_READY_FOR_HUMAN_REVIEW**, never ISOLATION_VERIFIED or authorization. No real profile mutation or operational journal directory. Final Git checks/local commit in repository history; no push/PR.
