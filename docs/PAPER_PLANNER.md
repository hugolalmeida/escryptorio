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

Sem posição é selecionado `if_flat`; com posição, `if_long`. HOLD não cria intenção de compra ou venda e informa se a exposição já excede o limite. A compra é limitada por saldo incluindo taxa, exposição máxima sobre patrimônio pós-custos marcado ao preço de referência, risco estimado, precisão e limites do instrumento. Não se compra com posição já aberta; uma decisão incompatível de compra sobre limite é recusada. O risco estimado considera stop hipotético, slippage adverso e custos de entrada e saída; arredondamento Decimal usa contexto de 80 dígitos, quantidade para baixo e preço estimado/tick de forma adversa. A venda, mesmo com exposição acima do limite, pode ser planejada para reduzir a posição; ela continua limitada à quantidade existente, sem short. A marcação precisa estar verificada também para venda: excesso de exposição não autoriza ignorar preço obsoleto, saldo, limites ou integridade. Stops e alvos são hipóteses, não ordens ativas; gaps e liquidez podem superar o risco estimado.

Para Buy & Hold, a política futura será uma única entrada ao iniciar sem posição e manutenção enquanto a posição existir, sem stop ou alvo obrigatórios. O orçamento de perda virtual deve assumir perda integral do capital alocado mais custos de entrada, limitado por `risk_fraction` do patrimônio, `exposure_fraction`, saldo, taxas, slippage e limites do instrumento; a disponibilidade futura da saída e sua liquidez não são garantidas. A política depende de definir e persistir o estado de entrada única, inclusive após venda ou reinício, antes de qualquer simulação. Ela ainda não está implementada: uma compra retorna `BUY_HOLD_POLICY_REQUIRED`, sem quantidade, stop ou alvo. A execução permanece desabilitada.

`validation_hash` identifica o conteúdo completo da proposta, incluindo sinal, vínculo, custos, premissas de mercado e hash/sequência do ledger. `decision_key` identifica o par sinal/carteira. A mesma entrada íntegra gera o mesmo resultado; uma alteração no ledger ou mercado gera outro hash ou bloqueio. O tempo pode invalidar uma proposta sem alterar seu hash. O consumidor futuro deverá refazer integralmente essas verificações e não confiar em resultado guardado.

A versão `cryptolab-paper-planner/2` identifica as regras deste contrato, incluindo exposição pós-custos e venda redutora; a versão 1 permanece identificada nos resultados antigos. Qualquer alteração de cálculo, elegibilidade ou semântica deve criar nova versão; resultados anteriores não devem ser reinterpretados sob a versão nova.

**Limitação de unicidade:** esta fase não persiste propostas nem o vínculo fornecido. Portanto, não é possível impedir duravelmente que dois arquivos de vínculo diferentes produzam análises alternativas com a mesma `decision_key`. Nenhuma é executável. A conferência de duas leituras reduz corridas durante a consulta, mas não substitui revalidação atômica no momento de uma futura operação.

## Requisitos para o próximo executor

Antes de qualquer efeito no ledger, uma migration separada deverá criar registros imutáveis, versionados e verificáveis de vínculos, contendo carteira e `wallet_hash`, bot, definição completa e `monitor_config_hash`, parâmetros, fingerprint, política de risco/custos e hash canônico. Cada carteira deve ter no máximo um vínculo ativo; troca de vínculo exige desativação explícita e auditável do anterior, sem reescrever sua história. Chaves estrangeiras, índice único para vínculo ativo e checagens de conteúdo devem impedir duas configurações ativas para o mesmo bot ou carteira. A política de ativação exige especificação e autorização na fase futura.

Um registro de decisão deve vincular a versão do vínculo, carteira, sinal íntegro, configuração, abertura do candle e ação, além de `decision_key`, `validation_hash`, sequência e hash da cabeça do ledger, cotação e limites usados. Uma restrição única por carteira, configuração e candle deve impedir decisões conflitantes, mesmo quando IDs de sinal diferem. Repetição com conteúdo idêntico retorna o registro existente; conteúdo divergente para a mesma chave falha fechado. Alterações ou expiração exigem transição auditável de invalidação e uma política explícita de substituição, nunca reinterpretação silenciosa.

O futuro executor deverá obter posse com controle de concorrência, iniciar `BEGIN IMMEDIATE`, verificar integridade e unicidade, reconstruir a carteira, conferir novamente relógio, origem, preço, risco, sinal e vínculo, e comparar a sequência/hash do ledger. O registro de decisão e eventual evento virtual deverão ser atômicos e idempotentes, com comparação da cabeça e rollback integral em falha; repetir após reinício deve recuperar o mesmo resultado. Nenhuma regra descrita aqui implementa ou autoriza essa escrita. Stops/targets persistentes, gaps e trilha de auditoria exigem projeto próprio, sem reescrever o ledger histórico.

## Marcação futura de posições

Hoje o planejador só lê a marca já existente e a compara ao ticker público fresco; não cria nem atualiza marcações. Na fase futura, um produtor dedicado poderá registrar marcações virtuais a partir de snapshots públicos verificados, identificando ativo, preço, timestamp da fonte, horário de coleta, candle, hash/proveniência e configuração. Deverá validar frescor, relógio, mercado, integridade e sequência temporal, usar idempotência e transação com a cabeça do ledger e nunca transformar uma consulta antiga em uma cotação nova. O formato atual de `MarkRecord` não guarda toda essa proveniência; sua evolução exige um contrato versionado e revisão da compatibilidade, não inferência retroativa. Em falha, pausa, ausência de snapshot ou preço divergente, preservar a última marca sem atualizar seu horário e bloquear novas análises que dependam dela, inclusive vendas. Toda operação futura terá de conferir novamente a marca e a cotação em sua própria transação.

## CLI PowerShell

```powershell
.\.venv\Scripts\python.exe -m cryptolab.paper.cli show --wallet <WALLET_ID>
.\.venv\Scripts\python.exe -m cryptolab.monitor --signals --bot <BOT_ID>
.\.venv\Scripts\python.exe -m cryptolab.paper.planner_cli --wallet <WALLET_ID> --signal <SIGNAL_ID> --binding <CAMINHO_JSON>
```

Substitua os marcadores por IDs e arquivo reais. Erros retornam JSON `BLOCKED` com código sanitizado e saída 1; HOLD e propostas condicionais retornam saída 0. A CLI não oferece criação de ordens, fills, ativação ou registro de propostas.
