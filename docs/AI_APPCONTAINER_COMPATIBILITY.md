# Compatibilidade AppContainer ? 2.3D3A.2

Estado PREPARATION_COMPLETE_AWAITING_APPROVAL. Baseline main limpa em 7af1767efb0b3e1d73dcb52208a7dd07eaf82c7c. Skills de continuidade e seguran?a aplicadas. O diagn?stico atual usou token não elevado e objetos ef?meros.

| Observa??o atual | Classifica??o |
| --- | --- |
| JOB_ONLY executa o probe de token, saída 0 | CONFIRMED_CAUSE apenas para demonstrar runtime funcional nessa configura??o |
| AppContainer sem perfil falha em CreateProcessW com 203 | Falha confirmada, causa raiz UNVERIFIED_HYPOTHESIS |
| Restricted Token cria processo e encerra com 0xC0000022, sem resposta do probe | Falha de inicializa??o observada, componente exato NOT_VERIFIED |
| Aus?ncia de perfil utiliz?vel | SUPPORTED_HYPOTHESIS pelo fluxo oficial, sem teste diferencial autorizado |
| DLL, stdlib, desktop, sess?o ou permiss?es de runtime | UNVERIFIED_HYPOTHESIS, sem rastreamento suficiente para atribuir a um objeto espec?fico |
| Incompatibilidade geral com Windows Home | UNVERIFIED_HYPOTHESIS, erro 203 não permite essa conclus?o |

A instala??o Python e suas ACLs ficaram fora das altera??es. O runtime copiado inclui pythonw.exe, DLLs e stdlib, com arquivo _pth, sem site-packages ou m?dulos financeiros. O controle JOB_ONLY reduz a hip?tese de runtime universalmente quebrado, mas não prova compatibilidade sob identidade restrita. Nenhum probe nativo adicional foi necess?rio para comprovar os limites de Job existentes.

A revis?o Win32 conferiu HANDLE/ponteiros/SIZE_T x64, DWORD/BOOL, tamanhos e lifetime de SECURITY_ATTRIBUTES, SECURITY_CAPABILITIES, STARTUPINFOEX, PROCESS_INFORMATION, SID_AND_ATTRIBUTES e buffers de atributos. Initialize/Update/DeleteProcThreadAttributeList mant?m buffers vivos at? CreateProcess. Processo suspenso, associa??o e IsProcessInJob antecedem ResumeThread. O handle do Job fica fora da heran?a. CloseHandle, LocalFree e FreeSid t?m ownership e erro de libera??o expl?citos. HRESULT de DeriveAppContainerSid ? distinto de GetLastError das fun??es BOOL. Cria??o/exclus?o de perfil não integram o adapter nativo desta entrega.

A lacuna corrigida foi a falta de captura/confer?ncia de DACL. GetFileSecurityW agora captura os descritores de todos os objetos sint?ticos antes de qualquer altera??o. Ap?s SetFileSecurityW, GetSecurityDescriptorDacl compara ACEs, flags, SIDs e m?scaras, mapeando direitos gen?ricos de arquivo para a representa??o efetiva. A primeira compara??o bin?ria falhou porque GR/GX s?o expandidos pelo Windows. A corre??o preserva a pol?tica e verifica equival?ncia de direitos. No diagn?stico foram capturados 48 objetos. Descritores e SIDs ficam em mem?ria e s?o descartados com a inst?ncia.

OS_ISOLATION_PROVEN permanece limitado ?s provas de recursos. PYTHON_RUNTIME_COMPATIBLE sob AppContainer e nega??o de filesystem/rede permanecem NOT_VERIFIED. A ?rvore foi removida com cleanup COMPLETE.

Refer?ncias oficiais para leitura de seguran?a e criação/exclus?o de perfis. [GetFileSecurityW](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getfilesecurityw), [CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile), [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile).


# Native lifecycle preparation 2.3D3A.3

PREPARATION_COMPLETE_AWAITING_APPROVAL. Native read-only adapter and blocked mutation interfaces prepared. ProfileLifecycle supports an optional durable journal for synthetic tests. Recovery is inspection-only and uncertain ownership requires manual review. Reserved profile was absent in inspected storage/registry locations. No profile creation/deletion executed. See [native lifecycle](AI_APPCONTAINER_NATIVE_LIFECYCLE.md), [recovery](AI_APPCONTAINER_RECOVERY.md) and [authorized test plan](AI_APPCONTAINER_AUTHORIZED_TEST_PLAN.md). Filesystem/network enforcement remains NOT_VERIFIED; ISOLATED_RESEARCH remains unavailable.
