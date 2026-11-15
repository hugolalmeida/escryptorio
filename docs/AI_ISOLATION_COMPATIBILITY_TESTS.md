# Testes de compatibilidade ? 2.3D3A.2

IMPLEMENTED e TESTED em mocks, ProfilePolicy fechada/congelada e identificada por SHA-256 no dom?nio escryptorio:profile-plan:v1. O nome ? reservado e capabilities s?o vazias. ProfileLifecycle não possui adapter nativo de muta??o. create retorna PROFILE_CREATION_REQUIRES_APPROVAL. O test seam exercise_mock requer adapter explicitamente sint?tico, sem equival?ncia com aprova??o humana.

Estados modelados s?o PLANNED, AUTHORIZED sint?tico, CREATING, CREATED, TESTING, CLEANING, CLEANED, ROLLBACK_INCOMPLETE e ROLLBACK_REQUIRES_MANUAL_REVIEW. Lookup anterior impede apropria??o de perfil preexistente. A exclus?o exige SID retornado e confirmado novamente. Cria??o incerta ou ownership divergente preserva o recurso para revis?o. CLEANED exige verifica??o de aus?ncia. Uma inst?ncia terminal não pode ser reutilizada.

Os 15 testes de profile_plan passaram isoladamente em 0,36 s. Exercitam contratos/autoriza??es, perfil preexistente, criação parcial, falhas de ACL/launch/Job/resume/timeout/cancelamento/gateway, parada/libera??o, falha de exclus?o, verifica??o residual e troca de ownership. Todos os perfis desses testes s?o entradas em dicion?rio. Uma execução com Windows isolation teve 43 aprovados em 16,74 s, com aviso Starlette/httpx preexistente, após corrigir o mapeamento de direitos gen?ricos. A primeira tentativa de read-back literal falhou, mantendo os processos bloqueados e a limpeza efetiva.

SecurityEvidence v1 ? fechado e tipado, com IDs/hash, launcher, ambiente, identidade, status do perfil/ownership, criação, runtime, recursos, filesystem/rede, rollback, execução, timestamp UTC em ms e limita??es. Nesta etapa filesystem/rede s? aceitam NOT_VERIFIED. O modelo não aceita caminhos privados/campos extras ou promo??o a enforcement. O contrato valida schema, e sua autoridade continua no supervisor.

O diagn?stico real repetiu JOB_ONLY EXITED/0, Restricted Token FAILED/3221225506 e AppContainer PROCESS_CREATION_FAILED/203. Runtime restrito não chegou ao probe, portanto falhas não foram promovidas a nega??o de arquivo/rede. Captura e read-back de DACLs em 48 objetos sint?ticos ocorreram com cleanup COMPLETE.

Testes com perfil real permanecem PREPARED_NOT_EXECUTED e NOT_AUTHORIZED, sem comando que os execute automaticamente. Cria??o/remoção real, escrita exclusiva em outputs e nega??o efetiva de loopback/arquivos ficam NOT_VERIFIED. Job, mem?ria, descendentes, timeout, morte do supervisor, cancelamento, limite de mensagens, não muta??o SQLite/bundle e can?rios continuam cobertos pela suíte Windows existente. O or?amento de tokens conserva simula??o.

Replays atuais em backup tempor?rio de origem mode=ro/query_only preservaram 38/38 IDs, 14 legados e fingerprint e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62. Limpeza terminou com REPLAY_CLEANUP_COMPLETE e saída 0. Resultados finais da suíte completa est?o em VERIFICATION.md. Playwright/build/typecheck dispensados pelo escopo backend/documenta??o.

Readiness PREPARATION_COMPLETE_AWAITING_APPROVAL. Riscos de acesso ao supervisor em JOB_ONLY, mem?ria f?sica/RSS, CPU/disco, autenticidade, IPC e c?digo hostil arbitr?rio conservam as limita??es anteriores.


Baseline `.venv/Scripts/python -m pytest backend/tests -q` antes das altera??es teve 455 passed/1 skipped em 158,26 s, saída 0. Su?te posterior teve 470 passed/1 skipped em 145,99 s, saída 0. O skip de symlink e o aviso Starlette/httpx s?o preexistentes. A captura de ACLs em duas passagens foi ajustada após iniciar essa suíte e foi verificada posteriormente no arquivo Windows junto aos testes de perfil. Diagn?stico e replays via stdin terminaram com saída 0 e REPLAY_CLEANUP_COMPLETE. `git diff --check` passou e o artefato %SystemDrive% permaneceu ausente.

## Relat?rio dos 30 itens

1. HEAD inicial ? 7af1767efb0b3e1d73dcb52208a7dd07eaf82c7c.
2. HEAD final ? informado na resposta final e commit desta fase.
3. Resumo ? PREPARATION_COMPLETE_AWAITING_APPROVAL.
4. Criados ? profile_plan.py, test_profile_plan.py e tr?s documentos AppContainer/compatibilidade.
5. Modificados ? windows_native.py, isolation_poc.py, seis documentos existentes e handoff.
6. Win32 ? assinaturas, x64, buffers, HRESULT/Win32, lifetime e DACL revisados.
7. 203 ? PROCESS_CREATION_FAILED reproduzido.
8. 0xC0000022 ? runtime sem probe reproduzido.
9. Causa confirmada ? diferen?as de representa??o de direitos gen?ricos na confer?ncia DACL.
10. Hip?teses ? perfil ausente, loader/DLL/desktop ainda não confirmados.
11. Python ? controle JOB_ONLY funciona, runtime restrito NOT_VERIFIED.
12. Windows ? token não elevado, APIs ef?meras exercitadas.
13. Gerenciador ? IMPLEMENTED e TESTED apenas com adapters sint?ticos.
14. Perfil criado ? N?O.
15. Autoriza??o ? NOT_AUTHORIZED / PROFILE_CREATION_REQUIRES_APPROVAL.
16. Acessos planejados ? zero capabilities, runtime RX, allowed R, outputs escrita m?nima.
17. Filesystem ? DACL configurada/conferida, nega??o pelo worker NOT_VERIFIED.
18. Rede ? controle local preservado, nega??o NOT_VERIFIED.
19. Job ? provas existentes reexecutadas nos testes Windows.
20. Rollback ? mocks de ownership/criação/exclus?o/verifica??o e bloqueio de reuso.
21. Não muta??o ? testes sint?ticos SQLite/bundle existentes reexecutados.
22. Python ? baseline455, posterior470, ambos com1skip.
23. Replays ? 38/38, 14 legados, saída0 e cleanup completo.
24. Fingerprint ? e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62.
25. Aplicados ? captura/read-back DACL sint?tica e limites Job nos cen?rios.
26. Preparados ? lifecycle e schema SecurityEvidence, sem adapter nativo de criação.
27. Riscos ? perfil residual, runtime restrito, FS/rede, CPU/disco e supervisor.
28. Readiness ? PREPARATION_COMPLETE_AWAITING_APPROVAL.
29. Plano futuro ? AI_APPCONTAINER_APPROVAL_PLAN.md.
30. Decis?o humana ? autorizar especificamente o ?nico perfil reservado, probes sint?ticos e remoção verificada.

Execu??o direcionada final: Windows isolation + profile_plan, 43 passed, um aviso preexistente, 13,66 s, saída 0. Nenhum perfil real foi criado.
