# Sprint 09 — Registro de validação

Validação executada em **09/11/2026**, na raiz do ReplayQuant, com **Python 3.12.14**, ambiente `.venv`, biblioteca padrão e `unittest`. Não foram instalados pacotes, atualizadas bibliotecas, usados dados reais ou enviados pedidos a exchanges.

## 1. Estado e cobertura da entrega

A suíte de entrada passou com **100 testes**. A suíte final passou com **136 testes**: os 100 anteriores e 36 novos da Sprint 09, com subcasos adicionais. Implementados schema 4 manual/SMA, dimensionamento, reservas, cancelamento, bloqueios, stop/alvo, análise e onze artefatos. Não há pendências conhecidas nos requisitos obrigatórios desta sprint.

Os contratos de entrada/saída anteriores foram preservados. Mudanças no código alteram seus hashes e os IDs derivados; não se afirma igualdade com IDs de versões anteriores. A especificação permanece em [sprint09.md](sprint09.md), uso no [README](../README.md) e conceitos no [glossário](sprint09-glossario.md).

## 2. Comandos realmente executados

`source .venv/bin/activate` foi executado antes dos roteiros. A versão observada foi Python 3.12.14. Cada comando/cmp do roteiro final teve código capturado individualmente, sem inferir sucesso pelo último comando. O esperado da demonstração SMA foi fixado antes da verificação final: **2**, por BELOW_MINIMUMS seguido de INSUFFICIENT_ASSET, sem fills.

| Comando | Esperado | Observado |
| --- | --- | --- |
| `python --version` | 0 | 0 |
| `python -m replayquant --help` | 0 | 0 |
| `python -m replayquant demonstrar --help` | 0 | 0 |
| `python -m replayquant demonstrar --formato json` | 0 | 0 |
| `python -m replayquant demonstrar --estrategia sma --analise --formato json` | 0 | 0 |
| `python -m replayquant demonstrar --risco --formato texto` | 0 | 0 |
| `python -m replayquant demonstrar --risco --formato json` | 0 | 0 |
| `python -m replayquant demonstrar --risco --formato markdown` | 0 | 0 |
| `python -m replayquant demonstrar --risco --formato html` | 0 | 0 |
| `python -m replayquant demonstrar --risco --estrategia sma --formato json` | 2 | 2 |
| `python -m replayquant demonstrar --risco --estrategia sma --formato html` | 2 | 2 |
| `python -m replayquant executar --dados data/fixtures/sprint09-candles.json --config experiments/sprint09-manual.json --saida $validacao_sprint09_dir/a --formato json` | 0 | 0 |
| `python -m replayquant executar --dados data/fixtures/sprint09-candles.json --config experiments/sprint09-manual.json --saida $validacao_sprint09_dir/b --formato json` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/manifest.json $validacao_sprint09_dir/b/manifest.json` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/events.jsonl $validacao_sprint09_dir/b/events.jsonl` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/report.json $validacao_sprint09_dir/b/report.json` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/ledger.jsonl $validacao_sprint09_dir/b/ledger.jsonl` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/equity.csv $validacao_sprint09_dir/b/equity.csv` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/trades.csv $validacao_sprint09_dir/b/trades.csv` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/metrics.csv $validacao_sprint09_dir/b/metrics.csv` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/benchmarks.csv $validacao_sprint09_dir/b/benchmarks.csv` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/report.md $validacao_sprint09_dir/b/report.md` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/risk.jsonl $validacao_sprint09_dir/b/risk.jsonl` | 0 | 0 |
| `cmp $validacao_sprint09_dir/a/reservations.jsonl $validacao_sprint09_dir/b/reservations.jsonl` | 0 | 0 |
| `python -m replayquant executar --dados data/fixtures/sprint09-candles-gap.json --config experiments/sprint09-manual.json --saida $validacao_sprint09_dir/gap --formato json` | 0 | 0 |
| `python -m replayquant executar --dados data/fixtures/sprint09-candles-alvo.json --config experiments/sprint09-manual.json --saida $validacao_sprint09_dir/alvo --formato json` | 0 | 0 |
| `python -m replayquant executar --dados data/fixtures/sprint09-candles-ambiguo.json --config experiments/sprint09-manual.json --saida $validacao_sprint09_dir/ambiguo --formato json` | 0 | 0 |
| `python -m unittest discover -s tests -v` | 0 | 0 |
| `git diff --check` | 0 | 0 |

`$validacao_sprint09_dir` abrevia **`/tmp/replayquant-sprint09-final-w6okjpks`**. Seu `commands.json` registra argumentos, stdout, stderr e códigos completos. Os relatórios HTML ficaram em `manual.html` e `sma.html`, fora dos diretórios de artefatos. Arquivos em `/tmp` são auxiliares e podem ser removidos pelo sistema; as conclusões observadas ficam neste documento.

`node --check replayquant/assets/chart.js` também retornou **0**. A sintaxe do controlador local modificado foi conferida sem instalar dependências.

## 3. Esperado e observado nos exemplos financeiros

| Exemplo | Quantidade BTC | Caixa final USDT: esperado = observado | Realizado USDT: esperado = observado | Taxas USDT: esperado = observado |
| --- | --- | --- | --- | --- |
| Stop a 90 | 0.981 | 990.00361 | -9.99639 | 0.18639 |
| Gap a 80 | 0.981 | 980.20342 | -19.79658 | 0.17658 |
| Alvo a 120 | 0.981 | 1019.40418 | 19.40418 | 0.21582 |
| Ambos os toques, STOP_FIRST | 0.981 | 990.00361 | -9.99639 | 0.18639 |

Todos os exemplos encerraram BTC em zero. R=10 USDT, E=100, S=90, T=120 e L=10.19 USDT/BTC. O candidato de risco preserva razão **1000/1019 BTC**, o piso em step 0.001 produz 981 incrementos e q=0.981. Reserva inicial **98.1981 USDT**, caixa total ainda 1000. Após compra: caixa 901.8019, posição e reserva compartilhada 0.981 BTC, taxa 0.0981. No fechamento seguinte antes do stop: patrimônio **1001.8639 USDT**. O stop recebe 88.20171 e a posição é zerada uma única vez.

A perda de gap excedeu o orçamento em 9.79658 USDT; ela foi mantida integralmente na contabilidade. A taxa não foi debitada novamente nem a perda foi limitada artificialmente. Ambos os toques reproduziram o stop com ambiguidade explícita. Comparações financeiras usaram Decimal exato, sem tolerância baseada em float. Zeros finais preservados em JSON não representam divergência numérica.

### SMA canônico e lote variável

Com o schema 4 e os filtros canônicos, SMA produziu oito avaliações e dois sinais iguais aos da fixture existente. A candidata BUY ficou abaixo de 0.001 BTC e a SELL posterior não encontrou ativo: código 2, caixa 1000, BTC e taxas zero. A ausência de trades não inventou taxa de acerto ou expectativa.

Um teste com step/mínimo 0.000001 BTC percorreu compra/venda SMA: q=0.000962 BTC, caixa **999.8076 USDT**, taxas **0.1924 USDT**. Outro teste manual percorreu dois lotes de tamanhos distintos, q=0.981 e q=0.485, sem reaplicar a quantidade antiga: quatro fills, caixa **989.80961**, taxas **0.38039**, BTC zero e ledger reconciliado. Esses testes usam o mesmo núcleo de sessão/ledger.

## 4. Evidências dos contratos

| Grupo | Resultado observado |
| --- | --- |
| Dimensionamento | Candidatos/razões, floor por step 0.000003, empate de três limitadores, igualdade com mínimos e rejeição sem aumento conferidos. O exemplo BTC E=100000/S=98000 produziu q=0.004549, desembolso 455.3549 e perda 9.998702. |
| Revalidação | Abrir a 101 manteve S=90/R=10 e rejeitou perda planejada 10.978371, liberando toda a reserva sem taxa. Abrir a 99 devolveu diferença de caixa, preservou q/S e produziu caixa final 990.985591. |
| Reservas | Reconstrução independente de quatro contas por deltas, propriedade e histórico em cada prefixo; reserva acima do total recusada sem mutação. Transferências não mudaram patrimônio. |
| Cancelamento | BUY seguido de CANCEL liberou 98.1981 uma vez; nenhum fill/taxa. CANCEL de SELL devolveu a titularidade à proteção. Concorrente não gastou nem liberou a primeira reserva. |
| Bloqueios | Igualdade, recuperação, virada UTC, drawdown persistente, patrimônio zero, base ausente/parcial e eventos distintos no mesmo timestamp conferidos por razões exatas. SELL/proteção continuaram habilitados. |
| Proteções | Candle de entrada ignorado, gap com open, range com S/T, ambiguidade STOP_FIRST e horário modelado no close conferidos. Venda comum venceu o range quando não havia gap; com gap foi preemptada e ocorreu uma única venda/taxa. |
| Causalidade | OHLC futuro não alterou o prefixo de aceitação/reserva/fill anterior. API incremental e arquivo produziram os mesmos eventos/relatórios. Novo BUY no candle da saída foi recusado. |
| Fim/interrupção | Término normal liberou pendência/grupo sem liquidar posição. Lacuna SMA preservou reserva BUY e também posição/reserva BTC já aberta em outro caso; referências pararam no mesmo prefixo. |
| Validação/API | Schemas/campos/tipos, dados não finitos, preço ausente/antigo/futuro, faixa de parâmetros e origem de sessão conferidos. Offset externo foi normalizado para UTC também em sinal incremental. |
| Atomicidade | Falhas injetadas de preparação e uma inexatidão financeira real não deixaram ordem, reserva, fill ou histórico parcialmente atualizado. Contexto externo com precisão 2/trap/flag de Inexact permaneceu inalterado. |
| Idempotência | Repetir ação/candle/fill/reserva não repetiu efeitos; conflitos falharam sem mutação. Alterar snapshot retornado não alterou o ledger aceito; histórico adulterado foi recusado na reconciliação. |
| Benchmarks | Mesmo capital/horizonte/custos, filtros fictícios aplicados ao passivo, sem risco/stops da estratégia. Na fixture principal BUY_HOLD_BTC comprou 9.99 BTC e conservou resíduo 0.001 USDT. Carteiras continuam isoladas. |
| Exportações | Onze arquivos válidos, versões 4, colunas CSV fixas, --analise redundante sem mudar identidade e cmp de todos os arquivos com igualdade byte a byte. Saída existente recusada; falha de escrita manteve INCOMPLETE. |

## 5. Conferência visual

Os relatórios manual e SMA foram abertos no Chrome headless pelo protocolo DevTools, com assets incorporados e **zero exceções JavaScript/zero requisições HTTP externas** no relatório. Desktop 1400×1000, tela estreita 390×900 e mídia de impressão foram capturados e inspecionados. Os quatro gráficos indicaram estado pronto, e as quatro imagens de impressão receberam conteúdo.

Foi corrigido um problema de largura causado por textos longos: na tela estreita, `innerWidth`, `clientWidth` e `scrollWidth` ficaram em **390 px**. Tabelas de risco largas usam rolagem horizontal para preservar números/datas/IDs; texto externo quebra sem ampliar a página. Capturas de impressão mostraram gráficos legíveis e resumo sem controles de navegação.

Exemplos de capturas auxiliares: `/tmp/replayquant-sprint09-desktop-risco.png`, `replayquant-sprint09-estreito.png`, `replayquant-sprint09-estreito-risco.png`, `replayquant-sprint09-impressao.png` e equivalentes `replayquant-sprint09-sma-*.png`, todos em `/tmp`. Registros das inspeções: `/tmp/replayquant-sprint09-visual-manual.json` e `/tmp/replayquant-sprint09-visual-sma.json`.

A primeira tentativa de iniciar Chrome no sandbox foi bloqueada por um socket interno (`setsockopt: Operação não permitida`). A execução local com a permissão de ferramenta necessária concluiu a inspeção. A inspeção de impressão foi de CSS/capturas, sem declaração de teste em impressora física ou de paginação PDF.

## 6. Decisões de implementação e limites

- `RiskSession` estende a sessão existente e reutiliza o ledger financeiro da Sprint 08. Uma extensão imutável registra contas/reservas e reconcilia seus deltas com os fills originais. Não há contabilidade financeira separada para a CLI. Cada ação prepara um snapshot completo e só o compromete no sucesso.
- Configuração schema 4 implica análise. Passar explicitamente analysis=False é erro na API; omitir a opção ou informar True tem identidade única. A CLI transforma --analise redundante nesse mesmo modo. Schemas legados mantêm seus caminhos anteriores.
- O alvo é mercado condicionado a toque, sem ordem limitada. Stop/alvo começam no próximo candle; range usa resolução no fechamento, não timestamp intraperíodo inventado. A curva usa a referência selecionada antes do fill e o close depois.
- A avaliação pura não reserva. Um fill BUY consome a reserva de caixa e cria uma única reserva compartilhada de BTC atomicamente. Transferência altera o titular; cancelamento e liberação não debitam taxas.
- O estado de bloqueio é atualizado no núcleo, com observações por horário/sequência/fase. Métricas de risco usam razões exatas; a apresentação com 12 casas não decide operações.
- Assets, custos, regras e versão Python participam da identificação conforme seus contratos. Biblioteca Lightweight Charts e licenças foram preservadas; somente o controlador local recebeu indicação de resolução no fechamento.

Apenas Python **3.12.14** foi executado neste ambiente; não foi validada matriz de Python/sistemas operacionais. Não foram testados grandes volumes, queda física de disco, recuperação após reinício ou negociação real. O modelo é sequencial em memória e usa snapshots completos, sem otimização de escala.

Liquidez ilimitada, latência zero, janela sem proteção e convenção OHLC continuam hipóteses. Stop não garante preço ou teto de perda. Benchmarks passivos não são carteiras geridas pelo mesmo orçamento. Não há novos dados reais, parciais, stop-limit, trailing stop, múltiplos pares ou infraestrutura externa. Não há pendências obrigatórias conhecidas; essas extensões continuam fora do escopo.

Nenhum commit, publicação ou alteração em projetos vizinhos foi realizado.
