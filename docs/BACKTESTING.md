# Fase 2.2 · Motor quantitativo

## Auditoria inicial · 02/11/2026

Git inicialmente limpo em `3a19942`. Lidos AGENTS, ARCHITECTURE, HISTORY, PHASE_2_2, FREQTRADE, VERIFICATION e módulos indicados. Baseline executada: 71 testes Python passaram (aviso Starlette/httpx já existente). Reutilizar Candle, SMA/EMA/RSI Wilder/ATR, DatasetReader com verificação integral, HistoryStore e migrations transacionais. Não reconstruir histórico, dashboard nem coletor público. Não instalar Freqtrade ou alterar a venv.

## Regras congeladas antes dos ensaios

Hipóteses experimentais, versão `1`, sem alegação de rentabilidade:

- **Trend**: SMA rápida 20 e lenta 50. Entrada por cruzamento ascendente (opção: estado rápida > lenta), fechamento > rápida; saída rápida <= lenta (opção: fechamento < rápida). Filtro opcional ATR14/close <= limite.
- **RSI**: Wilder14; compra apenas quando RSI anterior <= 30 e atual > 30. Saída RSI >= 60. Filtro opcional fechamento > SMA50.
- **Breakout**: fechamento > máxima dos 20 candles estritamente anteriores. Filtro opcional volume atual >= média dos volumes anteriores × multiplicador. Saída fechamento < mínima dos mesmos N candles anteriores.
- **Buy & Hold**: decisão de compra no primeiro fechamento elegível, entrada na abertura seguinte; uma única tentativa de entrada, sem stop/alvo. Capital, exposição, taxas, slippage, janela e política final iguais. Risco baseado em stop não se aplica a benchmark sem stop.
- **Mack**: não validada, inelegível; nenhuma regra inventada.

Padrões: capital 10.000 USDT, taxa 0,001 por lado, slippage 0,0005 adverso, risco planejado 0,01, exposição 1, stop 0,03, alvo 0,06. Todos são premissas configuráveis de pesquisa, não taxas verificadas de conta. Relação alvo/stop explícita. Regras de instrumento são copiadas do último snapshot público local, incluindo timestamp e hash; não representam regras históricas verificadas na data dos candles. Sem snapshot, a execução é recusada. CLI/API offline não fazem coleta.

## Semântica de execução

Intervalos UTC `[início,fim)`. Indicadores recebem somente histórico fechado causal; dados antes do início servem exclusivamente ao warm-up. Warm-up deve estar disponível no primeiro fechamento selecionado. Ordem decidida no fechamento t só é elegível na abertura t+1. Uma posição long por execução, sem saldo negativo. Quantidade arredondada para baixo pelo passo de base; preço adverso arredondado ao tick (compra para cima, venda para baixo). Mínimos e máximos verificados; residual abaixo do mínimo permanece aberto e identificado.

Stop/alvo são fixados no fill de entrada, a partir do preço efetivo e percentuais configurados. Gap abaixo do stop: preço base de saída é a abertura; gap acima do alvo: preço base é a abertura. Em candle que toca ambos sem gap decisivo, stop primeiro. Slippage e taxa incidem em cada fill. Stops podem disparar no candle de entrada após a abertura. Saída por decisão anterior é executada na abertura antes de avaliar stops intrabar. Não inventar caminho intrabar, liquidez, fila ou fills parciais. Slippage é impacto hipotético adverso e pode produzir preço fora do OHLC; não constitui fill observado. Risco planejado considera stop, slippage e taxas de ida/volta, mas gaps podem excedê-lo.

Política final comum: `mark_to_market` mantém posição aberta, sem taxa de saída inventada; `liquidate` aplica liquidação virtual no último fechamento conhecido como evento administrativo, com custos. Não é um sinal de estratégia nem antecipação do último candle. Drawdown é calculado sobre equity marcada a mercado no fechamento, incluindo capital inicial; não mede drawdown intrabar. Exposição é fração dos candles elegíveis com posição em algum momento do candle, não duração intrabar inferida.

Treino/validação/teste usam limites cronológicos explícitos e contíguos. Cada recorte começa com saldo novo; o histórico precedente só aquece indicadores. Parâmetros ficam congelados em um protocolo SHA-256 antes das execuções. Teste exige protocolo persistido; não há otimização automática. O sistema registra experimentos, mas não pode impedir seleção humana posterior após observar resultados. Menos de 30 trades encerrados é sinalizado como amostra insuficiente; ultrapassar esse limiar não valida rentabilidade.

Métricas sem denominador são `null` acompanhadas de explicação. Profit factor usa PnL líquido por trade; expectativa é média de PnL líquido dos trades encerrados; custos são taxas mais impacto monetário do slippage (já embutido no PnL, nunca subtraído novamente). Posições abertas não entram em win rate/profit factor. Comparação com Buy & Hold usa diferenças de retorno em pontos percentuais, sem ranking de vencedores.

Persistência: protocolos e resultados imutáveis, JSON canônico, Decimal como strings, SHA-256 sem relógio volátil. Metadados incluem versão do motor, commit e hash do código relevante para identificar alterações ainda não commitadas. Data de registro fica fora do hash. Integridade é verificada também na leitura dos resultados.

## Limites de instrumento

Verificada a [documentação oficial Bybit de instrumentos Spot](https://bybit-exchange.github.io/docs/v5/market/instrument) em 02/11/2026. Usamos `basePrecision`, `tickSize`, `minOrderAmt` e `maxMarketOrderQty`. Os campos `minOrderQty`, `maxOrderQty` e `maxOrderAmt` antigos estão depreciados e não são tratados como regras vigentes. O contrato puro aceita mínimos/máximos adicionais explícitos para testes ou futuras versões, mas o adaptador público não inventa limite substituto ausente. Taxas em USDT são acumuladas em Decimal sem emular arredondamento/denominação real da conta. A taxa efetiva e a moeda de cobrança não foram consultadas.

Fills intrabar têm `candle_time` identificando a barra e `time` no fechamento como instante contábil; OHLC não informa o instante real do toque. Fills de abertura e liquidação final têm horários exatos do modelo. Stops/alvos arredondados e preços efetivos são armazenados separadamente.

## API, CLI e interface

`POST /api/v1/research/protocols` congela uma configuração; `POST /runs` executa uma janela; `GET /runs` lista as 50 execuções mais recentes; `GET /runs/{hash}` verifica e consulta o resultado; `POST /runs/{hash}/verify` reexecuta e compara hashes. `GET /protocols/{hash}` consulta protocolo. As mutações exigem o cabeçalho de intenção e origem local. O proxy Next aceita somente hosts loopback, valida origem/Host e caminhos, limita corpo a 8 KiB e comunica com backend HTTP em loopback. O cabeçalho não substitui autenticação remota. A API executa no pool de threads, limita a uma pesquisa simultânea por processo e até 20.000 candles incluindo warm-up; não cria tarefas de download. Cada processo da API tem seu próprio limite, portanto mantenha apenas uma instância por banco.

CLI e exemplo de PowerShell em [README](../README.md); JSON em [backtest-example.json](backtest-example.json). O reader verifica integralmente o dataset, mesmo quando o replay usa um recorte. O hash de código cobre arquivos Python do backend, migrations e lockfile; o commit registrado pode referir-se ao HEAD anterior quando há alterações locais, por isso o hash adicional identifica o conteúdo efetivamente utilizado. A reexecução recusa código diferente em vez de substituir resultados. O hash do resultado engloba manifesto, estratégia, benchmark, métricas, equity, fills, trades e planos; o timestamp de inserção fica fora do payload.

O gráfico mostra patrimônio da estratégia, Buy & Hold e drawdown. Tabela paginada fornece valores exatos, e manifesto, fills, planos e recusas são inspecionáveis. Uma execução anterior permite restaurar seu protocolo congelado e continuar as outras janelas mesmo após recarregar a página. A interface usa float exclusivamente para gráfico e formatação visual; os valores exatos permanecem strings. Valores sem denominador são mostrados como indefinidos, com justificativa. Não há prêmio ou indicação automática de vencedor.

## Ensaio real controlado · 02/11/2026

Dataset aprovado BTCUSDT 1h, `[01/09/2026, 01/11/2026)`, SHA-256 `f3b2e55b1cc373d448efa3676c63064cb482c86be4ebd7442bce573134f972c6`. Aquecimento antes de 04/09; treino `[04/09,01/10)`, validação `[01/10,16/10)` e teste `[16/10,01/11)`, tudo UTC. Foram congelados quatro protocolos com os parâmetros padrão documentados acima, mesmo capital e custos; nenhuma otimização. Cada uma das 12 execuções foi reexecutada com hash idêntico. Snapshot público do instrumento: `basePrecision=0.000001`, `tickSize=0.1`, mínimo nominal 5, máximo de mercado 120 BTC, `source_time_ms=1793583197454`; não são regras históricas verificadas. Hash do código `85a5b51ab9a8a9a77e6e32f3ec887103b5dce701015077bf00b0335095d2168d`, HEAD `3a19942` com alterações locais identificadas por esse hash.

| Teste fora da amostra | Retorno líquido | PnL USDT | Drawdown máximo | Trades | Hash de execução |
| --- | ---: | ---: | ---: | ---: | --- |
| Trend | -2,02% | -202,19 | 2,10% | 5 | `f2da6263fcb89e9a62af26d88be26f89b145874aa5bd90318375a0206f51d2bc` |
| RSI | -0,97% | -97,42 | 1,29% | 3 | `0167d8320560db9a2aa6a3fd636b4557bfcfbac512962636fb672e22debf04f4` |
| Breakout | -0,82% | -81,73 | 1,22% | 3 | `9521a9a462bfedc8634a64aa54f69f0f9a98b9ff598d2c75e6f01e0c44000953` |
| Buy & Hold | -6,11% | -611,46 | 9,70% | 1 | `64a069cf374aac046a382c61dccd47d8fcbd55489a30c26818a45410f4f85ceb` |

O teste cobre somente 16 dias e 1–5 trades, uma amostra insuficiente para validar uma estratégia. Os resultados são específicos do modelo de custos e não estimam desempenho futuro. Os detalhes completos e hashes estão no banco local ignorado pelo Git; também foi salvo `artifacts/backtest-smoke.json` como artefato local ignorado. A CLI documentada executou o Trend em todas as janelas e confirmou o hash acima.

## Limitações e próxima fase

- Não há otimização ou seleção automática. Congelar e executar treino/validação primeiro não impede que uma pessoa crie múltiplos protocolos depois de ver o teste; controle de seleção e experimento verdadeiramente cego exigem processo externo.
- Apenas OHLCV e snapshot recente de regras. Sem order book, spreads observados, latência, liquidez, partial fills, taxas da conta, impostos, mudanças históricas de regras ou validação de elegibilidade. Taxa é aplicada em USDT, aproximação assumida.
- Liquidação final ocorre no fechamento como evento administrativo, com custos; não é uma ordem intrabar. Marcação não desconta taxa futura de saída. Caso mínimos ou máximos impeçam uma saída simulada, ela é recusada e a posição permanece aberta.
- O benchmark fica totalmente investido respeitando exposição e saldo, e não usa risco por stop. As demais estratégias podem ficar parcialmente alocadas pelo orçamento de risco; isso influencia a comparação.
- Uma regra de amostra abaixo de 30 trades é um aviso, não teste estatístico; 30 não é um limiar de validade.
- Freqtrade permanece sem integração executada. Comparação futura exige ambiente isolado Python 3.12+/Docker e as mesmas séries e semântica, conforme [FREQTRADE.md](FREQTRADE.md).
- Próxima fase Arena: contas virtuais independentes por estratégia, mesmos datasets/janelas/custos, persistência dos experimentos e apresentação fora da amostra sem declarar vencedor com dados insuficientes. Paper trading deverá ter ledger, idempotência, reinício e validação de dados obsoletos. Conta privada e execução real continuam fora desta entrega.
