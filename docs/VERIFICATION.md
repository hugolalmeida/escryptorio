# Evidências de verificação

Data: 01/11/2026. Ambiente Windows, Node v22.13.0, npm 11.0.0 e Python 3.10.11. Versões exatas de dependências em `package-lock.json` e `backend/requirements.lock.txt`.

## Resultado final

| Verificação | Resultado |
| --- | --- |
| `npm run build` | Passou: Next.js 16.4.3, compilação e checagem TypeScript. |
| `npm run typecheck` | Passou. |
| `python -m pytest backend/tests -q` na venv | **28 passaram**. |
| `python -m pip check` na venv | Sem dependências quebradas. |
| `CRYPTOLAB_LIVE_SMOKE=1 npm run test:ui` | **21 passaram**, Chromium, 1440×1000, 820×1180 e 390×844. |
| `python -m cryptolab.worker --once` na venv | Oito snapshots reais coletados e persistidos, saída 0. |
| `scripts/dev.ps1 -SkipInstall` | API, worker e Next iniciaram; dashboard e proxy HTTP 200, ETHUSDT real e `stale=false`. |
| Encerramento de `dev.ps1` | Ctrl+C; portas 8000 e 3100 sem listeners após encerramento. |

O serviço real foi verificado em toda a cadeia Bybit → worker → SQLite → FastAPI → Next → canvas. Os smoke tests verificaram BTCUSDT e ETHUSDT em todos os quatro intervalos, preço positivo, mercado Spot, 300 candles, histórico fechado, timestamps frescos e `live_trading_enabled=false`. Não foram enviadas ordens ou usadas credenciais privadas.

O Playwright MCP não está disponível na sessão. Foi usado o runner oficial Playwright com Chromium local; nenhuma inspeção é atribuída a MCP. As capturas finais de dados reais foram abertas e inspecionadas visualmente:

- [Desktop](../artifacts/dashboard-desktop.png)
- [Tablet](../artifacts/dashboard-tablet.png)
- [Celular](../artifacts/dashboard-mobile.png)

As capturas e o relatório HTML em `playwright-report/index.html` são artefatos locais ignorados pelo Git, gerados novamente no smoke real. A revisão visual confirmou composição, legibilidade, gráfico, estado de coleta e navegação. Textos auxiliares foram ampliados após a primeira inspeção.

## Cobertura relevante

Python: SMA/EMA de referência; RSI Wilder de referência; ATR com gap; warm-up; série constante; extremos; contexto Decimal independente; invariância de prefixo; candle aberto excluído; ordenação e gaps; OHLC inválido e não finitos; hash por conteúdo e dataset somente fechado; migrations idempotentes; precisão na persistência; freshness e relógio futuro; validação de símbolo/período/Host; ausência de rotas de ordem; recusa de flag live; falhas/rate limit/resposta de mercado errado; retenção de snapshot após erro; cliente sem credenciais e somente categoria Spot.

Playwright: seis cenários independentes com fixtures sintéticas de teste, repetidos em três tamanhos, mais um smoke real por tamanho. Exercita troca de ativo e período, linha/candles, médias, atualizar, erro inicial, snapshot antigo, falha após sucesso sem alterar horário original, navegação, bloqueio de execução, link de pular conteúdo e Escape no menu móvel. Sem erros JavaScript e sem overflow horizontal da página nos cenários de mercado e erro. A tabela tem rolagem interna intencional.

Na primeira execução, a porta 3000 já pertencia a outro projeto. A configuração foi corrigida para 3100, com servidor exclusivo nos testes e preflight de portas no script. Um controle somente com ícone perdeu o nome no celular e recebeu `aria-label`; o seletor de alertas foi restringido para não confundir o anúncio de rotas do Next. As verificações finais passaram após essas correções.

## Limites da evidência

Há um aviso de depreciação do Starlette ao usar TestClient com httpx 0.28.1; os testes passam, mas a migração do cliente de teste deve ser avaliada na próxima atualização de dependências. Não foi suprimido.

Não foram validados backtests, métricas da Arena, operações paper ou conta privada, porque esses módulos ainda não foram implementados. Freqtrade teve compatibilidade e manutenção avaliadas documentalmente, sem instalação ou integração funcional. Não há teste de execução real, nem capacidade de executá-la. Acesso público à API não comprova elegibilidade de conta.

Os processos de teste foram encerrados. Para usar a aplicação, iniciar pelo README. As exclusões legadas preexistentes foram preservadas; nenhuma alteração foi commitada ou publicada.
