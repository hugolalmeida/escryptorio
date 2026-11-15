# ADR-003 · Pacote imutável de evidências

- **Estado:** proposta. **Contexto:** LLM não é autoridade de preços ou resultados.
- **Alternativas:** acesso direto ao banco; referências soltas; pacote congelado e verificado.
- **Decisão recomendada:** pacote canônico versionado com referências íntegras e as-of explícito.
- **Justificativa:** rastreabilidade e validação causal independentes do modelo.
- **Consequências/riscos:** custo de captura e guarda; disponibilidade histórica pode ser desconhecida; SHA não é assinatura.
- **Reversibilidade:** versão nova de contrato, sem alterar hashes anteriores.
- **Questões abertas:** retenção, canonicalização exata, armazenamento e prova point-in-time.
# Aditamento 2.3D1

O subconjunto de dataset histórico aprovado é implementado por exportação manual offline, sem persistência nova no SQLite. Conteúdo e captura possuem domínios de hash distintos; PIT permanece desconhecido. A decisão anterior e suas questões abertas permanecem no histórico abaixo. Ver [implementação](../AI_EVIDENCE_IMPLEMENTATION.md).
# Aditamento 2.3D2

Bundle v2 congela dataset, protocolo e resultado persistido e valida seus vínculos offline, sem recálculo. Sua identidade usa novos domínios; autenticidade e disponibilidade histórica permanecem não comprovadas. Ver [validação](../AI_CLAIM_VALIDATION.md).
