# ReplayQuant — Sprints 06 a 11

Laboratório educacional de replay Spot em Python, com candles fictícios e ordens
manuais ou sinais SMA, EMA e RSI, com BTC/USDT e ETH/USDT fictícios. Mostra como um relógio simulado transforma solicitações em
preenchimentos, taxas e saldos. Funciona localmente com a biblioteca padrão,
sem rede ou credenciais. A Sprint 09 acrescenta risco e reservas pelo schema 4;
veja [Risco e saídas protetivas](#sprint-09--risco-e-saídas-protetivas). A Sprint 10 introduz estratégias modulares versionadas pelo schema 5.

## Preparação e demonstração

Execute na raiz deste repositório. Python **3.11+** é declarado como requisito;
a versão de referência e efetivamente validada é **3.12.14**. Não é necessário
instalar pacotes; `requirements.lock` registra a ausência de dependências externas.

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m replayquant --help
python -m replayquant demonstrar --formato texto
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --formato html > /tmp/replayquant-demonstracao.html
python -m unittest discover -s tests -v
```

A demonstração lê `data/fixtures/sprint06-candles.json` e
`experiments/sprint06-manual.json`, sem gravar arquivos. O texto explica as
fórmulas; JSON em stdout contém somente o relatório estruturado. Diagnósticos
ficam em stderr. O caso principal confere os resultados antes de retornar sucesso.

Use `--formato html` para gerar um relatório profissional independente, no mesmo
estilo do RiskGate: indicadores financeiros, tabelas de ordens e preenchimentos,
memória de cálculo e limitações. Abra o arquivo `.html` no navegador; para
imprimir ou salvar em PDF, use a opção **Imprimir**. O documento tem layout
adaptado a telas menores e impressão. O relatório manual legado sem análise não usa scripts; SMA, análise e risco
incorporam o JavaScript dos gráficos, sem buscar fontes ou recursos na internet.
Os valores usam vírgula decimal, preservando todos os dígitos do relatório.

| Etapa | Caixa USDT | Posição BTC |
| --- | --- | --- |
| Inicial | 1000 | 0 |
| Compra de 0.001 BTC a 100000, taxa 0.1 USDT | 899.9 | 0.001 |
| Venda a 101000, taxa 0.101 USDT | 1000.799 | 0 |

Taxas totais: **0.201 USDT**. Resultado líquido da ida e volta:
`100.899 - 100.1 = 0.799 USDT`. Esses números conferem a mecânica do simulador;
não avaliam desempenho de uma estratégia. USDT não é o próprio dólar.

## Executar arquivos e salvar resultados

```bash
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida runs/sprint06-manual --formato texto
```

Para salvar o HTML e os artefatos da mesma execução, escolha uma saída nova e
redirecione stdout para um arquivo fora desse diretório:

```bash
relatorios_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint06-candles.json --config experiments/sprint06-manual.json --saida "$relatorios_dir/execucao" --formato html > "$relatorios_dir/relatorio.html"
```

O shell cria o arquivo redirecionado antes de executar o programa. Por isso,
não redirecione para dentro de `--saida`, que precisa ser um caminho novo.
Confira o código de saída: 2 indica replay com bloqueios por política, rejeições
ou ordens não executadas, com relatório disponível; 1 indica falha técnica ou de
entrada, incluindo interrupção por lacuna no modo SMA.

A saída deve ser um caminho novo. O comando cria diretórios pais necessários,
mas recusa diretório, arquivo ou symlink já existente. Para repetir, escolha
outro nome; nenhum comando apaga resultados anteriores. Estrutura e domínio são validados
antes da simulação e da criação da saída; continuidade no modo SMA é conferida
progressivamente para preservar o prefixo anterior a uma lacuna.

Sem `--analise`, são produzidos `manifest.json`, `events.jsonl` e `report.json`. O manifesto inclui
hashes SHA-256 dos bytes de entrada e do código, versão Python real, política
financeira e modelo de execução. `run_id` depende desses conteúdos, sem caminhos
absolutos, hora real ou metadados Git. O diretório conterá `INCOMPLETE` durante a
gravação; só consuma artefatos quando houver manifesto e esse marcador estiver
ausente. Falha de escrita retorna erro técnico e pode deixar arquivos incompletos,
que devem ser preservados para diagnóstico e não representam execução persistida
com sucesso.

`--formato texto|json|html` controla stdout nos dois subcomandos; texto é o padrão.
O HTML vai somente para stdout e pode ser salvo por redirecionamento. Sem
`--analise`, os três artefatos persistidos continuam usando
schema JSON v1 no modo manual e v2 no modo SMA, decimais como strings e datas UTC
com microssegundos. Campos
inaplicáveis são `null` acompanhados de motivo. O log registra fases de mercado,
submissões, aceitações/rejeições, preenchimentos e encerramento, incluindo saldos
antes/depois dos preenchimentos.

| Código de saída | Significado |
| --- | --- |
| 0 | Replay concluído sem bloqueios por política ou ordens rejeitadas/não executadas; inclui roteiro vazio e aquecimento sem sinais |
| 1 | Dados/configuração inválidos, aritmética inexata, falha técnica ou saída existente; lacuna SMA gera relatório parcial identificado |
| 2 | Replay concluído com decisão bloqueada por política ou ordem rejeitada/não executada; os artefatos preservam o diagnóstico |

Erros de sintaxe do `argparse` também retornam 2, sem iniciar o replay. Exceções
inesperadas propagam com traceback; não são convertidas em rejeição de ordem.

## Contratos e modelo

Os contratos estão em [Sprint 06](docs/sprint06.md), [Sprint 07](docs/sprint07.md) e
[Sprint 08](docs/sprint08.md). Cada candle
fechado de um minuto tem origem/par/intervalo, início/fim, OHLC, volume base e
`is_closed=true`. Os arquivos contêm exatamente as chaves documentadas.
Decimais de entrada usam ponto, sem expoentes/espaços, até 18 dígitos no coeficiente
e expoente decimal absoluto até 12. Datas exigem fuso e são normalizadas para UTC.
JSON com chave duplicada, versão booleana, não finitos ou campos extras é inválido.
A API Python valida seus modelos mesmo sem passar pelo leitor JSON.

A ordem das fases é fechamento → submissões manuais → abertura seguinte →
preenchimento. Timestamp igual não significa evento igual: `seq` define a ordem
lógica. Na abertura, o motor recebe apenas horário, identidade e preço `open`;
o OHLCV completo é liberado no fechamento. Não há acesso antecipado aos extremos,
fechamento ou volume final para preencher uma ordem.

Nos modos legados, há uma pendência por vez e uma posição de quantidade fixa. Aceitar uma ordem não
debita nem reserva. Uma compra exige BTC zero e caixa estimado com taxa no
fechamento; uma venda exige BTC suficiente. O motor revalida na abertura e rejeita
integralmente se o preço efetivo tornar o caixa insuficiente. Posição e caixa só
mudam em um preenchimento válido. Não há venda descoberta ou saldo negativo.

Estados: `NEW`, `FILLED`, `REJECTED` e `UNEXECUTED`. Sem abertura futura, ordem
aceita termina `UNEXECUTED/NO_FUTURE_OPEN`. Não há liquidação automática de posição
aberta. O resultado de ida e volta só é informado para exatamente uma compra e
uma venda integral; outros roteiros conservam saldos, taxas e execuções, sem
inventar esse resultado agregado.

Cada preenchimento usa `bruto = preço × quantidade` e `taxa = bruto × alíquota`.
Compra debita bruto + taxa; venda credita bruto − taxa. Cálculos usam contexto
local `Decimal`, precisão 40 e `ROUND_HALF_EVEN`; resultado inexato é erro antes
da alteração financeira. Saldos derivados podem ter mais dígitos que as entradas,
desde que representáveis exatamente. Contexto decimal externo é preservado.

Duplicatas equivalentes de candle não geram outro evento de mercado; o diagnóstico
fica no log. Conflitos e séries fora de ordem impedem o início do replay. Lacunas
impedem o início no modo manual; no SMA, interrompem na primeira fronteira ausente
e preservam a carteira e a pendência sem incorporar o candle posterior. Repetir ordem/execução idêntica é inócuo; ID reutilizado com outro conteúdo
é erro. Deduplicação é local em memória e não oferece recuperação após reinício.

O preenchimento total supõe liquidez ilimitada, sem limite pelo volume do candle.
Não há modelo de spread; slippage é zero no modo manual e uma fração fixa adversa
no SMA. Essas configurações são hipóteses fictícias sobre execução. Não se descontam spread/slippage novamente dos resultados.

## Organização e API

- `validation.py`, `models.py`, `data.py`: contratos, JSON e pré-validação integral.
- `execution.py`, `portfolio.py`: custos e cálculo atômico de novos saldos.
- `engine.py`: `replay(candles, config)`, `Session` manual e `SMASession`, com fases explícitas.
- `strategies.py`: `SMACross`, histórico limitado à janela longa e comparação por razões exatas.
- `reporting.py`, `__main__.py`: identidade, relatórios, arquivos e CLI.
- `html_report.py`: documento HTML independente, responsivo e com estilo de impressão.
- `tests/test_sprint06.py`: testes financeiros, temporais, de erros e reprodução.
- `tests/test_html_report.py`: HTML, cálculos, segurança de apresentação e contratos da CLI.
- `tests/test_sprint07.py`: SMA, causalidade, slippage, lacunas, pendências e CLI versão 2.

Modelos são registros imutáveis. `Session` expõe snapshots de consulta; alterações
passam por `on_open(Opening)`, `on_close(Candle)`, `submit(Request)`,
`apply_fill(Fill)` e `finish()`. O replay utiliza esse mesmo núcleo. Não altere
atributos privados de uma sessão nem substitua sua configuração durante a execução.

Consulte o [planejamento](docs/planejamento.md), o
[glossário](docs/sprint06-glossario.md) e os
[resultados de validação](docs/sprint06-validacao.md).

Risco e reservas operacionais estão disponíveis no modo opt-in da Sprint 09.
Dados reais continuam previstos para sprints posteriores. A Sprint 08 acrescenta ledger, marcação e métricas com `--analise`. Esta entrega não conecta exchanges nem recomenda operações.


## Estratégia SMA — Sprint 07

Com `.venv` ativada, execute:

```bash
python -m replayquant demonstrar --estrategia sma --formato texto
python -m replayquant demonstrar --estrategia sma --formato json
python -m replayquant demonstrar --estrategia sma --formato html > /tmp/replayquant-sprint07.html
python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint07-sma.json --saida runs/sprint07-sma --formato texto
```

A demonstração confere oito avaliações, dois sinais e dois preenchimentos. Com
janelas 2/3, quantidade 0.001 BTC, taxa e slippage 0.001, compra a 100100 e vende a
99900 USDT/BTC. Taxas totais 0.2 USDT; caixa final **999.6 USDT**; resultado líquido
**-0.4 USDT**. O prejuízo fictício é um resultado esperado do teste de correção.

`experiments/sprint07-sma.json` usa schema 2, com `strategy` contendo `name:
SMA_CROSS`, `short_window` e `long_window`, inteiros `1 <= curta < longa`; não
aceita `orders`. Schema 1 conserva o roteiro manual e slippage zero. `executar`
seleciona o modo pela configuração; `--estrategia sma` pertence a `demonstrar`.
A API usa `SMAConfig`/`SMAParameters` ou `Config`/`Request`, respectivamente.
`load_inputs` carrega os arquivos; `replay` despacha pelo tipo da configuração.

A estratégia só recebe fechamentos liberados. Precisa de `longa + 1` candles
contíguos para comparar médias anterior/atual. BUY ocorre de curta <= longa para
curta > longa; SELL de curta >= longa para curta < longa. Igualdade atual e
permanência não repetem sinal. As decisões usam `Fraction` exato; a exibição de
médias no relatório preserva numerador/denominador, sem influenciar a decisão.

A sequência é fechamento → avaliação → sinal → decisão → intenção/ordem →
abertura seguinte → preenchimento. `seq` distingue eventos no mesmo timestamp
UTC, por convenção de latência zero. O slippage multiplica open por `1+a` na
compra e `1-a` na venda, e a taxa incide sobre o bruto efetivo. A estimativa no
fechamento já inclui ambos; caixa e posição são revalidados no preenchimento.
Uma rejeição não gera nova tentativa sem novo cruzamento.

Para alimentar eventos progressivamente, use `SMASession(config)` com
`on_open(candle.opening())`, `on_close(candle)` e `finish()`. `handle_signal` é a
fronteira de integração de sinais identificados na fase de fechamento, com
idempotência e decisão por política; o replay normal chama essa fronteira a
partir do cruzamento SMA. `submit` não aceita ordens manuais novas nesse modo.
Não passe o candle completo a `on_open` nem mude a configuração durante a sessão.

Em uma lacuna, a sessão fica `INTERRUPTED` com `DATA_GAP`, antes da abertura
posterior. `report` e `executar` preservam relatório parcial, saldos e ordem
pendente `NEW`, com código 1. A ordem não vira `NO_FUTURE_OPEN`. Corrija/versione
os dados e inicie nova execução; a sessão interrompida não continua. O manifesto
identifica o arquivo completo, inclusive o trecho não processado. No encerramento
normal sem abertura futura, a ordem termina `UNEXECUTED/NO_FUTURE_OPEN`, código 2.

O relatório inclui avaliações, comparações exatas, sinais, decisões, intenções,
ordens, preços de referência/efetivos e execuções. Não há lucro inventado para
posição aberta nem liquidação automática. Veja as [regras SMA](docs/estrategias/sma.md),
o [glossário](docs/sprint07-glossario.md) e a [validação](docs/sprint07-validacao.md).


### Gráfico de candles no HTML SMA

A saída `demonstrar --estrategia sma --formato html` inclui um gráfico interativo
com **TradingView Lightweight Charts 5.2.0**. O bundle JavaScript, os dados e os
avisos de licença estão incorporados no próprio HTML; não há CDN, API ou download
ao abrir o relatório. O mesmo gráfico aparece em `executar` com configuração SMA
e formato HTML.

Use o link **Gráfico**, arraste para navegar e use a roda do mouse ou os botões
**Zoom +**, **Zoom −**, **Ver tudo** e **Últimos 60** para ajustar o período.
O eixo de preços fica fixo à esquerda e o cursor mostra linhas de referência de
preço/tempo. A grade vertical é pontilhada. Ao mover o cursor, os detalhes abaixo
do gráfico mostram OHLCV, preço efetivo, quantidade, taxa e resultado da execução
naquele candle com os valores exatos do replay. Os números convertidos para
JavaScript são usados somente no desenho do gráfico.

O gráfico exige JavaScript habilitado; as tabelas e os resultados continuam
legíveis sem ele. A impressão captura a visualização atual do Canvas como imagem;
use **Ver tudo** antes de imprimir para incluir todo o período.

Os marcadores **COMPRA** (azul) e **VENDA** mostram o horário e preço efetivo dos
preenchimentos, incluindo slippage. Sinais bloqueados, ordens rejeitadas e ordens
sem abertura futura não recebem marcador. A ligação entre compra e venda e o
resultado de cada ida e volta ficam verdes para ganho líquido, vermelhos para
perda e cinzas para empate. O cálculo usa recebimento da venda após taxa menos
desembolso da compra com taxa, sem descontar slippage novamente. A cor verde ou
vermelha do candle representa sua variação de preço, independentemente do lucro.
Posições abertas não recebem resultado realizado.

O campo adicional `candles` do relatório SMA schema 2 contém apenas fechamentos
processados. Isso permite reconstruir o gráfico a partir de `report.json`,
inclusive do prefixo preservado em uma interrupção por lacuna. O relatório
manual schema 1 mantém seu formato.


### Cenário SMA com 240 candles

Para explorar um gráfico mais longo, use
`data/fixtures/sprint07-candles-expandido.json` e
`experiments/sprint07-sma-expandido.json`. O cenário tem **240 candles de um
minuto**, em **01/01/2026 das 12:00 às 16:00 UTC**, com altas, quedas, pavios,
pequenas diferenças entre fechamentos/aberturas e volume variável. Os preços
partem de aproximadamente 100000 USDT/BTC. São dados sintéticos, sem calibração
a um mercado real, gerados com aritmética inteira em centavos e semente local 7,
com reversão final controlada de semente 707. O replay lê somente o JSON fixo e
não usa aleatoriedade. A fixture foi construída para mostrar operações vencedoras
e perdedoras com saldo final positivo, como exemplo visual solicitado.

A configuração usa janelas SMA **9/21**, quantidade 0.001 BTC, capital inicial
1000 USDT, taxa 0.001 e slippage 0.001. Os parâmetros foram mantidos; a trajetória
sintética foi ajustada deliberadamente para a demonstração, sem evidência de
rentabilidade em mercado real. O arquivo de oito candles continua sendo a conferência manual
usada por `demonstrar --estrategia sma` e pelos testes.

Com `.venv` ativada, escolha um diretório de saída novo:

```bash
cenario_sma_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint07-sma-expandido.json --saida "$cenario_sma_dir/execucao" --formato html > "$cenario_sma_dir/relatorio.html"
```

Abra `relatorio.html` no navegador e use zoom ou arraste para explorar os candles. Na validação deste cenário houve 240 avaliações, seis preenchimentos
e três idas e voltas encerradas, com código 0 e posição final zerada:

| Operação | Compra UTC | Venda UTC | Resultado líquido USDT |
| --- | --- | --- | --- |
| 1 | 12:38 | 13:25 | +0.73754871919 |
| 2 | 14:20 | 15:02 | +0.77489849630 |
| 3 | 15:26 | 15:39 | -0.61089654715 |
| Total | — | — | **+0.90155066834** |

O saldo final é **1000.90155066834 USDT**, BTC zero, com taxas totais de
**0.60339361166 USDT**. Os resultados já incluem taxas de ambas as pontas e
slippage nos preços efetivos. O resumo HTML e o gráfico exibem a soma realizada
em verde, além dos resultados individuais verdes/vermelhos. O campo JSON
`round_trip_result` mantém seu contrato de uma única ida e volta e fica
indisponível para múltiplas operações; os preenchimentos e cálculos permitem
reconciliar o total mostrado no HTML.


### Biblioteca incorporada e reprodução

Os arquivos em `replayquant/assets/` contêm a versão fixa da biblioteca, o
controlador local, LICENSE/NOTICE e a licença MIT de fancy-canvas 2.1.0, incluído
no bundle. Fontes, integridade SHA-512 dos pacotes npm e hashes SHA-256 dos arquivos
vendorizados estão em `lightweight-charts-vendor.json`. Não é necessário instalar
Node/npm, pacotes Python ou conectar à internet para executar o projeto.

A atribuição à TradingView e os textos de licença estão no HTML. Consulte a
[documentação oficial](https://tradingview.github.io/lightweight-charts/docs)
e os [termos do projeto](https://github.com/tradingview/lightweight-charts).
O motor de replay continua usando apenas biblioteca padrão e `Decimal`/razões
exatas. A dependência JavaScript é exclusiva da apresentação HTML SMA.

O manifesto passa a incluir todos os arquivos de `replayquant/assets/` na lista
ordenada `code_files`, além dos arquivos Python e metadados já definidos. Assim,
alterar o bundle, o controlador ou as licenças também altera `code_hash`/`run_id`.
O manifesto SMA registra a biblioteca em `frontend_dependencies`; hashes dos
candles/configuração e resultados financeiros continuam com seus contratos.


## Ledger, patrimônio e métricas — Sprint 08

Ative a análise com `--analise`; a estratégia e a configuração continuam sendo
selecionadas como antes. Sem a flag, formatos e schemas anteriores permanecem.

```bash
source .venv/bin/activate
python -m replayquant demonstrar --analise --formato texto
python -m replayquant demonstrar --analise --formato json
python -m replayquant demonstrar --analise --formato markdown
python -m replayquant demonstrar --estrategia sma --analise --formato html > /tmp/replayquant-sprint08.html
python -m unittest discover -s tests -v
```

A demonstração manual confere os valores obrigatórios: caixa final **1000.799
USDT**, realizado **0.799 USDT**, taxas **0.201 USDT**, retorno patrimonial
**0.0799%** e retorno do trade **0.798201798202%**. O máximo drawdown é
**0.010090918174%**, a maior duração observada é **60 segundos**, e a exposição
é **60 de 180 segundos**. A queda da taxa na compra aparece na curva antes da
valorização; a taxa de venda cria outra queda depois do pico.

O ledger registra saldo inicial e cada preenchimento integral. Caixa e BTC são
projeções desses movimentos; a base de custo inclui a taxa de compra. Uma venda
realiza recebimento após taxa menos base de custo. Rejeições, sinais e ordens
não executadas não criam movimentos financeiros. O núcleo é o mesmo nos modos
manual/SMA, por arquivo ou pela API incremental.

A análise reconcilia, em cada ponto:

```text
patrimônio bruto = caixa total + BTC × preço disponível
patrimônio bruto = capital inicial + realizado + não realizado bruto
```

A curva inclui INITIAL, OPEN antes do fill, FILL depois do preenchimento e CLOSE.
A marca de um fill é o open de referência, preservando o impacto do slippage.
Caixa reservado é zero nesta etapa; reservas não são contadas duas vezes.

**KEEP_OPEN** mantém posição aberta no término. O patrimônio bruto marcado é
separado do valor líquido hipotético de liquidação, que considera slippage/taxa
de saída sem enviar ordem, cobrar taxa ou zerar BTC. Com só a compra do exemplo
e último close 101000, há caixa 899.9, BTC 0.001, realizado zero, não realizado
0.9, patrimônio 1000.9 e liquidação hipotética 1000.799 USDT. A taxa de saída
hipotética 0.101 USDT é distinta da taxa 0.1 já paga.

Os relatórios incluem realizado/não realizado, retornos, taxas, impacto de
slippage, contagens de ganhos/perdas/empates, acerto, expectativa amostral,
drawdown e sua duração, tempo em posição e referências. Sem trades, acerto e
expectativa são indisponíveis com `NO_CLOSED_TRADES`; retorno e drawdown zero
continuam válidos quando há patrimônio e horizonte conhecidos. Os percentuais e
a expectativa preservam razões exatas e exibem 12 casas com HALF_EVEN, sem
contaminar a contabilidade ou classificar um lucro pequeno como empate.

As referências são carteiras independentes: **HOLD_USDT** mantém o capital sem
juros; **BUY_HOLD_BTC** compra na primeira abertura, com os mesmos custos, usando
quase todo o caixa. Sua quantidade é arredondada para baixo por razão exata ao
quantum ilustrativo 0.000000000001 BTC. Ele mantém BTC aberto, com patrimônio bruto
e liquidação hipotética separados. Na fixture manual, termina com patrimônio
bruto **1008.991008991 USDT** e liquidação hipotética **1007.98201798201 USDT**.
As exposições diferem da quantidade fixa da estratégia; não somar saldos das
referências ou interpretar a comparação curta como ranking de investimento.

Para salvar a análise, escolha uma saída nova:

```bash
analise_sprint08_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint08-candles.json --config experiments/sprint08-manual.json --analise --saida "$analise_sprint08_dir/execucao" --formato json
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint07-sma-expandido.json --analise --saida "$analise_sprint08_dir/sma" --formato html > "$analise_sprint08_dir/sma.html"
```

Com a flag, são produzidos **nove arquivos**: `manifest.json`, `events.jsonl`,
`report.json`, `ledger.jsonl`, `equity.csv`, `trades.csv`, `metrics.csv`,
`benchmarks.csv` e `report.md`. Sem a flag, continuam os três arquivos anteriores.
`markdown` exige `--analise`; combinação inválida retorna 2 antes do replay.
JSON/JSONL enriquecidos usam schema 3; os schemas de entrada não mudam.
`round_trip_result` conserva o contrato legado; os novos resultados ficam em
`analysis.metrics`, `closed_trades` e `open_position`.

O manifesto inclui `analysis_policy: SPRINT08_V1` na identidade canônica, além
dos hashes de dados/configuração/código e Python real. A flag altera `run_id`;
diretório de saída e hora real não participam da identidade. Os assets, incluindo
o controlador das curvas, entram no hash do código. Duas execuções iguais em
pastas distintas devem coincidir nos nove arquivos byte a byte.

CSV usa UTF-8, vírgula, ponto decimal e linhas LF. Dados indisponíveis são células
vazias com motivo; sem trades, o arquivo contém apenas cabeçalho. Ordem completa
das colunas:

`equity.csv`:

```text
schema_version,run_id,portfolio,point_seq,at,source_event_seq,phase,cash_total,cash_available,cash_reserved,asset_quantity,mark_price,mark_at,mark_reason,cost_basis,realized_pnl,unrealized_pnl,gross_equity,hypothetical_liquidation_equity
```

`trades.csv`:

```text
schema_version,run_id,trade_id,lot_id,buy_execution_id,sell_execution_id,buy_at,sell_at,quantity,buy_price,sell_price,buy_gross,sell_gross,buy_fee,sell_fee,cash_outflow,cash_inflow,net_pnl,return_pct,return_numerator,return_denominator,duration_seconds,classification
```

`metrics.csv`:

```text
schema_version,run_id,scope,metric,value,unit,reason,numerator,denominator
```

`benchmarks.csv`:

```text
schema_version,run_id,portfolio,status,reason,observation_start,observed_until,initial_cash,final_cash,asset_quantity,paid_fees,gross_equity,hypothetical_liquidation_equity,return_pct,return_reason,hypothetical_return_pct,hypothetical_return_reason,time_in_position_seconds,time_in_position_pct
```

As curvas são ordenadas por carteira STRATEGY/HOLD_USDT/BUY_HOLD_BTC e point_seq;
trades pela sequência de saída; métricas por nome. O ledger JSONL é ordenado por
horário, evento de origem, carteira e sequência local. Cada linha identifica
schema/experimento/carteira; os saldos virtuais nunca se misturam.

O HTML enriquecido mantém os candles SMA e acrescenta três curvas patrimoniais
com a biblioteca já incorporada, sem CDN. O eixo horizontal representa **índice
de evento**, com UTC nos detalhes: duas alterações do mesmo horário continuam
em pontos distintos. Cada carteira tem sua própria sequência; o espaçamento
visual não representa tempo decorrido. Os valores exatos ficam nas tabelas,
e a impressão captura os Canvas. JavaScript desabilitado preserva as tabelas.

Interrupção por lacuna SMA gera código 1 e `analysis.scope: ACCEPTED_PREFIX`:
ledger, pendência e referências param antes da abertura posterior. A última marca
pertence ao prefixo e não é preço negociável depois da lacuna. No término normal,
ordem sem abertura futura permanece não executada (código 2). Métrica indefinida
por ausência de trades não transforma uma execução válida em falha.

API para análise de arquivos, usando o mesmo ledger da sessão:

```python
from replayquant.data import load_inputs
from replayquant.engine import replay
from replayquant.reporting import manifest, report

inputs = load_inputs("data/fixtures/sprint08-candles.json", "experiments/sprint08-manual.json")
metadata = manifest(inputs, analysis=True)
session = replay(inputs.candles, inputs.config, metadata["run_id"], inputs.diagnostics)
summary = report(session, analysis=True)
ledger = session.ledger  # entradas imutáveis; não altera o estado aceito
```

O ledger é integrado aos fills em todos os modos. A análise projeta a curva em
consulta, lendo exclusivamente o ledger comprometido e o prefixo de eventos
aceitos, sem executar operações de novo. `Session`/`SMASession` progressivas usam
o mesmo núcleo. `report` valida o encerramento normal ou a interrupção identificada.
Os formatos e exportações da análise podem ser reconstruídos de `report.json`
sem reler dados de mercado.

Veja a [validação](docs/sprint08-validacao.md) e o
[glossário](docs/sprint08-glossario.md). O modelo é fictício, local e sem
anualização, aportes ou liquidação forçada; reservas operacionais são exclusivas do modo da Sprint 09.


## Sprint 09 — Risco e saídas protetivas

A configuração **schema 4** ativa dimensionamento, reservas e stop/alvo com análise
obrigatória. Os schemas manuais 1 e SMA 2 mantêm sua semântica e continuam com
saída enriquecida 3 somente quando `--analise` for solicitado. O código evoluiu,
portanto os hashes de código e IDs de execução também mudam; seus algoritmos
anteriores foram preservados.

Na raiz, com `.venv` ativada:

```bash
python -m replayquant demonstrar --risco --formato texto
python -m replayquant demonstrar --risco --formato json
python -m replayquant demonstrar --risco --formato markdown
python -m replayquant demonstrar --risco --estrategia sma --formato json
```

Todos os comandos retornam **0**. A demonstração SMA usa step e mínimo fictícios
de 0.000001 BTC: compra/vende 0.000962 BTC, paga 0.1924 USDT em taxas e termina
com 999.8076 USDT e BTC zero. Um teste com filtros maiores (0.001 BTC) preserva
a cobertura de rejeição por `BELOW_MINIMUMS` e `INSUFFICIENT_ASSET`.

Salvar onze artefatos e um HTML em caminhos novos:

```bash
relatorios_sprint09_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint09-candles.json --config experiments/sprint09-manual.json --saida "$relatorios_sprint09_dir/execucao" --formato html > "$relatorios_sprint09_dir/relatorio.html"
```

Para comparar alvo, ambiguidade e gap, use as fixtures alternativas com a mesma
configuração manual. O bloco abaixo cria uma pasta temporária própria, com um
HTML e um diretório de artefatos para cada cenário:

```bash
cenarios_sprint09_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint09-candles-alvo.json --config experiments/sprint09-manual.json --saida "$cenarios_sprint09_dir/alvo" --formato html > "$cenarios_sprint09_dir/alvo.html"
python -m replayquant executar --dados data/fixtures/sprint09-candles-ambiguo.json --config experiments/sprint09-manual.json --saida "$cenarios_sprint09_dir/ambiguo" --formato html > "$cenarios_sprint09_dir/ambiguo.html"
python -m replayquant executar --dados data/fixtures/sprint09-candles-gap.json --config experiments/sprint09-manual.json --saida "$cenarios_sprint09_dir/gap" --formato html > "$cenarios_sprint09_dir/gap.html"
```

Os três comandos retornam **0**, com compra de **0.000981 BTC** e posição final
zerada. No alvo, a venda ocorre a 120000 e o caixa final é **1019.40418 USDT**.
No cenário ambíguo, o candle toca stop e alvo; a convenção **STOP_FIRST** resolve
a venda a 90000, com caixa final **990.00361 USDT**. No gap, a abertura a 80000 define
a execução do stop, com caixa final **980.20342 USDT**: a perda realizada supera
o orçamento planejado de 10 USDT. A tabela abaixo detalha resultados e taxas.

Para executar `experiments/sprint09-sma.json`, combine-o com os candles da
Sprint 07, usados também pela demonstração SMA com risco:

```bash
sma_sprint09_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint09-sma.json --saida "$sma_sprint09_dir/execucao" --formato html > "$sma_sprint09_dir/relatorio.html"
echo "Código de saída SMA: $? (esperado: 0)"
```

Esse exemplo usa janelas SMA **2/3**, produz oito avaliações, dois sinais e dois
preenchimentos. O código esperado é **0**, com caixa final **999.8076 USDT**,
BTC zero e taxas de **0.1924 USDT**.

### Exemplo lucrativo com 240 candles e risco

Use `experiments/sprint09-sma-expandido.json` com a fixture
`data/fixtures/sprint07-candles-expandido.json`, reutilizada sem alterações.
A configuração schema 4 combina SMA **9/21**, capital de **1000 USDT**,
taxa e slippage de **0.001** cada. Mantém os controles do Sprint 09:
risco de 1% por entrada, exposição máxima de 100%, stop de 10%, alvo de 20%,
limite de perda diária de 3%, drawdown de 5% e validade do preço de 60 segundos.
O lote é dimensionado pelo risco, com step e mínimo de 0.000001 BTC.

```bash
sma_lucrativo_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint09-sma-expandido.json --saida "$sma_lucrativo_dir/execucao" --formato html > "$sma_lucrativo_dir/relatorio.html"
```

Resultado validado: código **0**, 240 avaliações, seis preenchimentos,
três operações encerradas e posição final zerada. Todas as saídas ocorrem
por sinal SMA; stop e alvo ficam ativos, mas não são tocados neste cenário.

| Operação | Compra UTC | Venda UTC | Quantidade BTC | Lucro líquido USDT |
| --- | --- | --- | --- | --- |
| 1 | 12:38 | 13:25 | 0.000981 | +0.72353529352539 |
| 2 | 14:20 | 15:02 | 0.000983 | +0.76172522186290 |
| 3 | 15:26 | 15:39 | 0.000971 | -0.59318054728265 |

Caixa final: **1000.89207996810564 USDT**. Lucro realizado:
**0.89207996810564 USDT**, retorno de aproximadamente **0.089208%**.
Taxas totais: **0.59031179959436 USDT**; impacto de slippage:
**0.59031387230 USDT**, ambos já considerados no resultado líquido.
As operações acontecem em 01/01/2026. Trata-se de uma demonstração com dados
sintéticos construídos para um saldo positivo, sem evidência de rentabilidade
em mercado real. O dimensionamento variável explica a diferença em relação
ao exemplo da Sprint 07, que usa quantidade fixa.

### Sprint 09 com resultado equivalente ao Sprint 07

A configuração `experiments/sprint09-sma-equivalente-sprint07.json` deriva do
exemplo expandido acima. Altera somente `risk_fraction` para **0.011** (1,1%)
e os filtros `step`/`min_quantity` para **0.001 BTC**. Nos 240 candles de
`data/fixtures/sprint07-candles-expandido.json`, o orçamento permite candidatos
entre 0.001 e 0.002 BTC; o arredondamento para baixo pelo step resulta em
**0.001 BTC nas três compras**, reproduzindo o lote fixo do Sprint 07.
Taxas, slippage, janelas SMA e demais parâmetros de risco permanecem iguais
aos do exemplo expandido do Sprint 09.

```bash
sma_equivalente_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint09-sma-equivalente-sprint07.json --saida "$sma_equivalente_dir/execucao" --formato html > "$sma_equivalente_dir/relatorio.html"
```

Neste cenário, ambos produzem seis fills com os mesmos horários, lados,
quantidades, preços e taxas: lucro líquido de **0.90155066834 USDT**, taxas
**0.60339361166 USDT**, caixa final **1000.90155066834 USDT**, BTC zero e código
**0**. A equivalência é financeira; schema, identificadores e registros de risco
continuam distintos. O Sprint 09 mantém o dimensionamento por risco e suas
proteções: outros candles ou capital inicial podem produzir lotes diferentes,
rejeições ou saídas por stop/alvo. Esses filtros são fictícios para a demonstração.

As fixtures manuais da Sprint 09 usam a mesma escala de preços das sprints
06–08: referência inicial de 100000 USDT/BTC. Seus OHLC foram multiplicados
por 1000 e os filtros step/mínimo divididos por 1000 (0.000001 BTC), preservando
os valores em USDT dos cenários manuais. A unidade continua USDT/BTC; os dados
são fictícios. As duas configurações da Sprint 09 usam esses mesmos filtros.

`executar` reconhece o modo pelo schema da configuração; não recebe `--risco`.
`demonstrar --risco` não grava artefatos. `--analise` é redundante no schema 4 e
não muda resultados, artefatos ou identidade. Os quatro formatos são permitidos
nesse modo, inclusive Markdown sem `--analise`. A API `manifest(inputs)` e
`report(session)` ativa a análise automaticamente; passar explicitamente
`analysis=False` para configuração de risco é erro. O parâmetro continua sendo
booleano real quando informado.

A configuração completa está em `experiments/sprint09-manual.json`. Não há campo
`quantity`: cada BUY calcula a quantidade e cada SELL encerra o lote integral.
O modo manual admite BUY, SELL e CANCEL no fechamento; CANCEL tem
`target_order_id` e só cancela pendência comum. O schema 4 em modo SMA substitui
`orders` por `strategy`. Filtros de instrumento e percentuais são fictícios.
Veja campos, faixas e contratos na [especificação](docs/sprint09.md).

Com patrimônio P, caixa disponível B, exposição X, entrada estimada E, stop S,
alíquota f e orçamento R=P×r, a perda unitária planejada é
`L=E×(1+f)−S×(1−f)`. A quantidade é o menor limite de risco R/L, exposição
`max(0,P×x−X)/E` e saldo `B/(E×(1+f))`, ajustado para baixo em múltiplos exatos
do step. Razões preservam numerador/denominador; não se usam valores arredondados
ou floats para decidir. Um mínimo não autoriza aumentar a compra.

| Cenário fictício | q BTC | Caixa final USDT | Resultado realizado USDT | Taxas USDT |
| --- | --- | --- | --- | --- |
| Stop a 90000 | 0.000981 | 990.00361 | -9.99639 | 0.18639 |
| Gap: stop executado a 80000 | 0.000981 | 980.20342 | -19.79658 | 0.17658 |
| Alvo a 120000 | 0.000981 | 1019.40418 | 19.40418 | 0.21582 |
| Ambos os níveis: STOP_FIRST | 0.000981 | 990.00361 | -9.99639 | 0.18639 |

Capital inicial 1000, orçamento 10, compra a 100000, stop 90000, alvo 120000 e taxa 0.001.
Aceitar BUY reserva 98.1981 USDT, preservando caixa total e patrimônio. Preencher
consome o desembolso, abre BTC 0.000981 e cria **uma** reserva de BTC compartilhada
por stop e alvo. Disponível + reservado = total em cada moeda; não somar reserva
ao patrimônio novamente. Cancelar/rejeitar/liberar não cobra taxa nem inventa fill.
Abertura favorável devolve a diferença; desfavorável revalida risco/caixa antes de
qualquer débito. R, S, T e q ficam congelados na aprovação; falha de revalidação
rejeita integralmente e libera, sem redimensionar silenciosamente.

A proteção só é elegível no candle seguinte ao da entrada: existe uma janela
sem atuação. Na abertura, gap protetivo tem prioridade sobre venda comum; depois
vêm SELL comum e BUY revalidado. No intervalo, a execução recebe o OHLC completo
antes de CLOSE chegar à estratégia. Um único toque usa S ou T; ambos usam
STOP_FIRST com ambiguidade explícita. A referência recebe slippage adverso e taxa
uma única vez. Gap usa o open, não um stop ficticiamente garantido.

`BAR_CLOSE_RESOLUTION` indica saída resolvida no fechamento do intervalo, com
horário intraperíodo desconhecido. O marcador fica nesse horário modelado, e
trade/duração/exposição refletem a aproximação. A curva não transforma máximas
e mínimas em caminho observado. Nova BUY no fechamento do candle de uma saída é
bloqueada; é necessário um novo sinal/solicitação posterior.

Perda diária usa a primeira observação positiva do dia UTC; atingir o limite
bloqueia entradas até a virada do dia, mesmo com recuperação. Drawdown usa o pico
da sessão e seu bloqueio persiste até o fim do experimento. Reservas não provocam
perda. Saídas e proteções permanecem permitidas sob esses bloqueios. Sem base
positiva, usar indisponibilidade com motivo, sem dividir por zero.

Os códigos continuam 0/1/2. Stop/alvo/cancelamento válido são operações normais;
rejeição de entrada/cancelamento inválido/ordem sem abertura futura retorna 2;
erro técnico/dados inválidos/lacuna retorna 1. Perda realizada superior ao
orçamento não é erro do simulador. Posição final mantém KEEP_OPEN. No término
normal, reservas são liberadas sem vender a posição. Lacuna SMA conserva as
reservas/posição/pendência do prefixo aceito, sem finalização retroativa.

A saída schema 4 contém os nove arquivos da Sprint 08 e também `risk.jsonl`
(avaliações, observações/bloqueios e gatilhos) e `reservations.jsonl`
(titularidade/quantidade/status com referências ao ledger). `ledger.jsonl`
reconstrói totais, disponíveis e reservados. Em `equity.csv`, os cabeçalhos da
Sprint 08 são mantidos e acrescenta-se ao final `asset_available,asset_reserved`;
os outros CSVs conservam cabeçalhos e semântica, com versão 4. São **onze arquivos**
determinísticos, em diretório novo, com INCOMPLETE até terminar e manifesto por
último. Relatórios apresentam candidatos exatos, incrementos, fórmulas, reservas,
bloqueios, proteções e perdas previstas/realizadas. Tabelas largas têm rolagem
horizontal e valores exatos; gráficos e impressão são locais.

A identidade acrescenta `risk_policy` e `analysis_policy`, ambas `SPRINT09_V1`.
Não inclui horário real, caminho absoluto ou diretório de saída. Benchmarks usam
mesmos custos, datas e filtros de instrumento, com capital independente, sem
aplicar orçamento, bloqueios ou proteções da estratégia passiva.

Na API, use `RiskConfig`, `RiskRequest`, `RiskSession` e as fases de abertura e
fechamento existentes. A sessão prepara cada transição em um snapshot isolado e
só a compromete no sucesso; o ledger financeiro da Sprint 08 continua responsável
por custo, trades e saldos totais. A extensão de reservas é auditável por prefixo.
Consultas retornam snapshots. `EquityGuard` e `evaluate` oferecem componentes
puros para conferir bloqueios e dimensionamento isoladamente.

O modelo não garante preço nem teto de perda; não tem livro, fila, parciais,
stop-limit ou recuperação operacional após reinício. A implementação é em memória
e prepara snapshots completos; não foi otimizada para grandes históricos.
Consulte o [glossário](docs/sprint09-glossario.md) e o
[registro de validação](docs/sprint09-validacao.md).

## Sprint 10 — Estratégias modulares

O schema 5 usa `mode: "STRATEGY"`, risco e análise obrigatórios. Selecione
`strategy.name`, `strategy.version` e `strategy.parameters`. O registro resolve
`SMA_CROSS/1`, `EMA_CROSS/1` e `RSI_REVERSION/1`, criando uma instância por sessão.
Cada execução tem capital próprio, indicadores, ordens e reservas independentes.

SMA e EMA aceitam `short_window`/`long_window`. EMA usa semente SMA e
`alpha=2/(N+1)`. RSI aceita `period`, `oversold` e `overbought`, suavização de
Wilder e semente por médias simples. BUY ocorre na saída da sobrevenda e SELL
na saída da sobrecompra. Os indicadores usam razões exatas. Os gráficos e valores
decimais são apresentação, com 12 casas HALF_EVEN nos indicadores.

As avaliações registram identidade, parâmetros, candle, disponibilidade, valores
anteriores/atuais, prontidão e motivo. Os sinais seguem o risco, reservas,
revalidação e proteções da Sprint 09. A API `RiskSession.submit` aceita ações
CANCEL no modo STRATEGY para liberar uma pendência pelo coordenador existente.

Com o ambiente ativado, execute na raiz em diretórios novos. Os três primeiros
comandos retornam **2** pelos motivos esperados abaixo. O quarto retorna **0**.

```bash
sprint10_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint10-candles.json --config experiments/sprint10-sma.json --saida "$sprint10_dir/sma" --formato html > "$sprint10_dir/sma.html"
python -m replayquant executar --dados data/fixtures/sprint10-candles.json --config experiments/sprint10-ema.json --saida "$sprint10_dir/ema" --formato html > "$sprint10_dir/ema.html"
python -m replayquant executar --dados data/fixtures/sprint10-candles.json --config experiments/sprint10-rsi.json --saida "$sprint10_dir/rsi" --formato html > "$sprint10_dir/rsi.html"
python -m replayquant executar --dados data/fixtures/sprint10-candles-rsi.json --config experiments/sprint10-rsi.json --saida "$sprint10_dir/rsi-fechado" --formato html > "$sprint10_dir/rsi-fechado.html"
```

| Cenário | Caixa final USDT | BTC final | Patrimônio bruto USDT | Motivo do código |
| --- | --- | --- | --- | --- |
| SMA 2/3, comum | 983.4 | 0.000166 | 996.68 | SELL final sem abertura futura |
| EMA 2/3, comum | 983.4 | 0.000166 | 996.68 | SELL final sem abertura futura |
| RSI 2, comum | 1000 | 0 | 1000 | BUY excede risco no gap, SELL sem ativo |
| RSI 2, abertura contínua | 1000 | 0 | 1000 | Uma operação encerrada, lucro zero |

Capital inicial de 1000 USDT por linha, sete candles de 01/01/2026 12:00–12:07
UTC, taxas e slippage zero. A exposição aberta de SMA/EMA é marcada no último
close, com realizado zero e retorno patrimonial −0.332%. O RSI contínuo tem
retorno zero e drawdown máximo de aproximadamente 0.398406%, pois houve um pico
patrimonial durante a posição. Os parâmetros amplos de proteção dessas fixtures
servem à conferência dos indicadores. Resultados positivos não são exigidos.

Os onze artefatos seguem o modo de risco, com schema 5 e políticas financeiras
herdadas `SPRINT09_V1`. Os CSVs mantêm as colunas financeiras existentes.
HTML/Markdown incluem identidade, avaliações, risco e resultados. O HTML offline
acrescenta gráfico de indicadores, com escala RSI 0–100 e limiares. `--analise` é
redundante e não altera identidade ou artefatos. Os schemas 1, 2 e 4 continuam
aceitos.

Para investigar a influência da inicialização, execute o diagnóstico sem carteira.
Ele compara os mesmos 30 candles, do índice 50 ao 79 da fixture expandida,
após históricos de 0, 10 e 50 candles anteriores. Usa SMA/EMA 9/21 e RSI 14.
O arquivo de saída deve ser novo.

```bash
python -m replayquant.warmup --config experiments/sprint10-sma.json --saida "$sprint10_dir/aquecimento-sma.json"
python -m replayquant.warmup --config experiments/sprint10-ema.json --saida "$sprint10_dir/aquecimento-ema.json"
python -m replayquant.warmup --config experiments/sprint10-rsi.json --saida "$sprint10_dir/aquecimento-rsi.json"
```

O JSON contém hash dos dados, parâmetros, cobertura, pontos não comparáveis,
diferenças absolutas exatas e divergências de sinais. A amostra validada apresentou
diferenças nos valores de EMA/RSI e nenhuma divergência de sinais. SMA coincidiu
após aquecimento suficiente. Razões recursivas e snapshots completos podem crescer
com o histórico, sem otimizações de escala nesta etapa.

Consulte [Sprint 10](docs/sprint10.md), [validação](docs/sprint10-validacao.md),
[glossário](docs/sprint10-glossario.md) e as regras de
[SMA](docs/estrategias/sma.md), [EMA](docs/estrategias/ema.md) e
[RSI](docs/estrategias/rsi.md).

### Exemplos lucrativos de SMA, EMA e RSI com 240 candles

As configurações `experiments/sprint10-sma-expandido.json`,
`experiments/sprint10-ema-expandido.json` e
`experiments/sprint10-rsi-expandido.json` reutilizam, sem alterações,
`data/fixtures/sprint07-candles-expandido.json`. São 240 candles fictícios de
01/01/2026 12:00–16:00 UTC. Os parâmetros foram escolhidos nesta mesma fixture
para demonstrações positivas, sem avaliação em dados separados.

SMA e EMA usam janelas **9/21**. RSI usa período **21**, sobrevenda **30** e
sobrecompra **70**, com BUY na saída da sobrevenda e SELL na saída da sobrecompra.
Os três exemplos usam schema 5 e capital próprio de **1000 USDT**. Os custos,
filtros e limites de risco são os definidos em cada configuração.

| Parâmetro | SMA 9/21 | EMA 9/21 e RSI 21, 30/70 |
| --- | --- | --- |
| Taxa por execução | 0 | 0.001 (0,1%) |
| Slippage por execução | 0 | 0.001 (0,1%) |
| `step` e `min_quantity` BTC | 0.000001 | 0.001 |
| `min_notional` USDT | 0 | 0 |
| Risco por entrada | 1% | 1,1% |
| Exposição máxima | 100% | 100% |
| Stop abaixo da entrada estimada | 50% | 10% |
| Alvo acima da entrada estimada | 90% | 20% |
| Limite de perda diária | 90% | 3% |
| Limite de drawdown | 90% | 5% |
| Idade máxima do preço | 60 segundos | 60 segundos |

EMA e RSI usam os filtros e o risco do cenário equivalente ao Sprint 07,
produzindo **0.001 BTC por compra** nesta fixture. SMA usa dimensionamento variável
com incremento menor. As diferenças de resultado incluem os efeitos da estratégia,
dos custos e do dimensionamento de cada exemplo. Todas as saídas ocorreram por
sinal da estratégia, sem acionamento de stop/alvo.

Execute com o ambiente ativado, escolhendo diretórios de saída novos.

```bash
exemplos_sprint10_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint10-sma-expandido.json --saida "$exemplos_sprint10_dir/sma" --formato html > "$exemplos_sprint10_dir/sma.html"
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint10-ema-expandido.json --saida "$exemplos_sprint10_dir/ema" --formato html > "$exemplos_sprint10_dir/ema.html"
python -m replayquant executar --dados data/fixtures/sprint07-candles-expandido.json --config experiments/sprint10-rsi-expandido.json --saida "$exemplos_sprint10_dir/rsi" --formato html > "$exemplos_sprint10_dir/rsi.html"
```

| Resultado observado | SMA 9/21 | EMA 9/21 | RSI 21, 30/70 |
| --- | --- | --- | --- |
| Caixa inicial USDT | 1000 | 1000 | 1000 |
| Caixa final USDT | 1000.42208230 | 1000.71085163730 | 1001.93754109984 |
| Lucro líquido realizado USDT | 0.42208230 | 0.71085163730 | 1.93754109984 |
| Retorno da carteira % | 0.042208230000 | 0.071085163730 | 0.193754109984 |
| Taxas pagas USDT | 0 | 0.60322322270 | 0.40114808016 |
| Impacto de slippage USDT | 0 | 0.60322514 | 0.40115082 |
| Drawdown máximo % | 0.010099486656 | 0.106425847313 | 0.050896550140 |
| Operações encerradas | 3, duas vencedoras e uma perdedora | 3, duas vencedoras e uma perdedora | 2, ambas vencedoras |
| Quantidade final BTC | 0 | 0 | 0 |
| Código de saída | 0 | 0 | 0 |

Taxas e slippage configurados já estão considerados no lucro líquido. Cada coluna
de estratégia representa uma carteira independente. Os relatórios HTML incluem candles,
indicadores, decisões de risco, trades, curvas e benchmarks.

| Estratégia | Compra UTC | Venda UTC | Quantidade BTC | Lucro líquido USDT |
| --- | --- | --- | --- | --- |
| SMA | 12:38 | 13:25 | 0.000200 | +0.22783800 |
| SMA | 14:20 | 15:02 | 0.000200 | +0.23526000 |
| SMA | 15:26 | 15:39 | 0.000198 | −0.04101570 |
| EMA | 12:38 | 13:32 | 0.001 | +0.57718991851 |
| EMA | 14:22 | 15:09 | 0.001 | +0.65256543403 |
| EMA | 15:25 | 15:38 | 0.001 | −0.51890371524 |
| RSI | 12:33 | 13:26 | 0.001 | +0.89975380089 |
| RSI | 14:15 | 14:59 | 0.001 | +1.03778729895 |

A seleção de parâmetros de EMA/RSI, a tentativa inicial com filtros menores e a
verificação do SMA estão registradas na seção 8 de
[validação do Sprint 10](docs/sprint10-validacao.md).

## Sprint 11 — Múltiplos pares e catálogo

O schema 6 executa estratégias em instrumentos resolvidos por um catálogo local.
As fixtures iniciais usam **BTCUSDT e ETHUSDT fictícios**, com USDT como moeda de
cotação e candles de um minuto. O comando `comparar` executa uma sessão independente
para cada combinação de estratégia e par, com **1000 USDT por sessão**.

O catálogo `data/catalogo/sprint11-instrumentos.json` contém moedas base/cotação,
intervalos, disponibilidade, step, mínimos e origem/data/hipótese das regras.
Os filtros são sintéticos, identificados como `SYNTHETIC_ASSUMPTION`. Alterar o
catálogo altera a identidade dos experimentos, inclusive quando a entrada alterada
não participa daquela sessão. `CURRENT_RULES_ASSUMED_FOR_PERIOD` identifica uma
hipótese de regras atuais aplicadas ao período.

A configuração schema 6 declara origem, símbolo, intervalo, janela `[start,end)`,
capital, custos, risco e estratégia. Os filtros vêm do catálogo. Use `--catalogo`
na execução individual. Os schemas anteriores seguem os caminhos BTC existentes.
As saídas novas usam `final_balance.asset_quantity`, moeda base explícita e o
benchmark `BUY_HOLD_ASSET`. A API usa `CatalogConfig`, `Catalog` e `Window` validados,
com `AssetBalance` para o saldo e a mesma sessão `RiskSession`.

Com `.venv` ativada, execute na raiz. O individual ETH/RSI retorna **0**. As matrizes
retornam **2**, pois incluem ordens não executadas ou rejeitadas previstas.

```bash
sprint11_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint11-eth-candles.json --config experiments/sprint11-eth-rsi.json --catalogo data/catalogo/sprint11-instrumentos.json --saida "$sprint11_dir/eth-rsi" --formato html > "$sprint11_dir/eth-rsi.html"
python -m replayquant comparar --config experiments/sprint11-matriz.json --saida "$sprint11_dir/matriz" --formato html > "$sprint11_dir/matriz.html"
python -m replayquant comparar --config experiments/sprint11-matriz-parcial.json --saida "$sprint11_dir/parcial" --formato html > "$sprint11_dir/parcial.html"
```

A matriz canônica tem SMA 2/3, EMA 2/3 e RSI 2 com limiares 30/70, em ambos os pares.
Usa sete candles de 01/01/2026 12:00–12:07 UTC, taxa de **0.001** e slippage zero.
A série ETH é a transformação didática BTC/50. O risco e a semente dos indicadores
estão declarados na receita e nos relatórios.

| Combinação | Caixa final USDT | Ativo final | Patrimônio bruto USDT | Código | Ranking |
| --- | --- | --- | --- | --- | --- |
| SMA ou EMA / BTC | 980.06008 | 0.000166 BTC | 993.34008 | 2 | Indisponível, SELL final sem abertura |
| SMA ou EMA / ETH | 980.06008 | 0.00830 ETH | 993.34008 | 2 | Indisponível, SELL final sem abertura |
| RSI / BTC | 999.9602 | 0 BTC | 999.9602 | 0 | 1 |
| RSI / ETH | 999.96012 | 0 ETH | 999.96012 | 0 | 2 |

RSI compra e vende ao mesmo preço por par, com perdas líquidas de 0.0398 e 0.03988
USDT pelas duas taxas. A diferença resulta dos steps definidos para cada ativo.
SMA/EMA mantêm posições abertas e marcadas no último fechamento. O ranking usa
retorno patrimonial exato, com custos pagos, capital, amostra, drawdown e posição
exibidos. Só entram combinações FULL, concluídas com código 0 e condições/horizontes
comparáveis. Empates exatos recebem a mesma posição, com salto posterior.

Na matriz parcial, ETH só está disponível de 12:02 a 12:06 UTC. São quatro candles
para seu aquecimento, sem fills. SMA/EMA não sinalizam e retornam 0. RSI emite SELL
sem posição e retorna 2. As três linhas ETH têm cobertura PARTIAL e ranking nulo.
Os valores financeiros BTC permanecem os da matriz canônica.

Candles fora da janela ou disponibilidade são excluídos sem aquecer os indicadores.
O arquivo inteiro é validado antes do recorte, inclusive identidades estrangeiras.
Lacunas internas interrompem no prefixo aceito. Uma posição no fim de disponibilidade
é conservada e marcada no último preço válido. Aberturas posteriores são recusadas.
Um candle válido ainda pode resolver proteção no fechamento que coincide com o fim
de disponibilidade, conforme a convenção OHLC da Sprint 09.

Sem candles elegíveis, a combinação fica UNAVAILABLE, código 2, com métricas de
desempenho nulas e motivo `NO_ELIGIBLE_CANDLES`. O caixa inicial é conservado e
nenhum benchmark compra. A cobertura distingue janela solicitada, interseção
elegível, exclusões, duplicatas e lacunas. Não há negociação com preço carregado
após o horizonte aceito.

O diretório de comparação contém `manifest.json`, `comparison.json`,
`comparison.csv`, `comparison.md` e onze artefatos por filho em
`runs/<symbol>/<strategy_id>/`. Os quatro formatos de stdout são texto, JSON,
Markdown e HTML. O HTML é autossuficiente e tem navegação interna. Cada linha
representa capital independente, com a política `INDEPENDENT_CAPITAL_PER_RUN`.
As curvas e lucros das sessões não formam uma carteira única.

Caminhos da receita são resolvidos em relação ao próprio arquivo. A ordem de suas
listas não altera a identidade lógica ou os filhos. O hash original da receita
registra essa diferença de proveniência. Repetições da mesma entrada produzem
artefatos idênticos. Uma falha de gravação conserva o marcador INCOMPLETE.

Consulte [Sprint 11](docs/sprint11.md), [validação](docs/sprint11-validacao.md) e
[glossário](docs/sprint11-glossario.md).

## Sprint 12 — Carteira compartilhada

O comando `carteira` executa schema **7**, modo `SHARED_PORTFOLIO`, com um caixa físico USDT, posições separadas por moeda base e lotes atribuídos a titulares. A política `ALLOCATED_BUDGETS_V1` fixa atribuições iniciais; ganhos/perdas continuam com o titular e o residual `UNALLOCATED` fica indisponível para compras. Cada estratégia pode acompanhar vários pares com indicadores independentes. O comando `comparar` continua executando carteiras independentes.

```bash
source .venv/bin/activate
sprint12_dir=$(mktemp -d)
python -m replayquant carteira --help
python -m replayquant carteira --config experiments/sprint12-compartilhada.json --saida "$sprint12_dir/compartilhada" --formato html > "$sprint12_dir/compartilhada.html"
python -m replayquant carteira --config experiments/sprint12-multipar.json --saida "$sprint12_dir/multipar" --formato html > "$sprint12_dir/multipar.html"
python -m replayquant carteira --config experiments/sprint12-limite.json --saida "$sprint12_dir/limite" --formato json > "$sprint12_dir/limite.json"
python -m unittest discover -s tests -v
```

Os códigos individuais esperados são **0, 0 e 2** para as três receitas. Também há `texto`, `json` e `markdown`; `--analise` é redundante. Caminhos internos são relativos à receita. A saída exige diretório novo e publica exatamente **15 arquivos**: manifest.json, events.jsonl, report.json, ledger.jsonl, reservations.jsonl, risk.jsonl, equity.csv, trades.csv, metrics.csv, benchmarks.csv, allocations.csv, lots.csv, contributions.csv, exposure.csv e report.md. O HTML fica em stdout, fora desse diretório. Uma exportação interrompida conserva `INCOMPLETE`.

| Receita | Fills / lotes encerrados | Caixa final USDT | Taxas USDT | Código |
| --- | --- | --- | --- | --- |
| Compartilhada SMA/EMA em BTC | 4 / 2 | 989.95 | 0.05 | 0 |
| Multipar SMA/BTC e EMA/ETH | 4 / 2 | 989.95 | 0.05 | 0 |
| Teto BTC reduzido para 3% | 2 / 1 | 993.32680 | 0.03320 | 2 |

No canônico, as compras são 0.000166 e 0.000084 BTC a 120000 USDT/BTC. As saídas integrais a 80000 produzem PnL de −6.67320 e −3.37680 USDT. As atribuições finais são 493.32680 e 496.62320 USDT. O retorno global é −1.005%; contribuições −0.66732% e −0.33768% usam o capital inicial global. Os retornos próprios −1.33464% e −0.67536% usam as atribuições individuais e não devem ser somados. No multipar, a segunda quantidade é 0.00420 ETH e a exposição conjunta dura 120 segundos.

O coordenador publica marcas comuns CLOSE, resolve proteções elegíveis, avalia indicadores e sinais, processa cancelamentos/SELL e arbitra BUY. Depois valida a composição OPEN, publica suas marcas em lote, resolve gaps protetivos, executa SELL e revalida BUY. Prioridade crescente, titular, símbolo e sinal definem a arbitragem, independentemente da ordem das listas. Quantidade, orçamento e bracket não aumentam na abertura. No cenário de limite, a taxa da primeira compra reduz o teto patrimonial e rejeita a segunda por `EXPOSURE_INSTRUMENT`; o SELL posterior sem lote gera `INSUFFICIENT_ASSET`.

A API incremental exige `SharedConfig` com `Catalog`, `Window`, `PortfolioLimits`, `Allocation`, `StrategySpec` e `RiskParameters` tipados. O carregador abaixo resolve esses modelos; não há catálogo global implícito:

```python
from replayquant.shared_config import load_shared
from replayquant.shared_engine import SharedSession, SharedRequest

inputs = load_shared("experiments/sprint12-compartilhada.json")
session = SharedSession(inputs.config)
# Para cada minuto, fornecer apenas Candle encerrado e Opening já elegível:
# session.on_boundary(at, closes=(...), openings=(...), requests=(...))
# requests é opcional: SharedRequest(id, strategy_id, symbol, "BUY"|"SELL"|"CANCEL", ...).
# Na última fronteira, openings=(); depois session.finish().
```

Cada fronteira é preparada em cópia isolada. Repetição equivalente é inócua; conflito, evento estrangeiro, preço futuro, ordem temporal inválida ou falha aritmética preservam o estado aceito. SELL com `lot_id` de outro titular gera `OWNERSHIP_MISMATCH`. `CANCEL` exige `target_order_id` completo da ordem. A interface pública de mutação é `on_boundary`/`finish`; os métodos de fases são internos ao coordenador. Não há recuperação após reinício.

`GLOBAL_GAP_INTERRUPT_V1` conserva fechamentos/sinais válidos, mas não consome um lote OPEN incompleto. Essa interrupção retorna 1 e retém reservas. No término normal, `KEEP_OPEN` conserva lotes e libera reservas; indisponibilidade encerra proteção sem inventar saída. Marcas carregadas mantêm horário/idade e não viram cotações negociáveis. Carteira sem observações elegíveis retorna `PORTFOLIO_UNAVAILABLE`, código 2, capital preservado e desempenho nulo com motivo.

O ledger separa `PHYSICAL` e `ATTRIBUTION`: somar ambas como caixa físico duplicaria capital. Por ponto, `C = C_UNALLOCATED + Σ C_i`, `Q_base = Σ q_lote` e `P = C_UNALLOCATED + Σ P_i = capital_inicial + Σ PnL_i`. As reservas já integram os saldos totais. Os seis candidatos racionais de quantidade e seus empates ficam em `risk.jsonl`; revalidação substitui apenas o compromisso próprio e preserva os demais.

O HTML contém candles por ativo, fills/linhas vinculados por lote, indicadores por binding, curva global e parcelas por titular, tabelas e limitações. Gráficos SVG são locais, funcionam sem JavaScript e na impressão; valores em ponto flutuante são usados somente na geometria, enquanto tabelas/artefatos conservam finanças exatas. O eixo das curvas representa a sequência de observações, inclusive pontos distintos no mesmo UTC. `HOLD_USDT` e `BUY_HOLD_BASKET` usam capital independente e o mesmo horizonte aceito. No canônico, a cesta conserva 0.001 USDT e 0.00999 BTC, com patrimônio bruto final de 799.201 USDT.

Dados fictícios, liquidez ilimitada, ausência de latência positiva, `STOP_FIRST` e `BAR_CLOSE_RESOLUTION` são hipóteses declaradas. O risco planejado não garante teto de perda em gaps. A exposição simultânea a BTC/ETH não demonstra hedge, correlação ou rentabilidade. Consulte [especificação](docs/sprint12.md), [validação executada](docs/sprint12-validacao.md) e [glossário](docs/sprint12-glossario.md).
