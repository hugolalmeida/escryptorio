# Custo e avaliação de alternativas

| Alternativa | Chamadas / tokens | Latência e complexidade | Auditoria / risco | Decisão |
| --- | --- | --- | --- | --- |
| A · sem LLM | zero chamadas/tokens de modelo | menor; geração determinística local | comparável por versão e evidências; pode ser menos expressiva | **primeiro baseline recomendado** |
| B · um modelo | uma chamada por tentativa, mais validação; entrada e saída medidas | média; timeout e provedor/hardware | rastro de pacote/prompt/modelo; alucinação e não determinismo | experimento manual futuro, somente se aprovado e comparado com A |
| C · Bull/Bear/Risk | ao menos três chamadas conceituais, mais consolidação se usada | maior; texto repetido, latência e coordenação | divergências úteis como hipótese; erros correlacionados e consenso falso | adiar até benefício incremental contra B |

Custo externo por relatório = soma, para cada chamada, de `(tokens_entrada/1.000.000 × preço_entrada) + (tokens_saída/1.000.000 × preço_saída)`, com preços, moeda, data, cache e cobrança de tentativas explicitados; acrescentar impostos e outros custos contratados quando aplicáveis. Exemplo **hipotético**: 10.000 tokens de entrada a 2 unidades monetárias/milhão e 1.000 de saída a 8/milhão = 0,028 unidades por chamada, antes de outros custos. Não são preços de fornecedor. Arredondamento, cobrança mínima, tokens de raciocínio e retry dependem do contrato efetivo.

O modelo local pode manter dados offline se o processo, modelo e telemetria forem efetivamente isolados; requer hardware, energia, armazenamento e manutenção, não quantificados aqui. API externa reduz gestão local mas transmite dados permitidos ao fornecedor e cria dependência de retenção, região, autenticação, preço e SLA. Hardware e qualidade necessários dependem de benchmark real; nenhum modelo ou custo atual foi medido.

Antes de experimento, operador define orçamento máximo por relatório e sessão, chamadas, tokens de entrada/saída, timeout, tentativas, política de dados e cancelamento; defaults concretos dependem do hardware/provedor e da avaliação. Falha fechada sem retries infinitos; nenhuma pesquisa externa automática. O processo deve contabilizar consumo mesmo em erro parcial e não acionar chamadas nesta fase.

## Avaliação futura

Separar segurança, qualidade, utilidade e rentabilidade. Em conjunto congelado com casos positivos, negativos e adversariais, medir conformidade de schema, referências existentes e pertinentes, reconciliação numérica com o motor, rejeição de adulteração, datas stale/futuras e lookahead, tentativas de ferramenta proibida, vazamento de canário, falhas, custo e latência. Controles críticos de isolamento e mutação devem passar em todos os casos definidos; isso não prova ausência universal de falhas.

Comparar A/B/C cegamente sobre **os mesmos pacotes**, com métricas pré-registradas, avaliadores humanos independentes, concordância entre avaliadores, tempo de revisão e erros verificáveis; amostras e intervalos de confiança escolhidos em estudo posterior. Não escolher metas arbitrárias para utilidade, custo ou qualidade. Medir benefício incremental de B sobre A e C sobre B e interromper se não compensar risco e custo. Utilidade do relatório não comprova rentabilidade ou validade da estratégia.
