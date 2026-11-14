# Escryptorio · handoff

- Repositório: Escryptorio; branch verificada na preparação: `main`. Confirme branch e HEAD atuais com `git status -sb` e `git rev-parse HEAD`.
- Referência auditada: `d7ec4f11c3032bebbd938e1b5d1289b9dd9c00bd` (fase 2.3C3A); novos commits desta fase devem ser verificados no Git.
- Commit local A: `3bfce23` — orientações selecionadas reescritas e handoff; a etapa B registra o hardening do dashboard em commit próprio.
- Fase 2.3C3A.1: hardening do dashboard e revisão seletiva do kit v0.14. Não iniciar 2.3C3B sem nova tarefa.
- Arquitetura: FastAPI local → SQLite WAL e proxy Next → dashboard paper de leitura. Ver `docs/PAPER_DASHBOARD.md`.
- Baseline: `.venv/Scripts/python -m pytest backend/tests/test_paper_dashboard.py -q` — 7 aprovados antes das mudanças.
- Verificações finais: 277 testes Python, typecheck e build aprovados; Playwright completo 87 aprovados/12 ignorados e, após ajuste, 15 testes paper aprovados; 38 replays idênticos, 14 legados. Detalhes e limites em `docs/VERIFICATION.md`; arquivos da entrega em `git show --stat`.
- Observação de performance: overview de uma carteira fictícia em dez chamadas locais, mediana 73,17 ms e máximo 623,68 ms; sem comparação anterior equivalente ou conclusão de ganho.
- Limitação do kit: ZIP sem licença identificada; orientações locais são redação própria e não copiam o pacote.
- Invariantes: Bybit Spot público, BTCUSDT/ETHUSDT, Decimal, ledger auditável, sinais causais, replays, `LIVE_TRADING_ENABLED=false`, paper desativado por padrão, nenhuma ordem real ou conta privada.
- Próximo passo: conferir os commits e as pendências em `docs/VERIFICATION.md` antes de receber nova tarefa.
