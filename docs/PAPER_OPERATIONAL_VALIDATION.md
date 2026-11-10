# Validação operacional paper · Fase 2.3C2B2C

O diagnóstico usa somente coleta pública Bybit Spot e uma carteira fictícia num SQLite novo em diretório temporário local não sincronizado. Não contém opção de fill; o executor manual existente permanece separado. O script não aceita caminho de banco, cria um diretório exclusivo, exige que live e paper estejam desativados e passa o mesmo caminho explícito ao worker, monitor, planner e ledger. Nenhum arquivo existente é apagado. O banco criado é preservado para inspeção e pode ser removido manualmente depois de fechar os processos.

```powershell
# Diagnóstico offline: migrations e integridade em um banco novo, sem coletar.
.\scripts\smoke-paper.ps1
# Coleta pública única; carteira continua pausada por padrão.
.\scripts\smoke-paper.ps1 -Public
# Ativação explícita somente da nova carteira fictícia; coleta e decisão informativa.
.\scripts\smoke-paper.ps1 -Public -ActivateWallet
```

Use PowerShell no diretório do repositório com `.venv` instalada. `LIVE_TRADING_ENABLED` e `PAPER_SIMULATION_ENABLED` devem estar ausentes ou ser `false`. A saída JSON informa o banco, UTC, versão Python, snapshots, hashes, checkpoint, sinal, carteira, proposta, eventual decisão e reconciliação. Redirecione a saída para arquivo escolhido pelo operador se quiser preservar o relatório. O processo da coleta tem limite de 90 segundos; falha não é substituída por dados fictícios. O script gera ID exclusivo, capital fictício `1000`, risco `0.01`, exposição `0.10`, fee `0.001` e slippage `0.0005`; esses custos são hipóteses, não taxas da conta. Antes de ativar a carteira é necessário fornecer `-ActivateWallet`. Cada execução cria outro banco; não reutiliza ou sobrescreve o anterior.

`PASS` indica a coleta validada; `BLOCKED_EXPECTED` indica condição impeditiva, inclusive carteira pausada ou ausência de autorização para executar; `NO_ELIGIBLE_TRADE` indica HOLD; `FAILED` significa falha operacional; `NOT_RUN` identifica etapa não executada. Um BUY/SELL condicional não implica fill: o script termina bloqueado para a etapa de execução. Para operar manualmente em banco descartável previamente verificado, com decisão atual e autorização humana específica, consulte o fluxo de `preview`, `once --paper`, `show`, `history` e `verify` em [PAPER_EXECUTION.md](PAPER_EXECUTION.md). Não habilite a flag antes das verificações e remova-a após o comando. HOLD, sinal histórico, snapshot obsoleto ou relógio inválido nunca autorizam fill.

## Ensaio observado

Commit-base `6d86bbe44b4338766285a1ae5307e8ece051715d`; Windows, Python 3.10.11, 2026-11-10 aproximadamente 01:40 UTC. O sandbox inicialmente retornou `BYBIT_UNAVAILABLE`; uma coleta única fora da restrição de rede funcionou, sem contornar bloqueio regional. Banco isolado preservado: `C:\Users\hugog\AppData\Local\Temp\escryptorio-smoke-3a720cfbbdcd4efebe94fd98989daaf2\smoke.sqlite3`. A coleta obteve BTCUSDT e ETHUSDT nos quatro intervalos 15m, 1h, 4h e 1d. O ensaio automatizado posterior verificou os oito hashes, timestamps e regras de instrumento, com 299 candles fechados por snapshot e idade de fonte entre 2,4 e 6,7 segundos no momento da verificação.

Monitor Trend BTCUSDT 1h, parâmetros padrão: sinal `49da32feefde9ca0e2a0a5d27fd0b1e9d2e4f8ebca931e7aae29338f1a1d5bf9`, `schema_version=2`, `origin=current`, `mode=informational_only`; repetição retornou o mesmo ID. Dataset `c747ac404f892025584607c1f0aa114d03078c835928a77b5f6e7a4629077f7b`; fingerprint financeiro `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62`. Carteira `0758c90d2f6848949ade63cde8f224a1` nasceu pausada e foi ativada manualmente apenas no banco isolado; vínculo `80c4c13a54194831039e4faa5a128fe950be2114168bf22e3908a3aad8ad135b` ficou ativo. Planner: **HOLD**; decisão `63351453e43d5ab04dfcb8c0b5e0b7cba85a370ada2a90c9e203da175bfffb8e` registrada. A posição inicial e final foi `0` BTC, saldo `1000` USDT fictícios, fee, slippage realizado e PnL `0`.

A reconciliação final retornou `valid=true`, uma carteira, um vínculo, uma decisão, zero marcas e zero execuções. **NO_ELIGIBLE_TRADE**: não houve fill, portanto preview de fill, idempotência de fill, recuperação de fill após reinício e ciclo BUY/SELL com dados públicos são **NOT_RUN**. Esses cenários permanecem cobertos por testes sintéticos da fase anterior, não por este ensaio público. O ensaio não prova liquidez, preço executável ou proteção de stops/targets.

Após o envelhecimento do mesmo snapshot, nova avaliação retornou `STALE_SNAPSHOT`, com reconciliação válida e contagem financeira inalterada. Uma nova coleta pública seguida da CLI `cryptolab.monitor --once` recuperou o mesmo ID de sinal, e a CLI `cryptolab.paper.executor_cli verify` confirmou novamente a integridade. Um segundo ensaio pelo script com ativação explícita também terminou em HOLD e `NO_ELIGIBLE_TRADE`; a execução de fill permaneceu `NOT_RUN`.

Antes de operação contínua seriam necessários supervisor, coleta e relógio confiáveis, políticas de risco e marcação, reconciliação periódica, desenho de recuperação, revisão e testes de segurança; esta fase não implementa nem autoriza executor contínuo, ordens reais ou acesso privado.
