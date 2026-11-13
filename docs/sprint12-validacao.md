# Validação da Sprint 12 — Carteira compartilhada

## 1. Ambiente, pré-requisitos e escopo

Execução em **13/11/2026**, partindo do HEAD **db7fee9**, árvore inicialmente limpa. A especificação consultava `82128c8`; o HEAD posterior foi preservado. Não foram encontradas instruções `AGENTS.md` aplicáveis. Foram consultados planejamento, Sprint 12, contratos de risco, reservas, indicadores e catálogo das Sprints 09–11 e o registro da Sprint 11.

Ambiente existente `.venv`, **Python 3.12.14**, biblioteca padrão e `unittest`. A suíte de entrada passou com **170 testes**, em `/tmp/sprint12-baseline.log`; as ajudas principal/executar/comparar e demonstrações manual e SMA com risco retornaram 0, com captura individual em `/tmp/sprint12-entrada.json`. Não houve instalação de dependências, alteração de assets/licenças, acesso a mercado real, negociação, publicação ou commit.

A etapa entrega `SharedConfig`/`Allocation`/`PortfolioLimits`, carregamento estrito, `SharedSession`, API `on_boundary` e `finish`, comando `carteira`, lotes e subcontas comuns, limites, relatórios, duas fixtures, três receitas e testes. Os caminhos anteriores continuam aceitando seus schemas e comandos.

## 2. Decisões e contratos implementados

- `SharedSession` mantém um caixa físico, quantidades por base, contas atribuídas, lotes, ordens e reservas. O ledger schema 7 contém linhas `PHYSICAL` e `ATTRIBUTION`. A atribuição inicial debita UNALLOCATED e credita titulares; não cria capital. `fill_movements` em `portfolio.py` fornece os mesmos bruto/deltas aos ledgers individual e compartilhado; `make_sma_fill`, `effective_price`, indicadores e `EquityGuard` são reutilizados.
- Os indicadores são instâncias por binding; não existe aquecimento com candles excluídos. A estratégia é independente do patrimônio. Uma SELL explícita de lote estrangeiro gera `OWNERSHIP_MISMATCH`; sem lote próprio, `INSUFFICIENT_ASSET`. A quantidade de saída é integral.
- Cada reserva possui proprietário e detentor temporário. BUY reserva USDT uma vez para o compromisso físico/atribuído. A reserva base do lote é compartilhada por stop/alvo; SELL a recebe por transferência, cancelamento restaura o grupo e proteção preempta somente a saída do próprio lote.
- As sete fases seguem a especificação. Os sinais são registrados antes da arbitragem financeira. A prioridade é `(priority, strategy_id, symbol, signal_id)`. Todos os CLOSE e todos os OPEN de cada lote publicam marcas comuns antes das respectivas execuções. OHLC usa STOP_FIRST e BAR_CLOSE_RESOLUTION, com proteção somente a partir do candle seguinte à entrada.
- A fronteira inteira é preparada em cópia isolada. O digest ordena identidades e normaliza escalas decimais de eventos equivalentes. Repetição é inócua; conflito, ordem inválida e falha técnica/aritmética não alteram o estado aceito. DATA_GAP conserva o prefixo CLOSE/sinais, sem consumir qualquer OPEN do lote incompleto. No fim normal, reservas são liberadas; na interrupção são conservadas.
- Dimensionamento usa seis candidatos `Fraction`, mínimo exato e piso por step. A memória conserva candidatos e empates. Revalidação substitui apenas a candidatura/reserva própria, sem redimensionar quantidade, orçamento ou bracket. Os tetos observam custos e patrimônios já atualizados. Excesso de posição existente não provoca venda forçada; curva/relatório registram compromissos, risco e excesso.
- Cada ponto patrimonial reconcilia caixa físico, atribuições, quantidades físicas e lotes, caixa reservado, ledger de ativos e atribuições. Contribuições usam o capital global inicial. A curva inclui marcas, fills, transições de reservas e término, com sequência distinta mesmo no mesmo UTC.
- `HOLD_USDT` e `BUY_HOLD_BASKET` são referências independentes no horizonte aceito. A cesta usa parcela racional 1/N, primeira abertura elegível, custos e filtros; não usa os bloqueios/risco das estratégias. Capital de referência não é somado à carteira.
- O HTML novo usa **SVG estático local**, sem depender de JavaScript. A escolha permite preservar gráficos na impressão e sem JS. Candles/fills/linhas usam lot_id e titular; indicadores usam binding; curvas mostram patrimônio global e parcelas por titular. Apenas a geometria gráfica usa float; finanças permanecem Decimal/Fraction. O eixo das curvas representa a sequência de observações, explicitamente rotulada.

## 3. Memória financeira: esperado e observado

As fixtures têm oito candles fechados de 12:00 a 12:08 UTC em 01/01/2026. BTC fecha em 100000, 90000, 80000, 100000, 120000, 100000, 80000, 80000; ETH é BTC/50. Taxa 0.001, slippage zero. Cada titular recebe 500 USDT.

| Verificação | Esperado | Observado |
| --- | --- | --- |
| Avaliações/sinais no canônico | 16 / 4 | 16 / 4 |
| Fills / lotes encerrados | 4 / 2 | 4 / 2 |
| Entrada/saída | 12:05 a 120000; 12:07 a 80000 | Iguais |
| Quantidade SMA/BTC | 0.000166 BTC | Igual |
| Quantidade EMA/BTC | 0.000084 BTC | Igual |
| Desembolsos SMA/EMA | 19.93992 / 10.09008 USDT | Iguais |
| Recebimentos SMA/EMA | 13.26672 / 6.71328 USDT | Iguais |
| PnL SMA/EMA | −6.67320 / −3.37680 USDT | Iguais |
| Contas finais SMA/EMA | 493.32680 / 496.62320 USDT | Iguais |
| Caixa/patrimônio físico | 989.95 USDT | Igual |
| Taxas e BTC final | 0.05 USDT; 0 BTC | Iguais |
| Retorno global | −1.005% | Igual |
| Contribuições SMA/EMA | −0.66732% / −0.33768% | Iguais |
| Retornos próprios SMA/EMA | −1.33464% / −0.67536% | Iguais |
| BUY_HOLD_BASKET BTC | 0.00999 BTC; caixa 0.001; patrimônio 799.201 USDT | Iguais |

A perda unitária planejada é `120000×1.001 − 60000×0.999 = 60180 USDT/BTC`. O orçamento SMA de 10 USDT resulta em piso 0.000166 BTC. O teto BTC de 30.01 USDT deixa 10.09 para EMA, resultando em 0.000084 BTC. Compromisso planejado total 15.045 USDT. Após a taxa da primeira entrada, o teto é 30.0094022008 USDT: ainda comporta o nocional total de 30 USDT.

No **multipar**, a competição ocorre no teto global de 3.001%. SMA compra 0.000166 BTC; EMA compra 0.00420 ETH a 2400 e vende a 1600. Os mesmos desembolsos/recebimentos, caixa 989.95, taxas 0.05 e código 0 foram observados. A coexistência BTC/ETH vai de 12:05 a 12:07, **120 segundos**, sem somar quantidades de moedas diferentes.

No **limite BTC de 3%**, a segunda BUY é aprovada no fechamento com 0.000084 BTC, mas o teto cai a 29.9994024 USDT depois da taxa da primeira compra. A abertura rejeita integralmente por `EXPOSURE_INSTRUMENT`, libera a reserva e não redimensiona. O SELL EMA posterior é recusado por `INSUFFICIENT_ASSET`. Esperado e observado: dois fills, um lote encerrado, caixa **993.32680 USDT**, taxas **0.03320 USDT**, código **2**.

## 4. Testes de comportamento

A suíte final possui **203 testes**, sendo **33 novos** da Sprint 12. Os testes novos cobrem:

- Valores canônicos/multipar/limite e reconciliação em todos os pontos; contribuições e denominadores próprios; residual UNALLOCATED sem empréstimo; inversão de prioridade.
- Propriedade errada, lote inexistente, saída de apenas um titular, transferência/restauração de reserva SELL, cancelamento BUY sem gasto e repetição idempotente.
- Gap protetivo preemptando apenas a SELL própria; uma venda/taxa por lote; ambos os toques STOP_FIRST; níveis diferentes no mesmo ativo; range do candle de entrada ignorado.
- Seis candidatos exatos, empate de limites, candidato insuficiente com memória preservada, precedência dos tetos carteira/instrumento/estratégia/risco na revalidação e rejeição pós-taxa sem redimensionamento.
- Paridade arquivo/API, permutação de eventos e duplicatas dentro da fronteira, escalas decimais numericamente equivalentes, conflito, evento estrangeiro, OPEN futuro e fronteira fora de ordem sem mutação.
- Falha injetada durante fill, preservando caixa, ledger e contadores dos indicadores; repetição posterior válida.
- OPEN futuro alterado sem mudar decisões/reservas anteriores; lacuna global conservando CLOSE/sinais e reservas; ausência do stream inicial sem publicação parcial de OPEN.
- Listagem tardia sem aquecimento excluído; deslistagem com lotes conservados e reservas base liberadas; idade de marca de ativo detido; preço futuro; carteira sem observações e desempenho nulo; finalização recusada em prefixo ainda aberto.
- Bloqueios global e próprio na igualdade, recuperação, virada UTC, persistência de drawdown e SELL ainda habilitada. Os vetores do componente não representam depósitos no replay; as regressões de EquityGuard também permanecem na suíte anterior.
- API/JSON inválidos, soma de alocações por razão exata, IDs reservados, prioridades booleanas, referências, duplicatas e campos extras; contexto Decimal externo hostil.
- Quinze artefatos, HTML repetível, receita permutada com mesma identidade/eventos e proveniência original diferente; quatro formatos, outra cwd, saída existente e falha de escrita com INCOMPLETE e sem manifesto final.

## 5. Comandos realmente executados

A rodada consolidada está em **`/tmp/replayquant-sprint12-validado`**, com `commands.json` contendo cada comando completo, cwd, código esperado e observado, além de stdout/stderr individuais. O runner auxiliar está em `/tmp/sprint12-validate.py`. Esses caminhos são auxiliares locais; a documentação preserva os resultados e o README fornece receitas reproduzíveis.

| Grupo | Quantidade | Esperado/observado |
| --- | --- | --- |
| Python e ajudas principal, executar, comparar, carteira | 5 | 0 |
| Demonstrações manual/SMA, análise e risco | 4 | 0 |
| Canônico nos quatro formatos | 4 | 0 |
| Multipar nos quatro formatos | 4 | 0 |
| Limite nos quatro formatos | 4 | 2 |
| Repetição canônica HTML com --analise | 1 | 0 |
| Comparar matriz legada Sprint 11 | 1 | 2 |
| Individual ETH/RSI schema 6 | 1 | 0 |
| Cinco exemplos expandidos das Sprints 07, 09 e 10 | 5 | 0 |
| Execução em outra cwd com receita absoluta | 1 | 0 |
| Diretório de saída já existente | 1 | 1 |
| Sem observações elegíveis, quatro formatos | 4 | 2 |
| Suíte completa com unittest discover -s tests -v | 1 | 0, 203 testes |
| node --check: chart.js, equity.js, indicators.js | 3 | 0 |
| git diff --check | 1 | 0 |

A matriz legada retorna 2 pelos casos de ordens rejeitadas/não executadas já documentados na Sprint 11. As receitas antigas conservaram seus resultados financeiros; hashes/IDs de código refletem os módulos atuais. Os cinco exemplos expandidos terminaram sem posição com os caixas anteriores:

| Receita | Caixa final USDT |
| --- | --- |
| Sprint 07 SMA | 1000.90155066834 |
| Sprint 09 equivalente à 07 | 1000.90155066834 |
| Sprint 10 SMA | 1000.42208230 |
| Sprint 10 EMA | 1000.71085163730 |
| Sprint 10 RSI | 1001.93754109984 |

A indisponibilidade foi exercitada com janela em fevereiro e dados em janeiro: zero fills, capital 1000 USDT preservado, estado PORTFOLIO_UNAVAILABLE e desempenho nulo. Os quatro formatos e os quinze arquivos foram emitidos. Saída existente falhou sem sobrescrever o conteúdo anterior. Falha de escrita foi injetada no teste de exportação.

## 6. Reprodução e inspeção visual

`reproduction.json` compara os **15 arquivos por bytes** entre HTML/JSON/Markdown/texto, repetição com --analise e outra cwd. Todas as comparações são iguais. O HTML repetido também é idêntico. A receita permutada preserva run_id, prioridade, quantidades e eventos; recipe_hash registra separadamente os bytes originais. Listas ordenadas canonicamente e caminhos resolvidos não interferem na identidade lógica.

Os relatórios canônico, multipar e limite foram inspecionados em Chrome headless, desktop **1400×1000**, tela estreita **390×900**, mídia print e contexto com **JavaScript desativado**. Não ocorreram exceções JavaScript nem requisições HTTP externas. A largura da página coincide com o viewport; tabelas extensas possuem rolagem interna. Gráficos SVG e tabelas permanecem sem JavaScript, com títulos/unidades e vínculos por titular/lote. Foram observadas as capturas desktop/mobile/print, e gerados PDFs de mídia print; não houve impressão física.

O primeiro uso do Node do sistema (18.19.1) foi incompatível com o Playwright disponível. A inspeção utilizou o Node **24.22.1** do runtime já instalado e Chrome local. O sandbox bloqueou um socket interno do Chrome (`setsockopt`); a execução local com permissão de ferramenta concluiu a inspeção. Não foi instalado navegador ou pacote. As verificações `node --check` usam o Node do sistema e passaram.

Evidências: `visual.json`, `*-desktop.png`, `*-mobile.png`, `*-print.png` e `*-print.pdf` no diretório consolidado. SVG estático evita dependência de JS e mantém a alternativa offline; números geométricos não são usados no ledger ou nas decisões.

## 7. Limites e pendências

Concluídos os exemplos, contratos e verificações obrigatórias desta etapa. A suíte foi executada somente no Python 3.12.14 deste ambiente; não há matriz adicional de versões/sistemas nem ensaio de escala. O coordenador prepara snapshots completos sequencialmente e não foi otimizado. Os métodos de fases são internos; a fronteira pública de mutação é on_boundary/finish, com requests tipados opcionais. A deduplicação não promete recuperação após reinício.

Permanecem as hipóteses declaradas: fonte fictícia, USDT como cotação sem identidade presumida com USD, liquidez ilimitada, ausência de latência positiva, stop/alvo OHLC com STOP_FIRST, marcação BOUNDARY_MARKS_V1 e KEEP_OPEN. Gaps/slippage podem superar o risco planejado. Exposição conjunta não comprova hedge, correlação ou rentabilidade. A entrega não inclui voto/consenso, dados reais, banco, margem, parciais, novas estratégias/frequências, otimização ou paralelismo.

Os artefatos temporários podem ser removidos pelo sistema. Nenhum resultado foi inventado para obter lucro; o resultado negativo canônico é o esperado para verificar correção.

## 8. Arquivos alterados

| Grupo | Arquivos |
| --- | --- |
| Configuração, coordenação e apresentação | `replayquant/shared_config.py`, `replayquant/shared_engine.py`, `replayquant/shared_reporting.py`, `replayquant/__main__.py` |
| Aritmética financeira compartilhada | `replayquant/portfolio.py`, `replayquant/ledger.py` |
| Fixtures | `data/fixtures/sprint12-btc-candles.json`, `data/fixtures/sprint12-eth-candles.json` |
| Receitas | `experiments/sprint12-compartilhada.json`, `experiments/sprint12-multipar.json`, `experiments/sprint12-limite.json` |
| Testes | `tests/test_sprint12.py` |
| Documentação | `README.md`, `docs/planejamento.md`, `docs/sprint12.md`, `docs/sprint12-glossario.md`, `docs/sprint12-validacao.md` |
