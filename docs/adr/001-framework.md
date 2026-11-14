# ADR-001 · Framework multiagente

- **Estado:** proposta, não implementada. **Contexto:** pesquisa local requer isolamento e evidências auditáveis.
- **Alternativas:** framework multiagente, orquestração própria simples, nenhum agente.
- **Decisão recomendada:** nenhum framework no baseline; módulos determinísticos existentes primeiro.
- **Justificativa:** menos superfícies e dependências; papéis não exigem processos independentes.
- **Consequências/riscos:** coordenação e tracing precisarão ser projetados se a evidência justificar; simplicidade não substitui sandbox.
- **Reversibilidade:** avaliar framework futuramente sem comprometer contratos financeiros.
- **Questões abertas:** benefício medido, manutenção, licença e fronteiras efetivas no Windows.
