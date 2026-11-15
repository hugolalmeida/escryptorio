# Research Context Builder v1 · 2.3D3A

## Escopo implementado

`backend/cryptolab/research/ai_boundary` oferece projeção offline confiável, mock determinístico e validação externa ao subprocesso. A entrada é exclusivamente Evidence Bundle v2. O suporte a v1 continua nos verificadores anteriores e foi adiado no builder por ausência de necessidade nesta fase.

O builder copia os cinco arquivos limitados a 64 MiB cada para uma captura temporária, executa `bundle_v2.verify` nessa captura e projeta os mesmos bytes verificados. A verificação reconstrói pacote, relatório e resultados das claims a partir das fontes congeladas. Um rótulo `VALIDATED` fornecido isoladamente falha nessa reconstrução. O diretório de origem deve ser controlado pelo operador. Permanecem os riscos de substituição concorrente por processo com as mesmas permissões e de falsificação coordenada de fonte e hashes.

## Contrato fechado

`contracts.Context` usa Pydantic estrito, `extra=forbid`, objetos congelados e tuplas. Limite serializado de 32.768 bytes. Contrato v1 e política `minimal-v2/1`, builder `research-context/1`. A janela usa milissegundos UTC `[start_ms,end_ms)` e exige fim até o as-of. Tipos numéricos do contexto são inteiros estritos ou strings. Valores monetários são strings originadas da reconciliação existente.

| Campos autorizados | Conteúdo e finalidade |
| --- | --- |
| schema_version, builder_version, policy_version | Identificação do contrato e da projeção |
| context_id, content_hash, evidence_content_hash | Identidade semântica e vínculo com evidência |
| research_objective, mode | DESCRIBE_VERIFIED_CONTEXT e RETROSPECTIVE |
| symbol, interval, as_of_ms, window | Escopo de mercado e tempo |
| source_refs | Hashes do dataset, protocolo e resultado verificados |
| observations | Claims VALIDATED com nome, valor, unidade, método, fonte, janela, claim_id, validation_id, PIT e limitações |
| rejected_claims | Contagem de claims excluídas, incluindo PIT desconhecido |
| point_in_time, analysis_scope | UNVERIFIED_POINT_IN_TIME e RETROSPECTIVE_ANALYSIS |
| limitations, uncertainty, missing_evidence | Limites determinísticos produzidos pelo relatório verificado |

Os nomes de observações aceitos são dataset_id, symbol, interval, window, candle_count, net_return_pct, max_drawdown_pct, pnl, final_equity, fees, total_costs e closed_trades. Métodos permitidos são `dataset-reader/1` e `persisted-backtest/1`. Cada observação preserva o valor verificado e suas limitações. Referências apontam a conteúdo congelado, sem oferecer ferramenta de resolução ao worker.

Campos excluídos abrangem candles, frozen.json, payload de protocolo/resultado, configuração de execução, ledger, saldo de carteira privada, caminhos locais, nome de usuário, ambiente, credenciais, .env, logs, conversas e dados de outros projetos. Strings arbitrárias de warnings do resultado também são excluídas. O contexto registra que esses warnings devem ser consultados no relatório confiável. Essa escolha evita transportar dados privados ou instruções eventualmente contidos em warnings e reduz a informação disponível ao mock.

O identificador de captura do pacote fica no bundle confiável. O contexto usa `evidence_content_hash` para preservar a reprodutibilidade entre capturas do mesmo conteúdo. IDs de protocolos e resultados aparecem exclusivamente como proveniência.

## Hashes e causalidade

SHA-256 usa o algoritmo existente de domínio ASCII, NUL e JSON canônico UTF-8 com chaves ordenadas. O domínio do contexto é `escryptorio:research-context:v1`, sobre todos os campos exceto context_id e content_hash. Ambos recebem o digest semântico. As-of pertence ao conteúdo. Horários de captura, geração e execução ficam fora dele. Request ID pertence ao envelope operacional.

Outros domínios novos são `escryptorio:worker-input:v1`, `escryptorio:worker-output:v1` e `escryptorio:validation-gateway:v1`. Os hashes financeiros e os domínios históricos permanecem sob os algoritmos existentes. SHA detecta divergência de conteúdo. Autenticidade externa permanece desconhecida.

VALIDATED preserva a semântica de reconciliação ao resultado persistido. O builder utiliza os validadores existentes. Claims causais com disponibilidade desconhecida são excluídas das observações e contabilizadas. Dataset posterior ao as-of é recusado pelo verificador v2. Produção posterior do backtest permanece retrospectiva com horário histórico de disponibilidade desconhecido. O mock preserva PIT e limitações, e o gateway exige correspondência integral.

## Worker e gateway

WorkerInput v1 contém schema_version, request_id limitado a 64 caracteres alfanuméricos/underscore/hífen, operation, policy_version, context e input_hash. A única operação aceita é DESCRIBE_VERIFIED_CONTEXT. O orçamento permanece exclusivamente no supervisor.

WorkerOutput v1 contém schema_version, request_id, context_id, context_hash, worker_version, status, observations, evidence_refs, limitations, uncertainty, point_in_time, analysis_scope, usage e output_hash. O mock stdlib copia deterministicamente as observações autorizadas e estima tokens de entrada. Não há interpretação de linguagem natural.

O gateway constrói independentemente a resposta esperada a partir da requisição confiável. Compara JSON canônico integral, rejeitando campos extras, omissões, alterações de valor/unidade/fonte/janela, identidade, uso declarado, limitações ou PIT. JSON duplicado, malformado, não finito e acima do limite é recusado. O resultado local VALIDATED_MOCK valida somente essa operação fixa. A futura validação de linguagem livre exige outro contrato e testes.

## Uso local

```powershell
.venv/Scripts/python -m cryptolab.research.ai_boundary.cli inspect-context --bundle <BUNDLE_V2>
.venv/Scripts/python -m cryptolab.research.ai_boundary.cli run-mock --bundle <BUNDLE_V2> --mode DEVELOPMENT_MOCK
```

Sem `--mode DEVELOPMENT_MOCK`, run-mock solicita ISOLATED_RESEARCH e retorna código 2 com ISOLATED_RESEARCH_UNAVAILABLE. A CLI imprime códigos de falha sanitizados e distingue NOT_SANDBOXED. Testes usam exclusivamente fixtures sintéticas. Um exemplo sintético de métrica pode ser net_return_pct, valor string `1.25`, unidade percent, método persisted-backtest/1 e janela UTC explícita. A aceitação exige correspondência com a fonte verificada, além dos IDs válidos.

Estado IMPLEMENTED e TESTED para o subconjunto determinístico descrito. Isolamento forte permanece DEFERRED. Ver [isolamento](AI_RESEARCH_ISOLATION.md), [orçamento](AI_RESEARCH_BUDGET.md) e [verificação](VERIFICATION.md).
