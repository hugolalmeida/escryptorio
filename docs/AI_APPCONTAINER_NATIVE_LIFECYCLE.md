# Native lifecycle · 2.3D3A.3

Estado PREPARATION_COMPLETE_AWAITING_APPROVAL. Baseline d50f93291477581a37b9cd2be3c1dfe1a1fc696e, main limpa. Componentes confiáveis são o supervisor, o runtime fixo e os verificadores. Bundle/contexto/saída do worker não concedem autorização. Skills de continuidade e segurança aplicadas.

NativeProfileAdapter prepara assinaturas ctypes em userenv.dll para CreateAppContainerProfile, DeleteAppContainerProfile e GetAppContainerFolderPath. As três retornam HRESULT de 32 bits. Nome/display/descrição são PCWSTR, capabilities PSID_AND_ATTRIBUTES e contagem DWORD, SID retornado PSID*. O SID é liberado por FreeSid. GetAppContainerFolderPath recebe SID em texto e PWSTR*, liberado por CoTaskMemFree de ole32.dll. Isso difere dos erros BOOL/GetLastError de criação de processo/Job/ACL. As estruturas x64 e o lifetime dos atributos continuam sob os contratos anteriores.

create_profile e delete_profile recusam sempre com REQUIRES_APPROVAL. Nenhuma flag ou variável habilita execução. A preparação nativa contém bindings e inspeção read-only, sem dispatcher de mutação autorizado nesta fase. Não há integração com produção. O exercício sintético continua no mesmo ProfileLifecycle, agora com journal opcional, preservando callers anteriores.

inspect_profile deriva o SID e consulta somente o armazenamento retornado e a chave exata HKCU AppContainer/Mappings desse SID. HRESULT_FROM_WIN32(FILE_NOT_FOUND/PATH_NOT_FOUND) é distinguido de outros erros. Não há enumeração de perfis ou leitura de conteúdo privado. verify_removal conserva NOT_VERIFIED porque ausência nessas duas localizações não prova ausência universal de resíduos.

Inspeção atual do nome Escryptorio.PoC.D3A2.20261115.8c514dea retornou folder_present=False, mapping_present=False e ABSENT_IN_INSPECTED_LOCATIONS. Nome/SID derivado não comprovam propriedade. Qualquer presença futura aborta prepare_creation com PROFILE_ALREADY_EXISTS. Permissão negada ou outro HRESULT aborta a inspeção. Nenhum perfil foi criado ou excluído.

SecurityEvidence v1 foi preservado. Não se criou v2 porque os estados de recuperação estão no contrato Record v1 separado, sem alterar o schema anterior. O journal não atribui enforcement de filesystem/rede. Probes de leitura/escrita/listagem protegida e listener local permanecem preparados. O probe outputs grava somente uma mensagem sintética em outputs da árvore própria. Concessão de escrita para AppContainer e execução sob perfil ficam reservadas ao ensaio futuro.

A revisão não confirmou a causa raiz do erro 203 nem do status 0xC0000022. Perfil ausente segue hipótese apoiada no fluxo documentado, e loader/DLL/desktop permanecem hipóteses sem prova. Python restrito, filesystem, loopback, DNS, TCP externo e IPC permanecem NOT_VERIFIED. Os controles Job anteriores são reexecutados nos testes existentes.

Referências oficiais das assinaturas e regras de liberação. [CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile), [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile), [GetAppContainerFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-getappcontainerfolderpath).


# Runner preparation 2.3D3A.4

PREPARATION_COMPLETE_AWAITING_APPROVAL. Closed runner policy/request and read-only approval manifest prepared. Native Win32 mutation bodies are disconnected from the operational adapter and exercised only through a synthetic API seam. execute_authorized_test always refuses. Mock end-to-end now binds operation/request to the durable journal, confirms runtime identity, runs fixture probes/gateway, stops resources and verifies profile/tree removal before CLEANED. Unexpected returned SID goes to manual review without deletion. See [runner](AI_APPCONTAINER_AUTHORIZED_TEST_RUNNER.md) and [approval manifest](AI_APPCONTAINER_APPROVAL_MANIFEST.md). Real filesystem/network containment remains NOT_VERIFIED.
