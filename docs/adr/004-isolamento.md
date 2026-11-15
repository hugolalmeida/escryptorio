# ADR-004 · Isolamento da pesquisa

- **Estado:** proposta. **Contexto:** texto não confiável não pode controlar dinheiro ou ledger.
- **Alternativas:** prompt proibitivo; ferramentas restritas por aplicação; isolamento em processo/SO.
- **Decisão recomendada:** processo sem credenciais, executor, shell, banco gravável ou egress por padrão; apenas cópia mínima autorizada.
- **Justificativa:** ausência de capacidade é controle mais forte que instrução textual.
- **Consequências/riscos:** custo de implementação e verificação de ACL, rede e processos no Windows; permissões Python sozinhas não são sandbox.
- **Reversibilidade:** controles podem ser revisados sem conceder execução.
- **Questões abertas:** mecanismo concreto de sandbox e testes de escape antes de qualquer protótipo.

# Aditamento 2.3D3A

Decisão implementada para o subconjunto de desenvolvimento. Subprocesso fixo, stdlib, ambiente mínimo e gateway externo oferecem testes funcionais com cotas e timeout. DEVELOPMENT_MOCK é explicitamente NOT_SANDBOXED. ISOLATED_RESEARCH permanece indisponível e falha fechado. Job Object teve somente criação/fechamento comprovados. Launcher restrito, ACL, AppContainer, memória e egress ficam DEFERRED. O gate para D3B é NOT_READY. A decisão histórica e suas questões abertas permanecem registradas. Ver [matriz e riscos](../AI_RESEARCH_ISOLATION.md).

# Aditamento 2.3D3A.1

Decisão concretizada para experimentos sintéticos. Job Objects com processo inicialmente suspenso, memória/processos limitados e KILL_ON_JOB_CLOSE foram implementados e exercitados. Restricted Token e AppContainer têm launchers experimentais sem fallback, com falhas do runtime/criação documentadas. A PoC fica PARTIAL_POC e as fronteiras de arquivos/rede ficam NOT_VERIFIED. A criação de perfil persistente AppContainer permanece reservada a autorização futura. Context Builder, gateway e modos anteriores conservam seus contratos. Ver [PoC e riscos](../AI_WINDOWS_ISOLATION_POC.md).
