# ADR-002 · Modelo único ou conselho

- **Estado:** proposta. **Contexto:** mais agentes podem amplificar custo e erros correlacionados.
- **Alternativas:** relatório sem LLM; uma LLM; Bull/Bear/Risk em várias chamadas.
- **Decisão recomendada:** baseline sem LLM; experimento manual de um modelo depois de aprovação; conselho apenas após comparação cega.
- **Justificativa:** evidência de ganho incremental deve anteceder complexidade.
- **Consequências/riscos:** menos perspectivas automatizadas inicialmente; um modelo ainda pode alucinar.
- **Reversibilidade:** papéis são seções conceituais e podem ser testados separadamente.
- **Questões abertas:** modelo, dados, avaliadores, custo e critério de benefício.
