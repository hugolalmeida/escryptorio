# Dashboard paper · leitura local

`/paper` apresenta saldos **fictícios**, posições, marcações, sinais, decisões e histórico. Não há controles de gestão nem execução. O navegador usa GET no proxy Next local; o proxy aceita somente caminhos e parâmetros enumerados, origem backend HTTP loopback, sem redirects, com timeout e `no-store`. O FastAPI usa `mode=ro`, `PRAGMA query_only=ON` e uma transação SQLite por resposta. Nenhum handler chama `migrate`, altera o relógio de decisões ou persiste expiração; faltando migrations ou em caso de corrupção a leitura falha com erro sanitizado. A inicialização normal do backend continua aplicando migrations como nas fases anteriores.

Todas as respostas são versão 1: `{schema_version, observed_at_ms, data}`. Endpoints GET:

- `/api/v1/paper/overview`: carteiras, totais USDT, horários e estado dos snapshots.
- `/api/v1/paper/wallets/{id}`: ledger reconstruído, marca e vínculo ativo.
- `/api/v1/paper/wallets/{id}/events` e `/fills`: `limit` 1–100 e `offset` 0–1000000; as páginas são formadas no backend.
- `/api/v1/paper/wallets/{id}/equity`: até 500 observações verificáveis.
- `/api/v1/paper/signals` e `/decisions`: até 100 registros por consulta; expiração é derivada em memória.

A carteira é reconstruída pelo ledger; marcas com sidecar são verificadas com o verificador da fase anterior. A posição é marcada somente se a evidência mais recente for íntegra, mais recente que o último fill e tiver fonte dentro do limite configurado de frescor. Caso contrário, valor da posição, equity e PnL não realizado são indisponíveis. Uma carteira sem posição tem valor de posição e PnL não realizado iguais a zero. Valor = quantidade × preço marcado; equity = caixa + valor; PnL não realizado = valor − custo de aquisição; PnL total = realizado + não realizado. O custo contábil já inclui taxas de entrada e o PnL realizado inclui taxas de saída. Não subtraia custos novamente. Valores são Decimal serializados em strings; totais são apenas USDT e ficam indisponíveis se qualquer componente necessário estiver ausente.

Execuções com sidecar são verificadas antes de receber o rótulo `VERIFIED`; fills anteriores sem sidecar são `LEGACY_UNVERIFIED`. O gráfico usa pontos de genesis, marcas verificadas e encerramentos de posição, sem interpolar preços ou usar ticker atual para reconstruir o passado. Não representa rentabilidade contínua; pontos ausentes não significam zero. Marcação pública não garante liquidez ou preço executável. Stops e alvos são hipotéticos.

`WALLETS_VERIFIED` confirma a reconstrução dos ledgers consultados; não afirma que todos os sidecars, decisões e sinais da base foram auditados. Cada decisão e fill exibidos são conferidos na respectiva consulta. O estado do monitor permanece `UNKNOWN`, pois um registro anterior não comprova que o processo esteja ativo. Em falha de integridade ou backend, a tela deixa de apresentar o resumo antigo. O polling é a cada 15 segundos; o horário de origem nunca é atualizado artificialmente.

Limitações: o replay de cada carteira ainda lê a cadeia inteira no backend; a paginação limita a resposta, não o custo da verificação. Sinais e decisões exibem os últimos 20 por padrão e ainda não oferecem paginação na interface. O gráfico mostra observações discretas, não uma curva contínua. A consulta de eventos mostra até 10 na interface; a API aceita paginação. Não há consulta de conta privada, worker executor ou autorização de operação.

No Windows, use `scripts/dev.ps1` conforme o README para iniciar os serviços locais e abra `http://127.0.0.1:3100/paper`. Execute `.venv/Scripts/python -m pytest backend/tests -q`, `npm run typecheck`, `npm run build` e `npm run test:ui` para regressão. Fixtures sintéticas de teste nunca são fallback da aplicação.
