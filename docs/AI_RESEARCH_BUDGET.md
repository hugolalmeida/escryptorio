# Orçamento simulado · 2.3D3A

## Política implementada

`BudgetPolicy` é configuração imutável do supervisor. `BudgetSession` mantém reservas efêmeras protegidas por lock. O worker recebe somente o envelope de entrada e declara uso que o gateway reconcilia. O supervisor decide a reserva e mede bytes de saída.

| Limite padrão | Valor |
| --- | --- |
| Entrada do worker | 65.536 bytes |
| Contexto | 32.768 bytes |
| stdout e stderr | 65.536 bytes por stream |
| Chamadas por sessão | 4 |
| Tentativas por request_id | 1 |
| Concorrência por sessão | 1 |
| Tempo por processo | 5.000 ms |
| Estimativa de entrada por tentativa | 16.384 tokens simulados |
| Reserva estimada de saída por tentativa | 16.384 tokens simulados |
| Reserva acumulada de sessão | 131.072 unidades simuladas |

O teto configurável de entrada/saída é 65.536 bytes por stream e o timeout pode ir até 60.000 ms. Configurações exigem inteiros estritos entre zero e 2^31−1, com tetos adicionais de transporte/tempo. NaN, Infinity, negativos, bool e overflow são rejeitados. Valores zero esgotam a capacidade correspondente antes da execução, salvo saída zero, que permite apenas transporte vazio e será recusada pelo gateway.

## Estimativa e contabilidade

A heurística é `ceil(bytes_UTF8/4)` e serve somente à simulação local. O valor depende do tamanho serializado e inclui o envelope. Tokenizadores de provedores podem produzir contagens diferentes, especialmente em Unicode. Nenhum preço real, moeda, tokenizador externo ou cobrança é utilizado.

A reserva por tentativa soma estimativa de entrada e teto estimado de saída. O total deve caber nas unidades simuladas da sessão. Reservas permanecem consumidas em falha, cancelamento ou resposta inválida. Isso permite um limite conservador sem autorizar retries por devolução automática de reserva. Novos IDs continuam sujeitos ao teto total de chamadas e custo da sessão. A sessão vive somente no processo atual. Reiniciar o processo cria uma sessão nova.

Uma tentativa aprovada registra APPROVED, entrada, bytes efetivamente lidos de stdout e estimativas. Falhas registram FAILED e cancelamentos CANCELLED. Excesso de reserva retorna BUDGET_EXHAUSTED antes de criar subprocesso. Bytes de stdout observados antes de falha parcial são preservados na contabilidade, incluindo o chunk que identificou o excesso. stderr é drenado com seu próprio limite e descartado. Conteúdo bruto de falha permanece fora dos logs. Reservas rejeitadas preservam o contador de chamadas.

## Limites operacionais

O supervisor captura stdout/stderr em leitores concorrentes, aplica cotas durante a leitura e interrompe o filho direto por excesso, timeout ou cancelamento. stdin usa escrita separada para evitar bloqueio do supervisor. O comando é fixo, com shell desabilitado, Python `-I -S` e fixture stdlib copiada para diretório temporário. A API pública não aceita comando ou módulo fornecido pelo contexto.

O deadline abrange lançamento e I/O do processo. Preparação/verificação do bundle ocorre no processo confiável antes dele. Agendamento do Windows e coleta de processo encerrado podem acrescentar latência. Não há deadline rígido de tempo real. O cancelamento é observado a cada ciclo de até 10 ms e novamente antes de devolver resultado validado. O `finally` encerra e aguarda o filho direto e fecha streams.

Limites de memória, CPU, disco temporário e árvore de descendentes permanecem DEFERRED. O número de mocks ativos é limitado por BudgetSession, e sessões independentes não compartilham um limite global. O mock fixo não cria filhos. Encerramento abrupto do supervisor e sobrevivência de descendentes permanecem NOT_VERIFIED. O diretório temporário e o ambiente mínimo reduzem transporte de dados, com permissões herdadas do usuário.

## Testes

Fixtures sintéticas exercitam limite de entrada, saída stdout/stderr, chamadas, tentativas, orçamento zerado/insuficiente, custo acumulado, política inválida, concorrência de reservas, timeout, cancelamento ativo/prévio, uso declarado divergente e falha parcial. Resultados executados estão em [VERIFICATION.md](VERIFICATION.md). A simulação fica separada do ledger financeiro por módulos, objetos e ausência de persistência.
