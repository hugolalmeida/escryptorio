# Roadmap proposto · não autorizado para implementação

| Etapa | Pré-requisitos / entrada | Saída e critério de passagem | Parada |
| --- | --- | --- | --- |
| D1 · pacote e relatório sem LLM | ADRs revisados, esquema temporal e fonte read-only definidos | pacote e relatório determinísticos, hashes, fixtures, testes adversariais de tempo e integridade | parar se dados point-in-time ou isolamento não puderem ser demonstrados |
| D2 · validador de claims | D1 íntegro e schema congelado | validação de IDs, janelas e números, estado explícito de evidência insuficiente; nenhuma ferramenta financeira | parar se validação confundir referência existente com verdade semântica |
| D3 · um modelo isolado | aprovação de provedor, privacidade, orçamento e ambiente; benchmark A | experimento manual cego comparado ao baseline, sem ferramentas e com validação independente | não avançar se segurança falhar ou utilidade não compensar custo |
| D4 · Bull/Bear/Risk | D3 avaliado; critérios e orçamento pré-registrados | experimento controlado comparado ao modelo único; preservação de divergência | rejeitar conselho se ganho não demonstrado ou segurança piorar |
| D5 · visualização | relatórios validados, controle de dados e riscos UX revistos | leitura local não executável, estados e citações verificáveis | não expor alegações como ordens ou garantias |
| D6 · avaliação longitudinal | baseline, datasets independentes e métricas congeladas | testes adversariais, estabilidade, qualidade e custo em janelas separadas | interromper se o custo, privacidade ou fragilidade exceder benefício |

Avaliação de qualidade e custo começa já em D1–D3, não apenas no fim. Nenhuma etapa autoriza ordens reais, execução automática ou acesso privado. Decisões humanas pendentes: necessidade do produto, dados autorizados, orçamento, retenção, armazenamento, provedor, política de privacidade, hardware e critérios calibrados.

## Plano de testes antes de implementar

Unidade/propriedade: canonicalização, identidade, Decimal, prefixos causais, fronteiras UTC, fontes compatíveis, timestamps futuros, stale, janelas e dados insuficientes. Contratos: pacote válido e congelado, dataset ausente/adulterado, IDs incorretos, campo proibido, claim sem referência, referência inexistente, métrica inventada e contradição. Integração offline: reader read-only, ausência de rede, zero mutações em todas as tabelas financeiras, credenciais e capacidade de execução inacessíveis, falha de processo e replay preservado.

Adversarial: prompt injection no texto e em saídas de agentes, chamadas de ferramenta proibida, tentativa de exfiltração/canário, instrução operacional em campo livre, dados posteriores e vazamento de treino/teste. Resiliência: schema inválido, resposta parcial, timeout, provedor indisponível, orçamento excedido, limites de chamadas/tokens/retry e cancelamento. Repetibilidade: mesmo pacote e versão geram mesma identidade de entrada; mudar modelo/prompt gera proveniência distinta, sem prometer mesma resposta. Avaliação humana cega da qualidade e estatística OOS separadas de benchmarks de custo/latência. Nenhuma suíte de LLM foi executada nesta fase.
# Atualização 2.3D1

Fundação determinística local parcialmente implementada: uma fonte histórica aprovada, pacote e relatório offline. Point-in-time permanece não comprovado; fontes de backtest/Arena, LLM, agentes e interface ficam adiados. Ver [implementação](AI_EVIDENCE_IMPLEMENTATION.md).
# Atualização 2.3D2

Claims factuais e métricas de backtest persistido têm contratos determinísticos e verificação offline v2; PIT causal permanece desconhecido. Comparações entre estratégias, Arena como fonte e agentes permanecem adiados. Ver [AI_CLAIM_VALIDATION.md](AI_CLAIM_VALIDATION.md).
# Atualização 2.3D2.H1

Hardening e limites de compatibilidade estão em [AI_EVIDENCE_HARDENING.md](AI_EVIDENCE_HARDENING.md). Não foi iniciada a 2.3D3 nem implementada IA.

# Fundação de contexto e mock · 2.3D3A

O subconjunto determinístico está IMPLEMENTED e TESTED em `cryptolab.research.ai_boundary`. O builder aceita bundles v2 verificados e aplica allowlist. O mock stdlib executa em subprocesso supervisionado com gateway independente e orçamento simulado. DEVELOPMENT_MOCK devolve NOT_SANDBOXED. ISOLATED_RESEARCH retorna ISOLATED_RESEARCH_UNAVAILABLE. O gate para D3B é NOT_READY por ausência de fronteiras de SO comprovadas para arquivos, credenciais, rede e recursos.

Contratos, minimização e causalidade em [AI_RESEARCH_CONTEXT.md](AI_RESEARCH_CONTEXT.md). Ambiente Windows, matriz de alternativas e riscos em [AI_RESEARCH_ISOLATION.md](AI_RESEARCH_ISOLATION.md). Limites e contabilidade em [AI_RESEARCH_BUDGET.md](AI_RESEARCH_BUDGET.md). Resultados realmente executados em [VERIFICATION.md](VERIFICATION.md). A investigação e implementação de isolamento forte ficam DEFERRED.

# Prova Windows · 2.3D3A.1

A PoC experimental implementa processo suspenso, Job configurado e conferido antes do resume, limites de commit/processos, término da árvore e rollback. O teste de morte do supervisor comprova KILL_ON_JOB_CLOSE nas fixtures benignas. O resultado é PARTIAL_POC. Restricted Token criou processo, mas o runtime falhou na inicialização; AppContainer sem perfil falhou na criação. Negação de filesystem e rede permanece NOT_VERIFIED. ISOLATED_RESEARCH conserva falha fechada, e JOB_ONLY é seleção explícita exclusiva dos experimentos de recursos.

Capacidades observadas em [WINDOWS_ISOLATION_CAPABILITIES.md](WINDOWS_ISOLATION_CAPABILITIES.md). Launcher, política e rollback em [AI_WINDOWS_ISOLATION_POC.md](AI_WINDOWS_ISOLATION_POC.md). Evidências, limitações e próxima etapa em [AI_ISOLATION_TEST_RESULTS.md](AI_ISOLATION_TEST_RESULTS.md).
