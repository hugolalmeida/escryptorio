# Arena histórica · Fase 2.3A

A Arena é uma camada local de orquestração de pesquisa; usa exclusivamente `ResearchService`, `DatasetReader` e o motor existente. Não possui cliente da Bybit, credenciais ou funções de ordem. Cada competição contém Trend, RSI, Breakout e Buy & Hold, com quatro carteiras virtuais independentes e capital inicial igual. A interface `/arena` foi adicionada na Fase 2.3B.

## Contrato e fluxo

`ArenaConfig` registra dataset SHA-256, ativo/timeframe, limites UTC `[início,fim)` de treino, validação e teste, `BacktestConfig` compartilhado (capital, taxas, slippage, risco, exposição, encerramento), parâmetros e versão `1` de cada estratégia. Opcionalmente inclui quatro IDs de protocolos existentes. Sem eles, a criação congela os quatro protocolos por `ResearchService.freeze` antes de executar qualquer janela. O dataset aprovado é revalidado e deve corresponder a ativo/timeframe. Protocolos devem corresponder ao dataset, às três janelas, ao capital e às mesmas regras de custos/risco/exposição/encerramento; os parâmetros de estratégia podem diferir. Regras de instrumento, versão e fingerprint compatível do motor também devem coincidir. Se um snapshot do instrumento mudar enquanto os protocolos são congelados, a criação é recusada; tente novamente. Protocolos já criados permanecem preservados.

A execução chama o serviço existente nesta ordem: **quatro treinos → quatro validações → quatro testes**. O serviço já exige treino e validação antes do teste. Cada replay cria sua própria carteira inicial, e o histórico anterior aquece indicadores de forma causal; não há seleção ou otimização automática. Todos os protocolos são congelados antes de ver os resultados, mas múltiplos experimentos humanos podem ser criados após observar o teste; o sistema não os torna cegos retroativamente.

No fim, a Arena verifica manifestos, dataset, janelas, estratégia/versão/parâmetros, configuração, instrumento e fingerprint, capital inicial de cada carteira e igualdade do benchmark Buy & Hold em cada período. Compara retorno líquido usando `Decimal`, com ordenação decrescente e empate no mesmo posto (ex.: 1, 1, 3); ordem alfabética só estabiliza a apresentação de empates. Cada janela retorna ranking próprio com retorno, drawdown, profit factor, acerto, número de trades, expectativa, custos, exposição, diferença em pontos percentuais para Buy & Hold, motivos de métricas indefinidas e IDs de protocolo/execução. O teste vem com `out_of_sample=true`.

Menos de 30 trades é marcado `insufficient_sample=true`; a janela é marcada insuficiente se qualquer participante tem menos de 30. Buy & Hold normalmente tem um trade fechado, portanto essa regra conservadora geralmente marcará a janela insuficiente. O limiar não valida nenhuma estratégia, mesmo se superado. `validated_winner` é sempre `null`: classificação histórica é descritiva, não prova de lucratividade. O benchmark não tem stop e pode assumir mais exposição que as estratégias dimensionadas por risco.

## Integridade, retomada e concorrência

`arena_experiments` guarda JSON canônico imutável e ID SHA-256. O hash da configuração é único para reutilizar a mesma competição mesmo se o snapshot ou HEAD mudar depois; para criar uma competição com outras premissas ou protocolos, altere explicitamente a configuração. `arena_results` guarda um resultado imutável por experimento, com IDs das 12 execuções e rankings; seu próprio ID é SHA-256 do conteúdo. Triggers recusam update/delete. Timestamps de criação estão fora dos hashes.

Ao consultar o resultado, o serviço confere o hash do experimento, configurações e protocolos, e o hash de cada resultado referenciado; reconstrói os rankings e compara o payload persistido. Não altera registros existentes silenciosamente. `execute` reexecuta os backtests, confere o resultado calculado contra o registro existente e recusa divergências; `INSERT OR IGNORE` garante idempotência no SQLite. Uma interrupção pode deixar alguns protocolos e backtests persistidos, mas não um ranking parcial; repetir retoma pela execução determinística sem duplicar registros. A API compartilha um limitador com a API de backtest (um processamento por processo). CLI e múltiplos processos não compartilham esse limitador; SQLite e unicidade preservam a consistência, mas operadores devem evitar execuções simultâneas custosas.

`arena_version=cryptolab-arena/1` identifica o algoritmo de comparação e o formato do resultado. Alterações futuras de ordenação, métricas ou serialização da Arena devem introduzir uma nova versão e preservar um leitor/agregador explícito da versão anterior; não reaproveitar esse identificador para alterar resultados existentes. A Arena não integra o fingerprint do motor financeiro.

Protocolos legados podem ser informados explicitamente em `protocol_ids`. A ponte de fingerprint legada documentada em [BACKTESTING.md](BACKTESTING.md) é respeitada, sem reescrever IDs; equivalência de fingerprint entre protocolos não dispensa a verificação de compatibilidade feita pelo `ResearchService.run`. Hashes legados desconhecidos só podem ser reproduzidos no ambiente original. Adicionar a Arena e sua migration não alterou o fingerprint financeiro `e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62` no ambiente auditado.

## CLI e API

O exemplo [arena-example.json](arena-example.json) aponta ao dataset BTCUSDT 1h da Fase 2.1, se disponível, e usa as hipóteses padrão da Fase 2.2. Para outra instalação, altere o hash, ativo, timeframe e limites UTC em segundos. O JSON aceita `backtest`, `strategies` (cada uma com `version` e `parameters`) e opcionalmente `protocol_ids`; consulte os modelos Pydantic ou `/docs`. É necessário snapshot público local com regras de instrumento ao congelar novos protocolos. Nenhum download é disparado.

```powershell
$experimento = .\.venv\Scripts\python.exe -m cryptolab.arena.cli create --config docs/arena-example.json | ConvertFrom-Json
$experimento.id
$resultado = .\.venv\Scripts\python.exe -m cryptolab.arena.cli execute --experiment $experimento.id | ConvertFrom-Json
$resultado.rankings.test.entries | Format-Table strategy,rank,net_return_pct,max_drawdown_pct,closed_trades,insufficient_sample
.\.venv\Scripts\python.exe -m cryptolab.arena.cli result --experiment $experimento.id
.\.venv\Scripts\python.exe -m cryptolab.arena.cli show --experiment $experimento.id
.\.venv\Scripts\python.exe -m cryptolab.arena.cli list
```

API: `POST /api/v1/arena/experiments` cria, `POST /api/v1/arena/execute` recebe `{"experiment_id":"..."}`, `GET /api/v1/arena/experiments` lista até 50, `GET /api/v1/arena/experiments/{id}` consulta e `GET /api/v1/arena/experiments/{id}/result` verifica e retorna resultado. POSTs exigem `X-CryptoLab-Research: 1` e a proteção de origem local existente; Host continua restrito. Não há autenticação remota; não exponha a API na internet. Para usar as novas rotas, reinicie a API existente.

## Demonstração real · 02/11/2026

Dataset BTCUSDT 1h `f3b2e55b1cc373d448efa3676c63064cb482c86be4ebd7442bce573134f972c6`; treino `[04/09,01/10)`, validação `[01/10,16/10)` e teste `[16/10,01/11/2026)` em UTC. Capital 10.000 USDT, taxa 0,1% por fill, slippage 0,05%, risco planejado 1%, exposição máxima 100%, stop 3%, alvo 6% e encerramento por liquidação. Defaults das estratégias e limitações do modelo em [BACKTESTING.md](BACKTESTING.md).

| Teste fora da amostra | Retorno líquido | Drawdown máximo | Trades | Amostra |
| --- | ---: | ---: | ---: | --- |
| Breakout | -0,82% | 1,22% | 3 | insuficiente |
| RSI | -0,97% | 1,29% | 3 | insuficiente |
| Trend | -2,02% | 2,10% | 5 | insuficiente |
| Buy & Hold | -6,11% | 9,70% | 1 | insuficiente |

Experimento `1d8e0f0a7229bd181a4a6900d438ef3998782cc493d378b0307e97712fe6ba65`; resultado `a9dbb88ba11b21a6bf49630e99a33b94850ae194b468dcea810e06918462e92f`. A repetição teve o mesmo hash. Uma segunda competição com os quatro protocolos legados reais preservou seus IDs e concluiu: experimento `79e9e6839712bda6ab91975f681d94096b13b7cb42b2629188fefad45f025976`, resultado `f6bd0a132d5ed81e8a52f76c90f072128b4c0dc2958789a1fec071d09b750d2e`. Essas referências existem no banco local usado no ensaio, não são distribuídas pelo Git. A janela é curta e nenhum resultado valida uma estratégia ou prevê rentabilidade.

## Interface · Fase 2.3B

A página permite configurar janelas, capital, custos, risco e parâmetros individuais, criar e executar o experimento, consultar histórico e inspecionar os parâmetros congelados. A tabela preserva a ordem e os empates fornecidos pelo backend; null aparece como indefinido com motivo. Teste fora da amostra é a janela inicial, sem indicar vencedor validado. Dados e métricas nunca são gerados no navegador.

As quatro curvas são carregadas sequencialmente pelos IDs persistidos via `/api/research/runs/{id}`, usando o proxy local existente. A página confere IDs, janela e timestamps comuns antes de desenhar. O gráfico Lightweight Charts usa float apenas para renderização, exibe tooltip UTC e permite ocultar curvas; valores exatos do bot selecionado estão em tabela paginada. Nenhum ponto é interpolado ou alterado na fonte. As tabelas largas têm rolagem interna no celular.

`/api/arena/[...path]` aceita apenas os cinco recursos documentados, Host local e POST com cabeçalho de pesquisa/origem correspondente. O backend segue acessível apenas pelo servidor Next; 409 e 429 são exibidos, e o processamento síncrono não mostra percentual inventado. Um timeout ou falha de transporte ao executar dispara uma consulta de resultado; caso a API esteja ocupada ou indisponível, a reexecução fica bloqueada até uma consulta manual confirmar resultado persistido ou ausência. Não há POST automático. Essa verificação usa o limitador por processo já existente; CLI e outras instâncias externas não compartilham o limitador, portanto devem ser evitadas durante a recuperação. Para uma UX mais robusta em competições longas, uma fila/worker com estado durável é pendência futura.

## Preparação para 2.3C

A próxima fase deve partir dos contratos e resultados persistidos existentes, definindo seu próprio escopo antes de implementar. Paper contínuo, conta privada, execução real, fila distribuída e validação estatística permanecem fora desta entrega. A interface não altera motor, fingerprint, dados ou proteção de execução real.
