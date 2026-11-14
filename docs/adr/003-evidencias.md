# ADR-003 · Pacote imutável de evidências

- **Estado:** proposta. **Contexto:** LLM não é autoridade de preços ou resultados.
- **Alternativas:** acesso direto ao banco; referências soltas; pacote congelado e verificado.
- **Decisão recomendada:** pacote canônico versionado com referências íntegras e as-of explícito.
- **Justificativa:** rastreabilidade e validação causal independentes do modelo.
- **Consequências/riscos:** custo de captura e guarda; disponibilidade histórica pode ser desconhecida; SHA não é assinatura.
- **Reversibilidade:** versão nova de contrato, sem alterar hashes anteriores.
- **Questões abertas:** retenção, canonicalização exata, armazenamento e prova point-in-time.
