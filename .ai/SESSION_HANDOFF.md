# Escryptorio · handoff

- Repositório: Escryptorio; branch verificada na preparação: `main`. Confirme branch e HEAD atuais com `git status -sb` e `git rev-parse HEAD`.
- Referência auditada: `d7ec4f11c3032bebbd938e1b5d1289b9dd9c00bd` (fase 2.3C3A); novos commits desta fase devem ser verificados no Git.
- Commit local A: `3bfce23` — orientações selecionadas reescritas e handoff; a etapa B registra o hardening do dashboard em commit próprio.
- Fase 2.3C3C: estudo documental de arquitetura de pesquisa com IA, sem implementar agentes. Referência inicial `9842db0a3d5b6a52b143be056898f99ded459b56`; confirmar HEAD e diff no Git.
- Arquitetura: FastAPI local → SQLite WAL e proxy Next → dashboard paper de leitura. Ver `docs/PAPER_DASHBOARD.md`.
- Baseline: `.venv/Scripts/python -m pytest backend/tests/test_paper_dashboard.py -q` — 7 aprovados antes das mudanças.
- Verificações: baseline 26 testes; suíte Python completa 283 aprovados e, após acréscimo de teste, 7 testes operacionais aprovados; typecheck/build aprovados, Playwright completo 99 aprovados/12 ignorados e 24 testes paper finais, 38 replays idênticos, 14 legados. Consulte limitações em `docs/VERIFICATION.md` e o commit atual no Git.
- Observabilidade: `GET /api/v1/paper/operations/overview`, alertas derivados sem persistência, liveness UNKNOWN e integridade financeira parcial. Ver `docs/PAPER_OPERATIONS.md`.
- Observação de performance: overview de uma carteira fictícia em dez chamadas locais, mediana 73,17 ms e máximo 623,68 ms; sem comparação anterior equivalente ou conclusão de ganho.
- Limitação do kit: ZIP sem licença identificada; orientações locais são redação própria e não copiam o pacote.
- Invariantes: Bybit Spot público, BTCUSDT/ETHUSDT, Decimal, ledger auditável, sinais causais, replays, `LIVE_TRADING_ENABLED=false`, paper desativado por padrão, nenhuma ordem real ou conta privada.
- Próximo passo: conferir os commits e as pendências em `docs/VERIFICATION.md` antes de receber nova tarefa.
- Estudo: [AI_RESEARCH_ARCHITECTURE.md](../docs/AI_RESEARCH_ARCHITECTURE.md) e ADRs recomendam relatório determinístico primeiro; decisão de provedor, sandbox, retenção e orçamento continua aberta. D1–D6 não estão autorizadas.
- Nesta fase: fingerprint local `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`, links locais e diff verificados; suítes e replays não foram executados. O Git determina o commit final. Referências e limites em `docs/AI_REFERENCE_EVALUATION.md`.
# Atualização 2.3D1

- Referência inicial: `6faa148dbd217b9df2362d0ba3f493b7f7f6e628`. Consulte o Git para o commit posterior e o estado atual.
- Evidência histórica e relatório determinístico offline: [AI_EVIDENCE_IMPLEMENTATION.md](../docs/AI_EVIDENCE_IMPLEMENTATION.md). PIT desconhecido; nenhuma IA, execução, migration ou integração paper adicionada.
- Testes, fingerprint e limitações desta fase em [VERIFICATION.md](../docs/VERIFICATION.md); resultados de fases anteriores não constituem revalidação atual.
# Atualização 2.3D2

- Baseline `c97f00ab61a61616c6a0fbb834c8e36fc88dcfc9`; confirme o commit final e o estado pelo Git.
- Claims estruturadas e evidência de backtest offline v2 em [AI_CLAIM_VALIDATION.md](../docs/AI_CLAIM_VALIDATION.md); reconciliação não é recálculo, PIT é desconhecido.
- Testes, replays, fingerprint e limitações desta fase: [VERIFICATION.md](../docs/VERIFICATION.md). Nenhuma ordem, IA, migration ou alteração no motor.
# Atualização 2.3D2.H1

- Baseline `2816d67c9ee919f098244d4952447ae4f7f1de2c`; consulte o Git para o commit final.
- Política v1/v2, fixtures sintéticas geradas por `c97f00a`, matriz e riscos: [AI_EVIDENCE_HARDENING.md](../docs/AI_EVIDENCE_HARDENING.md).
- Verificações e limitações em [VERIFICATION.md](../docs/VERIFICATION.md); sem IA, ordens, alteração do motor ou migrations.

# Atualização 2.3D3A · 15/11/2026

- Baseline conferido na main, árvore limpa em `22f59e8dc01e1febd358a7dce3c332f4dd7d8cbc`. O commit desta entrega usa `feat: add isolated research context foundation`. Confirme HEAD/status atuais pelo Git.
- IMPLEMENTED e TESTED — builder somente v2, projeção fechada, mock stdlib em subprocesso fixo, gateway independente, budget efêmero e CLI local. Documentos [contexto](../docs/AI_RESEARCH_CONTEXT.md), [isolamento](../docs/AI_RESEARCH_ISOLATION.md) e [orçamento](../docs/AI_RESEARCH_BUDGET.md).
- DEVELOPMENT_MOCK é NOT_SANDBOXED. ISOLATED_RESEARCH falha fechado com ISOLATED_RESEARCH_UNAVAILABLE. Gate D3B NOT_READY. Launcher restrito, ACL, egress, memória e árvore de processos ficam DEFERRED/NOT_VERIFIED. Windows Home, APIs Win32 presentes e criação/fechamento de Job Object comprovados somente no ensaio mínimo.
- Baseline Python 354 passed/1 skipped. Suíte após implementação 427 passed/1 skipped em 148,27 s. Após reforço final do gateway, fronteira + cinco arquivos de evidência 143 passed/1 skipped em 60,14 s. Aviso Starlette/httpx preexistente. Skip real por Windows recusar criação de symlink. Primeira rodada nova teve 17 falhas de fixture por SystemRoot ausente, corrigidas e repetidas. Comandos e limites em [VERIFICATION.md](../docs/VERIFICATION.md).
- Fingerprint `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62` e 38/38 replays preservados, incluindo 14 legados, em backup temporário com origem somente leitura. Fluxo offline mock VALIDATED_MOCK, limpeza e processo com saída 0. Comparação integral de não mutação usa banco sintético, com várias tabelas financeiras vazias.
- Decisões de implementação — v1 adiado no builder, horários de captura excluídos da identidade, warnings livres suprimidos com limitação explícita e custo simulado conservador sem devolução de reserva em falha. Nenhuma dessas decisões autoriza LLM ou isolamento presumido.
- Próxima etapa depende de nova autorização e provas das fronteiras de SO, privacidade/retenção e riscos. O resultado atual serve ao desenvolvimento determinístico/mock. Frontend e dependências ficaram fora do diff, portanto Playwright/build/typecheck não foram repetidos.

# Atualização 2.3D3A.1 · 15/11/2026

- Baseline main limpa em `775e9c553d6ba346f23fceb1348345fc7eb30035`. Commit da entrega usa `feat: add windows isolation proof of concept`; conferir HEAD/status pelo Git.
- IMPLEMENTED e TESTED — windows_native.py, isolation_poc.py, isolation_probe.py, política v1 congelada, launcher suspenso, handles herdáveis limitados, Job de memória/processos e KILL_ON_JOB_CLOSE. Ambiente confirmado não elevado. Testes usam fixtures benignas, SQLite e loopback sintéticos.
- Gate PARTIAL_POC. Memória/processos/rollback ENFORCED_AND_TESTED nos cenários. Restricted Token inicializou processo, mas o runtime falhou com 0xC0000022. AppContainer sem perfil falhou com CreateProcessW/203. Negação de FS/rede NOT_VERIFIED. ISOLATED_RESEARCH permanece indisponível, com JOB_ONLY explicitamente selecionado para controles de recursos.
- Suítes completas 454/1 skip e depois 455/1 skip, saídas 0. Direcionados finais de fronteira/evidência/PoC 171/1 skip em 75,02 s. O reforço posterior de bloqueio de reuso após rollback incompleto teve nova execução Windows registrada em VERIFICATION e AI_ISOLATION_TEST_RESULTS. Aviso Starlette/httpx e skip de symlink preexistentes.
- Fingerprint e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62 preservado. 38/38 replays, incluindo 14 legados, em backup temporário de origem somente leitura, limpeza e saída 0 em 5,17 s. Não mutação integral usa fixture sintética.
- Correções observadas — buffer TokenElevation, SID Restricted Code, interpretador GUI sem conhost, nome pythonw preservado e espera de término assíncrono. Cache relativo incidental %SystemDrive% foi removido após verificar ownership/contenção; ambiente corrigido com SystemDrive e cwd próprio. Conferir sua ausência antes de retomar.
- Zero regras persistentes, contas, perfis ou ACLs externas criados. Perfil AppContainer foi DEFERRED por exigir autorização futura conforme o pedido. CPU/disco DEFERRED. Performance observada é limitada às amostras, sem garantia universal ou teste de escape de código hostil.
- Próximo passo mínimo depende de autorização específica para investigar perfil AppContainer descartável e runtime com testes de negação real de arquivo/loopback. Relatório dos 30 itens, comandos e limites em [AI_ISOLATION_TEST_RESULTS.md](../docs/AI_ISOLATION_TEST_RESULTS.md), [PoC](../docs/AI_WINDOWS_ISOLATION_POC.md) e [capacidades](../docs/WINDOWS_ISOLATION_CAPABILITIES.md).
- Verificação posterior ao último reforço de rollback: arquivo Windows com 28 passed, um aviso preexistente, 11,79 s e saída 0. Instância com falha nativa de limpeza bloqueia novo launch e conserva ROLLBACK_INCOMPLETE após remoção da árvore. A falha de diretório possui retry de limpeza separado e testado.
