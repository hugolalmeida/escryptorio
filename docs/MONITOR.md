# Monitor de candles e sinais · Fase 2.3C2A

O monitor é um processo local que lê snapshots públicos já coletados, sem rede e sem acesso a contas privadas ou carteiras paper. Não gera fills, ordens ou operações. `LIVE_TRADING_ENABLED=false` é obrigatório. São aceitos BTCUSDT/ETHUSDT Spot, intervalos 15m/1h/4h/1d e Trend, RSI, Breakout e Buy & Hold. Mack não é elegível.

## Decisões e integridade

O snapshot e o dataset fechado correspondente têm hash verificado. Fonte e coleta devem estar dentro do limite configurado de frescor (90 s por padrão), sem relógio mais de 5 s no futuro. Candles devem ser únicos, ordenados, alinhados, contíguos e fechados conforme o horário da fonte. O último candle fechado deve ser o mais recente tanto no relógio da fonte quanto no local, e deve haver warm-up suficiente. O snapshot, o dataset e o relógio são conferidos novamente sob transação antes de gravar.

O monitor usa `ResearchStrategy` sem alterar o motor, com Decimal de 34 dígitos e `ROUND_HALF_EVEN`. Cada sinal contém as condições hipotéticas `if_flat` e `if_long`; não há leitura de posição. Planos, quando presentes, são indicativos. `valid_until` é o fechamento seguinte, não uma ordem ou garantia de que uma abertura ainda esteja disponível. A ausência de posição não é comprovada e Buy & Hold representa somente uma hipótese. `mode` continua `informational_only` e `position_checked` é sempre falso.

Os sinais existentes de schema 1 permanecem imutáveis e verificáveis; não são retroativamente classificados como elegíveis. Os novos são schema 2: `origin=current` identifica uma avaliação fresca e `eligible_for_future_paper_analysis=true` significa apenas que poderá ser considerada em uma futura análise, sujeita a novas verificações de validade, posição e demais regras. `origin=historical_recovered` tem sempre `eligible_for_future_paper_analysis=false`: jamais deve produzir uma ação retroativa. Nenhum consumidor paper foi implementado.

`monitor_signals` mantém JSON canônico e ID SHA-256; índices de identidade e conteúdo são verificados, com triggers contra edição e exclusão. Esses hashes detectam corrupção, mas não são assinaturas contra alguém que controle todo o banco. O fingerprint financeiro permanece inalterado. A definição dos novos sinais inclui também versão e hash do código do monitor, dos contratos e do leitor histórico; alterações nesses arquivos criam uma identidade nova. O processo verifica o hash novamente e exige reinício se o código carregado mudar. Na troca de versão, o checkpoint é herdado do último sinal íntegro com a mesma configuração, inclusive de schema 1, sem reescrever sinais antigos. Alterar os parâmetros ou a versão da estratégia cria outra configuração; o primeiro processamento dessa configuração começa no último candle fechado.

## Lease, estado e recuperação

A migration 007 adiciona `monitor_runtime` e `monitor_leases`, sem mudar o ledger ou tabelas financeiras. Cada avaliação reivindica, em `BEGIN IMMEDIATE`, um lease de 120 s por configuração do bot, independente da versão do monitor. A posse usa token aleatório e é conferida novamente antes de gravar. Outra instância recebe `MONITOR_LEASE_BUSY`; um processo antigo não pode gravar após expiração ou substituição. Em saída normal, erro ou Ctrl+C o lease é liberado; após encerramento abrupto, outra instância pode retomá-lo depois do prazo. Avaliações que excedam esse prazo falham fechadas, sem gravar sinais parciais.

O estado persistente expõe último candle avaliado, horário da avaliação em milissegundos UTC, estado, erro sanitizado, identidade e validade do lease. `--status` informa `lease_expired` quando o proprietário desapareceu; o lease expirado será recuperado na próxima reivindicação. O checkpoint é comparado com os sinais íntegros antes de avançar. Uma configuração nunca é avançada silenciosamente sobre candles perdidos.

Após uma parada com lacuna, informe `--recovery-dataset` com o SHA-256 de um dataset histórico previamente coletado e aprovado. `DatasetReader` verifica SHA, manifesto, origem Bybit Spot, cobertura completa e sequência; o dataset deve cobrir o checkpoint e todos os candles intermediários, ter o mesmo mercado e timeframe e concordar com o candle original do checkpoint e todos os dados sobrepostos ao snapshot. O último snapshot ainda precisa estar fresco. A recuperação é limitada a 500 candles perdidos e um dataset de até 20.000 candles; dados fora desse limite, ausentes, insuficientes ou conflitantes são recusados. Não há download automático nem preenchimento artificial.

Para cada candle perdido, a estratégia recebe somente o prefixo do dataset até aquele candle, com warm-up adequado. O dataset inteiro identifica a proveniência, mas valores posteriores não entram na decisão. O início do dataset determina a inicialização dos indicadores recursivos; ela pode diferir da janela móvel do snapshot atual. Todos os sinais recuperados e o sinal corrente são gravados com o checkpoint na mesma transação, ou nenhum é gravado. Não há execução retroativa nem modificação de carteiras. Sem dataset aprovado utilizável, o estado permanece em erro até que o operador disponibilize dados adequados.

## CLI PowerShell

Com o worker público existente produzindo snapshots frescos no mesmo banco:

```powershell
.\.venv\Scripts\python.exe -m cryptolab.monitor --once --config docs/monitor-example.json
.\.venv\Scripts\python.exe -m cryptolab.monitor --loop --config docs/monitor-example.json --poll-seconds 15
.\.venv\Scripts\python.exe -m cryptolab.monitor --status --bot trend-btc-01
.\.venv\Scripts\python.exe -m cryptolab.monitor --signals --bot trend-btc-01
.\.venv\Scripts\python.exe -m cryptolab.monitor --once --config docs/monitor-example.json --recovery-dataset <SHA256_APROVADO>
```

`--loop` avalia imediatamente e espera de 10 a 60 segundos entre tentativas; erros sanitizados são informados e novas tentativas continuam. Ctrl+C encerra sem iniciar outra avaliação. O comando `--once` retorna 0 somente quando a avaliação atual foi concluída; erro retorna 1. Não execute o exemplo de recuperação com o marcador literal: use o hash de um dataset aprovado real. `--signals` é diagnóstico, e qualquer eventual consumidor futuro deve verificar origem e validade no momento de uso.

## Limitações

O monitor depende do worker público e de histórico já coletado e aprovado. Não prevê supervisor, coleta em streaming, integração com ledger, fills, interface, conta privada ou execução. O snapshot do dashboard não é um dataset histórico aprovado. No próximo estágio, qualquer consumidor de sinais deverá especificar explicitamente elegibilidade, expiração, causalidade t+1, idempotência e efeitos sobre o ledger, sem capacidade de envio de ordem real.

Na verificação local desta fase, o snapshot BTCUSDT 1h estava obsoleto e o comando `--once` retornou `STALE_SNAPSHOT`; nenhum sinal corrente foi criado. O conteúdo das tabelas paper foi comparado antes e depois, sem alteração. Não foram baixados dados para fabricar um exemplo.
