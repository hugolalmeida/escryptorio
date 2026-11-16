# OS resource receipts · 2.3D3A.4-BRIDGE

**TESTED** com processos benignos, Jobs descartáveis e árvores próprias no Windows. **NOT_VERIFIED** para ownership/Delete de perfil real, filesystem/network do AppContainer e ausência universal de handles/resíduos. Nenhum perfil real criado/excluído. Recibos não concedem autorização.

## Origem e valores

`OperationResources` vincula Record, Native, DirectoryScope e o Child existente antes de seu lançamento. `Child(native, resources=...)` é um hook opcional de ownership; o launcher, pipes, Job e cleanup continuam os da PoC. O coletor não implementa outro supervisor, não lança processos e não remove árvores. A fachada de perfil não gerencia processos nem aceita stop_and_release como prova; o bridge exige recibos independentes.

| Propriedade | TRUE | FALSE | NONE |
| --- | --- | --- | --- |
| process_stopped | Handle conhecido, IsProcessInJob confirma Job, Wait sinalizado e GetExitCodeProcess consultado; fato terminal preservado após fechamento. | Wait timeout zero observou processo ativo, com exit code consultado. | Handle/Job desconhecido, associação divergente ou consulta falha. |
| job_empty | QueryInformationJobObject consultou ActiveProcesses=0 e lista de PIDs vazia; snapshot conservado após fechamento próprio bem-sucedido. | Contagem/lista observou processo ativo. | Job desconhecido, query falha ou Job fechado antes de comprovar vazio. Kill-on-close isolado não prova vazio. |
| handles_released | CloseHandle bem-sucedido para todos os handles rastreados; streams CRT fechados e seus antigos valores retornaram INVALID_HANDLE em GetHandleInformation. | Algum handle conhecido segue aberto ou houve falha registrada de fechamento. | Nenhum conjunto completo conhecido ou valor de handle CRT possivelmente reciclado. |
| tree_absent / operation_directories_absent | Ausência observada sob ancestral preso, identidade do ancestral íntegra e todos os caminhos conhecidos da árvore ausentes. | Árvore/caminho conhecido ainda presente com identidade original. | Reparse, File ID divergente, acesso negado, caminho redirecionado ou consulta insuficiente. |
| ownership_confirmed | Somente recibo vivo do Create S_OK com SID confirmado e CREATED durável da mesma instância. | Contradição explícita de ownership, quando fornecida pelo supervisor. | Não existe criação confirmada; este é o resultado real desta fase. |
| delete_succeeded | Somente chamada Delete S_OK e verificações correspondentes do bridge. | Falha explicitamente observada, quando fornecida pelo supervisor. | API não executada ou resposta incerta; este é o resultado real desta fase. |

Código de saída não zero significa encerramento com erro funcional, não processo ativo. Um exit code 259 não substitui Wait: o sinal do handle determina encerramento. Erros de consulta zeram a observação corrente, sem promover valor antigo. Os diagnósticos do coletor conservam erros de processo/Job/fechamento e os últimos dados válidos disponíveis.

O registry em memória de handles impede duas operações de reclamarem o mesmo handle conhecido, incluindo ownership perdido sem fechamento comprovado. Não é uma fronteira do SO. Só o conjunto rastreado é coberto: nenhuma contagem local prova fechamento universal, inexistência de duplicatas externas ou ausência de handles em outros processos. Reutilização numérica incerta não autoriza fechar outro objeto. Falhas de CloseHandle/stream continuam registradas mesmo após limpeza posterior da fixture.

## Identidade, geração e consumo

Recibo nativo é a própria instância congelada de ResourceObservations emitida pelo coletor, associada à versão dos recursos e à geração atual do journal. Verificador exige o coletor correspondente para SUPERVISOR_READ_ONLY. Uma cópia JSON/model_copy, recibo anterior, outra operação/política/SID/token, journal diferente/falho ou geração alterada é recusado. Recolher dados invalida o recibo anterior. Consumir impede reutilização e sela a operação contra novos handles/Child/Job. Encerramento e inspeção dos recursos já conhecidos continuam possíveis.

Sem perfil real criado, os campos dependentes do perfil são NONE. Não se completa o recibo com True para alcançar um gate. O teste real que comprova processo/Job/handles/tree finalizados ainda recebe VERIFICATION_UNAVAILABLE por PROFILE_OWNERSHIP_NOT_VERIFIED; não pode publicar CLEANED.

Quando o perfil é FakeUserenv, o agregado recebe TESTED_MOCK, mesmo com recursos Win32 reais nos outros campos. Um teste específico mantém o journal em CLEANING e devolve RESIDUAL_RESOURCE_FOUND enquanto a árvore existe. Workers/bundles não fornecem esses recibos; nenhum callback True pode substituir as consultas do coletor.

## Escopo e corridas de diretórios

DirectoryScope captura raiz temporária existente e exclusiva, subdiretórios declarados e File IDs/volume do ancestral e dos caminhos. Recusa caminhos absolutos externos, `..`, caminhos não canônicos, arquivos no lugar de diretórios, junctions e outros reparse points. Consulta somente metadados, não conteúdo pessoal/financeiro. Acesso negado real numa fixture com DACL própria resulta em NONE, não ausência. Remover e recriar a raiz com outro File ID também resulta em NONE.

O ancestral fica aberto durante a inspeção, mas um processo com escrita legítima pode recriar uma entrada após a observação. O recibo é pontual; não elimina todas as corridas nem autentica contra o mesmo usuário/SYSTEM. Mudança detectada bloqueia; nenhuma limpeza de recursos desconhecidos tenta forçar sucesso. A futura conexão precisa preservar o selo da operação e a ordem de coleta/verificação/publicação.

## Provas executadas

`test_native_bridge_receipts.py` testa processo ativo/encerrado/erro, Job ativo/vazio, consulta falha, CloseHandle falho, diretório presente/removido/inacessível, junction, lançamento com outro Job, recibo copiado/velho/estrangeiro, manifesto adulterado, token elevado, HRESULT/SID/retorno perdido e falhas do journal antes/depois de Create simulado. Também testa renomeação/escrita recusadas com handles abertos, substituição de publicação recusada pelo SO e File ID divergente injetado com falha fechada. As mutações de perfil e a fachada DLL usam somente FakeUserenv. Não há código hostil, serviço externo ou processo financeiro.

Resultados finais e falhas intermediárias em [VERIFICATION](VERIFICATION.md). [Bridge e riscos residuais](AI_APPCONTAINER_NATIVE_BRIDGE.md). [GetHandleInformation](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-gethandleinformation) fundamenta a consulta limitada de handles; não certifica fechamento universal.
