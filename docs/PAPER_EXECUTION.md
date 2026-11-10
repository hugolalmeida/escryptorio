# Simulação manual exclusivamente virtual · Fase 2.3C2B2B

O executor opera apenas sobre carteira fictícia e dados públicos já armazenados. Não usa Pybit, credenciais, rede, conta privada ou API de ordens, e não representa uma operação de mercado. Não há worker, agendamento, frontend, margem, short ou alavancagem. `LIVE_TRADING_ENABLED` deve continuar `false`; `PAPER_SIMULATION_ENABLED` é `false` por padrão e precisa ser `true` junto de `--paper` em cada comando mutável. A carteira e o vínculo de planejamento devem estar ativos previamente; nenhum comando os ativa.

## Arquitetura e proveniência

`paper.marking` valida sinal atual, vínculo, carteira e snapshot público Bybit Spot em transação, incluindo candles fechados e contíguos, hash do dataset, ticker, instrumento `Trading`, horário da fonte e coleta e frescor. Rejeita relógios de mercado futuros e floats em dados financeiros. A migration `009_paper_execution.sql` cria sidecars append-only `paper_mark_evidence` e `paper_execution_evidence`, com hashes SHA-256, chaves estrangeiras, constraints e triggers. Migrations anteriores e fatos históricos não são reescritos. O método `PaperStore.append_in_transaction` reutiliza as transições e a cadeia do ledger existente na conexão da transação; a API `append` anterior continua compatível.

Uma marcação grava `MarkRecord` e evidência juntos: wallet, vínculo, sinal, chave idempotente, snapshot integral/hash, ticker, instrumento/hash, timestamp original, coleta, horário de marcação, candle, evento e hash. A repetição com a mesma chave devolve o recibo original, sem renovar artificialmente o horário; outra chave para o mesmo timestamp da fonte é recusada. A evidência é conferida contra o snapshot, dataset, sinal e cadeia do ledger. Para posições existentes, o executor exige que a última marca possua evidência íntegra e corresponda ao ticker atual. Se o preço ou timestamp mudar, marque novamente **antes de planejar e registrar uma nova decisão**, pois a marcação incrementa a sequência do ledger. A fonte pública é proveniência dos dados coletados, não assinatura criptográfica da Bybit nem prova de liquidez.

## Decisão e consumo

O executor consome somente decisão persistida `RECORDED`, não expirada, não invalidada e ligada a vínculo ativo; rejeita HOLD, sinal legado ou recuperado, carteira pausada, ledger ou projeções inválidos, alteração do checkpoint, dados antigos e regras incompatíveis. Na primeira execução, adquire `BEGIN IMMEDIATE`, verifica a decisão e seu hash, reconstrói o ledger e exige exatamente a sequência/hash registrados na decisão. Revalida sinal, snapshot, instrumento, ação e riscos com o planner existente na mesma conexão. O snapshot/ticker podem ter sido atualizados após a decisão: o cálculo usa a cotação atual verificada e os parâmetros congelados, sem reutilizar um preço antigo como fill.

A decisão ocorre no fechamento de t; o fill virtual só é registrado durante t+1 e antes da expiração. Uma cotação pública fresca de t+1 é referência para uma hipótese no instante atual; não se presume ter observado a abertura exata nem se simula execução retroativa. Candles abertos não entram no sinal, não se usam candles futuros e lacunas são recusadas. É preciso relógio confiável. A proteção contra retrocessos já observados usa o checkpoint de relógio existente; ela não detecta retrocesso nunca observado durante desligamento.

Dentro da **mesma transação**, o executor grava o fill no ledger, evidência e consumo. Se qualquer verificação ou gravação falhar, esses efeitos são revertidos; o checkpoint de relógio pode ter sido atualizado em uma transação prévia para preservar o horário observado. Uma linha de evidência significa `CONSUMED`; ausência dela não autoriza executar. `RECORDED`, `INVALIDATED` e `EXPIRED` da migration 008 permanecem inalterados. Uma decisão e uma chave por carteira são únicas; tentativa concorrente idêntica retorna o mesmo fill, e chave ou decisão conflitante é recusada. Após commit e perda de resposta, a mesma decisão e chave recuperam o recibo original mesmo se o mercado mudar. Esse recibo não autoriza outra operação.

## Modelo financeiro hipotético

Com Decimal em contexto do ledger, BUY usa ticker × (1 + slippage), arredondado para cima no tick; SELL usa ticker × (1 − slippage), arredondado para baixo. Quantidade respeita passo, máximo e mínimo nocional públicos. Fee virtual configurada é cobrada em USDT e arredondada para cima a 18 casas; não é uma taxa real verificada. Slippage informado inclui o arredondamento adverso. A compra é limitada por caixa incluindo fee, exposição pós-custos e risco planejado; após arredondar a fee, limites são conferidos novamente. A venda não excede posição e não pode ter fee superior ao produto. O ledger calcula custo de aquisição e PnL usando suas regras anteriores. Não há saldo negativo, empréstimo ou short.

Após BUY, stop e alvo são persistidos apenas como hipóteses `HYPOTHETICAL_ONLY`, com `automatic_monitoring=false`; não são ordens ativas nem protegem automaticamente a posição. A venda registra posição restante e, quando identificável, referência ao plano anterior; posições anteriores sem evidência de compra do executor não recebem proteção presumida. Sem monitoramento seguro de stop/target, não se inventa disparo ou fill. Buy & Hold continua bloqueado por `BUY_HOLD_POLICY_REQUIRED` até a entrada única e seu orçamento de perda total serem implementados e validados.

`show`, `history` e `verify` reconstroem e verificam hashes e eventos históricos. `verify` também procura eventos com chaves reservadas `exec-<SHA256>` ou `mark-<SHA256>` sem seus sidecars. SHA-256 e triggers detectam corrupção não coordenada, mas não são assinaturas contra quem controle toda a base. Use backup consistente SQLite/WAL e banco local fora de sincronização de arquivos. A coleta periódica não prova preço executável, profundidade, liquidez ou fill real; gaps e taxas efetivas podem diferir das hipóteses.

A versão dos contratos e evidências é `cryptolab-paper-executor/1`. Alterações futuras de cálculo, critérios ou formato exigem uma nova versão e leitor compatível; registros e hashes anteriores não devem ser reinterpretados. Os fills simulados são integrais para a quantidade calculada, sem modelo de liquidez ou preenchimento parcial de mercado; uma venda pode limitar a quantidade pela regra máxima do instrumento e deixar posição remanescente.

## CLI PowerShell

Para um diagnóstico com dados públicos e banco descartável, sem executar fills, consulte [PAPER_OPERATIONAL_VALIDATION.md](PAPER_OPERATIONAL_VALIDATION.md). A autorização para uma operação virtual manual é separada do diagnóstico.

Os marcadores abaixo devem ser substituídos por IDs reais de pesquisa local; não são dados de demonstração nem valores de mercado. Para posição existente, gere o sinal atual, faça a marcação, depois gere e registre uma decisão vinculada à nova sequência:

```powershell
$env:LIVE_TRADING_ENABLED = 'false'
$env:PAPER_SIMULATION_ENABLED = 'true'
.\.venv\Scripts\python.exe -m cryptolab.paper.executor_cli mark --binding <BINDING_ID> --signal <SIGNAL_ID> --key <CHAVE_MARCA> --paper
# Use planner_cli e decision_cli para obter uma decisão depois da marcação, quando houver posição.
.\.venv\Scripts\python.exe -m cryptolab.paper.executor_cli preview --decision <DECISION_ID>
.\.venv\Scripts\python.exe -m cryptolab.paper.executor_cli once --decision <DECISION_ID> --key <CHAVE_EXECUCAO> --paper
.\.venv\Scripts\python.exe -m cryptolab.paper.executor_cli show --execution <EXECUTION_ID>
.\.venv\Scripts\python.exe -m cryptolab.paper.executor_cli history --wallet <WALLET_ID>
.\.venv\Scripts\python.exe -m cryptolab.paper.executor_cli verify
Remove-Item Env:PAPER_SIMULATION_ENABLED
```

Use a mesma chave e decisão ao recuperar uma resposta perdida. `preview` é diagnóstico e não cria fill; `mark` altera somente marcação virtual do ledger, não saldo ou posição. O executor não ativa carteiras. As migrations são aplicadas pela CLI como no restante do projeto; nenhum comando permite operação real.
