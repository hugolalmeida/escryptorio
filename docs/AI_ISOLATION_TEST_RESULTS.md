# Resultados da PoC Windows · 2.3D3A.1

Estado do experimento PARTIAL_POC. As categorias abaixo descrevem propriedades específicas e suas observações. Sucesso dos testes que registram indisponibilidade preserva a classificação NOT_VERIFIED das fronteiras correspondentes.

| Propriedade | Controle e observação | Classificação |
| --- | --- | --- |
| Memória de processo | VirtualAlloc de 100.663.296 bytes recusado com erro 1455 sob limite de 67.108.864. Mesma solicitação permitida sob limite de 201.326.592 | ENFORCED_AND_TESTED para essa solicitação |
| Memória agregada | Teste independente mantém limite de processo em 192 MiB e reduz JobMemoryLimit para 64 MiB, com read-back e recusa nativa | ENFORCED_AND_TESTED para essa solicitação |
| Processos ativos | Criação do descendente negada com erro 1816 no teto de um. Controle com dois permite descendente | ENFORCED_AND_TESTED |
| Término de árvore | Job com dois processos esvazia após timeout e os recursos são liberados | ENFORCED_AND_TESTED |
| Morte do supervisor | Helper benigno proprietário do Job é encerrado pelo teste. Handles de ambos os processos sinalizam saída | ENFORCED_AND_TESTED |
| Tempo, cancelamento e bytes | Timeout, cancelamento ativo, entrada excessiva, stdout e stderr excessivos | TESTED, SUPERVISOR_ENFORCED |
| Arquivos protegidos | DACL aplicada a fixtures. Restricted Token encerra o runtime com 3221225506/0xC0000022. AppContainer falha no CreateProcessW com 203 | NOT_VERIFIED para negação de operações de arquivo |
| Loopback | Supervisor e JOB_ONLY conectam ao listener sintético. A tentativa AppContainer falha antes de conectar | NOT_VERIFIED para negação de rede |
| Internet, DNS e IPC | Nenhum destino externo ou serviço pessoal foi utilizado | NOT_VERIFIED |
| Canários | Payload/ambiente e saída preservam minimização. Bytes dos arquivos protegidos permanecem idênticos | TESTED nos cenários indicados |
| Rollback | Falhas de criação, configuração, associação, ACL, escrita, interrupção e cleanup injetadas. Repetições sem crescimento de handles | TESTED |
| CPU e disco | Limites específicos fora deste launcher | DEFERRED |

A execução CLI da suíte registrou pico de Job de 14.417.920 bytes na recusa por limite de processo e 112.762.880 no controle positivo. O Job de dois processos registrou 17.854.464 bytes. As amostras individuais ficaram entre zero ms no erro de criação e 1.016 ms no timeout de um segundo. Variações de agendamento e carregamento do runtime afetam esses valores. O teste independente de JobMemoryLimit observou contador de pico acima do teto durante tentativa recusada, portanto a evidência não é apresentada como teto de RSS ou pico instantâneo universal.

## Comandos e histórico de correções

`git status -sb`, `git rev-parse HEAD` e `git log -5 --oneline` confirmaram main limpa em `775e9c553d6ba346f23fceb1348345fc7eb30035`. Os números 427/143 da fase anterior eram baseline documental, sem reexecução inicial atribuída à fase atual.

O diagnóstico inicial corrigiu buffer de TokenElevation após erro 24. Restricted Token com SID de pacote falhou com erro 87, e a implementação final usa Restricted Code. O interpretador console criou conhost adicional, e o launcher passou ao pythonw.exe com pipes explícitos. Preservar o nome original do executável corrigiu uma falha de fixture de descendente por caminho inexistente. A limpeza foi ajustada para aguardar término assíncrono do Job antes de avaliar corrida com TerminateProcess. Uma asserção inicial incorreta sobre o pico contábil foi substituída pela verificação de negação nativa e read-back, mantendo os limites de teste.

O arquivo de testes Windows teve uma execução intermediária com 22 aprovados em 9,35 s. Após cenários adicionais de rollback e integração, registrou 27 aprovados em 12,73 s. A execução da CLI `--suite` terminou com código 0, readiness PARTIAL_POC, directory_cleanup COMPLETE e canaries_unmodified True. As tentativas restritas constam como FAILED nas amostras, e as fronteiras de arquivo/rede constam como NOT_VERIFIED nos controles.

Resultados finais de suíte, execução direcionada e revisão ficam em [VERIFICATION.md](VERIFICATION.md). O relatório foi mantido sem stdout bruto dos probes e sem caminhos de usuário. As evidências não constituem auditoria de escape universal.

## Integridade financeira

Um script via stdin para `.venv/Scripts/python -` abriu a origem SQLite do projeto com URI mode=ro e query_only, fez Connection.backup para cópia temporária e executou ResearchService.verify em todos os research_runs dessa cópia. Os 38 IDs foram preservados, incluindo 14 legados. A cópia foi removida após fechar conexões, com saída 0 e 5,17 s.

Fingerprint atual preservado.

```text
e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62
```

A integração sintética congela evidência v2, constrói contexto, cria envelope, executa o mock no launcher JOB_ONLY explicitamente selecionado e valida a saída no gateway anterior. Compara dump integral do banco sintético e bytes do bundle antes/depois. O teste usa tabelas paper/monitor em grande parte vazias. Alteração do banco pessoal foi evitada por acesso somente leitura na origem, com replay restrito à cópia.

A revisão final encontrou um diretório relativo `%SystemDrive%` no workspace, contendo caches incidentais do Windows produzidos por um ensaio com ambiente mínimo incompleto. O diagnóstico inspecionou somente metadados. O launcher e o helper passaram a fornecer SystemDrive explicitamente, e o helper passou a usar cwd dentro da árvore sintética. O artefato foi removido por caminho literal após conferir sua contenção no workspace e sua ausência no baseline. A verificação final confere que ele permanece ausente. Essa correção integra o rollback da tarefa.

## Relatório final dos 30 itens

| Item | Estado e entrega |
| --- | --- |
| 1. HEAD inicial | TESTED — 775e9c553d6ba346f23fceb1348345fc7eb30035, main limpa |
| 2. HEAD final | DOCUMENTED — informado na resposta final, commit `feat: add windows isolation proof of concept` |
| 3. Capacidades Windows | TESTED — Home x64, token não elevado, APIs de Job/token/DACL disponíveis nas operações indicadas |
| 4. Alternativas | DOCUMENTED — Job, Restricted Token, AppContainer sem perfil, perfil autorizado futuro e VM |
| 5. Mecanismo escolhido | IMPLEMENTED — Job + processo suspenso para recursos, launchers restritos experimentais separados |
| 6. Justificativa | DOCUMENTED — mecanismo sem elevação com enforcement de recursos observado, fronteiras restantes explicitadas |
| 7. Criados | IMPLEMENTED — windows_native.py, isolation_poc.py, isolation_probe.py, test_windows_isolation.py e estes três documentos de PoC |
| 8. Modificados | DOCUMENTED — AI_RESEARCH_ISOLATION, AI_RESEARCH_ROADMAP, AI_THREAT_MODEL, VERIFICATION, ADR-004 e SESSION_HANDOFF |
| 9. Política | IMPLEMENTED e TESTED — IsolationPolicy v1 fechada/congelada, launcher windows-isolation-poc/1, hash com domínio próprio |
| 10. PoC | IMPLEMENTED e TESTED — operação fixa, runtime stdlib temporário, handles herdáveis limitados e supervisor externo |
| 11. Filesystem | IMPLEMENTED para DACL sintética, NOT_VERIFIED para operações negadas ao worker |
| 12. Rede | TESTED no controle local positivo, NOT_VERIFIED para negação de loopback/TCP/DNS/IPC |
| 13. Memória | ENFORCED_AND_TESTED — solicitação VirtualAlloc limitada, controles pareados de processo e Job |
| 14. Processos | ENFORCED_AND_TESTED — descendente recusado no teto de um, árvore de dois encerrada |
| 15. Controles aplicados | ENFORCED_AND_TESTED — Job, memória, contagem de processos, KILL_ON_JOB_CLOSE nas fixtures. Timeout/bytes/cancelamento SUPERVISOR_ENFORCED |
| 16. Indisponíveis | FAILED — AppContainer sem perfil e inicialização Python sob Restricted Token. CPU/disco DEFERRED |
| 17. Canários | TESTED — arquivos intactos, ambiente mínimo e saída sanitizada. Negação arbitrária de acesso NOT_VERIFIED |
| 18. Adversariais | TESTED — operações desconhecidas, parâmetros inválidos, JSON inválido, garantia forjada, saída excessiva, timeout e falha de processo |
| 19. Rollback | TESTED — criação/configuração/associação, DACL, escrita, interrupção, cleanup incompleto e repetição |
| 20. Temporários criados | DOCUMENTED — árvore própria, runtime copiado, canários/SQLite fictício, pipes, tokens, SID, Jobs e listener local |
| 21. Temporários removidos | TESTED — árvore e handles liberados, processos aguardados. Cache relativo incidental corrigido e removido |
| 22. Configurações globais | DOCUMENTED — zero alterações intencionais de firewall, perfis, contas, serviços, instalação Python ou ACLs externas |
| 23. Python | TESTED — números finais registrados em VERIFICATION.md após encerramento dos comandos |
| 24. Direcionados | TESTED — 171 aprovados/1 skip, incluindo 28 testes Windows, após correções finais |
| 25. Fingerprint | TESTED — e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62 |
| 26. Replays | TESTED — 38/38, 14 legados, origem somente leitura, cópia removida e processo com saída 0 |
| 27. Limitações | DOCUMENTED — startup restrito falhou antes de acessar canários/rede, isolamento ainda parcial |
| 28. Riscos | DOCUMENTED — JOB_ONLY conserva FS/rede do usuário, confiança no runtime/supervisor e concorrência do mesmo usuário |
| 29. Readiness | DOCUMENTED — PARTIAL_POC, ISOLATED_RESEARCH indisponível |
| 30. Próxima etapa mínima | DEFERRED — revisão autorizada de perfil AppContainer descartável e testes de negação FS/loopback com rollback |

Hash da política padrão final, incluindo launcher_version e identity APPCONTAINER.

```text
b607218b0e8b9691ee7b9f11e37afeec9c8aec69bce0291a1ef38ac435acc436
```

A repetição final do agregador via stdin terminou com saída 0, readiness PARTIAL_POC, cleanup COMPLETE e canaries_unmodified True. O relatório atribuiu ENFORCED_AND_TESTED a MEMORY_LIMIT, PROCESS_LIMIT e ROLLBACK. FILESYSTEM_DENY e NETWORK_DENY permaneceram NOT_VERIFIED. Foram observados novamente exit code 3221225506 para Restricted Token e erro 203 em CreateProcessW para AppContainer. Uma eventual criação de perfil com efeitos persistentes exige a autorização futura indicada no pedido.

A última execução `.venv/Scripts/python -m pytest backend/tests/test_windows_isolation.py -q`, posterior ao bloqueio persistente de reuso após rollback incompleto, terminou com 28 passed, um aviso Starlette/httpx, em 11,79 s e saída 0. A suíte completa repetida teve 455 passed/1 skipped em 148,32 s. A execução direcionada teve 171 passed/1 skipped em 75,02 s. O skip é a criação de symlink recusada pelo Windows. O teste final confirma propagação de ROLLBACK_INCOMPLETE mesmo após remover a árvore sintética.
