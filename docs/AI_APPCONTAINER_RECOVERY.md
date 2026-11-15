# Journal e recuperação · 2.3D3A.3

Record v1 é fechado e imutável. Registra operação, nome exato, política, correlação ownership_token, SID esperado/observado, horários UTC em ms, geração, estado, manifesto de recursos e verificação. ownership_token é correlação local da operação, sem credencial de provedor. Os testes usam apenas IDs fictícios e diretórios temporários. O fluxo real precisará gerar IDs imprevisíveis e guardar o journal em diretório protegido escolhido pelo supervisor.

Journal cria exclusivamente um subdiretório com operation_id SHA-256 dentro da raiz confiável. Uma operação existente nunca é reaberta para escrita. Isso elimina writers concorrentes de instâncias independentes pelo mesmo identificador. A instância possui lock para serializar suas transições. Caminhos com symlinks são recusados. Readers limitam tamanho a 64 KiB, rejeitam JSON duplicado, campos extras, hash adulterado, operação/token/política divergentes.

Publicação escreve temporário irmão, flush, fsync, os.replace e read-back validado. Fsync/publicação falhos conservam o registro anterior e invalidam a instância. Falha após publicação pode deixar a nova geração em disco e exige inspeção. O diretório de operação é mantido para revisão em falha de inicialização. Não há overwrite de diretório desconhecido ou retomada silenciosa. Durabilidade contra queda de energia e atomicidade em filesystem remoto/OneDrive não são comprovadas. SHA-256 com domínio escryptorio:profile-journal:v1 detecta divergência, sem autenticar contra controle total do diretório pelo mesmo usuário.

Transições fechadas cobrem PLANNED, AUTHORIZATION_PENDING, AUTHORIZED, CREATING, CREATED, VERIFYING, VERIFIED, TESTING, CLEANING, CLEANED e estados de rollback. Estados terminais bloqueiam launch/transição. CREATED e CLEANED exigem igualdade SID esperado/observado no journal, além das verificações do lifecycle sintético. AUTHORIZED é apenas estado do modelo e não uma autorização operacional para o adapter nativo.

ProfileLifecycle grava intenção antes da criação mockada. Após retorno, confronta lookup/SID e registra CREATED. Antes da exclusão mockada, encerra/libera recursos e confere novamente ownership. CLEANED exige lookup ausente. Uma criação com resposta perdida/ambígua ou erro de journal pode impedir limpeza automática segura e deve conservar recursos para revisão manual.

read_record oferece reabertura somente leitura após crash. recovery_decision nunca executa exclusão. CREATING com perfil presente, SID inesperado, journal incompleto/adulterado, exclusão com resposta perdida e qualquer conflito retornam MANUAL_REVIEW_REQUIRED ou falham na validação. CLEANED com lookup ausente retorna CLEANED_REQUIRES_STORAGE_VERIFICATION. Journal isolado não prova ownership. Recuperação automática de perfil real permanece DEFERRED até autorização e provas externas suficientes.

Testes sintéticos cobrem lifecycle persistido, reinício/read-only, duplicação, terminal sem reuso, fsync/publicação falhos, truncamento, campo extra, troca de operação/token, hash e SID divergente. Os testes anteriores de lifecycle cobrem falhas de ACL, Job, resume, runtime, timeout, cancelamento, gateway, parada, remoção e verificação. Remoção de perfil real e rollback real permanecem NOT_AUTHORIZED/NOT_VERIFIED.

## Delivery record

1. Initial HEAD d50f93291477581a37b9cd2be3c1dfe1a1fc696e.
2. Final HEAD in final reply, commit feat: prepare native appcontainer lifecycle.
3. Created profile_native.py, profile_journal.py, test_profile_journal.py and three required documents.
4. Changed ProfileLifecycle, fixed probe allowlist/outputs probe, documentation and handoff; selected encoding repairs preserve wording.
5. Win32 signatures reviewed against Microsoft userenv documentation, HRESULT separated from BOOL errors.
6. Native adapter IMPLEMENTED for inspection and PREPARED_NOT_EXECUTED for mutations.
7. Real create/delete always blocked with REQUIRES_APPROVAL.
8. ProfilePolicy v1 preserved, exact name and empty capabilities.
9. Journal Record v1 closed with operation/policy/ownership correlation and SHA-256 domain.
10. Sibling temporary, flush/fsync, replace, read-back; no writable reopen after crash.
11. Closed transition graph and terminal state rejection TESTED.
12. Expected/observed SID and independent lifecycle lookup; journal alone cannot authorize deletion.
13. Read-only recovery returns MANUAL_REVIEW_REQUIRED in uncertainty.
14. Synthetic rollback TESTED, real rollback NOT_AUTHORIZED.
15. Fault injection for fsync/publication/read-back, identity and lifecycle failures TESTED.
16. Filesystem/outputs and loopback fixed synthetic probes PREPARED_NOT_EXECUTED under real profile.
17. Job limits and existing lifecycle tests reexecuted; prior scope of enforcement preserved.
18. Filesystem/network/Python under profile NOT_VERIFIED.
19. Full Python480 passed/1skip, exit0; final targeted result in VERIFICATION.
20. Targeted journal/profile/Windows tests, no native mutation tests.
21. 38/38 replay IDs, 14 legacy, exit0 and cleanup complete.
22. Fingerprint e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62.
23. Financial data origin opened read-only; synthetic nonmutation exercised.
24. Windows changes limited to authorized ephemeral fixtures; profile queries read-only.
25. Zero real profile resources created.
26. Synthetic journal/Job/tree resources cleaned by tests; uncertain real cleanup never attempted.
27. Residual same-user writer, crash ambiguity, power-loss and unknown storage semantics documented.
28. PREPARATION_COMPLETE_AWAITING_APPROVAL.
29. Exact profile and operations in AI_APPCONTAINER_AUTHORIZED_TEST_PLAN.md.
30. Human decision pending for Stage G creation/test/removal after plan and code review.

Final targeted command `.venv/Scripts/python -m pytest backend/tests/test_profile_journal.py backend/tests/test_profile_plan.py backend/tests/test_windows_isolation.py -q`: 55 passed, one preexisting warning, 12.46 s, exit0. No real profile creation/deletion.
