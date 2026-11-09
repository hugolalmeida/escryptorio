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
2. `record-decision` recebe vínculo, sinal e hash da proposta original. Antes de qualquer recálculo, consulta atomicamente sob `BEGIN IMMEDIATE` a chave de carteira e candle. Se já existe decisão, verifica integralmente sua cadeia, índices, sinal, vínculo e checkpoint do ledger histórico; exige os mesmos `binding_id`, `signal_id` e `validation_hash`. Identidade divergente gera `DECISION_CONFLICT`.
3. Para um registro ainda inexistente, exige vínculo ativo e valida sinal, fingerprint, prazo, carteira, snapshot, instrumento e causalidade; recalcula a proposta com os mesmos validadores do planner na **mesma conexão e transação**. O hash esperado deve coincidir com o cálculo atual. O hash da versão 3 do planner inclui o snapshot completo, não apenas seus campos financeiros. Mudança de saldo, risco, posição, estado, sinal, limites ou snapshot bloqueia uma nova gravação. Revalida relógio e proposta antes do commit. Somente `HOLD` e `CONDITIONAL_REVALIDATION_REQUIRED` podem ser registrados; `AWAITING_NEXT_OPEN` e `BUY_HOLD_POLICY_REQUIRED` são diagnósticos incompletos.
4. A decisão imutável contém vínculo e versão, sinal/hash, carteira, configuração, candle, proposta completa, risco, custos, estratégia, ledger, snapshot público integral, regras do instrumento e timestamp. Seu ID é o SHA-256 do conteúdo. A restrição `UNIQUE(wallet_id,candle_time)` impede inclusive decisões para sinais ou configurações diferentes no mesmo candle. HOLD não é intenção de fill.

## Recuperação após timeout ou reinício

Se o commit ocorreu e a resposta foi perdida, repita `record-decision` com os **mesmos três identificadores originais**. O recibo retorna o mesmo ID e `receipt_mode=RECOVER_EXISTING_RECEIPT`, mesmo se o snapshot ou ticker tiver mudado, a carteira tiver sido pausada, o ledger tiver avançado ou o vínculo tiver sido desativado. Não recalcula nem aprova um preço histórico e não reescreve a decisão. A resposta mostra `binding_state`, `wallet_state`, sequência e hash atuais do ledger para diagnóstico, além de `execution_enabled=false` e `needs_revalidation=true`. `REGISTER_NEW_DECISION` identifica o primeiro registro. Esses campos de recibo são metadados da resposta, não alteram o conteúdo ou hash dos fatos anteriores; a CLI mantém os mesmos argumentos.

O recibo retorna o estado auditável atual, inclusive `INVALIDATED` ou `EXPIRED`; jamais reativa uma decisão. Essa é uma alteração explícita do contrato: uma repetição idêntica desses estados retorna o recibo, em vez dos antigos erros `DECISION_NOT_CURRENT` ou `DECISION_EXPIRED`. Não é uma nova aprovação e não habilita operação. Os registros são recuperados somente quando sua integridade completa e identidade exata passam; divergência de hash, vínculo ou sinal falha como conflito, e adulteração de payload ou checkpoint falha por integridade. Para qualquer futuro efeito no ledger, o eventual executor deverá revalidar integralmente as condições atuais em transação própria.

O registro inicial gera evento `RECORDED`; invalidação explícita gera `INVALIDATED` com motivo sanitizado. Na consulta ou repetição de registro, se `valid_until` tiver sido alcançado, gera-se um evento imutável `EXPIRED`. Uma repetição idêntica retorna o recibo expirado; mesmo em repetição conflitante, a expiração observada é persistida antes da rejeição. As cadeias não permitem retorno desses estados a `RECORDED`; não existe consumo nesta fase. A consulta de decisão usa uma transação de escrita **somente nas tabelas desta fase** para persistir a observação do relógio e, se necessário, a expiração. Antes da transação principal, cada tentativa de registro confirma uma observação do relógio mesmo se a tentativa seguinte falhar. O maior horário observado é persistido e o relógio regressivo é recusado. Isso protege contra retrocesso já observado; não detecta uma alteração de relógio feita enquanto a aplicação não estava em execução e nunca observou o horário correto. É necessário relógio confiável e sincronizado.

Bloqueio SQLite, constraints, hashes e revalidação protegem concorrência entre processos, timeout e reinício. Uma falha antes do commit reverte integralmente decisão e evento. Após commit, repetição idêntica retorna o registro. Mesmo com isso, `RECORDED` é só um fato histórico: a futura etapa 2.3C2B2B deverá verificar transacionalmente novamente vínculo, expiração, ledger, preço, limites, idempotência e segurança antes de qualquer efeito virtual. Não existe executor, estado consumido, política implementada de Buy & Hold sem stop nem produtor de marcação nesta entrega.

Na fase posterior 2.3C2B2B, a simulação manual opcional usa um sidecar de consumo e revalida transacionalmente esses fatos; os estados históricos desta tabela não são reescritos. Veja [PAPER_EXECUTION.md](PAPER_EXECUTION.md). A execução real continua inexistente.

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
