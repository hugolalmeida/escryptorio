# ADR · Avaliação Freqtrade

Pesquisa em 01/11/2026. Decisão: candidato a comparação offline na fase 4; não instalar no ambiente atual nem usá-lo como processo de execução do CryptoLab.

## Evidência

O Freqtrade documenta Bybit Spot como mercado suportado via CCXT. Isso difere do Pybit escolhido para coleta principal. A tabela de recursos informa ausência de stoploss na corretora para Bybit Spot nessa integração; não generalizar essa limitação para toda a API Bybit. [Notas de exchanges](https://www.freqtrade.io/en/stable/exchanges/).

Há manutenção ativa: release **2026.10**, publicada em 30/10/2026, com mudanças no backtesting e infraestrutura. A release removeu suporte ao Python 3.11; a instalação atual exige **Python 3.12+**. O ambiente inspecionado usa **Python 3.10.11**, portanto não é compatível com a versão atual na mesma venv. A documentação recomenda Docker no Windows e também oferece script PowerShell/WSL. [Releases oficiais](https://github.com/freqtrade/freqtrade/releases), [instalação](https://www.freqtrade.io/en/stable/installation/).

O backtesting tem premissas próprias sobre preço de fill, ordem de eventos e taxas. Não se deve comparar resultados sem harmonizar esses pressupostos. [Backtesting oficial](https://www.freqtrade.io/en/stable/backtesting/).

## Integração proposta, ainda não validada por execução

Criar processo isolado Docker ou Python 3.12+ com release e imagem fixadas. Exportar dataset fechado aprovado pelo hash para formato aceito pelo Freqtrade, incluindo timezone e intervalo; nunca pedir que um download novo represente o mesmo dataset. Implementar adaptadores das mesmas regras Trend/RSI/Breakout e baseline; configurar somente Spot, sem leverage, chaves, bots live ou conexão à conta.

Executar apenas CLI offline de backtest e análise de lookahead/recursividade; importar JSON de resultados com manifesto de versão, dataset, parâmetros e custos. Reconciliar trade a trade, warm-up, fee model e liquidação final antes de aceitar equivalência. Manter capital igual e mesmas janelas cronológicas; não usar hyperopt na amostra de teste.

## Trade-off

Favorece: motor conhecido, métricas, ferramentas de análise e referência independente. Custo: outra runtime e CCXT, dependências maiores, semântica de execução própria, adaptação de dados e verificação de equivalência. O motor puro do CryptoLab mantém contratos auditáveis e controle dos invariantes Spot. Os indicadores já implementados não substituem uma avaliação do backtester inteiro. Compatibilidade documental foi confirmada; integração funcional e performance permanecem pendentes de um spike isolado.
