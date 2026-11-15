# Authorized test runner · 2.3D3A.4

Estado PREPARATION_COMPLETE_AWAITING_APPROVAL. Baseline main limpa em 1fd80d2be38282c9718fdefcfc5ee78b74db48ad. Skills locais de continuidade e segurança aplicadas. Supervisor, política, lifecycle, journal e verificadores são confiáveis. Bundle e saída de worker são dados sem autorização operacional.

## Separação operacional

prepare_authorized_test produz política, pedido e inspeção read-only, sem criar journal ou perfil. execute_authorized_test sempre retorna PROFILE_CREATION_REQUIRES_APPROVAL, inclusive se receber approve=True. As entradas create_profile/delete_profile do NativeProfileAdapter conservam o bloqueio anterior. Nenhuma CLI, variável ou arquivo habilita execução real. ISOLATED_RESEARCH permanece indisponível.

PreparedNativeMutationContract contém corpos revisáveis das chamadas CreateAppContainerProfile e DeleteAppContainerProfile. Seu construtor exige API explicitamente sintética. NativeProfileAdapter tem synthetic_only=False e não pode ser conectado a esse seam. Um procedimento operacional nativo separado ainda exige revisão e autorização futura. O objetivo do marcador sintético é separar os fluxos normais de teste; código local arbitrário executado pelo usuário continua fora dessa garantia.

Os corpos usam nome exato, capabilities NULL/count zero, HRESULT S_OK e ponteiro SID inicializado em NULL. ALREADY_EXISTS é distinguido de outros HRESULTs, incluindo valores assinados e S_FALSE inesperado. SID retornado é convertido/confrontado e liberado via FreeSid. A exclusão exige SID de ownership confirmado novamente, HRESULT S_OK, lookup ausente e verificação separada do armazenamento. Call bodies foram executados somente contra DLL fictícia. CoTaskMemFree permanece responsável pelas strings do getter read-only.

Referências oficiais das assinaturas e ownership. [CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile), [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile).

## Fluxo sintético

TestPolicy é fechada, congelada e usa domínio escryptorio:authorized-test-policy:v1. Inclui nome, capabilities, runtime relativo fixo worker/pythonw.exe, política de arquivos/rede, 64 MiB por processo, 96 MiB por Job, um processo e três segundos. TestRequest identifica operação e hash dessa política. Não contém aprovação ativável.

exercise_mock_runner exige adapters sintéticos para perfis e fixtures. Antes de qualquer criação, valida operação e hashes e grava runner-request.json exclusivamente no diretório próprio do journal, com flush/fsync/read-back. Esse arquivo correlaciona pedido/política e ownership_token com o journal v1 sem alterar hashes legados. Arquivo preexistente não é sobrescrito. Uma gravação inicial parcial implica revisão manual, sem criação automática ou retry da mesma operação.

O fluxo usa o ProfileLifecycle existente. Após criar e conferir SID no adapter, prepara árvore, aplica ACL, simula lançamento suspenso/Job, confirma runtime/identidade, executa probes e gateway mockados. Antes de excluir perfil, encerra processos e libera recursos. Exclusão, verificação de ausência do perfil e remoção/verificação da árvore precedem CLEANED no journal. Falha de parada impede exclusão. Falha de remoção conserva ROLLBACK_INCOMPLETE e prevalece sobre sucesso funcional.

A revisão encontrou uma falha no caminho de SID divergente do lifecycle com journal. Um SID diferente do esperado podia ser recusado pelo journal e ainda entrar no finally de exclusão. Agora a divergência vai para ROLLBACK_REQUIRES_MANUAL_REVIEW antes de CREATED, sem excluir o perfil retornado. Um teste de regressão verifica explicitamente a lista de exclusões vazia.

## Provas e limites

Testes do runner exercitam árvore/ACL/launch/identidade/probes/gateway/parada/remoção, HRESULTs, perfil residual, SID divergente, políticas e gates. As etapas internas são mocks e o resultado recebe TESTED_MOCK, com filesystem/network NOT_VERIFIED. O gateway real e a não mutação de banco/bundle continuam cobertos pelos testes Windows/AI boundary existentes.

Os probes reais de arquivos, outputs e listener local permanecem preparados na PoC anterior. A futura política deve conceder escrita somente a outputs e manter o journal fora do alcance da identidade AppContainer. Processo iniciado e token restrito precisam ser comprovados antes de classificar acesso negado. Os limites Job anteriores foram preservados. Memória significa commit, com as limitações de pico/RSS já documentadas.

Crash recovery permanece somente leitura. Journal adulterado, resposta de criação perdida, exclusão ambígua, ownership conflitante ou recurso residual bloqueiam retry automático. O futuro journal será planejado em %LOCALAPPDATA%/Escryptorio/IsolationPoC/journals, com volume local não sincronizado e DACL proprietário/SYSTEM a verificar antes de gravar. Esse local não foi criado nesta tarefa. SHA-256 não autentica contra quem controle seus arquivos. CPU/disco, compatibilidade do runtime restrito e negação FS/rede permanecem pendentes.

## Delivery record

1. Initial HEAD1fd80d2, final HEAD in final reply and commit subject above.
2. Created authorized_runner.py, test_authorized_runner.py, runner and approval-manifest documents.
3. Modified native call contract/profile lifecycle and required documentation/handoff.
4. Native adapter entry points still blocked; reviewed call bodies use synthetic APIs only.
5. Create/Delete HRESULTs, zero capabilities, SID allocation/FreeSid and getter CoTaskMemFree audited against Microsoft docs.
6. Journal integrated with operation/request manifest; existing record schema/hash preserved.
7. Crash recovery remains read-only/manual on ambiguity, no automatic re-create/delete.
8. Unexpected SID preserves returned resource; regression asserts no deletion.
9. Cleanup failure overrides probe success and prevents CLEANED.
10. Full mock pipeline and fault cases TESTED_MOCK, never OS enforcement.
11. Protected/allowed/outputs probes prepared, real AppContainer filesystem NOT_VERIFIED.
12. Local listener probes prepared, real network NOT_VERIFIED.
13. Suspended launch/Job/quotas/kill-on-close preserved and tested in existing Windows suite.
14. Exact approval manifesto and policy/operation hashes recorded in AI_APPCONTAINER_APPROVAL_MANIFEST.md.
15. Real profile created: NO.
16. Zero intentional persistent Windows resource mutations; synthetic journals temporary.
17. Full499 passed/1skip, exit0; final targeted results below.
18. Targeted runner/profile/journal/Windows/AI boundary command documented below.
19. Financial fingerprint e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62.
20. 38/38 replays14legacy, origin read-only and temporary copy removed, exit0.
21. Residual same-user writer, loader/desktop, storage verification, crash/power-loss, CPU/disk and network limitations.
22. Execution gate PROFILE_CREATION_REQUIRES_APPROVAL, real native operational bridge DEFERRED.
23. PREPARATION_COMPLETE_AWAITING_APPROVAL; filesystem/network NOT_VERIFIED.
24. Human decision pending for exact single-profile synthetic test and verified removal in a later interaction.


Final targeted command `.venv/Scripts/python -m pytest backend/tests/test_authorized_runner.py backend/tests/test_profile_plan.py backend/tests/test_profile_journal.py backend/tests/test_windows_isolation.py backend/tests/test_ai_boundary.py -q` completed with147 passed, one preexisting warning,58.82s,exit0. A final explicit tree-absence confirmation guard and regression case followed; `test_authorized_runner.py -q` then passed20 tests in1.51s,exit0. A callback returning False cannot publish CLEANED. These final changes were verified by the targeted commands; the earlier full-suite count remains499/1skip.
