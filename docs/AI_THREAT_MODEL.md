# Modelo de ameaças · proposta futura

Ameaças pressupõem fontes, respostas de modelo e outros agentes não confiáveis. Sem runtime de IA nesta fase, controles abaixo são **requisitos propostos**, não garantias já implementadas.

| Ameaça / severidade | Exemplo | Mitigação determinística proposta | Teste / risco residual |
| --- | --- | --- | --- |
| Prompt injection / alta | fonte ou saída de outro papel tenta alterar política | entrada tratada como dados; schema fechado; nenhum executor, shell ou SQL; instruções com precedência fora da entrada | fixtures adversariais, strings codificadas e campos livres; não há prova geral de imunidade |
| Exfiltração / alta | prompt inclui arquivos locais, tokens ou dados de carteira | pacote mínimo allowlist; processo segregado sem segredos, ACL read-only, egress bloqueado por padrão; provedor externo só com autorização explícita | teste canário local, inspecionar payload e rede; modelo local também pode vazar se processo tiver acesso |
| Abuso de ferramenta / crítica | modelo pede ordens, rede irrestrita ou escrita | remover capacidade no SO/processo, sem executor, imports acessíveis, banco gravável, shell ou credenciais; allowlist vazia por padrão | tentar invocar ferramenta, rede e mutação; fronteira precisa ser efetivamente testada no Windows |
| Integridade financeira / crítica | PnL inventado, preço de outro instante, mudança de ledger | cálculos e snapshots do motor; hashes/índices e recomputação determinística; não aceitar números sem referência | mutação de valor, hash, janela e ledger; hash não protege contra reescrita coordenada da base |
| Lookahead / alta | documento conhecido depois de as-of ou seleção após teste | `available_at` comprovado, limites UTC, recusa de disponibilidade desconhecida, separação de teste congelada | prefixos, janelas adjacentes e fontes com publicação posterior; data da coleta não prova data histórica de disponibilidade |
| Reprodutibilidade / alta | modelo, prompt, dados ou dependências mudam | hash de pacote, prompt, validador e versões, captura de parâmetros e resposta; reexecutar verificações determinísticas | comparar inputs e validar replay; resposta LLM não é deterministicamente reproduzível só com seed |
| Custo / disponibilidade / média | loop, timeout, excesso de tokens, provedor indisponível | orçamento pré-aprovado, limite de chamadas/tokens/tentativas/tempo, cancelamento e falha fechada; sem egress por padrão | respostas parciais, timeout, concorrência, cota e reboot; custo de rede cancelada pode ainda ser cobrado |
| Confusão de autoridade / alta | texto persuasivo interpretado como plano ou autorização | saída rotulada não executável, schema fechado e política de conteúdo; nenhum consumidor de execução | instrução em texto livre, campos desconhecidos, tentativa de encaminhar conteúdo ao planner; revisão humana necessária |

IDs e citações não garantem pertinência, autoria autêntica ou verdade; validação semântica de linguagem não é completa. Estado `VALIDATED` não deve ser apresentado como conselho financeiro. Qualquer capacidade nova de rede, fornecedor, autenticação, persistência ou ferramenta exige revisão específica e autorização; nenhuma é concedida neste estudo.

# Fundação de contexto e mock · 2.3D3A

O subconjunto determinístico está IMPLEMENTED e TESTED em `cryptolab.research.ai_boundary`. O builder aceita bundles v2 verificados e aplica allowlist. O mock stdlib executa em subprocesso supervisionado com gateway independente e orçamento simulado. DEVELOPMENT_MOCK devolve NOT_SANDBOXED. ISOLATED_RESEARCH retorna ISOLATED_RESEARCH_UNAVAILABLE. O gate para D3B é NOT_READY por ausência de fronteiras de SO comprovadas para arquivos, credenciais, rede e recursos.

Contratos, minimização e causalidade em [AI_RESEARCH_CONTEXT.md](AI_RESEARCH_CONTEXT.md). Ambiente Windows, matriz de alternativas e riscos em [AI_RESEARCH_ISOLATION.md](AI_RESEARCH_ISOLATION.md). Limites e contabilidade em [AI_RESEARCH_BUDGET.md](AI_RESEARCH_BUDGET.md). Resultados realmente executados em [VERIFICATION.md](VERIFICATION.md). A investigação e implementação de isolamento forte ficam DEFERRED.

# Prova Windows · 2.3D3A.1

A PoC experimental implementa processo suspenso, Job configurado e conferido antes do resume, limites de commit/processos, término da árvore e rollback. O teste de morte do supervisor comprova KILL_ON_JOB_CLOSE nas fixtures benignas. O resultado é PARTIAL_POC. Restricted Token criou processo, mas o runtime falhou na inicialização; AppContainer sem perfil falhou na criação. Negação de filesystem e rede permanece NOT_VERIFIED. ISOLATED_RESEARCH conserva falha fechada, e JOB_ONLY é seleção explícita exclusiva dos experimentos de recursos.

Capacidades observadas em [WINDOWS_ISOLATION_CAPABILITIES.md](WINDOWS_ISOLATION_CAPABILITIES.md). Launcher, política e rollback em [AI_WINDOWS_ISOLATION_POC.md](AI_WINDOWS_ISOLATION_POC.md). Evidências, limitações e próxima etapa em [AI_ISOLATION_TEST_RESULTS.md](AI_ISOLATION_TEST_RESULTS.md).
