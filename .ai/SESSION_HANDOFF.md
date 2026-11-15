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
