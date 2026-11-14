# Escryptorio · handoff

- Repositório: Escryptorio; branch e HEAD devem ser conferidos com `git status -sb` e `git rev-parse HEAD`.
- Referência auditada: `d7ec4f11c3032bebbd938e1b5d1289b9dd9c00bd` (fase 2.3C3A); novos commits desta fase devem ser verificados no Git.
- Objetivo atual: hardening 2.3C3A.1 e revisão seletiva do kit v0.14. Não iniciar 2.3C3B.
- Arquitetura: FastAPI local → SQLite WAL e proxy Next → dashboard paper de leitura. Ver `docs/PAPER_DASHBOARD.md`.
- Baseline: `.venv/Scripts/python -m pytest backend/tests/test_paper_dashboard.py -q` — 7 aprovados antes das mudanças.
- Verificações finais e arquivos da entrega: consultar `docs/VERIFICATION.md` e `git show --stat`; não inferir resultados a partir deste documento.
- Limitação do kit: ZIP sem licença identificada; orientações locais são redação própria e não copiam o pacote.
- Invariantes: Bybit Spot público, BTCUSDT/ETHUSDT, Decimal, ledger auditável, sinais causais, replays, `LIVE_TRADING_ENABLED=false`, paper desativado por padrão, nenhuma ordem real ou conta privada.
- Próximo passo: conferir os commits e as pendências em `docs/VERIFICATION.md` antes de receber nova tarefa.
