# Fase 2.3C2A · Monitor de candles e sinais

O monitor lê somente snapshots públicos Bybit Spot já armazenados pelo worker existente, em SQLite. Não coleta dados, usa SDK, consulta conta, lê ou modifica carteiras paper, produz fills ou envia ordens. Não há frontend nem execução contínua nesta entrega. A CLI `--once` faz uma avaliação local e termina; a periodicidade e eventual supervisor ficam para uma fase posterior.

## Validação e decisões

Cada configuração identifica bot, ativo, timeframe, estratégia e versão, parâmetros e fingerprint do motor. Somente BTCUSDT/ETHUSDT, 15m/1h/4h/1d e Trend, RSI, Breakout ou Buy & Hold são aceitos; Mack continua inelegível. O monitor reutiliza `ResearchStrategy` e seu warm-up, com contexto Decimal fixo de 34 dígitos e `ROUND_HALF_EVEN`; não altera o motor.

O snapshot e seu dataset fechado devem ter hash verificado e estar disponíveis no banco. Fonte e coleta precisam estar dentro do limite de frescor da aplicação (90s por padrão), sem relógio mais de 5s no futuro. Candles devem ter timestamps únicos, ordenados, alinhados e contíguos; cada flag de fechamento é confrontada com o horário da fonte. Nenhum candle aberto entra na estratégia, e o último fechado deve corresponder ao intervalo corrente tanto da fonte quanto do relógio local. Warm-up insuficiente, dados antigos, lacunas ou hash inconsistente impedem a emissão. Antes de gravar, o monitor confere novamente o snapshot e relógio em transação, recusando troca de dataset ou passagem de janela durante a avaliação.

O resultado registra **duas condições hipotéticas**: `if_flat` e `if_long`. O monitor não lê posição nem saldo e o campo `position_checked` é sempre falso. Decisões `hold` também são registradas para auditoria. Buy & Hold apenas informa a condição hipotética para ausência de posição; sem consultar carteira, não se afirma que a compra única já ocorreu. Um plano indicativo para condição de compra de estratégias com stop informa preço de fechamento, stop, alvo, relação risco/retorno e invalidação. O instante de decisão é o fechamento; `valid_until` limita a janela informativa ao fechamento seguinte, não autoriza execução nem garante que a abertura de t+1 ainda esteja disponível. Decisões e planos não são recomendações nem ordens.

## Idempotência, integridade e retomada

`monitor_signals` guarda JSON canônico, ID SHA-256, bot, hash da configuração e abertura do candle. Uma restrição única em `(bot_id, config_hash, candle_time)` e `BEGIN IMMEDIATE` garantem que execuções concorrentes e repetidas retornem o mesmo sinal. Conteúdo divergente para a mesma chave gera `SIGNAL_CONFLICT`; os registros têm triggers contra atualização/exclusão. O fingerprint do motor é parte da configuração, e uma alteração no código carregado durante o processo é recusada até reiniciar. O catálogo verifica hash e campos de índice ao consultar os 100 sinais mais recentes. Hashes detectam corrupção, não são assinaturas contra quem possa reescrever o banco e seus índices.

Não há cursor mutável separado: o último sinal persistido identifica o último candle processado daquela configuração. Na primeira execução é avaliado apenas o último candle fechado. Depois de reiniciar, o mesmo candle é idempotente e o candle seguinte pode ser processado. Se houver candles intermediários não processados, o monitor retorna `MISSED_OR_REWOUND_CANDLES` e não cria sinal atrasado nem salta silenciosamente o período. Nesta fase não existe backfill de sinais ou comando de reset; resolver a lacuna exige um procedimento futuro explicitamente projetado. Alterar uma configuração cria outra identidade e não apaga registros anteriores. Esse comportamento protege a retomada, mas não garante processamento contínuo após parada prolongada.

## CLI PowerShell

Com o worker público existente em execução e snapshot fresco no mesmo banco, use a configuração de exemplo (hipótese Trend, sem posição real):

```powershell
.\.venv\Scripts\python.exe -m cryptolab.monitor --once --config docs/monitor-example.json
.\.venv\Scripts\python.exe -m cryptolab.monitor --signals --bot trend-btc-01
```

O JSON pode conter `parameters` compatíveis com `StrategyParameters`; salve uma configuração separada para cada bot. `LIVE_TRADING_ENABLED` deve ser `false`. Saída 0 significa avaliação ou consulta concluída; erros retornam código sanitizado e saída 1. O comando `--signals` é diagnóstico local e pode listar sinais antigos, cujo `valid_until` deve ser verificado; todos continuam informativos.

Em 07/11/2026, o snapshot BTCUSDT 1h disponível no banco local estava obsoleto. O exemplo `--once` retornou `{"error":"STALE_SNAPSHOT"}` e não emitiu sinal. O conteúdo integral das três tabelas paper foi comparado antes e depois, sem diferenças; testes sintéticos também conferiram eventos e saldo. Nenhum dado novo foi baixado para produzir esse exemplo.

## Limitações e próxima etapa

Não há execução em loop, backfill de sinais perdidos, fonte em streaming, posição ou carteira conectada, validação de elegibilidade, gestão de ordens, paper fills, UI ou conta privada. Snapshot de dashboard não é dataset histórico aprovado para backtesting; seu hash é uma referência à janela fechada existente, não aprovação de cobertura histórica. Para evolução será necessário especificar política de retomada de lacunas, estado durável do produtor, testes de concorrência entre processos e como eventuais consumidores recusariam dados expirados. Qualquer integração com ledger paper deverá ser projeto separado, respeitando t+1 e sem capacidade de ordem real.
