# ReplayQuant — Planejamento do backtest de aprendizado

**Nome fictício do projeto:** ReplayQuant  
**Diretório/repositório sugerido:** `replayquant`  
**Linguagem:** Python  
**Mercado inicial:** criptomoedas Spot, posições compradas, sem alavancagem  
**Evolução:** `sprint06.md` até `sprint20.md`  
**Natureza:** projeto educacional com práticas de engenharia e pesquisa quantitativa  
**Estado deste documento:** planejamento; nenhuma implementação ou validação é declarada como executada.

## 1. Objetivo e resultado final

Construir progressivamente um motor de backtest que permita compreender e auditar o caminho entre dados, indicadores, sinais, decisões de risco, ordens simuladas, execuções, carteira e resultados.

Ao final, o ReplayQuant deverá comparar estratégias e pares, simular uma carteira com capital compartilhado, separar ajuste de avaliação, executar walk-forward e investigar robustez, custos e incerteza estatística. Cada resultado deverá ser reproduzível com a mesma versão dos dados, do código e da configuração.

O objetivo não é encontrar lucro garantido, prever a moeda mais lucrativa ou construir infraestrutura de negociação real. Um resultado negativo, uma hipótese rejeitada ou uma conclusão inconclusiva são resultados válidos do aprendizado.

## 2. Premissas adotadas

- Aproveitar os conhecimentos das etapas 1 a 5: mercado Spot, Python, dados, sinais e risco.
- Exigir, em cada documento de `sprint06.md` a `sprint20.md`, uma seção **Prompt autossuficiente de execução**, pronta para copiar e executar por um agente de desenvolvimento.
- Criar um único projeto incremental. As sprints 06 a 20 evoluem o mesmo código; não criam quinze projetos independentes.
- Não depender de módulos de SpotLab, PySpot, CandleVault, CrossSignal ou RiskGate. Podem servir como referências de conceitos, mas o ReplayQuant deve ser autossuficiente.
- Executar localmente, com interface de terminal e documentação em português.
- Começar com fixtures fictícias pequenas e verificáveis manualmente. Dados históricos reais entram em uma etapa específica.
- BTCUSDT e ETHUSDT serão os primeiros pares ilustrativos. Outros pares serão configuráveis após a introdução do catálogo de instrumentos.
- USDT será a moeda de relatório; sua equivalência ao dólar não será presumida como identidade. Conversão entre moedas de cotação diferentes fica fora do núcleo obrigatório.
- Foco inicial em candles de um minuto e SMA. A modularidade permitirá ampliar estratégias, frequências e modelos de execução nas etapas previstas.
- Não haverá envio de ordens, uso de chaves privadas, futuros, margem, venda descoberta, tributação, implantação em AWS ou interface web neste plano.
- Não há cronograma em dias: o avanço depende dos critérios de aceite e da compreensão da etapa anterior.

Essas premissas permitem começar sem decisões adicionais. Escolha de período histórico, recursos da máquina e eventuais fontes pagas será feita quando afetar uma sprint concreta; o percurso obrigatório deve continuar reproduzível com dados locais.

## 3. O que significa profissional neste projeto

Profissional significa tornar hipóteses, limitações, dados, cálculos e decisões verificáveis. Não significa reproduzir integralmente uma exchange, adquirir dados institucionais ou comprovar viabilidade de investimento.

| Pilar | Requisito |
| --- | --- |
| Causalidade | Cada decisão usa somente informações disponíveis até o instante simulado |
| Contabilidade | Caixa, reservas, ativos, taxas e resultados reconciliam |
| Execução | O modelo de preenchimento declara o que sabe e o que aproxima |
| Pesquisa | Ajuste, seleção e avaliação final têm fronteiras explícitas |
| Robustez | Custos, parâmetros, períodos e condições adversas são investigados |
| Reprodução | Código, configuração, dados e sementes identificam o experimento |
| Honestidade | Amostra insuficiente e limitações são exibidas; não se inventa precisão |

## 4. Arquitetura de referência

Monólito modular orientado a eventos. As interfaces surgem conforme a necessidade das sprints; não implementar antecipadamente todas as abstrações.

| Módulo | Responsabilidade |
| --- | --- |
| `data` | Leitura, validação, catálogo, qualidade e disponibilização temporal dos dados |
| `engine` | Relógio de simulação e ordenação determinística dos eventos |
| `strategies` | Indicadores e sinais sem acesso ao futuro |
| `risk` | Dimensionamento e aprovação/rejeição de novas exposições |
| `execution` | Ordens, preenchimentos, custos, cancelamentos e latência modelada |
| `portfolio` | Caixa, reservas, posições, lotes e marcação a mercado |
| `research` | Experimentos, divisões temporais, walk-forward e robustez |
| `reporting` | Métricas, benchmarks, tabelas, gráficos e exportações |
| `cli` | Configuração e comandos de execução |

O núcleo de estratégia e risco deve ser reutilizável em replay com eventos progressivos. A fonte pode carregar um arquivo completo, mas a estratégia recebe apenas os eventos já liberados pelo relógio.

### 4.1. Regras técnicas transversais

1. Usar Python 3.11 ou superior e ambiente isolado. Fixar uma versão concreta suportada na implementação e registrar dependências em `pyproject.toml` e lockfile.
2. Começar com biblioteca padrão e `unittest`. Adicionar bibliotecas de análise, persistência ou gráficos apenas na sprint em que tenham propósito verificável, documentando a decisão.
3. Usar `Decimal` na contabilidade e em preços, quantidades e taxas. Definir precisão, arredondamento e limites dos valores de entrada. Não herdar silenciosamente o contexto decimal do chamador.
4. Indicadores inicialmente usam `Decimal`. Arrays numéricos em ponto flutuante podem ser usados posteriormente para estatística/gráficos, com fronteira explícita, tolerâncias e sem contaminar o ledger financeiro.
5. UTC para armazenamento e simulação; intervalos de candles no formato `[início, fim)`. Normalizar timestamps de fontes externas para esse contrato.
6. Separar horário do mercado, disponibilidade da informação e evento de execução. Fechamento de um candle e abertura seguinte podem ter o mesmo timestamp nominal: sua ordem lógica deve ser explícita.
7. Uma intenção não é uma execução. Saldo e posição mudam somente por eventos apropriados do ledger; reservas também precisam de eventos e liberação auditáveis.
8. Manter sinais, ordens, preenchimentos, métricas e motivos de rejeição vinculados ao experimento.
9. Não duplicar spread/slippage: quando já incorporados ao preço de execução, não subtraí-los outra vez do resultado.
10. Não preencher lacunas de mercado silenciosamente nem confundir preço carregado para marcação com dado negociável atual.
11. Resultados inexistentes ou indefinidos serão `null` com motivo; não usar zeros, infinito ou percentuais inventados.
12. Toda aleatoriedade terá semente registrada. Tempos reais de processamento ficam fora da igualdade lógica exigida para reprodução.

## 5. Mapa das sprints

| Sprint | Arquivo futuro | Nível | Resultado principal |
| --- | --- | --- | --- |
| 06 | `sprint06.md` | Básico | Motor mínimo com replay e operação conferível manualmente |
| 07 | `sprint07.md` | Básico | SMA causal e execução no próximo evento |
| 08 | `sprint08.md` | Básico | Ledger, patrimônio, métricas e benchmarks |
| 09 | `sprint09.md` | Intermediário | Risco, reservas e saídas protetivas modeladas |
| 10 | `sprint10.md` | Intermediário | Estratégias intercambiáveis: SMA, EMA e RSI |
| 11 | `sprint11.md` | Intermediário | Múltiplos pares e catálogo de instrumentos |
| 12 | `sprint12.md` | Intermediário | Carteira compartilhada e conflitos entre estratégias |
| 13 | `sprint13.md` | Intermediário | Dados históricos reais versionados e auditados |
| 14 | `sprint14.md` | Avançado | Experimentos e separação temporal da pesquisa |
| 15 | `sprint15.md` | Avançado | Walk-forward e prevenção de vazamento nas fronteiras |
| 16 | `sprint16.md` | Avançado | Sensibilidade, estresse e registro de todas as tentativas |
| 17 | `sprint17.md` | Avançado | Execução mais detalhada e múltiplas frequências |
| 18 | `sprint18.md` | Avançado | Incerteza estatística e diagnóstico de seleção |
| 19 | `sprint19.md` | Avançado | Desempenho, processamento em lotes e paridade de replay |
| 20 | `sprint20.md` | Projeto final | Pesquisa integrada e relatório técnico auditável |

As dependências são cumulativas: cada sprint parte da anterior aprovada. A numeração continua a trilha de estudo, mas as entregas deste novo projeto começam na Sprint 06.

## 6. Sprint 06 — Motor mínimo e operação manual

**Objetivo de aprendizado:** entender como um simulador transforma eventos em mudanças financeiras.

**Implementação:** criar pacote, configuração versionada, CLI, relógio determinístico e leitura de candles fictícios válidos. Processar ordens de compra/venda previamente roteirizadas, sem estratégia automática. Usar quantidade fixa, taxa percentual em USDT e preenchimento total em evento posterior. Começar com slippage zero configurado explicitamente. Criar estados mínimos de ordem, validação de saldo e posição e registro de eventos.

**Exemplo obrigatório:** capital de 1.000 USDT; compra de 0,001 BTC a 100.000 e venda a 101.000; taxa de 0,10% em cada ponta. Resultado líquido de 0,799 USDT e saldo final de 1.000,799 USDT.

**Entregáveis:** projeto executável, fixture, log estruturado, relatório mínimo, README e roteiro de validação.

**Aceite:** cálculos exatos com `Decimal`; nenhuma venda descoberta; ordem inválida não altera carteira; executar duas vezes produz os mesmos eventos e resultados lógicos. Sem alegação de avaliação de estratégia nesta sprint.

## 7. Sprint 07 — Estratégia SMA e causalidade

**Objetivo:** substituir ordens roteirizadas por sinais calculados a partir do passado disponível.

**Implementação:** SMA curta/longa configuráveis, histórico de aquecimento e cruzamento definido com desigualdades explícitas. Sinal no fechamento; compra/venda a mercado simulada no próximo evento de abertura elegível. Explicitar a convenção de latência zero entre eventos ordenados no mesmo timestamp nominal; atraso positivo será introduzido depois. Adicionar slippage percentual fixo configurável, adverso na compra e venda.

**Casos:** entrada, saída, igualdade, ausência de cruzamento, histórico insuficiente, sinal no último candle e lacuna. Uma ordem sem evento futuro fica não executada e é reportada.

**Aceite:** alterar candles futuros não muda avaliações anteriores; nenhum uso do fechamento futuro; nenhum sinal repetido apenas por permanência acima da média. Sinal, decisão, ordem e preenchimento são identificáveis separadamente.

## 8. Sprint 08 — Ledger, métricas e referências

**Objetivo:** explicar para onde foi cada unidade de capital e como medir o resultado.

**Implementação:** ledger auditável, curva patrimonial marcada a mercado, resultado realizado/não realizado e política de posição no encerramento. Padrão: manter posição aberta e apresentar patrimônio bruto marcado, separado do valor hipotético líquido de liquidação. Liquidação forçada só mediante regra explícita e evento suportado pelos dados.

**Métricas:** retorno líquido, drawdown máximo e duração, custos, número de operações encerradas, ganhos/perdas/empates, expectativa e tempo em posição. Comparar manter USDT e comprar/manter BTC sob datas, custos e capital comparáveis. Não anualizar uma amostra curta como evidência de retorno sustentável.

**Aceite:** patrimônio reconcilia com caixa e ativos; métricas conferidas em sequências manuais; ausência de trades não gera taxa de acerto fictícia. Relatórios JSON/CSV e Markdown reproduzíveis.

## 9. Sprint 09 — Risco e saídas protetivas

**Objetivo:** dimensionar exposição e separar proteção planejada de resultado garantido.

**Implementação:** quantidade limitada por orçamento de risco, saldo com taxas, exposição e filtros do instrumento; ajuste para baixo em múltiplos do incremento. Reservas para ordens pendentes com liberação em rejeição/cancelamento. Bloqueios de novas entradas por perda diária e drawdown, sem impedir saídas ou acompanhamento.

**Execução protetiva:** modelo simplificado de stop e alvo sobre OHLC, com regras documentadas para gaps e candle que toca ambos. Na ausência de sequência intraperíodo, usar convenção conservadora predefinida e registrar ambiguidade; não afirmar que essa foi a ordem real. Saída por gap pode ocorrer pior que o gatilho. Evitar novas entradas no mesmo candle para simplificar inicialmente.

**Aceite:** fundos reservados não são gastos duas vezes; mínimos não obrigam aumento da compra; perda efetiva pode exceder orçamento; todos os eventos financeiros reconciliam.

## 10. Sprint 10 — Estratégias modulares

**Objetivo:** comparar regras diferentes sem duplicar o motor financeiro.

**Implementação:** contrato de estratégia e registro por nome/versão; implementar SMA, cruzamento de EMA e RSI com regras completas de entrada/saída. Definir sementes da EMA, suavização do RSI, igualdade, divisão por zero e aquecimento. Rodar cada estratégia isoladamente com capital próprio, claramente identificado.

**Pesquisa:** parâmetros em configuração; nenhuma seleção automática do maior lucro ainda. Incluir comparação de indicadores com cálculos manuais e investigação de estabilidade do aquecimento de indicadores recursivos.

**Aceite:** trocar estratégia não altera o modelo de taxas/execução; cada avaliação explica seu motivo; todas respeitam causalidade. Documentos técnicos individuais para cada estratégia.

## 11. Sprint 11 — Múltiplos pares e catálogo

**Objetivo:** distinguir efeito da estratégia de efeito do instrumento.

**Implementação:** catálogo de pares com moeda base/cotação, disponibilidade temporal, incremento, mínimos e fonte das regras. Usar BTCUSDT/ETHUSDT fictícios inicialmente; executar matriz estratégia × par com experimentos independentes e saldo inicial igual.

**Controles:** evitar mistura de históricos, respeitar início/fim de disponibilidade, registrar lacunas, preços desatualizados e cobertura de cada conjunto. Regras atuais sem histórico não podem ser apresentadas como regras históricas conhecidas: usar hipótese explicitamente rotulada.

**Aceite:** isolamento entre testes; ranking acompanha custos, drawdown, amostra e cobertura; pares não disponíveis não negociam. Não somar resultados independentes como se fossem carteira compartilhada.

## 12. Sprint 12 — Carteira compartilhada

**Objetivo:** simular estratégias e pares concorrendo pelo mesmo capital.

**Implementação:** relógio global, eventos sincronizados, limites por instrumento/estratégia/carteira e arbitragem determinística de sinais simultâneos. Definir a ordem entre saídas, liberações e entradas sem favorecer inadvertidamente a ordem dos arquivos.

**Propriedade:** posições físicas por ativo, com lotes virtuais atribuídos à estratégia para auditoria. Uma estratégia não vende a quantidade pertencente a outra sem política explícita. Começar por alocação de orçamento; depois acrescentar combinação opcional de sinais com conflitos documentados. Não misturar voto de indicadores com várias carteiras independentes.

**Aceite:** não duplicar caixa/reservas; soma de contribuições reconcilia com a carteira total; testes de concorrência lógica e inversão de ordem de entrada dos arquivos produzem o resultado definido pela política. Exposição correlacionada aparece no relatório, sem prometer hedge.

## 13. Sprint 13 — Dados históricos reais

**Objetivo:** aplicar o motor já verificado a dados externos sem perder rastreabilidade.

**Implementação:** adaptador de arquivos históricos públicos de fonte oficial, preferencialmente Binance Spot; rede somente para obtenção explícita de dados públicos, nunca no núcleo do backtest. Fixar versão do conjunto, checksums, período e origem. Permitir importação local equivalente para operação offline.

**Qualidade:** normalização de unidades de timestamp, fuso, fim inclusivo/exclusivo, volume base/cotação, duplicatas, candles incompletos, lacunas e disponibilidade dos pares. Não presumir unidade de timestamp constante em todos os arquivos da fonte. Manter camada bruta imutável e normalizada rastreável.

**Persistência:** catálogo e metadados em SQLite; camada analítica Parquet/DuckDB apenas se volume justificar, com decisão documentada e preservação da precisão. Não é requisito converter tudo antecipadamente.

**Aceite:** relatório de qualidade; reprodução offline; fixture com par retirado e universo temporal. Se dados de deslistagem/universo completo não existirem, declarar restrição de sobrevivência e limitar a conclusão ao universo observado.

## 14. Sprint 14 — Registro de experimentos e divisão temporal

**Objetivo:** separar descoberta, seleção e avaliação.

**Implementação:** manifesto por execução com hash dos dados, configuração, código, dependências, estratégia, custos e sementes. Registrar todos os candidatos, inclusive falhas e resultados ruins; estabelecer objetivo e restrições antes de comparar.

**Pesquisa:** períodos cronológicos de desenvolvimento, validação e teste final. Iniciar carteira vazia em cada avaliação; aquecimento pode usar apenas dados anteriores permitidos e não pode gerar operações retroativas. Nenhuma estatística ajustada no futuro deve entrar no passado.

**Aceite:** teste final não participa da seleção; acesso/execução final fica registrado. Código impede uso acidental nos comandos normais de ajuste, mas não se afirma que software elimina contaminação por inspeção humana. Se o pesquisador alterar regras após olhar o teste, registrar consumo do holdout e exigir nova avaliação futura.

## 15. Sprint 15 — Walk-forward

**Objetivo:** repetir ajuste no passado e avaliação no período seguinte.

**Implementação:** janelas móveis e expansivas; busca pequena e limitada a treino/validação interna de cada fold. Escolher parâmetros antes do respectivo trecho fora da amostra e congelá-los durante ele. Separar um teste final ainda não usado.

**Fronteiras:** impedir sobreposição de resultados/labels de operações entre ajuste e avaliação. Aplicar purge/embargo quando houver horizontes sobrepostos ou dependências que o justifiquem; tamanho deriva do método, não de percentual arbitrário. Neste laboratório, avaliação começa sem posição e seu histórico anterior serve só a aquecimento. Não carregar artificialmente posição escolhida com dados futuros.

**Aceite:** linha temporal de cada fold exportada; parâmetros não usam o teste seguinte; resultados fora da amostra não são contados duas vezes. Agregar retornos por encadeamento patrimonial, com convenção explícita entre folds, e não por soma de percentuais.

## 16. Sprint 16 — Sensibilidade e estresse

**Objetivo:** descobrir fragilidades antes de celebrar o melhor resultado.

**Implementação:** matriz limitada de parâmetros, vizinhanças da configuração, cenários de taxas/slippage, atraso de execução e janelas de mercado. Comparar resultados por par, estratégia e período; avaliar dependência de poucas operações excepcionais. Regimes devem ser definidos sem introduzir informação futura na negociação; rótulos retrospectivos servem apenas à análise descritiva.

**Controles:** registrar quantidade de tentativas e separar investigação exploratória de confirmação. Não escolher custos de execução pelo resultado mais favorável. Não exigir lucratividade para passar o aceite técnico.

**Aceite:** relatório de superfícies/intervalos de sensibilidade e cenários adversos; hipótese pode ser reprovada. Critérios definidos antes do teste final. Sem novo ajuste silencioso baseado em resultados de avaliação reservada.

## 17. Sprint 17 — Execução avançada e frequências

**Objetivo:** medir como hipóteses de execução mudam as conclusões.

**Implementação:** modelos intercambiáveis de mercado/limitada/stop, preenchimento parcial, cancelamento e expiração. Participação máxima no volume, taxas maker/taker fictícias ou historicamente justificadas, atraso positivo e preenchimento em evento disponível após a elegibilidade. Reavaliar ou rejeitar entrada cujo preço real simulado invalide saldo/risco; nunca preencher e deixar caixa negativo.

**Dados:** permitir detalhe intraperíodo quando disponível e agregação causal para múltiplas frequências. Candle de cinco minutos só é liberado após fechamento. Tocar o preço de uma limitada não garante fila nem execução; modelos OHLC devem declarar convenções. Volume de candle não revela liquidez disponível em cada preço.

**Aceite:** testes de gap, ambos os gatilhos, latência, parcial e cancelamento; reservas reconciliam. Relatório compara modelo básico/conservador/detalhado. Sem alegação de reconstrução exata de livro de ofertas ou posição na fila.

## 18. Sprint 18 — Incerteza e risco de seleção

**Objetivo:** acrescentar evidência estatística e reconhecer seus limites.

**Implementação:** retornos periódicos em frequência uniforme e métricas como Sharpe/Sortino com convenções de frequência, anualização e taxa de referência. Não tratar USDT automaticamente como livre de risco. Casos sem variância ou com amostra insuficiente retornam indisponibilidade justificada.

**Reamostragem:** bootstrap em blocos dos retornos para intervalos e cenários de trajetória, com sementes, tamanho de bloco e sensibilidade documentados. Não reamostrar trades como se fossem independentes quando compartilham exposição ou dependência temporal. Resultados condicionam-se à história observada, não são probabilidades garantidas do futuro.

**Seleção:** acrescentar um estudo didático de PBO/CSCV ou Sharpe deflacionado, escolhido conforme dados/candidatos disponíveis, validado contra referência primária e caso conhecido. Não implementar uma fórmula apenas pelo nome. Se faltarem tentativas/amostra ou hipóteses, retornar não aplicável. Essa análise não substitui avaliação cronológica nem concede aprovação para operar.

**Aceite:** invariantes, casos analíticos e reprodução das sementes; relatório separa retorno observado, intervalo estimado e diagnóstico exploratório. Nenhum nível de confiança inventado a partir de poucos trades.

## 19. Sprint 19 — Desempenho e paridade

**Objetivo:** aumentar escala preservando o comportamento financeiro e temporal.

**Implementação:** medir gargalos antes de otimizar; processamento por partes, cache identificado pelo conjunto/configuração e execução paralela de experimentos independentes. Estados de estratégias concorrentes dentro da mesma carteira continuam coordenados pelo relógio e pelo ledger.

**Paridade:** comparar motor de referência com caminhos otimizados e replay que libera eventos progressivamente. Reutilizar o mesmo núcleo para esse replay, preparando uma futura etapa de paper trading sem conectar serviços nesta sprint.

**Aceite:** resultados financeiros/eventos iguais quando exatos ou tolerâncias justificadas apenas nos componentes estatísticos; orçamento de memória/tempo medido em máquina e dados identificados. Não sacrificar causalidade para obter velocidade. Aceleração deve ser evidenciada, não presumida.

## 20. Sprint 20 — Projeto avançado integrado

**Objetivo:** concluir uma pesquisa reproduzível com limitações e evidência suficientes para revisão.

**Experimento final:** comparar SMA, EMA e RSI em pelo menos BTCUSDT/ETHUSDT, testes isolados e carteira compartilhada; dados históricos com cobertura declarada; custos e risco; benchmarks; seleção e walk-forward; estresse; incerteza quando aplicável. Incluir um exemplo controlado que parece excelente com vazamento/custos omitidos e demonstrar por que é inválido, mantendo-o separado do motor válido.

**Entregáveis:** guia completo, arquitetura final, catálogo de dados, receitas de execução, manifestos, relatórios por experimento, curvas patrimoniais e relatório final em Markdown/HTML estático. Gráficos serão gerados de dados reais da execução, sem valores ilustrativos misturados às conclusões.

**Aceite final:** um comando de demonstração offline reproduz fixtures; receita histórica reproduz resultados com dados identificados; ledger e testes causais passam; todas as limitações são apresentadas. Resultado poderá ser promissor, insuficiente ou rejeitado. A conclusão não depende de obter lucro e não autoriza negociação real.

## 21. Critérios comuns de conclusão de cada sprint

- Documento `sprintNN.md` com prompt completo e autossuficiente de execução; objetivo e lista de tarefas, isoladamente, não atendem a esse requisito.
- Implementação dentro do escopo e compatível com etapas anteriores.
- Exemplo pequeno cuja lógica possa ser conferida manualmente.
- Testes de comportamento financeiro/temporal, erros e preservação de estado; evitar testes que só espelhem funções internas.
- Comandos realmente executados registrados com resultados observados. Não confundir esperado com verificado.
- Suíte relevante aprovada e verificação das regressões afetadas, sem repetir verificações sem motivo.
- README, glossário e roteiro de validação atualizados em português.
- Nenhuma ação externa de negociação; dependências e dados públicos só conforme a sprint.
- Alterações de escopo ou decisões relevantes registradas antes de mudar as hipóteses do experimento.

## 22. Documentos e comandos previstos

Estrutura conceitual; criar somente os arquivos necessários à sprint em execução:

| Local | Conteúdo |
| --- | --- |
| `planejamento.md` | Este plano e seu estado de evolução |
| `sprints/sprintNN.md` | Escopo e prompt autossuficiente de cada sprint |
| `docs/sprintNN-validacao.md` | Como verificar e o que foi efetivamente observado |
| `docs/sprintNN-glossario.md` | Conceitos novos da etapa |
| `docs/estrategias/` | Regras, parâmetros e limitações de cada estratégia |
| `docs/decisoes/` | Decisões de arquitetura, modelos e pesquisa |
| `data/fixtures/` | Dados pequenos e reproduzíveis para aprendizado |
| `data/catalogo/` | Manifestos/versionamento de conjuntos históricos |
| `experiments/` | Configurações dos experimentos |
| `runs/` | Resultados gerados e manifestos por execução |

Comandos serão introduzidos progressivamente, por exemplo `python -m replayquant demonstrar`, `validar-dados`, `executar`, `comparar`, `walk-forward` e `relatorio`. A CLI exata será fixada na sprint correspondente, com ajuda e códigos de saída documentados. Não prometer comandos ainda não implementados.

## 23. Prompt obrigatório em cada sprint

**Cada documento de `sprint06.md` até `sprint20.md` deve conter a seção “Prompt autossuficiente de execução”, com o texto completo em um único bloco copiável.** O prompt deve permitir que um agente implemente, teste e documente a sprint sem precisar desta conversa. Uma descrição de objetivo, resumo ou lista de tarefas não substitui o prompt.

Os prompts serão produzidos junto com os respectivos documentos de sprint, antes de iniciar sua implementação. A evolução continua incremental: autossuficiência das instruções não significa recriar o projeto a cada etapa.

### 23.1. Conteúdo mínimo do prompt

1. **Projeto e contexto:** nome ReplayQuant, número da sprint e objetivo concreto de aprendizado e implementação.
2. **Diretório e estado de entrada:** local de trabalho, dependências das sprints anteriores, versão/commit quando disponível e como verificar os pré-requisitos. A Sprint 06 deve orientar a criação inicial; as demais devem orientar a evolução do código existente.
3. **Escopo e exclusões:** funcionalidades a implementar, limites da etapa e comportamentos anteriores que precisam ser preservados.
4. **Contratos e regras:** entradas, saídas, configurações, fórmulas, unidades, precisão, datas, sequência de eventos e tratamento de estados/erros aplicáveis.
5. **Exemplos reproduzíveis:** fixtures explícitas e resultados esperados conferíveis manualmente; nas etapas estatísticas, sementes, hipóteses e tolerâncias justificadas.
6. **Entregáveis:** código, configuração, testes e documentação, incluindo `docs/sprintNN-validacao.md` e glossário pertinente.
7. **Comandos:** preparação do ambiente, execução dos exemplos e testes, com diretório de execução, argumentos e códigos de saída definidos. Não deixar comandos essenciais para serem adivinhados.
8. **Critérios de aceite:** verificações observáveis, invariantes e regressões relevantes, incluindo causalidade e reconciliação financeira quando afetadas.
9. **Instrução de execução:** implementar a etapa e corrigir falhas encontradas, preservando trabalho alheio; não entregar apenas uma proposta.
10. **Registro final:** informar arquivos alterados, comandos realmente executados, resultados, limitações e pendências; nunca declarar testes não realizados como aprovados.

### 23.2. Regras de qualidade

- O prompt deverá ser específico da sprint, sem campos essenciais em aberto ou frases como “seguir as regras combinadas na conversa”.
- Contratos necessários deverão estar explícitos no próprio prompt ou vinculados a documentos versionados acessíveis no projeto. O agente deverá inspecioná-los antes de alterar código.
- As dependências e condições de entrada deverão ser verificáveis; se faltar um pré-requisito essencial, registrar a lacuna antes de executar trabalho dependente. Não presumir que uma sprint anterior foi concluída.
- O agente não deverá implementar antecipadamente sprints futuras, substituir dados reais por resultados inventados ou alterar hipóteses de pesquisa para obter lucro.
- Não realizar negociação real, publicação ou alterações externas sem solicitação.
- O roteiro de validação deverá ser atualizado após a execução, separando resultados esperados dos efetivamente observados.

Este planejamento estabelece o requisito para todas as quinze sprints. Seus prompts completos serão escritos nos respectivos documentos. O próximo documento a produzir será **`sprint06.md`**, já com seu **Prompt autossuficiente de execução**.

## 24. Riscos de interpretação e limites

| Risco | Tratamento previsto |
| --- | --- |
| Fixtures positivas confundidas com desempenho | Separar testes de correção de pesquisa com dados históricos |
| Uso de dados futuros | Relógio causal, testes de prefixo e fronteiras temporais |
| Seleção dos sobreviventes/vencedores | Universo temporal ou restrição declarada |
| Execução perfeita irreal | Modelos explícitos, custos e comparação de hipóteses |
| Somar carteiras independentes | Ledger único para simulação compartilhada |
| Excesso de busca | Registro de tentativas, seleção temporal e diagnóstico estatístico |
| Pequena amostra | Não aplicável/inconclusivo em vez de falsa precisão |
| Regras históricas ausentes | Hipóteses rotuladas e análise de sensibilidade |
| Complexidade antecipada | Aceite incremental e otimização somente após medir |

Ficam como extensões posteriores, fora das sprints obrigatórias: paper trading conectado em tempo real, múltiplas moedas de cotação, livro de ofertas completo, dados de alta frequência, derivativos, aprendizado de máquina e operação com recursos reais. Qualquer extensão deve ter planejamento próprio.

## 25. Referências de método

Fontes de estudo, não dependências obrigatórias do motor nem garantia de desempenho. Consultadas em 06/11/2026; versões podem mudar.

- [QuantConnect — Reality Modeling](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts): separação entre modelos de custos, preenchimento e condições de mercado.
- [Freqtrade — Lookahead Analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/): verificação de uso indevido de dados futuros.
- [Freqtrade — Recursive Analysis](https://www.freqtrade.io/en/stable/recursive-analysis/): sensibilidade de indicadores ao histórico de inicialização.
- [Bailey, Borwein, López de Prado e Zhu — The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf): seleção entre alternativas e diagnóstico de sobreajuste; uso avançado condicionado ao estudo do método.
- [Binance — documentação oficial Spot](https://github.com/binance/binance-spot-api-docs): referência a consultar ao implementar adaptadores e regras de instrumento.

O ReplayQuant será um ambiente para aprender a formular, testar e rejeitar hipóteses com disciplina. Seu produto final será evidência rastreável sobre o que foi simulado e suas limitações.
