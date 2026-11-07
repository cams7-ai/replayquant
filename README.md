# ReplayQuant — Sprints 06 e 07

Laboratório educacional de replay Spot em Python, com candles fictícios e ordens
manuais ou sinais SMA de BTC/USDT. Mostra como um relógio simulado transforma solicitações em
preenchimentos, taxas e saldos. Funciona localmente com a biblioteca padrão,
sem rede ou credenciais.

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
adaptado a telas menores e impressão. O relatório manual não usa scripts; o SMA
incorpora o JavaScript do gráfico, sem buscar fontes ou recursos na internet.
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

São produzidos `manifest.json`, `events.jsonl` e `report.json`. O manifesto inclui
hashes SHA-256 dos bytes de entrada e do código, versão Python real, política
financeira e modelo de execução. `run_id` depende desses conteúdos, sem caminhos
absolutos, hora real ou metadados Git. O diretório conterá `INCOMPLETE` durante a
gravação; só consuma artefatos quando houver manifesto e esse marcador estiver
ausente. Falha de escrita retorna erro técnico e pode deixar arquivos incompletos,
que devem ser preservados para diagnóstico e não representam execução persistida
com sucesso.

`--formato texto|json|html` controla stdout nos dois subcomandos; texto é o padrão.
O HTML vai somente para stdout e pode ser salvo por redirecionamento. Os três
artefatos persistidos continuam usando
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

Os contratos estão em [Sprint 06](docs/sprint06.md) e [Sprint 07](docs/sprint07.md). Cada candle
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

Há uma pendência por vez e uma posição de quantidade fixa. Aceitar uma ordem não
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

Risco, reservas, ledger completo, dados reais e métricas continuam previstos para
sprints posteriores. Esta entrega não conecta exchanges nem recomenda operações.


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
