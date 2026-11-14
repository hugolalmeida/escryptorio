# Evidência e relatório determinístico v1

Esta fase implementa exclusivamente pesquisa offline com dataset histórico aprovado; não implementa IA, agentes, recomendações nem execução. A leitura usa SQLite `mode=ro`, `query_only` e transação, capturando payload e manifesto na mesma visão. `DatasetReader` verifica o dataset congelado com o algoritmo histórico existente. Não são executadas migrations, estratégias, Arena, monitor ou paper. As fontes de backtest, protocolos e Arena ficam adiadas e são rejeitadas pela CLI.

## Contratos e identidade

`research/evidence/core.py` define o contrato v1; `bundle.py` exporta e valida; `cli.py` oferece operações explícitas. O pacote contém versão, modo, `as_of_ms`, símbolo, intervalo, janela UTC `[start_ms,end_ms)`, fonte única, métricas vazias, premissas, ausências, frescor e validação, além de `content_hash`, `capture_id` e `captured_at_ms`. A fonte aponta o SHA histórico, SHA-256 dos bytes do manifesto, versão, proveniência e tempos desconhecidos representados por `null`. O bundle contém o payload e manifesto históricos originais como strings, preservando seus hashes anteriores.

Canonicalização v1: JSON UTF-8, `ensure_ascii=false`, chaves ordenadas, separadores compactos; strings são preservadas sem normalização Unicode, números são inteiros, floats e constantes não finitas são rejeitados. Valores financeiros nas fontes históricas são strings decimais normalizadas pelo algoritmo histórico. Arrays mantêm sua ordem; v1 possui exatamente uma fonte e nenhuma métrica financeira. O verificador reconstrói os contratos fechados e rejeita campos extras ou diferentes. Os hashes novos são SHA-256 de domínio ASCII, byte NUL e JSON canônico: `escryptorio:evidence-content:v1` sobre corpo sem IDs/captura; `escryptorio:evidence-capture:v1` sobre `{content_hash,captured_at_ms}`; `escryptorio:report-content:v1` sobre corpo do relatório; `escryptorio:report-generation:v1` sobre `{report_content_hash,generated_at_ms}`. Captura ou geração diferente muda o ID respectivo, sem alterar o hash semântico correspondente. Hashes não são assinaturas e não comprovam autenticidade da Bybit.

O relatório `DETERMINISTIC_REPORT` identifica pacote, objetivo, modo, símbolo, intervalo e janela; seus fatos de ID e contagem referenciam o dataset verificado. Métricas e observações estão vazias. Inclui ausências, limitações, incerteza, validação e versão do gerador. Não há tese, previsão, confiança probabilística, preço ou recomendação.

## Tempo e limites

Todos os tempos são inteiros em milissegundos UTC. O fim da janela é o fechamento do último candle, exclusivo, e não pode exceder `as_of_ms`; o as-of não pode exceder a captura. A cobertura contígua e os candles fechados são verificados por `DatasetReader` e `canonical_history`. Nem o fechamento nem a coleta provam disponibilidade histórica: ambos os modos recebem `UNVERIFIED_POINT_IN_TIME`, `available_at_ms=null` e `freshness=UNKNOWN`. Logo não são evidência causal nem classificação de dados atuais. Resultados posteriores, PIT verificável, múltiplas fontes e comparação de janelas de treino/teste ainda não são suportados.

O limite é uma fonte e zero métricas, até 100.000 candles conforme `HistoryRequest`, 64 MiB por arquivo e 64 MiB de fonte no banco. Os cinco datasets locais observados tinham no máximo 2.976 candles e payload de 408.337 bytes; isso não comprova desempenho para o máximo teórico. A reconstrução é linear no tamanho da fonte; não há prazo máximo de execução nem benchmark de 100.000 candles. A validação tem custo de memória proporcional aos arquivos; acesso concorrente hostil ao diretório não é uma fronteira de segurança garantida.

## CLI PowerShell

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python -m cryptolab.research.evidence.cli build --source approved-history --source-id <SHA256_DO_DATASET> --as-of-ms <FIM_OU_POSTERIOR_EM_MS> --output <DIRETORIO_NOVO>
.venv/Scripts/python -m cryptolab.research.evidence.cli verify --bundle <DIRETORIO_NOVO>
```

`--database` opcional especifica banco local; `--mode` seleciona `RETROSPECTIVE` ou `RECENT_OBSERVATION`. O diretório de saída deve ser novo e seu pai deve existir. Exporta em diretório temporário irmão, verifica e publica por rename; não sobrescreve propositalmente. Bundle contém exatamente `source.json`, `evidence.json`, `report.json` e `manifest.json`. A verificação offline confere arquivos, hashes, IDs, conteúdo, vínculos e tempos sem banco ou rede; não reconcilia com banco de origem. Sem assinatura, um atacante capaz de substituir toda a fonte e recalcular todos os hashes pode criar outro bundle íntegro. A validação de symlinks não elimina corridas de alteração por outro processo com acesso ao diretório.

Testes sintéticos verificam identidade, janela, adulteração, campos inesperados, referências, manifesto e ausência de mutação das tabelas do banco isolado. Não inferir desses testes uma prova completa contra todas as falhas de sistema ou de point-in-time.
