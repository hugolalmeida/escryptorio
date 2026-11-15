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
