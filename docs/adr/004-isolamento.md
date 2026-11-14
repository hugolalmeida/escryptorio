# ADR-004 · Isolamento da pesquisa

- **Estado:** proposta. **Contexto:** texto não confiável não pode controlar dinheiro ou ledger.
- **Alternativas:** prompt proibitivo; ferramentas restritas por aplicação; isolamento em processo/SO.
- **Decisão recomendada:** processo sem credenciais, executor, shell, banco gravável ou egress por padrão; apenas cópia mínima autorizada.
- **Justificativa:** ausência de capacidade é controle mais forte que instrução textual.
- **Consequências/riscos:** custo de implementação e verificação de ACL, rede e processos no Windows; permissões Python sozinhas não são sandbox.
- **Reversibilidade:** controles podem ser revisados sem conceder execução.
- **Questões abertas:** mecanismo concreto de sandbox e testes de escape antes de qualquer protótipo.
