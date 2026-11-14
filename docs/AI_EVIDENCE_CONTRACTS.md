# Contratos propostos originalmente

Implementação parcial v1 em [AI_EVIDENCE_IMPLEMENTATION.md](AI_EVIDENCE_IMPLEMENTATION.md): dataset histórico aprovado, relatório determinístico, bundle e verificação offline. Os contratos de LLM, múltiplas fontes, teses e persistência transacional descritos abaixo continuam propostos, não implementados. As identidades implementadas separam conteúdo e captura/geração.

## Evidence Package v1

Envelope conceitual: `schema_version`, `package_id`, `mode` (`RETROSPECTIVE` ou `RECENT_OBSERVATION`), `as_of_ms`, `created_at_ms`, `symbol`, `interval`, `window` UTC `[start,end)`, `sources[]`, `metrics[]`, `assumptions[]`, `missing[]`, `freshness`, `validation`. Cada fonte traz `kind`, `id`, hash canônico, intervalo, timestamp de origem/coleta, disponibilidade conhecida, versão e referência local autorizada. Métricas incluem unidade, valor Decimal como string, método, período e ID da fonte. Preço e regras não são consultados diretamente pela LLM.

Identidade proposta: SHA-256 do payload canônico versionado UTF-8, chaves ordenadas, valores financeiros em strings decimais normalizadas, sem floats; `package_id` é excluído do próprio hash. `created_at_ms` pertence ao envelope de captura, portanto capturas com horário distinto produzem IDs distintos; uma futura implementação poderá definir separadamente um `content_hash` que exclua captura, com versão e domínio explícitos. Não usar hash como assinatura ou prova de origem confiável. O pacote é congelado para a sessão; referências apontam a cópias ou registros imutáveis verificados, não apenas a IDs que possam desaparecer. Nenhuma serialização nova altera o hash histórico.

O `dataset_id` identifica candles fechados do dashboard; o dataset histórico aprovado tem seu próprio hash e manifesto. `snapshot_hash` representa o snapshot integral canônico e **não** equivale ao ID do dataset. `protocol_id`, `result_id`, `arena_id`, `package_id` e `report_id` pertencem a domínios distintos; cada vínculo precisa ser validado na origem. Snapshot atual é substituível; seu hash e conteúdo devem ser congelados. Separar instante de origem, coleta, disponibilidade, captura e as-of.

Retrospectiva: todos os fatos e documentos devem ter `available_at <= as_of`; se a disponibilidade histórica não for comprovada, excluir ou marcar `UNVERIFIED_POINT_IN_TIME` e não usar como evidência causal. Um backtest produzido depois do as-of pode ser análise retrospectiva explicitamente rotulada, não evidência disponível naquele instante; configuração, seleção e resultados posteriores exigem barreira para evitar leakage. Não deixar Arena, treino ou escolha de parâmetros consultar o teste para ajustar hipótese. Notícias externas estão fora do escopo de ingestão nesta fase.

## Research Report v1

Campos: `schema_version`, `report_id`, `evidence_package_id`, `research_objective`, `research_mode`, `symbol`, `interval`, `bull_thesis[]`, `bear_thesis[]`, `risk_assessment[]`, `unsupported_claims[]`, `missing_data[]`, `uncertainty[]`, `limitations[]`, `model_provenance`, `estimated_cost`, `validation_result`, `generated_at_ms`. Cada claim: `claim_id`, `statement`, `evidence_refs[]`, `counterarguments[]`, `confidence_label`, `confidence_rationale`. Rótulo de confiança é qualitativo e não é probabilidade calibrada.

O `report_id` proposto é SHA-256 com domínio e versão próprios, calculado sobre o relatório canônico sem o próprio ID, incluindo pacote, proveniência, resultado da validação e horário de geração. Mesmo pacote não implica mesmo ID ou conteúdo quando há geração em momentos diferentes ou saída não determinística. Uma revalidação posterior gera novo artefato, preservando o original.

Proveniência de modelo, quando houver: fornecedor, modelo/revisão efetivamente informada, hash de prompt e schema, parâmetros, tokens observados, uso de cache, timestamps, origem e versão do validador; campos não conhecidos são `null`. Chave ou token de autenticação nunca é proveniência. Custo estimado é valor e moeda com fonte/data explícitas ou ausente; não inventar gasto.

Estados propostos: `VALIDATED` = schema, vínculos, limites temporais e métricas automáticas aprovados, **não** garantia da verdade das teses; `PARTIALLY_SUPPORTED` = fatos não críticos pendentes identificados; `INSUFFICIENT_EVIDENCE` = falta essencial; `INVALID` = contrato, integridade, valor ou proibição violada; `UNAVAILABLE` = falha operacional. A política final de priorização e interpretação depende de testes. Dados stale não podem ser classificados como atuais.

Schema fechado, tipos e limites de tamanho; rejeitar chaves desconhecidas e recursivamente `execute_order`, `broker_order`, `private_wallet`, `place_trade`, `leverage`, `guaranteed_profit`, `automatic_execution_approval`. Isso não impede instruções operacionais em texto livre: validador de política e revisão humana devem também examinar conteúdo e remover qualquer capacidade de execução independentemente do texto. Referências válidas não comprovam que uma tese decorra da evidência; usar verificação determinística de métricas e revisão humana.

Exemplo **sintético esquemático**, placeholders não são hashes reais nem preços:

```json
{
  "schema_version": 1,
  "report_id": null,
  "evidence_package_id": "<sha256-do-pacote>",
  "research_mode": "RETROSPECTIVE",
  "symbol": "BTCUSDT",
  "interval": "60",
  "bull_thesis": [{"claim_id": "C1", "statement": "Hipótese descritiva sujeita a revisão.", "evidence_refs": ["<id-verificado>"], "confidence_label": "qualitativa", "confidence_rationale": "não calibrada", "counterarguments": ["Amostra insuficiente"]}],
  "bear_thesis": [],
  "missing_data": ["Liquidez histórica não comprovada"],
  "validation_result": "INSUFFICIENT_EVIDENCE",
  "model_provenance": null,
  "estimated_cost": null,
  "generated_at_ms": null
}
```

É exemplo parcial ilustrativo, não uma instância validada do futuro schema. O schema completo deve definir obrigatoriedade, limites e algoritmos de identificação antes da implementação. Relatórios iniciais: exportação local explícita com hash e manifesto; persistência imutável transacional é adiada até requisito comprovado e ADR revisado.
