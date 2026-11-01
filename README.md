# Escryptorio · CryptoLab

Workspace privado de pesquisa de criptomoedas. Primeira entrega: dashboard local, dados públicos reais da Bybit Spot, indicadores determinísticos e snapshots versionados. BTCUSDT e ETHUSDT; sem credenciais, margem, empréstimo, alavancagem ou ordens reais.

## Iniciar no Windows

Requisitos: Node.js 22+, npm, Python 3.10+ 64 bits e acesso HTTPS à Bybit. Na raiz do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

O script instala as dependências locais, inicia API e worker em segundo plano e abre o servidor Next no terminal. Acesse **http://127.0.0.1:3100**. A API fica em **http://127.0.0.1:8000/docs**. A porta 3000 não é usada, pois já havia outra aplicação local nela. Após a primeira instalação, use `-SkipInstall`. Ctrl+C encerra os processos API e worker iniciados pelo script.

Não é preciso criar `.env` nem informar chaves. `.env.example` documenta as opções. Python lê variáveis de ambiente do processo (não carrega `.env` automaticamente); Next lê `apps/web/.env.local`. Nunca use `NEXT_PUBLIC_*` para configuração privada. O script fixa `LIVE_TRADING_ENABLED=false`.

### Iniciar os processos separadamente

Instalação, uma vez:

```powershell
npm ci
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e ./backend
```

Em três terminais, a partir da raiz:

```powershell
# Terminal 1 · API
.\.venv\Scripts\python.exe -m uvicorn cryptolab.api:app --host 127.0.0.1 --port 8000
# Terminal 2 · worker
.\.venv\Scripts\python.exe -m cryptolab.worker
# Terminal 3 · frontend
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

Arena, backtesting, sinais operacionais, paper trading e carteira privada têm páginas de escopo e **ainda não executam suas funções**. Mack permanece não validada. Não há rota de ordem, cliente autenticado ou toggle para ativar trading. Os testes atuais comprovam causalidade dos indicadores; ainda não existe backtest a validar.

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
npm run test:ui
```

Capturas reais ficam em `artifacts/dashboard-{desktop,tablet,mobile}.png`, relatório em `playwright-report/`. Ambas as pastas são ignoradas pelo Git. O Playwright MCP não está disponível nesta sessão; a validação usa o runner Playwright/Chromium local.

## Diagnóstico

| Sintoma | Ação |
| --- | --- |
| Sem dados | Inicie worker e API; aguarde a coleta dos oito pares ativo/período. |
| Dados obsoletos | Verifique o worker, a rede, o relógio do Windows e `/health`. Atualizar no navegador apenas relê o banco. |
| Bybit indisponível | O worker registra um código sanitizado e tenta no próximo ciclo; não troca domínio nem contorna restrições regionais. |
| Porta ocupada | Encerre apenas a instância correspondente; scripts/testes não matam processos de outros projetos. |
| Banco lento | O banco padrão está em `data/`, dentro deste workspace OneDrive. Para uso contínuo, configure `CRYPTOLAB_DATABASE` fora de pasta sincronizada em ambos os processos. |

Banco e dependências são locais e ignorados. Datasets não são apagados automaticamente; acompanhe o espaço em disco. Esta entrega coleta janelas de 300 candles, sem paginação histórica longa. Acesso público não confirma elegibilidade ou permissões de uma conta privada. Não exponha os serviços em interfaces de rede públicas; não há autenticação multiusuário.

Arquitetura e fases: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Design e referências: [docs/DESIGN.md](docs/DESIGN.md). Pesquisa Freqtrade: [docs/FREQTRADE.md](docs/FREQTRADE.md). Evidências: [docs/VERIFICATION.md](docs/VERIFICATION.md).
