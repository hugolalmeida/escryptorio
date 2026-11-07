# Planejador virtual · Fase 2.3C2B1

O planejador consulta SQLite com `mode=ro` e `query_only`, em duas transações de leitura independentes. Reconstrói a cadeia da carteira e confere sinal e mercado em cada leitura; se o resultado mudar, devolve `STATE_CHANGED_RETRY`. Não executa SQL de escrita, migrations, rede, ordem ou fill e não ativa carteira. Cada resultado é uma hipótese com `execution_enabled=false` e `needs_revalidation=true`, não uma autorização. `LIVE_TRADING_ENABLED` deve ser `false` na CLI.

## Vínculo explícito

O ledger atual identifica bot, estratégia e versão, ativo e timeframe, mas **não registra parâmetros da estratégia, hash do motor, versão do monitor ou política de risco**. Por isso o operador deve fornecer um arquivo JSON local com `wallet_id`, `wallet_hash` e `monitor_config_hash`, além da política de risco. O hash da carteira é verificado na reconstrução integral do ledger; o hash da configuração vincula toda a definição do monitor, inclusive parâmetros, versão e fingerprints. Também são comparados bot, estratégia, versão, ativo e timeframe. Configuração concorrente ativa ou outro resultado do mesmo bot no mesmo candle bloqueia a análise.

Exemplo de formato, com marcadores que devem ser substituídos por valores reais escolhidos pelo operador:

```json
{
  "schema_version": 1,
  "wallet_id": "<ID_DA_CARTEIRA>",
  "wallet_hash": "<SHA256_DA_CARTEIRA>",
  "monitor_config_hash": "<SHA256_DA_CONFIGURACAO_DO_SINAL>",
  "risk": {
    "risk_fraction": "<FRACAO_DE_RISCO_VIRTUAL>",
    "exposure_fraction": "<FRACAO_MAXIMA_DE_EXPOSICAO>",
    "costs": {"fee_rate": "<TAXA_VIRTUAL>", "slippage_rate": "<SLIPPAGE_VIRTUAL>"}
  }
}
```

Custos são hipóteses explicitamente fornecidas, não taxas da conta Bybit. Use strings decimais; floats são recusados. Consulte `paper.cli show` para `wallet_hash` e `monitor --signals` para `config_hash` e ID do sinal. A carteira nasce pausada e o planejador retorna `WALLET_PAUSED` sem ativá-la. Conserve o arquivo escolhido em local protegido e revise seu conteúdo antes de uso; ele não é assinatura nem credencial.

## Validações

São aceitos exclusivamente sinais schema 2, `current`, elegíveis para futura análise, informativos e sem posição verificada. O planejador verifica SHA e índices, definição e fingerprint atuais do monitor e motor, checkpoint, tempos, expiração e snapshot público fresco e íntegro. Recalcula as condições do sinal com a mesma estratégia e candles fechados verificados. Sinais schema 1 ou históricos recuperados são recusados. O ledger inteiro é reproduzido e seu hash, sequência e checkpoint verificados na mesma transação que o sinal e o mercado. Para posições, a marcação precisa ser recente e coincidir com a cotação pública; uma marcação isolada do ledger não é prova de preço de mercado.

As regras públicas do instrumento e o ticker têm timestamps próprios e também devem estar frescos. Símbolo, status, precisão, tick, mínimo nocional e máximo de quantidade de mercado são validados. A quantidade mínima positiva é derivada matematicamente de `basePrecision`; não é apresentada como mínimo de negociação. A Bybit informa que `minOrderQty` Spot é obsoleto e orienta conferir `minOrderAmt`: [instrumentos Bybit](https://bybit-exchange.github.io/docs/v5/market/instrument). Taxas são somente premissas virtuais, e regras de conta ou elegibilidade não são inferidas.

## Causalidade e risco

`decision_candle` é a abertura de t; `earliest_fill_candle` é a abertura de t+1. Nenhum fill é criado. Sem candle t+1 aberto e ticker posterior ao fechamento de t, o resultado é `AWAITING_NEXT_OPEN`, sem quantidade ou preço de execução. Após t+1, uma cotação pública fresca pode servir apenas como referência para estimativa condicional em instante posterior; a abertura histórica de t+1 nunca é usada para fingir execução retroativa. O sinal expira em `valid_until` e deve ser recusado a partir desse instante.

Sem posição é selecionado `if_flat`; com posição, `if_long`. HOLD não cria intenção de compra ou venda. A compra é limitada por saldo incluindo taxa, exposição máxima, risco estimado, precisão e limites do instrumento. O risco estimado considera stop hipotético, slippage adverso e custos de entrada e saída; arredondamento Decimal usa contexto de 80 dígitos, quantidade para baixo e preço estimado/tick de forma adversa. A venda é limitada à quantidade existente, sem short. Stops e alvos calculados são hipóteses de planejamento, não ordens ativas; gaps e liquidez podem superar o risco estimado. Buy & Hold não define stop no contrato do monitor e retorna `RISK_STOP_UNAVAILABLE` para compra até existir política própria explícita. Faltas de dados, saldo, limites ou frescor bloqueiam a análise.

`validation_hash` identifica o conteúdo completo da proposta, incluindo sinal, vínculo, custos, premissas de mercado e hash/sequência do ledger. `decision_key` identifica o par sinal/carteira. A mesma entrada íntegra gera o mesmo resultado; uma alteração no ledger ou mercado gera outro hash ou bloqueio. O tempo pode invalidar uma proposta sem alterar seu hash. O consumidor futuro deverá refazer integralmente essas verificações e não confiar em resultado guardado.

A versão `cryptolab-paper-planner/1` identifica as regras deste contrato. Qualquer alteração de cálculo, elegibilidade ou semântica deve criar nova versão; resultados anteriores não devem ser reinterpretados sob a versão nova.

**Limitação de unicidade:** esta fase não persiste propostas nem o vínculo fornecido. Portanto, não é possível impedir duravelmente que dois arquivos de vínculo diferentes produzam análises alternativas com a mesma `decision_key`. Nenhuma é executável. A fase 2.3C2B2 deve introduzir registro imutável e único de vínculo e decisão, com transação e controle de concorrência, antes de permitir qualquer efeito no ledger. A conferência de duas leituras reduz corridas durante a consulta, mas não substitui revalidação atômica no momento de uma futura operação. Também será necessário projetar stops/targets persistentes, execução virtual, gaps e auditoria sem modificar a cadeia atual retrospectivamente.

## CLI PowerShell

```powershell
.\.venv\Scripts\python.exe -m cryptolab.paper.cli show --wallet <WALLET_ID>
.\.venv\Scripts\python.exe -m cryptolab.monitor --signals --bot <BOT_ID>
.\.venv\Scripts\python.exe -m cryptolab.paper.planner_cli --wallet <WALLET_ID> --signal <SIGNAL_ID> --binding <CAMINHO_JSON>
```

Substitua os marcadores por IDs e arquivo reais. Erros retornam JSON `BLOCKED` com código sanitizado e saída 1; HOLD e propostas condicionais retornam saída 0. A CLI não oferece criação de ordens, fills, ativação ou registro de propostas.
