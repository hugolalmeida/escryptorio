# Plano específico do Stage G · NOT_AUTHORIZED

Perfil único proposto Escryptorio.PoC.D3A2.20261115.8c514dea. Capabilities vazias. Inspeção atual read-only encontrou pasta e mapeamento ausentes nas localizações consultadas. Essa inspeção deverá ser repetida imediatamente antes de eventual criação. Perfil preexistente não será reutilizado, modificado ou excluído.

Operações persistentes futuras são criação do armazenamento per-user/per-app e registro por CreateAppContainerProfile, escrita do journal local durável, e exclusão desse perfil próprio por DeleteAppContainerProfile. O SID esperado será derivado e comparado ao SID retornado. A autorização deve identificar a operação e a política exatas. Os métodos nativos desta entrega ainda recusam essas mutações; um fluxo autorizado terá de ser revisado antes do ensaio.

1. Confirmar token limitado, ausência de elevação e local protegido do journal. Repetir inspeção exata do perfil. Não há plano de pedir administrador. Se necessário, interromper para nova decisão.
2. Criar operação independente e journal com PLANNED/AUTHORIZATION_PENDING. Registrar a autorização futura de maneira auditável. Persistir CREATING antes da API. Nunca considerar flag CLI, ambiente ou texto do worker como autorização.
3. Criar um perfil com capabilities vazias, registrar HRESULT/SID/ownership e recursos. Diante de retorno perdido ou criação parcial, interromper para revisão, sem inferir ownership pelo nome.
4. Preparar árvore própria protected/allowed/worker/outputs, canários e runtime mínimo. Capturar ACLs antes das alterações, aplicar somente nessa árvore e conferir. Runtime RX, allowed R e outputs com escrita mínima. Supervisor conserva permissão de limpeza.
5. Criar Job com memória/processos limitados. Lançar suspenso, associar, verificar e retomar. Confirmar identidade AppContainer e resposta inicial do runtime antes de avaliar acesso.
6. Executar leitura/listagem/escrita negadas em protected e leitura permitida em allowed, mais escrita limitada em outputs. Comparar bytes dos canários. Registrar códigos OS e confirmação do probe.
7. Usar listener local efêmero, controle positivo supervisor/JOB_ONLY e tentativa AppContainer. Correlacionar conexões recebidas e erros. Loopback não comprova bloqueio de Internet, DNS ou IPC.
8. Encerrar processos, aguardar Job vazio e handles sinalizados, liberar recursos. Conferir operação/política/SIDs/journal/estado externo antes de excluir exclusivamente o perfil próprio.
9. Verificar remoção por armazenamento e registro exatos e ausência de resíduos conhecidos. SID derivável e sucesso de Delete não bastam. Remover árvore própria e encerrar journal somente após verificações.

Crash recovery começa pela inspeção read-only do journal e do estado externo. Recursos incertos exigem MANUAL_REVIEW_REQUIRED. Falhas de exclusão/verificação mantêm ROLLBACK_INCOMPLETE e bloqueiam reutilização. O journal deve sobreviver à queda do supervisor, mas não autentica contra atacante com escrita no diretório. Possíveis resíduos incluem perfil, registro, diretórios, journal parcial e handles/processos pendentes. Limpeza por prefixo ou registro manual fica fora do plano.

Evidências esperadas são identidade do processo, runtime funcional, códigos ACCESS_DENIED em tentativas explícitas, controles positivos, limites Job, integridade dos canários e ausência observável dos recursos. Recursos financeiros reais, credenciais e LLM ficam fora desse ensaio. D3B exige decisão separada.

Aprovação específica solicitada em interação posterior para criar esse único perfil, executar o conjunto sintético em árvore própria com Job limitado e listener local, remover somente o perfil de ownership comprovado e verificar resíduos. Estado atual PROFILE_CREATION_REQUIRES_APPROVAL.


# Runner preparation 2.3D3A.4

PREPARATION_COMPLETE_AWAITING_APPROVAL. Closed runner policy/request and read-only approval manifest prepared. Native Win32 mutation bodies are disconnected from the operational adapter and exercised only through a synthetic API seam. execute_authorized_test always refuses. Mock end-to-end now binds operation/request to the durable journal, confirms runtime identity, runs fixture probes/gateway, stops resources and verifies profile/tree removal before CLEANED. Unexpected returned SID goes to manual review without deletion. See [runner](AI_APPCONTAINER_AUTHORIZED_TEST_RUNNER.md) and [approval manifest](AI_APPCONTAINER_APPROVAL_MANIFEST.md). Real filesystem/network containment remains NOT_VERIFIED.
