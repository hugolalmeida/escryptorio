# Validação determinística de alegações

O módulo `research/evidence/claims.py` valida fatos estruturados de histórico; `metrics.py` reconcilia métricas com resultado de backtest congelado; `backtest.py` verifica dataset, protocolo e resultado, com SHA histórico e ligações de símbolo, janela, configuração, custos, regras de instrumento e versão. Não reexecuta estratégia nem calcula métricas. `bundle_v2.py` produz pacote e relatório v2, preservando a leitura de bundles v1. Não existe LLM, NLP, recomendação, ordem, paper ou endpoint novo.

Claim v1 é objeto fechado com `schema_version`, `claim_id`, `claim_type`, `subject_id`, `predicate`, `value`, `unit`, `evidence_refs`, `window`, `method` e `availability_scope`. O ID é SHA-256 do domínio `escryptorio:claim:v1`, NUL e JSON canônico do corpo sem ID. O resultado tem ID no domínio `escryptorio:claim-validation:v1`, sem relógio. Limite: 100 claims, 4096 bytes por claim; uma referência por claim. `SOURCE_FACT` admite `dataset_id`, `symbol`, `interval`, `window`, `candle_count` e método `dataset-reader/1`. `VERIFIED_METRIC` admite `net_return_pct`, `max_drawdown_pct`, `pnl`, `final_equity`, `fees`, `total_costs` e `closed_trades`, método `persisted-backtest/1`, unidades respectivamente `percent`, `USDT` ou `count`. Decimais são strings finitas e comparados numericamente via Decimal, sem arredondamento; contagens são inteiros estritos.

`INVALID` tem precedência para schema, ID, referência, método, unidade, janela ou valor incorreto. Se íntegro e exato, escopo `RETROSPECTIVE_ANALYSIS` é `VALIDATED` apenas como reconciliação com conteúdo persistido; escopo `CAUSAL_INFORMATION` é `UNVERIFIED_POINT_IN_TIME`. O dataset inteiro precisa terminar até `as_of_ms`. Nenhum horário de produção do backtest ou disponibilidade histórica é inventado; não é previsão anterior ao evento. Um hash não comprova autenticidade externa nem correção matemática: o verificador compara com o resultado armazenado e não o recalcula. Não há `PARTIALLY_SUPPORTED`, `UNAVAILABLE` ou `INSUFFICIENT_EVIDENCE` como estados de claim implementados nesta versão; erros operacionais são erros explícitos, e tipos de claim não suportados são inválidos.

## Exemplos sintéticos

Um corpo de claim usa placeholders, não valores financeiros reais:

```json
{"schema_version":1,"claim_type":"VERIFIED_METRIC","subject_id":"<id-do-resultado>","predicate":"net_return_pct","value":"1.25","unit":"percent","evidence_refs":["<id-do-resultado>"],"window":{"start_ms":1704067200000,"end_ms":1704153600000},"method":"persisted-backtest/1","availability_scope":"RETROSPECTIVE_ANALYSIS"}
```

Use `cryptolab.research.evidence.claims.claim` para calcular `claim_id`. Se o resultado verificado registrar `1.25`, o valor pode ser validado retrospectivamente; se registrar `1.24`, é `INVALID`; se o escopo for `CAUSAL_INFORMATION`, o valor correspondente permanece `UNVERIFIED_POINT_IN_TIME`. Este exemplo não é resultado de mercado.

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python -m cryptolab.research.evidence.cli build-backtest --result-id <SHA256> --as-of-ms <TIMESTAMP_EM_MS> --claims <CLAIMS_JSON> --output <NOVO_DIRETORIO>
.venv/Scripts/python -m cryptolab.research.evidence.cli verify --bundle <DIRETORIO>
```

O JSON de claims é uma lista dos objetos completos, incluindo IDs. O bundle v2 inclui evidência, relatório, claims, fontes congeladas e manifesto; verificação reconstrói os resultados offline. Pacotes/report v2 usam domínios `escryptorio:evidence-content:v2`, `escryptorio:evidence-capture:v2`, `escryptorio:report-content:v2`, `escryptorio:report-generation:v2` e `escryptorio:backtest-frozen:v2`; os hashes v1 não são reescritos. Limite de 64 MiB por arquivo e profundidade 64, até 100.000 candles no histórico, sem prazo máximo nem benchmark no limite. A nova restrição de profundidade também se aplica a v1: um bundle antigo aceito com estruturas mais profundas pode agora ser recusado; compatibilidade universal não foi comprovada. Uma fonte histórica e um resultado por bundle; Arena, comparações entre resultados e fatos de outras origens são adiados.

Exportação usa diretório temporário irmão, fsync dos arquivos, verificação e rename; não é sandbox contra processo hostil com acesso simultâneo ao mesmo diretório. As verificações de symlink e existência não eliminam corrida entre checagem e abertura/publicação em todos os sistemas. Use diretório local controlado pelo usuário. SHA-256 detecta corrupção, não substitui assinatura. Os testes sintéticos e lacunas restantes estão em [VERIFICATION.md](VERIFICATION.md).
# Atualização 2.3D2.H1

A política legada do v1 foi ampliada para profundidade 256; v2 permanece em 64. Ver a matriz e a limitação residual em [AI_EVIDENCE_HARDENING.md](AI_EVIDENCE_HARDENING.md).
