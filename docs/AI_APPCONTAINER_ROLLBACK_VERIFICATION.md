# Atualização · 2.3D3A.4-BRIDGE

O coletor [OperationResources](AI_APPCONTAINER_OS_RECEIPTS.md) agora emite recibos reais de processo/Job/handles conhecidos/diretórios, vinculados à operação, versão e geração. Para SUPERVISOR_READ_ONLY o verificador exige a própria instância de recibo emitida pelo coletor correspondente e a consome; cópia, recibo estrangeiro ou antigo são recusados. Dados de worker nunca alimentam esse caminho. Ownership desconhecido é NONE e devolve VERIFICATION_UNAVAILABLE; nada completa esse campo com True para um perfil não criado. NativeProfileBridge prepara Delete somente após recibos obrigatórios; S_OK com verificação suficiente pode confirmar Delete, falha/resíduo confirmado é False, resposta perdida é None. O bridge não publica CLEANED. Perfil mock mantém TESTED_MOCK no agregado. Todas as mutações reais continuam não autorizadas, mesmo com os recursos benignos comprovados. [Bridge](AI_APPCONTAINER_NATIVE_BRIDGE.md) registra pinning, recuperação e riscos atuais; o texto abaixo preserva o estado anterior.

# Verificação de rollback · 2.3D3A.4-GATE

**PREPARED_NOT_EXECUTED / NOT_AUTHORIZED** para rollback real. `rollback_verification.py` não chama Delete, não escreve no journal, não mata processos, não enumera perfis e não remove diretórios. O supervisor consulta o mapeamento HKCU exato do SID e o storage retornado pela API. Derivar SID não demonstra existência.

`ResourceObservations` é contrato fechado, estrito, congelado e separado da resposta do worker. Identifica operação, política de perfil, ownership token e SID esperado. As observações de ownership/Delete/processo/Job/handles/diretórios/tree devem vir do supervisor confiável; dados de worker ou bundle não podem fornecer esses recibos. Nenhum recibo é uma autorização. Nesta fase esses recibos são **TESTED_MOCK**; um coletor de recibos Win32 para a operação futura continua **DEFERRED**. Não se inventam valores positivos quando a observação não existe.

| Resultado estruturado | Significado |
| --- | --- |
| PROFILE_ABSENT_IN_CHECKED_LOCATIONS | Mapeamento/storage ausentes e todos os recibos disponíveis positivos; limitado aos locais e recursos conhecidos. |
| PROFILE_PRESENT | Mapeamento exato ainda presente. |
| RESIDUAL_RESOURCE_FOUND | Storage presente ou processo/Job/handle/diretório/tree/Delete não confirmado positivamente. |
| VERIFICATION_UNAVAILABLE | Acesso negado, journal/caminho indisponível ou alguma observação ausente. |
| VERIFICATION_ERROR | Identidade/ownership/journal incoerente, SID divergente, HRESULT/erro inesperado. |

Após checar schema/identidade, o verificador relê o journal sem alterá-lo e compara com a geração em memória. Estado deve ser CLEANING ou CLEANED; SID observado deve coincidir com esperado. Ownership precisa de recibo do Create S_OK da operação viva, além de concordância com journal e estado externo. Um journal recuperado não reconstrói esse recibo.

O runner sintético encerra recursos antes de Delete e depois remove sua tree. Antes de CLEANED, exige verificação independente positiva, ligada à mesma operação/política/token/SID. Job ativo, handle não liberado, storage ou tree residuais e observações desconhecidas impedem CLEANED. Falha de limpeza prevalece sobre sucesso do gateway. Ownership conflitante mantém revisão manual; demais falhas de limpeza mantêm ROLLBACK_INCOMPLETE. Se o journal falhar, conservar estado durável conhecido e bloquear a sessão, sem tentar forçar outra publicação.

O journal operacional futuro exige `validate_journal_preflight`; o verificador com fonte SUPERVISOR_READ_ONLY já recusa um journal sem guard. Um resultado TESTED_MOCK nunca atesta isolamento do SO. O journal Record v1 não ganhou campos com semântica incompatível; CLEANED antigo continua `CLEANED_REQUIRES_STORAGE_VERIFICATION` no recovery read-only.

## Matriz de crash

| Janela | Conduta |
| --- | --- |
| Antes de Create, inclusive falha de fsync da intenção | Não chamar Create; bloquear sessão falha. |
| Durante Create / perfil criado com resposta perdida | CREATING/estado manual, reinspecção read-only e revisão humana; nenhum Delete por nome. |
| SID retornado, fsync/replace/read-back falha | Manter recurso; estado em memória manual; arquivo pode conservar CREATING ou publicação não confirmada. |
| Publicação parcial/corrupta/substituída | Rejeitar leitura/writer; nenhum retry automático. |
| CREATING com perfil presente/ausente/SID divergente | MANUAL_REVIEW_REQUIRED em todos os casos. |
| Delete retorna e confirmação se perde | ROLLBACK_INCOMPLETE ou CLEANING durável; não repetir Delete automaticamente. |
| CLEANING com perfil presente | Recurso residual, revisão; nenhum segundo Create ou limpeza por prefixo. |
| CLEANED lido após reinício | Reinspecção externa obrigatória; nunca garantia universal de ausência. |

Testes exercitam essas janelas com FakeUserenv e perfis em memória. ACL/junction usam apenas árvore descartável. Nenhum teste cria/exclui perfil real. Processos/Jobs do Windows pertencem aos controles benignos preexistentes, sem perfil AppContainer. Não se certifica apagamento universal, ausência de todos os caches do Windows ou negação de arquivos/rede ao worker.
