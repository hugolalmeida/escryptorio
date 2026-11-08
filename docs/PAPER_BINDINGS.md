# Vínculos e decisões virtuais · Fase 2.3C2B2A

Esta camada persiste fatos locais de planejamento; não executa estratégias ou operações, não cria fills, não atualiza saldo e não acessa rede ou credenciais. `LIVE_TRADING_ENABLED=false` é obrigatório na CLI. Nenhum estado armazenado autoriza execução, inclusive `RECORDED`.

## Persistência e integridade

A migration incremental `008_paper_decisions.sql` cria `paper_bindings`, `paper_binding_events`, `paper_binding_heads`, `paper_binding_active`, `paper_decisions`, `paper_decision_events`, `paper_decision_heads` e `paper_decision_clock`. As três tabelas financeiras existentes não são modificadas. Vínculos, decisões e eventos são JSON canônico com SHA-256; triggers recusam edição ou exclusão de fatos. Eventos encadeiam o hash do registro e seu predecessor; projeções mutáveis de estado e de vínculo ativo são confrontadas com a cadeia ao consultar. A verificação também reconstrói o ledger, verifica o checkpoint histórico usado pela proposta, índices, referências, hashes de sinal e snapshot, e chaves estrangeiras.

SHA-256 detecta corrupção e alteração não coordenada, mas não é assinatura contra quem controle o arquivo SQLite e possa reescrever todos os registros. Faça backups consistentes pelo SQLite/WAL e mantenha o banco fora de sincronização de arquivos para operação contínua. Não há âncora externa neste estágio.

## Vínculos

O arquivo `PlannerBinding` informa ID/hash da carteira, hash da definição do monitor e risco/custos explícitos; seu formato está em [PAPER_PLANNER.md](PAPER_PLANNER.md). O registro inclui cópia íntegra da definição com parâmetros, versão de estratégia, símbolo/timeframe, versão e fingerprint do monitor, fingerprint financeiro, versão do planner, política, horário UTC em milissegundos e número de versão por carteira. Ele é imutável. Na criação, a carteira e a configuração são conferidas com o ledger íntegro e o monitor atual, inclusive identidade do bot. Repetir o mesmo vínculo não desativado retorna o registro existente.

O vínculo começa `REGISTERED`; ativação manual explícita gera evento `ACTIVE`, e desativação gera `DISABLED` com código de motivo. `DISABLED` é terminal; uma nova versão exige novo registro. A projeção ativa tem unicidade SQLite por carteira, bot e vínculo. Assim, uma alteração de parâmetros ou risco pode ser registrada como próxima versão, mas não pode ser ativada até a versão ativa anterior ser desativada explicitamente. Um vínculo ativo é somente para planejamento e nunca ativa a carteira paper, o monitor ou trading. A carteira deve estar ativa separadamente para registrar uma decisão.

## Decisões

1. O operador consulta o planner de leitura e obtém `validation_hash`; isso não registra ou executa nada.
2. `record-decision` recebe vínculo ativo, sinal e o hash da proposta. Sob `BEGIN IMMEDIATE`, verifica a cadeia e projeção do vínculo; valida o sinal e sua origem, fingerprint, candle e prazo; reconstrói a carteira e seu checkpoint; valida snapshot, instrumento, frescor e causalidade; recalcula a proposta com os mesmos validadores do planner na **mesma conexão e transação**.
3. O hash esperado deve coincidir com o cálculo atual. O hash da versão 3 do planner inclui o snapshot completo, não apenas seus campos financeiros. Mudança de saldo, risco, posição, estado, sinal, limites ou snapshot bloqueia a gravação. Revalida relógio e proposta novamente antes do commit. Somente `HOLD` e `CONDITIONAL_REVALIDATION_REQUIRED` podem ser registrados; `AWAITING_NEXT_OPEN` e `BUY_HOLD_POLICY_REQUIRED` são diagnósticos incompletos.
4. A decisão imutável contém vínculo e versão, sinal/hash, carteira, configuração, candle, proposta completa, risco, custos, estratégia, ledger, snapshot público integral, regras do instrumento e timestamp. Seu ID é o SHA-256 do conteúdo. A restrição `UNIQUE(wallet_id,candle_time)` impede inclusive decisões para sinais ou configurações diferentes no mesmo candle. Repetição idêntica e ainda válida retorna o mesmo ID; conteúdo divergente falha fechado. HOLD não é intenção de fill.

O registro inicial gera evento `RECORDED`; invalidação explícita gera `INVALIDATED` com motivo sanitizado. Na consulta ou repetição de registro, se `valid_until` tiver sido alcançado, gera-se um evento imutável `EXPIRED`. A repetição registra a observação antes de rejeitar a solicitação, para que o rollback do pedido não apague a expiração. As cadeias não permitem retorno desses estados a `RECORDED`; não existe consumo nesta fase. A consulta de decisão usa uma transação de escrita **somente nas tabelas desta fase** para persistir a observação do relógio e, se necessário, a expiração. O maior horário observado é persistido e o relógio regressivo é recusado. Isso protege contra retrocesso já observado; não detecta uma alteração de relógio feita enquanto a aplicação não estava em execução e nunca observou o horário correto. É necessário relógio confiável e sincronizado.

Bloqueio SQLite, constraints, hashes e revalidação protegem concorrência entre processos, timeout e reinício. Uma falha antes do commit reverte integralmente decisão e evento. Após commit, repetição idêntica retorna o registro. Mesmo com isso, `RECORDED` é só um fato histórico: a futura etapa 2.3C2B2B deverá verificar transacionalmente novamente vínculo, expiração, ledger, preço, limites, idempotência e segurança antes de qualquer efeito virtual. Não existe executor, estado consumido, política implementada de Buy & Hold sem stop nem produtor de marcação nesta entrega.

## CLI PowerShell

Os comandos abaixo são modelos; substitua os marcadores por IDs reais e um arquivo JSON de vínculo preenchido pelo operador. Custos são apenas premissas virtuais, nunca taxas reais presumidas. O planner existente é somente leitura; a CLI de decisões aplica migrations pendentes e escreve apenas nas tabelas de vínculo/decisão e metadados de migration.

```powershell
$vinculo = .\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli register-binding --binding <CAMINHO_JSON> | ConvertFrom-Json
.\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli activate-binding --id $vinculo.id
.\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli list-bindings
$proposta = .\.venv\Scripts\python.exe -m cryptolab.paper.planner_cli --wallet <WALLET_ID> --signal <SIGNAL_ID> --binding <CAMINHO_JSON> | ConvertFrom-Json
$decisao = .\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli record-decision --binding-id $vinculo.id --signal <SIGNAL_ID> --validation-hash $proposta.validation_hash | ConvertFrom-Json
.\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli get-decision --id $decisao.id
.\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli invalidate-decision --id $decisao.id --reason OPERATOR_REVIEW
.\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli disable-binding --id $vinculo.id --reason OPERATOR_STOP
.\.venv\Scripts\python.exe -m cryptolab.paper.decision_cli verify
```

Há também `get-binding --id`. Motivos são códigos `[A-Z][A-Z0-9_]{0,63}`; não insira segredos neles. A API retorna JSON estruturado e erros sanitizados. Nenhum comando ativa a carteira ou envia operação.
