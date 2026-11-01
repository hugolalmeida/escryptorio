# Design system · CryptoLab

Direção: mesa de pesquisa privada, com o gráfico como ferramenta central. Modo de uso operacional, sem linguagem de campanha, imagens decorativas ou promessa de rentabilidade. Nome do produto, escopo Spot e estado da coleta precisam ser identificáveis imediatamente.

## Avaliação das referências em 01/11/2026

| Referência | Avaliação | Aplicação nesta entrega |
| --- | --- | --- |
| [Emil Kowalski / skills](https://github.com/emilkowalski/skills), [skill de design engineering](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md) | Forte em feedback, duração e finalidade de animações. | Transições de cor/pressão curtas; sem animação das cotações ou entrada de cada painel; respeitar reduced motion. |
| [Impeccable](https://github.com/pbakaus/impeccable), [skill](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/SKILL.md), [craft floor](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/reference/craft-floor.md) | Útil para semântica, hierarquia, estados de erro, contraste e refinamento de ferramentas. | Componentes consistentes, foco visível, copy que informa recuperação, vazio sem números fictícios e revisão da renderização. |
| [Taste Skill](https://github.com/Leonxlnx/taste-skill), [skill](https://github.com/Leonxlnx/taste-skill/blob/main/skills/taste-skill/SKILL.md), [app screens](https://github.com/Leonxlnx/taste-skill/blob/main/skills/taste-skill/references/app-screens.md) | A orientação para apps distingue uma tela de trabalho de uma landing page; prioriza dados e navegação discreta. | Painéis planos, números tabulares, cores com função e composição densa, navegação recolhida no celular. |

As referências foram lidas e avaliadas como material de design. Não foram instaladas como skills, executadas suas ferramentas, copiados layouts nem alterados hooks do ambiente. A orientação local-only de Sites foi consultada; não houve cadastro ou publicação.

## Tokens e componentes

| Papel | Token |
| --- | --- |
| Fundo | `#0c131d` |
| Painel | `#101924` |
| Superfície selecionada | `#121e2d` |
| Texto principal | `#e5ebf3` |
| Texto secundário | `#9aaabd` |
| Borda | `#253244` |
| Ação/foco | `#8bb9fb` |
| Alta | `#61d5af` |
| Baixa | `#f29399` |
| Atenção | `#e8bf7d` |

Segoe UI local do Windows, sem dependência de fontes remotas. Fonte de dado `Consolas` apenas para hash. Números com `tabular-nums`. Corpo 14px; título 26px; painéis 14px; rótulos densos têm escala reduzida, com revisão visual em três larguras. Botão shadcn/ui editável usa Slot/CVA, estados disabled, foco e pressão; configuração `components.json` preparada para ampliar a biblioteca. Ícones Lucide, sem emoji como controles. Sidebar 208px; separação por bordas suaves; raio 8px; sem sombra decorativa ou gradientes.

## Composição e comportamento

Dashboard: dois ativos selecionáveis, gráfico e controles, leitura técnica, resumo 24h, status das estratégias e proveniência. O retorno ainda não calculado aparece como travessão; nada sugere rentabilidade medida. A seção técnica explicita que não gera sinal de entrada.

Desktop 1440px: gráfico dominante à esquerda e resumo de 263px à direita. Tablet 820px: gráfico em largura inteira da área útil e painéis técnicos em duas colunas. Celular 390px: navegação com botão, painéis em uma coluna, tabela com rolagem interna; sem overflow da página. Botões informam seleção por `aria-pressed`. Link para pular navegação e foco visível. Menu fecha por botão, navegação ou clique no fundo. Gráfico tem descrição acessível e resumo numérico visível.

O gráfico interativo permite zoom/pan, linha/candles e alternar médias. Atualizações de dados preservam zoom. Alterar ativo/período reinicializa a janela. TradingView recebe atribuição no gráfico e link abaixo, conforme [licença/documentação](https://tradingview.github.io/lightweight-charts/docs).

Carregamento, erro inicial, atualização interrompida, snapshot antigo e relógio adiantado têm estados distintos. O servidor nunca fornece fallback sintético. Horários de leitura em Brasília; eixo em UTC com indicação visível e tooltip UTC. Estado de segurança sempre legível e sem botão de ativação.

## Próximos refinamentos

Ao implementar Arena e paper, preservar cores e densidade, testar nomes longos e retornos extremos. Adicionar alternativa tabular acessível completa ao gráfico caso pesquisa exija inspeção detalhada sem canvas. Validar com leitor de tela antes de ampliar público. A entrega atual foi verificada por teclado, semântica e navegador; não certifica conformidade WCAG integral.
