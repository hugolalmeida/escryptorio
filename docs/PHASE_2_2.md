# Plano · Fase 2.2 — Estratégias e Backtesting

Pré-requisito entregue: arquivo incremental, catálogo aprovado, hash reproduzível, reader offline Decimal e verificação de integridade. Esta fase é um plano; nenhuma estratégia foi implementada na fase 2.1.

## Sequência proposta

1. Definir contratos puros `Strategy`, `Decision`, `BacktestConfig`, `CostModel`, `Fill`, `Portfolio`, `RunManifest` e `Metrics`, independentes de FastAPI/Pybit/SQLite. Entrada exclusivamente por `DatasetReader` com hash aprovado e limites explícitos.
2. Especificar regras e parâmetros long-only de Trend, RSI, Breakout e Buy & Hold. Reutilizar indicadores fechados já testados. Breakout consulta somente N candles anteriores; decisão ao fechamento de t não pode ser preenchida em t. Mack fica reservada e não validada.
3. Implementar replay determinístico: fill mais cedo na abertura de t+1, slippage adverso, taxa por fill, saldo nunca negativo, precisão Decimal e limites de instrumento versionados. Documentar gaps, falta de liquidez, fills parciais e política conservadora para stop/alvo no mesmo candle. Nenhuma chamada a endpoints de ordens reais.
4. Separar treino, validação e teste cronológicos. Usar dados anteriores apenas para warm-up causal; congelar parâmetros antes do teste. Registrar versão do motor/estratégia, hash do dataset e dependências. Seeds só se houver componente aleatório explicitamente adotado.
5. Calcular equity marcada a mercado, retorno líquido, drawdown, profit factor, acerto, expectativa e trades. Tratar ausência de perdas/trades como casos explícitos; definir política de liquidação final comum para Buy & Hold e estratégias.
6. Persistir execuções imutáveis por manifesto, resultados e trilha de fills. Reexecução do mesmo manifesto deve produzir conteúdo e hash de resultado iguais, sem depender da data atual ou da Bybit. O recorte e o hash completo do dataset devem constar no manifesto.
7. Adicionar CLI/API de pesquisa e interface de resultados após validação matemática. Arena comparativa e paper ficam para a etapa seguinte; não antecipar rankings com métricas incompletas.
8. Fazer spike de validação cruzada Freqtrade isolado, conforme ADR existente. Fixar release e runtime Python 3.12+/imagem, importar a mesma série e reconciliar fills/custos/saídas antes de interpretar diferenças como desempenho.

## Aceite proposto

- Testes de referência manuais para fills, fees, slippage, equity e métricas; custos e lucro líquido verificáveis trade a trade.
- Invariância de prefixo para indicadores e decisões; modificar dados futuros não altera decisões/fills anteriores.
- Mesmo dataset/configuração gera resultado idêntico após reinício e sem conexão externa.
- Backtest recusa hash adulterado, dataset incompleto, recorte desalinhado ou warm-up insuficiente.
- Treino/validação/teste e custos identificáveis no resultado; nenhum parâmetro escolhido no teste.
- Capital e custos equivalentes entre estratégias; Buy & Hold com a mesma política final.
- Dashboard e histórico mantêm suas suítes de regressão; `LIVE_TRADING_ENABLED=false` e nenhuma capacidade de ordens reais.

Antes de comparar rentabilidade, ampliar a cobertura por ativo/timeframe para períodos que atravessem diferentes regimes. Os 5.475 candles coletados na fase 2.1 demonstram infraestrutura; não constituem validação de estratégia ou recomendação de operação.
