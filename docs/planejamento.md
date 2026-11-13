# ReplayQuant — Planejamento do backtest de aprendizado

**Nome fictício do projeto:** ReplayQuant  
**Diretório/repositório sugerido:** `replayquant`  
**Linguagem:** Python  
**Mercado inicial:** criptomoedas Spot, posições compradas, sem alavancagem  
**Evolução:** `sprint06.md` até `sprint20.md`  
**Natureza:** projeto educacional com práticas de engenharia e pesquisa quantitativa  
**Estado deste documento:** planejamento incremental; as Sprints 06, 07, 08, 09, 10, 11, 12 e 13 possuem implementação e validação registradas em [sprint06-validacao.md](sprint06-validacao.md), [sprint07-validacao.md](sprint07-validacao.md), [sprint08-validacao.md](sprint08-validacao.md), [sprint09-validacao.md](sprint09-validacao.md), [sprint10-validacao.md](sprint10-validacao.md), [sprint11-validacao.md](sprint11-validacao.md), [sprint12-validacao.md](sprint12-validacao.md) e [sprint13-validacao.md](sprint13-validacao.md). As demais sprints continuam previstas.

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

### 2.1. Continuidade das sprints 01 a 05

Revisão documental em **06/11/2026**, confrontando READMEs, registros de validação e trechos de implementação/testes dos cinco projetos locais. Os registros descrevem verificações anteriores; suas suítes não foram reexecutadas nesta revisão. Os projetos são referências de contratos e exemplos, não dependências de execução nem pré-requisitos instaláveis do ReplayQuant.

| Referência | Aprendizado a preservar | Aplicação no ReplayQuant |
| --- | --- | --- |
| [SpotLab — Sprint 01](../../spotlab/README.md) | Unidades base/cotação, taxas, reservas, estados de ordem e limites do OHLCV | Exemplo financeiro na Sprint 06; reservas na 09; parciais e cancelamentos na 17, sem exigir livro de ofertas |
| [PySpot — Sprint 02](../../pyspot/README.md) | Validação de domínio, contexto decimal local, UTC e rejeições sem mutação | Contratos de entrada e cálculos desde a Sprint 06 |
| [CandleVault — Sprint 03](../../candlevault/README.md) | Identidade dos candles, versões, duplicatas, lacunas e persistência decimal | Fixtures validadas desde a Sprint 06; ingestão histórica rastreável na 13 |
| [CrossSignal — Sprint 04](../../crosssignal/README.md) | Cruzamento exato, aquecimento, intenção pendente, idempotência e causalidade | Estratégia SMA e fluxo de eventos na Sprint 07 |
| [RiskGate — Sprint 05](../../riskgate/README.md) | Risco com taxas, incrementos, bloqueios persistentes e memória de cálculo | Gestão de risco na Sprint 09 e relatórios explicativos a partir da 08 |

As convenções diferem entre os laboratórios: SpotLab usa precisão decimal 40, enquanto PySpot e RiskGate usam contexto local com precisão 28; as gramáticas decimais também variam. CrossSignal usa razões exatas para decidir cruzamentos, mesmo exibindo médias em `Decimal`. ReplayQuant definirá seus próprios contratos versionados, preservando os comportamentos relevantes sem copiar configurações globais ou presumir compatibilidade direta de arquivos.

CandleVault guarda apenas a versão atual de cada candle e não preserva todas as revisões; isso não basta para reconstruir disponibilidade histórica da informação. CrossSignal confirma intenções somente em horário estritamente posterior. ReplayQuant adotará uma convenção própria de eventos ordenados, podendo compartilhar timestamp entre fechamento, sinal e abertura seguinte. Essa diferença deverá ser demonstrada e testada, sem usar o fechamento ou os extremos do candle seguinte para preencher sua abertura.

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
4. Indicadores inicialmente recebem `Decimal`; decisões de cruzamento SMA usam comparação exata de razões/somas, como no CrossSignal, sem depender das médias arredondadas para exibição. Arrays numéricos em ponto flutuante podem ser usados posteriormente para estatística/gráficos, com fronteira explícita, tolerâncias e sem contaminar o ledger financeiro.
5. UTC para armazenamento e simulação; intervalos de candles no formato `[início, fim)`. Normalizar timestamps de fontes externas para esse contrato.
6. Separar horário do mercado, disponibilidade da informação e evento de execução. Fechamento de um candle e abertura seguinte podem ter o mesmo timestamp nominal: sua ordem lógica deve ser explícita.
7. Uma intenção não é uma execução. Saldo e posição mudam somente por eventos apropriados do ledger; reservas também precisam de eventos e liberação auditáveis.
8. Manter sinais, ordens, preenchimentos, métricas e motivos de rejeição vinculados ao experimento.
9. Não duplicar spread/slippage: quando já incorporados ao preço de execução, não subtraí-los outra vez do resultado.
10. Não preencher lacunas de mercado silenciosamente nem confundir preço carregado para marcação com dado negociável atual.
11. Resultados inexistentes ou indefinidos serão `null` com motivo; não usar zeros, infinito ou percentuais inventados.
12. Toda aleatoriedade terá semente registrada. Tempos reais de processamento ficam fora da igualdade lógica exigida para reprodução.
13. Validar também construções pela API Python: tipos, finitude, faixas, unidades e datas com fuso. Para JSON, versionar o schema, representar decimais como strings e rejeitar chaves duplicadas, campos inesperados, constantes não finitas e booleanos usados como números. Fixar gramática e limites de magnitude; apresentação não altera valores de decisão.
14. Identificar candles por origem, par, intervalo e abertura. Validar alinhamento, duração, OHLC consistente e volume base não negativo. Candles abertos não alimentam indicadores de fechamento; duplicata equivalente não repete avaliação, conflito é erro e eventos fora de ordem não são reordenados silenciosamente pelo motor. A preparação de arquivos pode ordenar dados, desde que registre essa transformação antes do replay.
15. Identificar eventos de execução deterministicamente por experimento: repetição idêntica é inócua; mesmo ID com conteúdo divergente é erro. Rejeições preservam estado financeiro e histórico aceito, admitindo apenas registros explícitos de diagnóstico/bloqueio. O escopo inicial de deduplicação é a execução local, sem promessa de recuperação operacional após reinício.
16. Distinguir dados inválidos, rejeição por política e falha técnica, com motivos estáveis e códigos de saída documentados. Uma demonstração que confere rejeições previstas pode concluir com sucesso; falha inesperada não pode ser mascarada como resultado de estratégia.

### 4.2. Contrato temporal mínimo dos dados

Desde a Sprint 06, distinguir abertura/fim do intervalo, instante de disponibilidade da informação e ordem lógica de processamento. O replay de um candle completo libera sua abertura para execução e seus dados completos somente após o fechamento; carregar a linha inteira do arquivo não permite expor high, low, close ou volume final antecipadamente. A Sprint 09 poderá usar o OHLC completo para resolver saídas intraperíodo pela convenção documentada, sem disponibilizá-lo à estratégia antes do fechamento.

Na Sprint 13, metadados de observação da fonte (`snapshot_at`, quando disponíveis) e recebimento local (`received_at`) serão preservados separadamente. Receber hoje um arquivo histórico não demonstra quando cada dado estava disponível no passado. Se a fonte só fornecer candles finais, declarar a hipótese de disponibilidade no fechamento e a ausência de histórico de revisões; não apresentar essa hipótese como latência observada.

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

**Contratos iniciais:** schema de candles e configuração, contexto decimal local, IDs determinísticos e identificação da execução com versão/hash dos dados, código e configuração. A Sprint 14 ampliará esse registro para pesquisa e seleção. Enquanto não houver reservas, admitir somente uma ordem pendente por vez e revalidar saldo com taxa e posição no preenchimento; não aceitar compromissos concorrentes sobre o mesmo saldo.

**Aceite:** cálculos exatos com `Decimal`; nenhuma venda descoberta; ordem inválida não altera carteira; executar duas vezes produz os mesmos eventos e resultados lógicos. Sem alegação de avaliação de estratégia nesta sprint.

## 7. Sprint 07 — Estratégia SMA e causalidade

**Objetivo:** substituir ordens roteirizadas por sinais calculados a partir do passado disponível.

**Implementação:** SMA curta/longa configuráveis, histórico de aquecimento e cruzamento definido com desigualdades explícitas. Sinal no fechamento; compra/venda a mercado simulada no próximo evento de abertura elegível. Explicitar a convenção de latência zero entre eventos ordenados no mesmo timestamp nominal; atraso positivo será introduzido depois. Adicionar slippage percentual fixo configurável, adverso na compra e venda.

**Casos:** entrada, saída, igualdade, ausência de cruzamento, histórico insuficiente, sinal no último candle e lacuna. Uma ordem sem evento futuro fica não executada e é reportada.

**Contrato SMA e pendências:** `1 <= curta < longa`; comparar médias anterior/atual exige `longa + 1` candles fechados contíguos. Entrada: curta anterior <= longa anterior e curta atual > longa atual; saída: curta anterior >= longa anterior e curta atual < longa atual. Igualdade atual não sinaliza. Usar razões exatas para que diferenças abaixo da precisão exibida continuem decidindo corretamente. Uma intenção pendente impede outra para a mesma posição; cancelamento/falha preserva a posição e não gera nova tentativa sem novo cruzamento.

**Lacunas:** a política inicial interrompe o replay com diagnóstico, preservando posição, caixa e pendências, sem incorporar o candle posterior nem executar através do intervalo ausente. Recuperação exige corrigir/versionar o conjunto e iniciar nova execução; não reconstruir operações retroativamente dentro da execução interrompida. Políticas futuras por instrumento deverão ser explícitas e manter a distinção entre preço de marcação e dado negociável.

**Aceite:** alterar candles futuros não muda avaliações anteriores; nenhum uso do fechamento futuro; nenhum sinal repetido apenas por permanência acima da média. Sinal, decisão, ordem e preenchimento são identificáveis separadamente.

## 8. Sprint 08 — Ledger, métricas e referências

**Objetivo:** explicar para onde foi cada unidade de capital e como medir o resultado.

**Implementação:** ledger auditável, curva patrimonial marcada a mercado, resultado realizado/não realizado e política de posição no encerramento. Padrão: manter posição aberta e apresentar patrimônio bruto marcado, separado do valor hipotético líquido de liquidação. Liquidação forçada só mediante regra explícita e evento suportado pelos dados.

**Métricas:** retorno líquido, drawdown máximo e duração, custos, número de operações encerradas, ganhos/perdas/empates, expectativa e tempo em posição. Comparar manter USDT e comprar/manter BTC sob datas, custos e capital comparáveis. Não anualizar uma amostra curta como evidência de retorno sustentável.

**Interpretação:** separar retorno sobre desembolso da operação de retorno sobre patrimônio inicial. No exemplo da Sprint 06, `0,799 / 100,1 × 100` é aproximadamente `0,798202%` por operação; `0,799 / 1.000 × 100 = 0,0799%` é o retorno da carteira. Exibir entradas, fórmulas, unidades e memória de cálculo dos exemplos manuais. Caixa total já inclui reservas: patrimônio soma caixa disponível + reservado + posições marcadas, sem contar a reserva novamente. Não há depósitos/retiradas no núcleo obrigatório.

**Aceite:** patrimônio reconcilia com caixa e ativos; métricas conferidas em sequências manuais; ausência de trades não gera taxa de acerto fictícia. Relatórios JSON/CSV e Markdown reproduzíveis.

## 9. Sprint 09 — Risco e saídas protetivas

**Objetivo:** dimensionar exposição e separar proteção planejada de resultado garantido.

**Implementação:** quantidade limitada por orçamento de risco, saldo com taxas, exposição e filtros do instrumento; ajuste para baixo em múltiplos do incremento. Reservas para ordens pendentes com liberação em rejeição/cancelamento. Bloqueios de novas entradas por perda diária e drawdown, sem impedir saídas ou acompanhamento.

**Dimensionamento de referência:** para patrimônio `P`, saldo livre `B`, exposição nominal atual `X`, entrada estimada `E`, stop planejado `S < E`, taxas fracionárias `fc/fv`, risco fracionário `r` e exposição máxima fracionária `x`, usar `R = P*r`, `L = E*(1+fc) - S*(1-fv)` e `q_bruta = min(R/L, max(0, P*x-X)/E, B/(E*(1+fc)))`. Ajustar `q = floor(q_bruta/step)*step` por contagem de incrementos, inclusive para `step=0,000003`; não basta arredondar casas decimais. Recalcular perda, desembolso e exposição após o ajuste, reduzindo incrementos se o arredondamento exceder limites. Igualdade com limites/mínimos é válida; mínimos nunca autorizam aumento. Declarar qualquer ampliação do modelo para custos adicionais.

**Estado e tempo:** aprovação de risco não é reserva nem execução; o motor valida e reserva numa única transição lógica antes de aceitar a ordem. Preço ausente, futuro ou desatualizado impede entrada, sem zerar o valor de posições. Configurar idade máxima pela informação disponível no relógio simulado. Documentar precedência dos bloqueios, pendências e filtros; registrar candidata rejeitada separada de quantidade aprovada.

**Bloqueios patrimoniais:** primeira observação da sessão positiva; perda diária calculada desde a primeira observação positiva do dia UTC, identificando base parcial, e drawdown desde o pico da sessão. Atingir o limite diário bloqueia até a virada UTC, mesmo após recuperação; drawdown bloqueia até o fim do experimento. Virar o dia não limpa drawdown. Patrimônio zero após início aciona bloqueios; sem base diária positiva, perda diária fica indisponível com motivo. Não reiniciar sessões para remover bloqueios durante o mesmo experimento.

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

**Ingestão e versões:** duplicata fechada numericamente equivalente é ignorada; divergência na mesma chave é conflito, sem sobrescrever o conjunto usado por experimentos anteriores. Correção aceita da fonte gera nova versão identificada do conjunto. Se houver snapshots abertos, documentar precedência por observação e fechamento, sem alimentar a estratégia com versões incompletas. Fixar atomicidade de lotes e distinguir rejeição de domínio de falha técnica. Em SQLite, preservar decimais como texto canônico e calcular em Python, sem conversão financeira para `REAL` ou ordenação numérica de texto.

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
| `docs/planejamento.md` | Este plano e seu estado de evolução |
| `docs/sprintNN.md` | Escopo e prompt autossuficiente de cada sprint |
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

Este planejamento estabelece o requisito para todas as quinze sprints. A especificação da Sprint 06 e seu **Prompt autossuficiente de execução** estão em [sprint06.md](sprint06.md). A especificação e o prompt da Sprint 07 estão em [sprint07.md](sprint07.md), com execução registrada em [sprint07-validacao.md](sprint07-validacao.md). A especificação e o prompt da Sprint 08 estão em [sprint08.md](sprint08.md), com execução registrada em [sprint08-validacao.md](sprint08-validacao.md). A especificação e o prompt da Sprint 09 estão em [sprint09.md](sprint09.md), com execução registrada em [sprint09-validacao.md](sprint09-validacao.md). A especificação e o prompt da Sprint 10 estão em [sprint10.md](sprint10.md), com execução registrada em [sprint10-validacao.md](sprint10-validacao.md). A especificação e o prompt da Sprint 11 estão em [sprint11.md](sprint11.md), com execução registrada em [sprint11-validacao.md](sprint11-validacao.md). A Sprint 12 está implementada conforme [sprint12.md](sprint12.md), com execução registrada em [sprint12-validacao.md](sprint12-validacao.md). A Sprint 13 está implementada conforme [sprint13.md](sprint13.md), com execução registrada em [sprint13-validacao.md](sprint13-validacao.md). Os documentos seguintes continuam previstos; o próximo será **`sprint14.md`**, antes de iniciar sua implementação.

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
