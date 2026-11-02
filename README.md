# Escryptorio · CryptoLab

Workspace privado de pesquisa de criptomoedas. Dashboard local, dados públicos reais da Bybit Spot, indicadores determinísticos, histórico versionado e backtests offline reproduzíveis. BTCUSDT e ETHUSDT; sem credenciais, margem, empréstimo, alavancagem ou ordens reais.

## Iniciar no Windows

Requisitos: Node.js 22+, npm, Python 3.10+ 64 bits e acesso HTTPS à Bybit. Na raiz do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

O script instala as dependências locais, inicia API, worker do dashboard e worker histórico em segundo plano e abre o servidor Next no terminal. Acesse **http://127.0.0.1:3100** e **http://127.0.0.1:3100/history**. A API fica em **http://127.0.0.1:8000/docs**. A porta 3000 não é usada, pois já havia outra aplicação local nela. Após a primeira instalação, use `-SkipInstall`. Ctrl+C encerra os três processos Python iniciados pelo script. Se já houver uma instância da fase anterior, reinicie-a para carregar as novas rotas e o worker histórico.

Não é preciso criar `.env` nem informar chaves. `.env.example` documenta as opções. Python lê variáveis de ambiente do processo (não carrega `.env` automaticamente); Next lê `apps/web/.env.local`. Nunca use `NEXT_PUBLIC_*` para configuração privada. O script fixa `LIVE_TRADING_ENABLED=false`.

### Iniciar os processos separadamente

Instalação, uma vez:

```powershell
npm ci
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e ./backend
```

Em quatro terminais, a partir da raiz:

```powershell
# Terminal 1 · API
.\.venv\Scripts\python.exe -m uvicorn cryptolab.api:app --host 127.0.0.1 --port 8000
# Terminal 2 · worker
.\.venv\Scripts\python.exe -m cryptolab.worker
# Terminal 3 · worker histórico, separado da atualização do dashboard
.\.venv\Scripts\python.exe -m cryptolab.history.worker
# Terminal 4 · frontend
npm run dev
```

Para uma única coleta: `.\.venv\Scripts\python.exe -m cryptolab.worker --once`.
Para produção local: `npm run build`, depois `npm start`, mantendo API e worker ativos.

## O que está implementado

- Design system azul-grafite, navegação, responsividade e componentes de botão no padrão shadcn/ui (Radix Slot + CVA).
- Dashboard BTC/ETH, 15m/1h/4h/1d, candles ou linha, volume, SMA 20, EMA 50, RSI 14 e ATR 14.
- Valores, volume e variação de 24h reais; horário da resposta Bybit e idade do snapshot. Polling de 15s, não streaming de ticks.
- Indicadores somente em candles fechados; último candle em formação identificado. Horários de resumo em Brasília; eixo do gráfico em UTC, explicitamente indicado.
- Worker Pybit público separado do FastAPI. FastAPI lê SQLite; Next atua como proxy local com parâmetros permitidos.
- SQLite WAL, migrations transacionais, último snapshot por ativo/período e datasets fechados imutáveis por SHA-256.
- Validação de OHLC, lacunas, duplicatas, ordenação, alinhamento temporal, dados antigos e não finitos.
- Falhas preservam o último snapshot e seu horário original. Após 90s ele é marcado obsoleto. Nenhum fallback fictício.
- Especificações públicas de instrumento (precisão, mínimos e limites) persistidas para uso em módulos futuros.
- Página **Dados históricos**: ativo/timeframe, período UTC, solicitação de coleta, progresso, pausa/retomada, cobertura, lacunas, catálogo e verificação de datasets.
- Backfill paginado até 1.000 candles por chamada, arquivo incremental sem duplicação, retries limitados, lease persistido e retomada somente das faixas ausentes.
- Datasets históricos aprovados com 100% de cobertura, SHA-256, manifesto e proteção SQL contra alteração; leitor offline para o futuro motor quantitativo. Snapshots do dashboard permanecem separados.
- Backtesting offline de Trend, RSI, Breakout e Buy & Hold, com indicadores causais, custos, stop/alvo, limites de instrumento e janelas cronológicas. Protocolos e resultados imutáveis por SHA-256; nenhuma rede durante o replay.

Arena, sinais operacionais, paper trading e carteira privada têm páginas de escopo e **ainda não executam suas funções**. Mack permanece não validada. Não há rota de ordem, cliente autenticado ou toggle para ativar trading. Um backtest é pesquisa histórica, não validação de rentabilidade.

## Backtesting offline · Fase 2.2

Acesse **http://127.0.0.1:3100/backtesting**. Selecione um dataset aprovado e período, revise estratégia e custos, congele o protocolo, execute treino e validação e depois o teste fora da amostra. Cada janela começa com saldo virtual novo; dados anteriores servem apenas para aquecimento. O painel permite consultar resultados anteriores, retomar o protocolo após recarregar a página e verificar o hash. O snapshot público do instrumento precisa estar disponível no banco; seus limites são premissas atuais, não regras históricas verificadas. Nenhuma conta é conectada. Reinicie a API e o frontend se estiverem abertos em versão anterior.

Padrões experimentais: capital 10.000 USDT, taxa 0,1% por fill, slippage adverso 0,05%, risco planejado 1%, exposição 100%, stop 3% e alvo 6%. Trend SMA20/50, RSI Wilder14 recuperação de 30 e saída 60, Breakout de 20 candles anteriores. Buy & Hold não usa stop. A interface aceita outras premissas; taxas não são verificadas na conta. Amostra com menos de 30 trades é marcada insuficiente; isso não significa que amostras maiores sejam validadas. Não há ranking automático.

### CLI PowerShell

O exemplo [docs/backtest-example.json](docs/backtest-example.json) usa o dataset BTCUSDT 1h da seção anterior; uma instalação nova precisa coletá-lo e ter snapshot público do instrumento. Alterar o JSON antes de congelar, inclusive ativo, estratégia (`trend`, `rsi`, `breakout`, `buy_hold`), períodos UTC em segundos e custos. Como estratégia, parâmetros, código e regras do instrumento fazem parte do protocolo, o ID pode variar. Nenhuma chamada à Bybit é feita pela CLI de pesquisa.

```powershell
.\.venv\Scripts\python.exe -m cryptolab.research.cli datasets
$protocolo = .\.venv\Scripts\python.exe -m cryptolab.research.cli freeze --config docs/backtest-example.json | ConvertFrom-Json
$protocolo.id
$treino = .\.venv\Scripts\python.exe -m cryptolab.research.cli run --protocol $protocolo.id --partition train | ConvertFrom-Json
$validacao = .\.venv\Scripts\python.exe -m cryptolab.research.cli run --protocol $protocolo.id --partition validation | ConvertFrom-Json
$teste = .\.venv\Scripts\python.exe -m cryptolab.research.cli run --protocol $protocolo.id --partition test | ConvertFrom-Json
$teste.simulation.metrics
.\.venv\Scripts\python.exe -m cryptolab.research.cli trades --run $teste.id
.\.venv\Scripts\python.exe -m cryptolab.research.cli show --run $teste.id
.\.venv\Scripts\python.exe -m cryptolab.research.cli verify --run $teste.id
.\.venv\Scripts\python.exe -m cryptolab.research.cli runs
```

Teste final exige treino e validação já persistidos para o mesmo protocolo. O replay verifica fingerprint versionado das dependências efetivas e do runtime; alterações independentes não invalidam novos protocolos. Protocolos legados mantêm o hash original, com uma ponte explícita apenas para a versão e ambiente auditados. Se o motor ou o runtime mudar, consulte o resultado antigo e use o ambiente original para reverificá-lo. Até 20.000 candles incluindo warm-up por protocolo. Freqtrade fica isolado e não foi instalado. Detalhes, hipóteses e limitações em [docs/BACKTESTING.md](docs/BACKTESTING.md).

## Histórico de pesquisa · Fase 2.1

Períodos são **`[início, fim)` em UTC**, alinhados ao timeframe. Datas simples significam meia-noite UTC; horários exigem offset (`Z` ou `-03:00`). A interface recebe horários em UTC, independentemente do fuso do Windows. Limite de 100.000 candles por solicitação; divida períodos maiores.

Coletar pelo PowerShell, a partir da raiz, sem precisar manter o worker histórico aberto:

```powershell
.\.venv\Scripts\python.exe -m cryptolab.history.cli collect --symbol BTCUSDT --interval 60 --start 2026-09-01 --end 2026-11-01
```

O comando mostra ID, candles confirmados, páginas e JSON final. Ctrl+C pausa com segurança; **repita o mesmo comando para retomar**. Jobs já concluídos retornam o mesmo dataset sem novas chamadas de rede. Se outro coletor detiver o lease, o job fica persistido na fila para o worker; código de saída 2 informa que não houve conclusão nesta execução. Após encerramento abrupto, o lease expira em até 120s e uma nova tentativa pode recuperar o job.

Consultar cobertura e catálogo sem acessar a corretora:

```powershell
.\.venv\Scripts\python.exe -m cryptolab.history.cli coverage --symbol BTCUSDT --interval 60 --start 2026-09-01 --end 2026-11-01
.\.venv\Scripts\python.exe -m cryptolab.history.cli datasets
```

Consulta offline real de três candles do dataset BTCUSDT criado nesta entrega:

```powershell
.\.venv\Scripts\python.exe -m cryptolab.history.cli read --dataset f3b2e55b1cc373d448efa3676c63064cb482c86be4ebd7442bce573134f972c6 --start 2026-09-01 --end 2026-09-01T03:00:00Z
```

Esse hash existe no banco local usado na verificação; uma instalação nova precisa coletar ou receber um backup consistente do banco. `read` valida o dataset completo antes de recortar. `reference_hash` continua referindo-se ao dataset completo; não é um hash do JSON de saída nem do recorte. O motor Python pode usar `DatasetReader.read(hash, start_time, end_time)` para obter uma tupla OHLCV Decimal, manifesto e hash, sem rede.

Cobertura real obtida em 01/11/2026: **5.475 candles únicos**, quatro séries completas: BTCUSDT 1h e 4h entre 01/09 e 01/11/2026; ETHUSDT 15m entre 01/10 e 01/11/2026; ETHUSDT 1d entre 01/01/2025 e 01/11/2026. Os limites finais são exclusivos. Um quinto dataset de 24 candles BTCUSDT foi aprovado por reutilização do arquivo, sem aumentar esse total. Hashes e evidências estão em [docs/HISTORY.md](docs/HISTORY.md).

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm run typecheck
npm run build
npx playwright install chromium
npm run test:ui
```

Playwright inicia um servidor de produção exclusivo na porta 3100 (deixe-a livre); compile antes de executá-lo. A suíte de interface usa fixtures sintéticas isoladas, sem depender da corretora. Para incluir smoke tests com dados reais, inicie API e worker e execute:

```powershell
$env:CRYPTOLAB_LIVE_SMOKE = '1'
$env:CRYPTOLAB_HISTORY_SMOKE = '1' # opcional: requer o backfill BTC acima e worker histórico ativo
$env:CRYPTOLAB_BACKTEST_SMOKE = '1' # opcional: requer dataset BTC aprovado e snapshot do instrumento
npm run test:ui
```

Capturas reais ficam em `artifacts/dashboard-{desktop,tablet,mobile}.png` e `artifacts/history-{desktop,tablet,mobile}.png`, relatório em `playwright-report/`. Ambas as pastas são ignoradas pelo Git. O Playwright MCP não está disponível nesta sessão; a validação usa o runner Playwright/Chromium local. Sem flags de smoke, os testes não consultam a Bybit nem exigem backend.

Para preservar instâncias já abertas durante QA, é possível usar um backend próprio em outra porta de loopback e definir `$env:BACKEND_URL='http://127.0.0.1:18000'` e `$env:CRYPTOLAB_TEST_PORT='13100'` antes do Playwright. O runner continua exigindo servidor próprio e não reutiliza nem encerra processos existentes. As proteções de Host, origem, mercado e credenciais permanecem iguais.

## Diagnóstico

| Sintoma | Ação |
| --- | --- |
| Sem dados | Inicie worker e API; aguarde a coleta dos oito pares ativo/período. |
| Dados obsoletos | Verifique o worker, a rede, o relógio do Windows e `/health`. Atualizar no navegador apenas relê o banco. |
| Bybit indisponível | O worker registra um código sanitizado e tenta no próximo ciclo; não troca domínio nem contorna restrições regionais. |
| Porta ocupada | Encerre apenas a instância correspondente; scripts/testes não matam processos de outros projetos. |
| Banco lento | O banco padrão está em `data/`, dentro deste workspace OneDrive. Para uso contínuo, configure `CRYPTOLAB_DATABASE` fora de pasta sincronizada em ambos os processos. |
| Histórico na fila | Inicie `python -m cryptolab.history.worker` na venv ou use a CLI. Um backfill por banco é executado por vez. |
| Histórico incompleto | Consulte as lacunas; retome após corrigir a causa. Candles abertos ou anteriores à listagem não são inventados. |
| `BYBIT_FORBIDDEN` | A tentativa para, sem repetir 403. Não alterar domínio para contornar restrições. Se for bloqueio por frequência, respeitar a espera prevista pela Bybit antes de retomar. |

Banco e dependências são locais e ignorados. Datasets não são apagados automaticamente; acompanhe o espaço em disco. O dashboard mantém janelas de 300 candles; o histórico usa seu próprio arquivo incremental paginado. Acesso público não confirma elegibilidade ou permissões de uma conta privada. Não exponha os serviços em interfaces de rede públicas; não há autenticação multiusuário.

Arquitetura e fases: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Motor histórico: [docs/HISTORY.md](docs/HISTORY.md). Backtesting: [docs/BACKTESTING.md](docs/BACKTESTING.md). Plano anterior: [docs/PHASE_2_2.md](docs/PHASE_2_2.md). Design: [docs/DESIGN.md](docs/DESIGN.md). Pesquisa Freqtrade: [docs/FREQTRADE.md](docs/FREQTRADE.md). Evidências: [docs/VERIFICATION.md](docs/VERIFICATION.md).
