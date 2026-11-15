# Hardening de evidências 2.3D2.H1

Baseline: commit `2816d67c9ee919f098244d4952447ae4f7f1de2c`, working tree limpo e 36 testes de evidências aprovados. A pesquisa por `manifest.json`, `evidence.json` e `frozen.json` no repositório, excluindo dependências e build, não encontrou bundle anterior. Não foi feita busca em todos os diretórios do computador; não afirmamos inexistência de artefatos externos.

## Problemas reproduzidos e correções

Uma fixture sintética gerada pelo código `c97f00a` com metadados de manifesto aninhados em 70 níveis foi aceita pelo v1 original, mas rejeitada com `SCHEMA_INVALID` pelo código isolado `2816d67`. O verificador v1 agora usa limite de profundidade **256** para o conteúdo histórico embutido; o contrato atual permanece com limite **64**. Não se alterou serialização nem hash v1. Um v1 que antes excedesse 256 ainda pode ser recusado para limitar consumo: compatibilidade universal não é afirmada. Limites de arquivo continuam 64 MiB, claims 100 e 4096 bytes por claim; limite de histórico 100.000 candles não foi exercitado no máximo.

A CLI escolhia o verificador pela presença de `frozen.json`. Agora lê primeiro `manifest.json` com tamanho limitado, JSON estrito, schema inteiro conhecido e campos esperados; chama apenas o verificador da versão declarada. Layout incompatível, arquivos extras, versão desconhecida e ausência de manifesto falham. Argumentos inválidos retornam JSON com `ARGUMENT_INVALID`, estado `INVALID` e código de saída não zero. Falhas previsíveis de entrada retornam códigos sanitizados; falhas inesperadas não são convertidas em sucesso.

## Matriz de compatibilidade

| Caso | Resultado | Evidência |
| --- | --- | --- |
| v1 simples sintético, gerado por `c97f00a` | ACCEPTED | `test_golden_v1_previous_code_and_bytes` verifica bytes e IDs fixos. |
| v1 sintético com 70 níveis, gerado por `c97f00a` | ACCEPTED | `test_v1_deep_legacy_golden`; `2816d67` rejeitava. |
| v1 próximo de 64 MiB | NOT_TESTED | Sem benchmark no limite de arquivo. |
| v1 com tempos de captura distintos | ACCEPTED | Teste sintético existente de identidade semântica. |
| v1 adulterado ou manifesto inválido | REJECTED_AS_EXPECTED | Testes de hash, campos e caminhos. |
| v1 real anterior | NOT_TESTED | Nenhum bundle encontrado na busca limitada ao repositório. |
| v2 válido | ACCEPTED | Fixture sintética e verificação offline existentes. |
| v2 adulterado ou layout incompatível | REJECTED_AS_EXPECTED | Testes de hashes e claims adulteradas. |

As fixtures `backend/tests/fixtures/evidence_v1_golden` e `evidence_v1_deep_golden` foram geradas exclusivamente com dados sintéticos pelo código extraído do commit `c97f00a`, com tempos fixos; não são dados reais. O teste guarda independentemente os hashes dos três arquivos, IDs de conteúdo, captura, relatório e manifesto. O conteúdo sintético profundo tem hash semântico `f535553e7607d9dcbca8d0c4042d6e420d3649ee8a1ec954aafedabd960b66da`.

V1 contém `source.json`, `evidence.json`, `report.json` e `manifest.json`; v2 contém `frozen.json`, `claims.json`, `evidence.json`, `report.json` e `manifest.json`. O manifesto identifica a versão e hashes dos arquivos. Os domínios e campos de ambos estão em [AI_EVIDENCE_IMPLEMENTATION.md](AI_EVIDENCE_IMPLEMENTATION.md) e [AI_CLAIM_VALIDATION.md](AI_CLAIM_VALIDATION.md).

Testes adicionais exercitam JSON inválido e duplicado, UTF-8 inválido, limites de profundidade, caminhos no manifesto, dispatch, versão desconhecida, `fsync` interrompido, vínculos de backtest alterados com hashes recalculados, unidade e valor inválidos e precedência de erro sobre PIT. Symlink é testado quando o Windows permite criá-lo. Os testes sintéticos anteriores comparam o banco isolado antes/depois; não foi feita comparação integral do banco pessoal.

Os exportadores usam diretório temporário irmão, flush/fsync e rename, mas checagens de caminho não impedem todas as corridas com outro processo que controle o diretório. Use diretório local controlado; não há garantia absoluta de isolamento ou assinatura. Disponibilidade histórica permanece `UNVERIFIED_POINT_IN_TIME`; métricas são reconciliadas ao resultado persistido e não recalculadas. Não há rede, execução, LLM ou mutação financeira nesta funcionalidade.

Claims idênticas repetidas são preservadas como entradas repetidas com a mesma identidade de validação, por compatibilidade com o contrato v2 anterior; não representam evidências independentes. Mais de 100 claims são rejeitadas. Decimal usa comparação numérica exata sem arredondamento e aceita representações equivalentes, com limite de 128 caracteres; valores não finitos e expoentes que o Decimal não consegue representar são rejeitados. Não foram exercitadas todas as combinações adversariais ou o limite superior de arquivo.

Para avançar à 2.3D3, revisar cobertura adversarial restante, ensaiar bundles históricos reais se forem encontrados, avaliar limites máximos e ameaça de concorrência no ambiente de implantação. Nada aqui autoriza agentes ou operações.
