# ReplayQuant — Sprints 06 a 09

Laboratório educacional de replay Spot em Python, com candles fictícios e ordens
manuais ou sinais SMA de BTC/USDT. Mostra como um relógio simulado transforma solicitações em
preenchimentos, taxas e saldos. Funciona localmente com a biblioteca padrão,
sem rede ou credenciais. A Sprint 09 acrescenta risco e reservas pelo schema 4;
veja [Risco e saídas protetivas](#sprint-09--risco-e-saídas-protetivas).

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

O último comando **retorna 2 por política**, como esperado: com o step fictício
0.001 BTC da configuração de demonstração, o orçamento não permite quantidade
mínima para a compra a preços próximos de 102000 USDT/BTC. A decisão é
`BELOW_MINIMUMS`; a saída SMA posterior informa `INSUFFICIENT_ASSET`. Não houve
posição, taxa ou perda nesse cenário. Um teste com filtros menores valida o
caminho SMA com compra/venda efetivas, sem alterar os candles da Sprint 07.

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

Os três comandos retornam **0**, com compra de **0.981 BTC** e posição final
zerada. No alvo, a venda ocorre a 120 e o caixa final é **1019.40418 USDT**.
No cenário ambíguo, o candle toca stop e alvo; a convenção **STOP_FIRST** resolve
a venda a 90, com caixa final **990.00361 USDT**. No gap, a abertura a 80 define
a execução do stop, com caixa final **980.20342 USDT**: a perda realizada supera
o orçamento planejado de 10 USDT. A tabela abaixo detalha resultados e taxas.

Para executar `experiments/sprint09-sma.json`, combine-o com os candles da
Sprint 07, usados também pela demonstração SMA com risco:

```bash
sma_sprint09_dir=$(mktemp -d)
python -m replayquant executar --dados data/fixtures/sprint07-candles.json --config experiments/sprint09-sma.json --saida "$sma_sprint09_dir/execucao" --formato html > "$sma_sprint09_dir/relatorio.html"
echo "Código de saída SMA: $? (esperado: 2)"
```

Esse exemplo usa janelas SMA **2/3**, produz oito avaliações da estratégia e dois
sinais, mas nenhum preenchimento: BUY é rejeitada por `BELOW_MINIMUMS` e SELL
por `INSUFFICIENT_ASSET`. O código **2** é esperado; o HTML e os onze artefatos
são gravados, com caixa final **1000 USDT**, BTC e taxas zero. Em scripts com
`set -e`, trate esse retorno esperado para continuar após o comando.

Use `sprint09-candles.json` e suas variantes para os exemplos manuais acima.
Combinar `sprint06-candles.json` com `sprint09-manual.json` também rejeita a
entrada por `BELOW_MINIMUMS`: ao preço de 100000, a quantidade permitida pelo
risco é aproximadamente 0.000981354269 BTC, abaixo do mínimo e step de 0.001 BTC.

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
| Stop a 90 | 0.981 | 990.00361 | -9.99639 | 0.18639 |
| Gap: stop executado a 80 | 0.981 | 980.20342 | -19.79658 | 0.17658 |
| Alvo a 120 | 0.981 | 1019.40418 | 19.40418 | 0.21582 |
| Ambos os níveis: STOP_FIRST | 0.981 | 990.00361 | -9.99639 | 0.18639 |

Capital inicial 1000, orçamento 10, compra a 100, stop 90, alvo 120 e taxa 0.001.
Aceitar BUY reserva 98.1981 USDT, preservando caixa total e patrimônio. Preencher
consome o desembolso, abre BTC 0.981 e cria **uma** reserva de BTC compartilhada
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
