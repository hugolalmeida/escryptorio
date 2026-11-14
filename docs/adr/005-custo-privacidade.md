# ADR-005 · Provedor, custo e privacidade

- **Estado:** proposta. **Contexto:** processamento local ou externo apresenta custos e superfícies distintas.
- **Alternativas:** sem LLM, modelo local isolado, API externa autorizada.
- **Decisão recomendada:** sem provedor até benchmark e autorização; definir limites e política de dados antes de qualquer chamada.
- **Justificativa:** evitar despesa, vazamento e dependência sem benefício demonstrado.
- **Consequências/riscos:** modelo local exige hardware e teste de egress; API transmite contexto e pode cobrar tentativas.
- **Reversibilidade:** escolha posterior por relatório sem alterar a autoridade do motor.
- **Questões abertas:** preço, retenção, região, modelo, hardware, timeout e orçamento.
