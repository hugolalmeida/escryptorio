# Fase 2.3C1 · Fundação de carteiras virtuais

Esta fase implementa somente armazenamento local e auditoria de carteiras paper. Não há worker, coleta de candles em tempo real, conexão privada, execução automática de estratégia, interface ou ordem real. O módulo não acessa rede ou SDK; não é uma conta Bybit. `LIVE_TRADING_ENABLED` continua obrigatório como `false` nos pontos de entrada existentes e na CLI.

## Arquitetura e contratos

`paper.models` define carteira, fill virtual, marcação, estado e dados financeiros Decimal; reutiliza `Contract`, `Symbol` e `Interval`. `paper.ledger` aplica transições puras sob contexto Decimal local de 80 dígitos. `paper.storage.PaperStore` usa `Store.connect` e a migration transacional `005_paper_ledger.sql`, sem alterar `storage.py`, motor de backtest ou fingerprint. A CLI só cria e consulta carteiras; não há comando CLI para ativar carteira, registrar fill ou iniciar estratégia. `append()` é uma interface Python de infraestrutura que registra fatos virtuais explicitamente fornecidos; não gera fills, não monta ordens e não consulta preços.

Cada `bot_id` é único no banco. A carteira identifica estratégia e versão, BTCUSDT ou ETHUSDT, timeframe, capital virtual e abertura UTC. A criação inicia **pausada**, sem posição. O estado reconstruído contém saldo USDT, quantidade do ativo, custo de aquisição, PnL realizado, taxas totais, último preço de marcação e seus timestamps, estado operacional e patrimônio. O patrimônio é saldo mais quantidade × último preço de marcação informado; quando há posição sem marcação, é `null`. Sem posição, é igual ao saldo. A marcação fornecida não é verificada contra fonte de mercado ou relógio e pode estar obsoleta; a fase não usa esse valor para agir.

`append` recebe um objeto validado e chave de idempotência para eventos `state` (pausar/ativar), `fill` (compra/venda virtual) ou `mark` (preço de marcação explícito). Há também um `genesis` automático e reservado. Fills e marcações registram timestamp do candle, preço de referência e instante do evento quando aplicável; timestamps devem ser cronológicos, com abertura do candle alinhada ao timeframe e não posterior ao evento. Não se assume que o candle ou preço foram autenticados, nem se valida execução t+1 nesta fundação. A integração futura deverá verificar fonte, fechamento, causalidade e frescor antes de produzir eventos. Somente uma carteira ativa aceita registros de fill virtual; a CLI não possui comando para ativá-la.

Compra debita quantidade × preço efetivo mais taxa em USDT, e acrescenta esse custo à posição. Venda não pode exceder a quantidade existente; a taxa em USDT é subtraída do produto, e custo médio proporcional é removido. Venda integral remove exatamente todo o custo residual. O PnL realizado inclui taxas de entrada e saída, e taxas totais são registradas separadamente sem nova dedução. Não se permite saldo negativo, venda a descoberto, taxa de venda maior que produto, margem ou empréstimo. O modelo usa contexto fixo de 80 dígitos e arredondamento `ROUND_HALF_EVEN`; custo médio proporcional pode exigir arredondamento nesse contexto. Campos de entrada aceitam no máximo 28 dígitos e 18 casas decimais; valores binários `float` são recusados, use strings ou `Decimal`. Não se supõe taxa da conta, moeda de cobrança real, precisão ou mínimo efetivo da Bybit.

## Ledger, integridade e recuperação

`paper_wallets` guarda metadata canônica e hash; `paper_events` guarda eventos imutáveis com sequência por carteira, ID único, chave idempotente, tipo, entrada e estados antes/depois. Valores financeiros são strings na serialização e no SQLite. Cada evento SHA-256 inclui carteira, sequência, identificador, chave, tipo, payload e hash anterior; o primeiro aponta ao hash da metadata da carteira. `paper_heads` mantém o último número e hash. Triggers recusam alteração/exclusão de carteira e eventos e exclusão do checkpoint.

A metadata imutável identifica as regras como `cryptolab-paper-ledger/1`. Uma futura mudança de cálculo ou formato exige nova versão e leitor/validador explícito da versão anterior; não se reinterpreta ou reescreve o ledger histórico. Versões desconhecidas são recusadas.

Criação, evento e atualização do checkpoint usam `BEGIN IMMEDIATE` e uma única transação. Repetir a mesma chave e conteúdo normalizado retorna o evento original; reutilizá-la com outro conteúdo falha. Chaves de eventos são únicas por carteira, e a chave de criação é única no banco. Escritas concorrentes serializam; antes de escrever, o serviço reconstrói e confere toda a cadeia. Cada leitura usa uma transação de snapshot e verifica metadata, sequência contígua, hash, checkpoint, transições e estados antes/depois. Uma falha antes do commit reverte evento e checkpoint; repetir a chamada após corrigir a causa é seguro. O ledger inteiro é reprocessado em cada operação: é uma implementação simples de fundação, com custo linear e sem retenção/compactação automática.

O hash e as triggers detectam corrupção e alterações não coordenadas; não são assinatura nem proteção contra quem consiga reescrever toda a base, cadeia e checkpoint ou substituir a aplicação. Para evidência contra adulteração deliberada, será necessário ancorar o hash fora do banco e controlar acesso/backup. Use backup consistente SQLite/WAL. O banco padrão em OneDrive tem as limitações documentadas em `ARCHITECTURE.md`.

## CLI no Windows

O capital é virtual. A data de abertura e a chave devem permanecer iguais numa repetição idempotente. Este exemplo cria uma carteira pausada e não usa rede:

```powershell
$aberturaPaper = [int64][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$carteiraPaper = .\.venv\Scripts\python.exe -m cryptolab.paper.cli create --bot trend-btc-01 --strategy trend --symbol BTCUSDT --interval 60 --capital 10000 --opened-at $aberturaPaper --key criar-trend-btc-01 | ConvertFrom-Json
$carteiraPaper.wallet_id
.\.venv\Scripts\python.exe -m cryptolab.paper.cli list
.\.venv\Scripts\python.exe -m cryptolab.paper.cli show --wallet $carteiraPaper.wallet_id
.\.venv\Scripts\python.exe -m cryptolab.paper.cli ledger --wallet $carteiraPaper.wallet_id
.\.venv\Scripts\python.exe -m cryptolab.paper.cli verify --wallet $carteiraPaper.wallet_id
```

Para repetir a criação, mantenha a mesma chave e o mesmo `$aberturaPaper`; em outra sessão, recupere `spec.opened_at` da carteira. Reutilizar a chave com um pedido diferente falha. IDs, saldos e histórico são consultados localmente; nenhum exemplo sintético é entregue como dado do produto.

## Pendências para 2.3C2

Na Fase 2.3C2B1, [PAPER_PLANNER.md](PAPER_PLANNER.md) descreve o planejador somente de leitura, seu vínculo explícito, risco e limitações. Não há integração executora nem alteração do ledger.

Na Fase 2.3C2B2A, [PAPER_BINDINGS.md](PAPER_BINDINGS.md) descreve vínculos e decisões persistidos em tabelas independentes, com revalidação sob transação. Essa camada não movimenta saldos nem cria fills.

Na Fase 2.3C2B2B, [PAPER_EXECUTION.md](PAPER_EXECUTION.md) descreve a simulação manual e exclusivamente virtual, com marcação e fill no ledger somente após validação e habilitação explícita de paper. Não há API privada ou execução real.

Especificar separadamente o produtor de eventos: candles fechados e contíguos, relógio/frescor e fonte verificados, decisão em t e fill mais cedo em t+1, política de taxas/slippage, precisão e mínimos da versão do instrumento, idempotência entre processos, estados de pausa e recuperação. Estudar reconciliação entre eventos e coleta, marcas obsoletas, limites de exposição e modelo de fills antes de conectar qualquer worker. Nenhuma destas funcionalidades foi ativada aqui. Paper permanece distinto de execução real e não autoriza qualquer conexão privada ou envio de ordens.
