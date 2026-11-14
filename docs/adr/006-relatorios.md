# ADR-006 · Persistência e versionamento

- **Estado:** proposta. **Contexto:** relatórios devem ser auditáveis, mas retenção financeira imutável aumenta complexidade.
- **Alternativas:** memória efêmera, exportação local explícita, armazenamento imutável transacional.
- **Decisão recomendada:** primeiro exportação local manual com manifesto e hash; nenhuma migration ou persistência nesta fase.
- **Justificativa:** testar utilidade antes de introduzir base e política de retenção.
- **Consequências/riscos:** arquivo pode ser removido ou substituído; SHA sem âncora externa não prova autoria; capturar versões e limites.
- **Reversibilidade:** reavaliar armazenamento imutável e leitor de versões sem reescrever resultados históricos.
- **Questões abertas:** retenção, acesso, backup, assinatura e identidade de captura versus conteúdo.
