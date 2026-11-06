# ReplayQuant — Sprint 06

Laboratório educacional de replay Spot em Python, com candles fictícios e ordens
manuais de BTC/USDT. Mostra como um relógio simulado transforma solicitações em
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
adaptado a telas menores e impressão, sem fontes, scripts ou recursos externos.
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
Confira o código de saída: 2 indica replay com rejeições ou ordens não executadas,
com relatório disponível; 1 indica falha técnica ou de entrada.

A saída deve ser um caminho novo. O comando cria diretórios pais necessários,
mas recusa diretório, arquivo ou symlink já existente. Para repetir, escolha
outro nome; nenhum comando apaga resultados anteriores. Entradas são validadas
integralmente antes da simulação e da criação da saída.

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
schemas JSON v1, decimais como strings e datas UTC com microssegundos. Campos
inaplicáveis são `null` acompanhados de motivo. O log registra fases de mercado,
submissões, aceitações/rejeições, preenchimentos e encerramento, incluindo saldos
antes/depois dos preenchimentos.

| Código de saída | Significado |
| --- | --- |
| 0 | Replay concluído sem ordens rejeitadas ou não executadas; roteiro vazio também é válido |
| 1 | Dados/configuração inválidos, aritmética inexata ou falha técnica, inclusive saída existente |
| 2 | Replay concluído com ordem rejeitada/não executada; os artefatos preservam o diagnóstico |

Erros de sintaxe do `argparse` também retornam 2, sem iniciar o replay. Exceções
inesperadas propagam com traceback; não são convertidas em rejeição de ordem.

## Contratos e modelo

A especificação integral está em [docs/sprint06.md](docs/sprint06.md). Cada candle
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
fica no log. Conflitos e séries fora de ordem ou com lacunas impedem o início do
replay. Repetir ordem/execução idêntica é inócuo; ID reutilizado com outro conteúdo
é erro. Deduplicação é local em memória e não oferece recuperação após reinício.

O preenchimento total supõe liquidez ilimitada, sem limite pelo volume do candle.
Não há modelo de spread; slippage zero é uma configuração fictícia, sem evidência
sobre mercado real. Não se descontam spread/slippage novamente dos resultados.

## Organização e API

- `validation.py`, `models.py`, `data.py`: contratos, JSON e pré-validação integral.
- `execution.py`, `portfolio.py`: custos e cálculo atômico de novos saldos.
- `engine.py`: `replay(candles, config)` e `Session`, com fases explícitas.
- `reporting.py`, `__main__.py`: identidade, relatórios, arquivos e CLI.
- `html_report.py`: documento HTML independente, responsivo e com estilo de impressão.
- `tests/test_sprint06.py`: testes financeiros, temporais, de erros e reprodução.
- `tests/test_html_report.py`: HTML, cálculos, segurança de apresentação e contratos da CLI.

Modelos são registros imutáveis. `Session` expõe snapshots de consulta; alterações
passam por `on_open(Opening)`, `on_close(Candle)`, `submit(Request)`,
`apply_fill(Fill)` e `finish()`. O replay utiliza esse mesmo núcleo. Não altere
atributos privados de uma sessão nem substitua sua configuração durante a execução.

Consulte o [planejamento](docs/planejamento.md), o
[glossário](docs/sprint06-glossario.md) e os
[resultados de validação](docs/sprint06-validacao.md).

SMA, risco, reservas, ledger completo, dados reais e métricas serão introduzidos
nas sprints previstas. Esta entrega não conecta exchanges nem recomenda operações.
