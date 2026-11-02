# Escryptorio / CryptoLab

Aplicação privada, local, usuário único, exclusivamente Bybit Spot BTCUSDT e ETHUSDT.

## Regras invariantes
- Nenhum envio, alteração ou cancelamento de ordem real. Nenhuma margem, empréstimo, short ou alavancagem.
- `LIVE_TRADING_ENABLED=false`. O backend e o worker devem recusar inicialização se outro valor for informado; uma flag não basta para autorizar implementação de execução.
- SDK público sem credenciais. Nunca ler chaves implicitamente, incluir segredos em `NEXT_PUBLIC_*`, commits, logs ou mensagens de erro.
- Preservar alterações e exclusões preexistentes no Git, inclusive projetos legados ausentes.
- Sem números financeiros inventados. Testes usam fixtures explicitamente sintéticas e isoladas; a aplicação não oferece fallback demonstrativo.
- Precisão financeira em Decimal no Python e strings na API/SQLite. Float só para renderização de gráficos/formatadores.
- Indicadores usam somente candles fechados, ordenados, contíguos e únicos. Dataset imutável identificado por SHA-256.
- Estratégias futuras: decisão no fechamento de t; primeiro fill permitido na abertura de t+1, custos em cada fill. Nenhuma otimização no teste.
- Mack fica não validada e inelegível até especificação, testes e validação fora da amostra.

## Organização
- `apps/web`: Next.js, TypeScript, Tailwind, componentes shadcn/ui e Lightweight Charts.
- `backend/cryptolab/api.py`: FastAPI; consultas e fila local de pesquisa histórica; não faz coleta de rede.
- `backend/cryptolab/worker.py`: processo de coleta pública Pybit para snapshots do dashboard.
- `backend/cryptolab/history`: coletor, CLI e worker próprios; histórico separado dos snapshots, sem estratégias.
- Mutações HTTP de histórico apenas enfileiram/pausam/retomam pesquisa local e exigem cabeçalho `X-CryptoLab-Research: 1`. Nunca são endpoints de execução de trades.
- Histórico usa intervalos UTC `[início, fim)`, sem preenchimento de lacunas; aprovar somente cobertura de 100%. Nunca sobrescrever candles conflitantes ou datasets aprovados.
- `backend/cryptolab/engine`: funções puras, independentes de API/SDK/persistência.
- `backend/cryptolab/research`: protocolo congelado, execução offline por `DatasetReader`, persistência imutável e API/CLI locais de simulação. Mutações exigem `X-CryptoLab-Research: 1`; não são endpoints de trades reais.
- `backend/cryptolab/migrations`: migrations SQL incrementais e transacionais.
- `docs`: arquitetura, decisões, desenho, roteiro e verificações.

## Execução e verificação
Consultar README. `npm run build`, `npm run typecheck`, `npm run test:ui` e `.venv/Scripts/python -m pytest backend/tests`.
Mudanças no motor exigem testes de referência, invariância de prefixo (causalidade), warm-up e extremos.
Erros upstream preservam o último snapshot e tornam seu estado obsoleto por idade; nunca atualizam artificialmente o timestamp.
Não instalar hooks, publicar, conectar conta privada ou ativar módulos futuros por inferência.
