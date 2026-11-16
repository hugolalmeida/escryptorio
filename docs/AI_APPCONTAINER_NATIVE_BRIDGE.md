# Native bridge · 2.3D3A.4-BRIDGE

**BRIDGE_READY_FOR_HUMAN_REVIEW.** Execução **NOT_AUTHORIZED**; `ISOLATED_RESEARCH_UNAVAILABLE`, filesystem/network **NOT_VERIFIED**. Nenhum Create/DeleteAppContainerProfile real executado. Este documento descreve código preparado, não autorização para conectá-lo. Revisão do bridge não significa ISOLATION_VERIFIED.

Baseline obrigatório confirmado: `main`, `4a3bac1eaafabdb0bcc5497496682e7403805dbe`, working tree limpa e sem alterações preexistentes. Commit local da entrega: `feat: prepare appcontainer native bridge and os receipts`; HEAD final no Git e na resposta da entrega. Não há push, PR, D3B, LLM ou integração financeira.

## Implementação e desconexão

`NativeProfileBridge` implementa estruturalmente `ProfileOperationPort`: `create_owned(Record) -> str` e `delete_owned(Record) -> None`. Recebe Journal, TestRequest e OperationResources. Sua API de mutação é **None por padrão**. Sem essa dependência de código, ambos os métodos recusam com PROFILE_CREATION_REQUIRES_APPROVAL. Não existe factory, endpoint, CLI, flag ou leitor de configuração que conecte a fachada nativa. `execute_authorized_test` continua sempre bloqueado e não importa o bridge; NativeProfileAdapter mantém create_profile/delete_profile bloqueados.

`NativeProfileCalls` prepara a adaptação dos bindings Win32 existentes: inspeção exata, lookup, discovery, conversão/liberação de SID e delegação das chamadas Create/Delete em userenv.dll. Seu construtor apenas prepara NativeProfileAdapter; nenhum caminho normal o instancia. A fachada não é conectada ao seam synthetic_only e é recusada por ele. `_ProfileMutationCalls` compartilha os corpos de chamada com o seam legado, evitando uma segunda implementação de HRESULT/SID. O bridge não depende da convenção synthetic_only.

As assinaturas permanecem HRESULT de 32 bits, LPCWSTR, ponteiro para SID_AND_ATTRIBUTES, DWORD e saída PSID*. Capabilities são NULL/count zero. Somente S_OK com SID não NULL, SID igual ao esperado e reinspeção correspondente aceitam criação. ERROR_ALREADY_EXISTS é normalizado com `& 0xffffffff`; S_FALSE e outros HRESULTs abortam. FreeSid ocorre no finally inclusive em falha parcial/conversão. Strings da inspeção continuam com CoTaskMemFree. A fachada DLL foi exercitada **somente com bindings FakeUserenv**, sem construir uma instância real dela ou chamar mutações do Windows.

Esta separação não impede código Python arbitrário do host de chamar Win32 com as permissões do usuário. Campos privados, nomes de classes e marcadores de origem não são uma fronteira de segurança nem autorização. A garantia desta entrega é a ausência de conexão com os executores disponíveis e a recusa desses executores. Conectar a API real ao bridge exige mudança de código revisada e autorização humana específica em outra tarefa, fora dos dados de worker/bundle.

## Criação e ownership

O bridge confere nome reservado `Escryptorio.PoC.D3A2.20261115.8c514dea`, hash de ProfilePolicy, operação/SID/token esperados, igualdade integral com a geração do journal, TestRequest/TestPolicy e manifesto exclusivo de bytes canônicos. Não interpreta AUTHORIZED, manifesto ou hash como consentimento humano: no caminho normal continua sem API de mutação. A autorização futura precisa anteceder uma conexão de código revisada; nenhum mecanismo de consentimento por arquivo/JSON foi criado.

Precondições testadas incluem token primário não elevado, perfil ausente no storage/mapeamento inspecionados, estado AUTHORIZED consistente, journal com guard e manifesto verificado. Antes de Create publica CREATING com flush/fsync/replace/read-back. Durante a chamada mantém journal/manifesto e seus ancestrais abertos para bloquear substituição e escrita comuns. Após confirmar o SID, publica CREATED. Só então conserva em memória o recibo vivo da criação e o associa ao coletor da mesma operação. Nome, SID derivado e journal recuperado não reconstroem esse recibo.

Falha de precondição bloqueia reutilização da instância. Retorno perdido, SID divergente, HRESULT inesperado e falha de journal após Create bloqueiam a instância e exigem revisão manual, sem Delete nem retry automático. Quando a publicação falha, não tenta forçar outra gravação sobre journal.failed. O recurso pode existir mesmo quando nenhum SID confirmado ficou durável.

## Exclusão preparada

Delete exige o recibo vivo da mesma instância, SID observado/esperado coincidentes, operação íntegra e estados permitidos. Publica CLEANING, coleta recibo atual e consome sua identidade em memória. Exige processo encerrado, Job vazio e handles conhecidos liberados antes de chamar a API. Uma vez consumido o recibo, a operação não aceita novos handles/Child/Job, mas pode atualizar observações de limpeza.

Após S_OK, verifica novamente lookup, storage e mapeamento exatos. Falha ou resíduo mantém ROLLBACK_INCOMPLETE; ownership incerto bloqueia para revisão manual. Delete nunca publica CLEANED. Esse estado depende do [verificador independente](AI_APPCONTAINER_ROLLBACK_VERIFICATION.md), incluindo ausência da árvore e recibos correspondentes. Falha funcional e falha de rollback não se compensam.

Quando FakeUserenv é a fonte do perfil, a observação agregada conserva TESTED_MOCK mesmo se seus processos e diretórios foram verificados no Windows. As provas de recursos reais são descritas separadamente em [OS receipts](AI_APPCONTAINER_OS_RECEIPTS.md). Nenhum recibo real de criação/exclusão de perfil está disponível.

## Journal e corridas

`pinned_paths` abre ancestrais antes dos filhos com CreateFileW/OPEN_EXISTING, OPEN_REPARSE_POINT e BACKUP_SEMANTICS, sem herança. Compara caminho final, atributos, número de links, volume e File ID de 128 bits por GetFileInformationByHandle/GetFileInformationByHandleEx. Diretórios negam delete sharing durante as operações críticas. Arquivos pedem GENERIC_READ para participar das restrições de compartilhamento e negam escrita/rename comuns durante leitura e verificações. Um handle somente de metadados não foi suficiente no teste real; essa versão foi corrigida.

OWNER/DACL são consultados no objeto aberto por GetKernelObjectSecurity e comparados com a política explícita proprietário/SYSTEM antes e depois do uso. A raiz mantém identidade congelada. O manifesto e a geração recebem criação exclusiva. O writer CRT exclusivo do temporário tem seu File ID capturado antes do conteúdo; a DACL é aplicada/verificada antes de escrever. Após flush/fsync/close, o temporário é aberto para leitura sem compartilhar escrita, comparado ao File ID do writer e mantido aberto durante replace com delete sharing específico para essa etapa. O destino publicado deve ter o mesmo File ID e bytes/hash esperados; a identidade publicada é capturada enquanto o destino está preso por handle.

Substituição, sharing violation, acesso negado, reparse point, caminho final inesperado, volume/File ID diferente ou falha de consulta impedem continuar. Falhas na entrada/saída dos contextos críticos também tornam journal.failed permanente. Schema Record v1, hash domain-separated, IDs, gerações e recovery somente leitura foram preservados.

**Limites:** não existe compare-and-swap atômico do destino por File ID no uso de os.replace. Há uma janela entre liberar a leitura do alvo anterior e executar replace; diretórios/temporário continuam presos e o destino é conferido depois. Um escritor legítimo do supervisor/SYSTEM continua fora da garantia de autenticidade. DACLs podem mudar, mappings previamente abertos e componentes do kernel não são cobertos universalmente. Observações de recursos são pontuais, não garantias futuras. Descritores/IDs indisponíveis são recusados, nunca convertidos em autorização. Não se declara eliminação universal de TOCTOU ou proteção contra o próprio usuário administrador. A raiz operacional LOCALAPPDATA não foi criada.

## Relatório dos 14 itens

| # | Entrega |
| --- | --- |
| 1 | HEAD inicial completo acima, main limpa. |
| 2 | HEAD final consultável no Git/resposta; assunto do commit acima. |
| 3 | Novos native_bridge.py, os_receipts.py, windows_paths.py, test_native_bridge_receipts.py e dois documentos. Alterados bindings, facade/call bodies, Child, guard/journal, verificador e documentação exigida; lista exata no commit. |
| 4 | Bridge tipado e fachada DLL implementados, com corpo de chamada compartilhado. |
| 5 | Desconectado para não conceder execução nesta fase; default sem API, executor bloqueado, sem factory/CLI/flag. |
| 6 | Processo, Job, handles conhecidos, diretórios e erros verificados em fixtures Win32 benignas. |
| 7 | Ownership/Delete de perfil real indisponíveis; FS/rede e compatibilidade AppContainer não comprovadas. |
| 8 | Handles, caminho final, File ID/volume, SD por handle e identidade writer/temporário/publicação. |
| 9 | Janela do replace, controle do mesmo usuário/SYSTEM e snapshots pontuais, sem autenticidade universal. |
| 10 | Comandos/saídas/exit codes, falhas intermediárias e resultados finais em [VERIFICATION](VERIFICATION.md). |
| 11 | Fingerprint financeiro preservado; 38/38 replays, 14 legados, origem ro/query_only e backup temporário removido. |
| 12 | Zero perfil real, journal operacional, firewall, conta, serviço ou mudança global. ACLs apenas em fixtures; processos/Jobs benignos efêmeros. Pytest pode reter fixtures recentes em TEMP. |
| 13 | BRIDGE_READY_FOR_HUMAN_REVIEW após 603 testes completos/1 skip e249 direcionados, exit0; nunca significa ISOLATION_VERIFIED ou autorização. |
| 14 | Revisar commit/riscos e decidir separadamente eventual conexão/ensaio, com perfil/política exatos e rollback revisado. Não iniciar D3B. |

Referências: [CreateFileW e compartilhamento](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [informações por handle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle), [FileIdInfo](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex), [caminho final](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew), [SD por handle](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getkernelobjectsecurity), [Create](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile), [Delete](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile).
