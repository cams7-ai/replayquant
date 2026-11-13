# Sprint 13 — Dados históricos reais

**Projeto** ReplayQuant  
**Nível** intermediário  
**Referência** [Planejamento](planejamento.md), especialmente seções 4, 13, 21 e 23  
**Pré-requisitos** Sprints 06 a 12 implementadas e verificadas  
**Estado** especificação para implementação futura. Os comandos, arquivos novos e resultados esperados abaixo ainda precisam ser implementados e validados.

## 1. Objetivo e estado de entrada

Aplicar o motor já verificado a arquivos históricos públicos, com origem, integridade, unidades, disponibilidade e versões auditáveis. Entregar obtenção explícita, importação local equivalente, catálogo/metadados SQLite, relatório de qualidade e reprodução offline de execuções individuais, matriz independente e carteira compartilhada.

Trabalhar em `/home/cams7/Dev/Cripto_Tests/replayquant`, evoluindo o projeto existente. A referência consultada é o commit **`0b2ba4f`**, que implementa a Sprint 12. Inspecionar HEAD, `git status` e instruções `AGENTS.md` aplicáveis; preservar alterações existentes e posteriores. Ler o planejamento, [Sprint 11](sprint11.md), [Sprint 12](sprint12.md) e suas [validações](sprint12-validacao.md), além dos contratos de precisão/risco pertinentes das Sprints 09 e 10. A validação anterior registra Python 3.12.14 e 203 testes; isso é referência documental, não aprovação da árvore futura.

Inspecionar `models.py`, `catalog.py`, `data.py`, `catalog_config.py`, `coverage.py`, `comparison.py`, `shared_config.py`, `shared_engine.py`, relatórios e testes antes de alterar contratos. Atualmente existem restrições explícitas a `FICTICIA` nos modelos de mercado, catálogo e configuração compartilhada. Os parsers legados sem catálogo continuam limitados ao instrumento fictício. A origem real exige extensão contextual, não substituição de rótulo nem um segundo motor financeiro.

Esta sprint não pretende demonstrar rentabilidade. O conjunto real pequeno serve para verificar a cadeia de ingestão e execução. Ausência de trades, rejeições esperadas e resultado negativo são resultados válidos.

## 2. Escopo e exclusões

Implementar adaptador **`BINANCE_SPOT_KLINES_CSV_V1`** para CSV de klines Spot finais em ZIPs públicos oficiais, BTCUSDT/ETHUSDT, cotação USDT e frequência 1m. Usar `BINANCE_SPOT` como identidade de origem real. Manter `FICTICIA` para exemplos e testes sintéticos, com identificação explícita do tipo de conjunto.

Separar três responsabilidades:

1. `obter-dados`: única etapa com rede, acionada explicitamente para arquivos públicos e seus checksums.
2. `importar-dados` e `validar-dados`: leitura local, normalização, controle de qualidade, versões e persistência.
3. `executar`, `comparar` e `carteira`: consumo de snapshots normalizados e manifestos fixos, sem acesso à rede e sem consulta automática a uma versão “mais recente”.

Usar Python >= 3.11, biblioteca padrão, `unittest`, `sqlite3`, `csv`, `zipfile`, `hashlib`, `urllib` e a aritmética exata existente. Não adicionar pandas, NumPy, bibliotecas de exchange ou dependências de rede ao núcleo. Parquet/DuckDB são opcionais apenas após medição e decisão versionada; não são requisito de aceite nem devem substituir SQLite nesta entrega.

Preservar os schemas de configuração 1/2/4/5/6/7, saída analítica 3 e os resultados legados. Os novos documentos de aquisição/importação/manifesto têm schema próprio 1; não reutilizar um número de schema do motor com significado diferente. Ampliar schema 6 e schema 7 para origem real autorizada por catálogo, mantendo seus campos, políticas financeiras e análise obrigatória.

Ficam fora: API REST de candles como ingestão obrigatória, WebSocket, snapshots de candles abertos, negociação ou contas autenticadas, novos indicadores/frequências, parciais, margem, conversão de cotação, seleção/otimização, divisão temporal de pesquisa da Sprint 14, walk-forward, paralelismo e recuperação operacional após reinício. Nenhuma chave privada é necessária.

## 3. Fonte oficial, aquisição e proveniência

### 3.1. Referências consultadas

Documentação oficial consultada em **13/11/2026**:

- [Binance Public Data](https://github.com/binance/binance-public-data): organização dos arquivos públicos e convenções do acervo.
- [Binance Spot — klines](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data): estrutura dos campos e semântica dos candles.
- [Binance Public Data — termos do conjunto](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md): referência a conservar na proveniência; não confundir licença de scripts com condições de uso dos dados.

O acervo documenta timestamps Spot em **microssegundos a partir de 01/01/2025**, checksums SHA-256 e possibilidade de revisões posteriores dos arquivos. Esses pontos motivam unidades explícitas por arquivo e preservação de versões. A documentação REST descreve outras opções de unidade; não transferir seu padrão automaticamente aos ZIPs. Conferir novamente a fonte ao implementar e registrar eventual mudança. [Fonte](https://github.com/binance/binance-public-data), [documentação REST](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#general-api-information).

### 3.2. Receita real de aquisição

Criar `experiments/sprint13-aquisicao-real.json`, com exatamente:

```json
{
  "schema_version": 1,
  "mode": "PUBLIC_ARCHIVE_DOWNLOAD",
  "provider": "BINANCE_PUBLIC_DATA",
  "market": "SPOT",
  "source": "BINANCE_SPOT",
  "interval": "1m",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "dates": ["2024-12-31", "2025-01-01"],
  "base_url": "https://data.binance.vision/data/spot/daily/klines"
}
```

Para cada combinação, formar `{base_url}/{symbol}/1m/{symbol}-1m-{date}.zip` e a URL correspondente com sufixo `.CHECKSUM`. São quatro ZIPs e quatro arquivos de checksum. As URLs são receitas baseadas no layout documentado; **os arquivos e seus hashes ainda não foram obtidos/verificados nesta especificação**. A tentativa de abrir dois checksums pela ferramenta de pesquisa não retornou conteúdo. Não inventar hashes, número de linhas ou disponibilidade para suprir essa verificação.

`obter-dados --config --destino --formato` aceita texto ou JSON. O destino guarda os nomes originais e um `acquisition.json` com URLs solicitadas/finais, hashes, tamanho, status por objeto, data de obtenção UTC e referência documental. Transferir para temporário, verificar SHA-256 e só então publicar o objeto. Um objeto existente idêntico é reutilizado; conteúdo divergente exige novo destino e diagnóstico `SOURCE_REVISION_DETECTED`, sem sobrescrita. Recebimento parcial nunca se apresenta como aquisição completa.

Usar HTTPS, destino oficial declarado, timeout de 30 segundos por tentativa e no máximo três tentativas por objeto para falhas transitórias. Recusar redirecionamento para origem não autorizada. Fixar limites de 10 MiB por ZIP e 100 MiB descompactados por arquivo nesta receita pequena; rejeitar excesso antes de normalizar. Proteger leitura ZIP contra traversal, membros inesperados/duplicados, caminhos absolutos, CRC inválido e expansão excessiva. Não executar conteúdo do arquivo. Os limites são escolhas desta sprint, não limites atribuídos à fonte.

O checksum verifica integridade dos bytes recebidos; não comprova a correção econômica de cada registro. Guardar o texto original do checksum e validar a associação ao ZIP esperado. Falha de checksum, HTTP, certificado ou timeout não deve acionar fallback para candles inventados ou outra fonte.

### 3.3. Operação offline

O importador recebe os mesmos ZIPs/checksums por caminhos locais e não sabe fazer download. O backtest também não. A obtenção deve poder ocorrer uma vez, seguida de desconexão completa e reprodução em repositório SQLite novo.

Conservar bytes brutos em armazenamento imutável por SHA-256. Fixar os hashes realmente observados e as referências documentais na entrega da implementação. Disponibilizar uma receita local e os arquivos pequenos necessários à reprodução real offline, respeitando as condições da fonte; se a redistribuição não for adotada, documentar explicitamente como fornecer os mesmos arquivos locais. Uma receita que depende de download futuro não satisfaz, sozinha, a demonstração offline.

Se a aquisição estiver indisponível, concluir testes/fixtures locais e registrar a demonstração real como **pendente**. Não declarar a sprint integralmente validada nem substituir os resultados reais pelos sintéticos. Uma cópia local com os mesmos checksums é alternativa válida.

## 4. Contrato de normalização e qualidade

### 4.1. Entrada e unidades

O adaptador aceita CSV sem cabeçalho, com **12 colunas** na ordem documentada para klines. Validar quantidade/tipos de todas as colunas, mesmo as não usadas na estratégia. Não adivinhar cabeçalhos, delimitadores, frequência ou unidade temporal por heurística de magnitude. Cada arquivo declara `timestamp_unit: ms|us`; uma unidade incompatível com as datas/alinhamento do arquivo gera `TIMESTAMP_UNIT_MISMATCH`.

A configuração identifica símbolo, mercado e intervalo; o CSV não possui coluna de símbolo. Conferir também nome do ZIP, membro CSV e declaração do arquivo. Identidades de domínio usam `(source, symbol, interval, open_time)`; não juntar BTC e ETH na mesma série. Validar o arquivo inteiro antes de qualquer recorte, incluindo linhas fora da janela escolhida.

Preços, OHLC, volume base, volume cotação e volumes taker são `Decimal` a partir de texto, sem conversão intermediária para float. Aplicar gramática/finitude/representação do projeto; não arredondar silenciosamente um dado que exceda seus limites. Preços são positivos, volumes não negativos e número de trades é inteiro não negativo. Verificar OHLC, taker base <= volume base e taker cotação <= volume cotação. Com volume base zero, os volumes de cotação/taker também devem ser zero. Não exigir que volume cotação seja igual a close × volume base.

O campo `volume` normalizado mantém **volume base**. Preservar volume cotação, trades, volumes taker e campo ignorado em metadados auxiliares rastreáveis, sem ampliar retroativamente o significado do campo Candle.volume. Preços e médias continuam USDT/base; RSI permanece em pontos. Não tratar USDT como USD.

### 4.2. Tempo e fechamento

Converter timestamps por aritmética inteira a partir da época UTC. Não usar `datetime.fromtimestamp` com float financeiro ou arredondamento de microssegundos. Para um candle de minuto:

```text
open_time_normalizado = epoch_UTC + timestamp_open / unidade
end_exclusive = open_time_normalizado + 60 segundos
close_time_fonte + 1 unidade = end_exclusive
```

Exigir abertura alinhada ao minuto, duração de 60 segundos e relação de fechamento inclusivo válida. O `close_time` do Candle do motor é **end_exclusive**; conservar o valor inclusivo original na proveniência. Recusar arredondamento para fazer uma linha inválida caber num minuto. A janela seleciona somente candles integralmente contidos em `[start, end)`.

`as_of` é um instante UTC explícito da receita, não o relógio da máquina. Somente registros com `end_exclusive <= as_of` são finais/elegíveis. Linhas posteriores ficam fora do fluxo com `CANDLE_NOT_FINAL`, contabilizadas no relatório e preservadas no bruto. A estratégia recebe o candle completo apenas em seu fechamento normalizado. Receber hoje um ZIP não prova a disponibilidade histórica daquela versão; registrar `FINAL_ARCHIVE_ASSUMED_AVAILABLE_AT_CLOSE` e a ausência de histórico de revisões em tempo real.

Esta versão não ingere snapshots abertos de streaming. Se aparecer indicação de registro aberto em outra entrada, recusar o formato ou classificá-lo como incompleto; nunca promover implicitamente OHLC parcial a candle final. Extensão para precedência entre observações abertas/fechadas exige contrato próprio futuro.

### 4.3. Ordem, duplicatas e conflitos

Declarar `input_order: REQUIRE_ASCENDING_PER_FILE`. Recusar retrocesso de abertura dentro do arquivo; duplicata da chave já vista é examinada antes dessa regra. Arquivos de uma receita são tratados como conjunto, ordenados canonicamente por identidade/período; a ordem da lista não decide precedência.

- Candle final numericamente equivalente na mesma chave é deduplicado; escala decimal diferente não cria outro preço. Contar duplicatas e guardar suas origens/linhas.
- Comparar todos os campos normalizados e metadados de mercado relevantes, não apenas OHLC. Divergência final na mesma chave gera `CANDLE_CONFLICT` e rejeita o lote inteiro.
- Um conflito não é “corrigido” escolhendo a última linha, a maior observação ou o arquivo de maior nome. Uma correção aceita da fonte só entra numa nova versão, pelo procedimento da seção 5.
- A chave de origem/arquivo/linha é proveniência; não substitui a chave de domínio do candle.

### 4.4. Lacunas e cobertura

Não preencher minuto ausente, interpolar OHLC ou criar volume zero. O relatório relaciona janela solicitada, disponibilidade declarada, cobertura bruta/normalizada, primeiro/último registro, esperados, finais únicos, selecionados, duplicados, incompletos, exclusões e lacunas, com intervalos e contagens. Separar contagens por instrumento e por arquivo; uma mesma linha não pode ser contada como aceita duas vezes.

Expor cobertura da janela solicitada e da interseção com a disponibilidade. Minutos fora da disponibilidade não são lacunas; minutos ausentes dentro dela são. Dados sem observações elegíveis continuam reportáveis com motivo e desempenho indisponível. Não inferir listagem/deslistagem pela primeira/última linha de um arquivo recortado.

Uma série estruturalmente válida com lacunas pode ser publicada como `QUALITY_WARNINGS`, código 2, para estudar o prefixo. O importador não executa operações. No replay, preservar a política anterior: interrupção de sessão individual aplicável e `GLOBAL_GAP_INTERRUPT_V1` para carteira compartilhada, antes de um lote OPEN incompleto. O relatório de qualidade deve permitir saber que a lacuna existe antes de executar.

## 5. Armazenamento SQLite, identidade e versões

### 5.1. Livro de dados imutável

Usar SQLite para catálogo, metadados, versões, registros normalizados e relações de proveniência. Definir migração própria com `PRAGMA user_version`, `foreign_keys=ON`, transações explícitas e consultas parametrizadas. Recusar versão de banco desconhecida; não recriar nem apagar banco existente para contornar migração.

Estrutura lógica mínima, com nomes concretos documentados pelo implementador:

| Entidade | Conteúdo necessário |
| --- | --- |
| dataset | Chave estável do conjunto e tipo `PUBLIC_HISTORICAL` ou `SYNTHETIC_FORMAT_FIXTURE` |
| dataset_version | ID imutável, pai opcional, hashes normalizados/catálogo, janela, as_of, políticas e estado de qualidade |
| raw_object | SHA-256, caminho do blob, tamanho e hash do checksum/evidência de integridade |
| ingestion | ID do lote, versão associada, receita/proveniência, adaptador/código e diagnóstico de publicação |
| ingestion_file / bar_origin | Relação símbolo/arquivo/membro/linha/unidade com os registros aceitos e duplicatas |
| candle | Chave da versão/origem/símbolo/intervalo/abertura, campos normalizados e metadados de mercado |
| instrument / universe_evidence | Snapshot temporal, filtros, base/cotação, hipóteses e evidências |
| quality_issue | Tipo, instrumento, chave/intervalo, origem e severidade |

Preços, quantidades, volumes, taxas e filtros são **TEXT decimal canônico**. Definir zero como `0`, retirar zeros fracionários redundantes, não usar notação científica nem sinal de zero negativo. Timestamps normalizados podem ser INTEGER de microssegundos desde epoch, com faixa de datetime validada; contagens usam INTEGER. Ordenar candles pela chave temporal inteira. Não usar `REAL`, cast financeiro, soma financeira em SQL ou ordenação lexicográfica de texto decimal para comparar valores. Calcular em Python Decimal/Fraction sob contexto local.

### 5.2. Duas identidades e revisão explícita

Distinguir:

- `dataset_version`: hash canônico do conteúdo final normalizado, snapshot de catálogo/universo, tipo/origem, janela, as_of e versões das políticas/adaptador. Não depende de caminhos, relógio de obtenção ou ordem de listas.
- `ingestion_id`: identifica bytes de origem, associação por símbolo, unidade, checksum e transformação/código usados para obter aquela versão. O hash textual original da receita é proveniência separada; caminhos equivalentes não devem alterar a identidade lógica do lote.

Guardar os hashes brutos e o mapa de derivação em todo caso. Importar os mesmos bytes/receita lógica é idempotente e não repete candles. Uma importação numericamente equivalente pode ter nova proveniência bruta sem criar outra versão de candles: vincular o novo lote à mesma versão, conservando o registro anterior. Não editar um manifesto imutável antigo para acrescentar proveniência; criar outro registro de ingestão.

Para correção com valores divergentes, exigir `supersedes` apontando a versão anterior e `revision_reason` não vazio na receita. Aceitar apenas substituição explicitamente revisada do mesmo dataset/chave de janela; nunca alterar a versão pai. Publicar novo ID e conservar ambas as versões. Tentativa divergente sem revisão declarada é `DATASET_CONFLICT`. Um apontador de descoberta pode existir, mas experiências sempre fixam IDs e hashes explícitos.

### 5.3. Atomicidade e falhas

Validar estrutura, checksum, todos os arquivos, conflitos, catálogo e projeções antes de aceitar o lote. Preparar blobs/arquivos imutáveis fora da transação; publicar relações/linhas da versão em **uma transação SQLite**. Falha de domínio, SQL ou aritmética anterior ao commit preserva as versões/linhas aceitas. Uma falha no último arquivo não deixa o primeiro importado parcialmente. Blobs órfãos após falha não são versões aceitas e devem ser identificáveis; não apagar objetos de outras versões.

Não prometer transação atômica única entre SQLite e o sistema de arquivos. O banco só referencia blobs completos verificados; leitores recusam blob ausente/divergente. Separar claramente commit de ingestão e exportação de relatórios. Se uma exportação falhar após commit, informar versão já aceita e fase `EXPORT_FAILED`; conservar `INCOMPLETE` na saída e permitir reexportação offline, sem duplicar ingestão. Falha de relatório não autoriza apagar uma versão aceita. Manifesto final de exportação é publicado por último, somente depois dos demais arquivos.

A API exige modelos tipados equivalentes aos JSONs e mantém o mesmo comportamento transacional/idempotente. Não permitir que construções Python burlem faixas, unidades, versões inteiras, referências ou validação de conflitos.

## 6. Catálogo temporal e restrição de sobrevivência

Adicionar `BINANCE_SPOT` à autorização contextual de mercado e catálogo, preservando os caminhos fictícios. Não renomear dados reais para FICTICIA para satisfazer um validador. Sem catálogo explícito, os caminhos legados não passam a aceitar qualquer exchange/par. A origem deve acompanhar eventos, ledger, relatórios, CSVs, gráficos e identidade das execuções.

O catálogo de negociação conserva o formato da Sprint 11. Acrescentar evidências em documento auxiliar versionado, associado por hash à versão de dados: origem, instrumento, intervalo de cobertura, fundamento de disponibilidade, data da evidência e referência/limitação. Diferenciar `VERIFIED_TEMPORAL_UNIVERSE`, `OBSERVED_COVERAGE_ONLY` e `SYNTHETIC_FIXTURE` nesse auxiliar.

Para a amostra real, sem evidência histórica de listagem/deslistagem completa, autorizar apenas o horizonte observado escolhido e registrar **OBSERVED_COVERAGE_ONLY / SURVIVORSHIP_RESTRICTION**. Isso limita o universo do experimento; não afirma que o ativo foi listado no primeiro minuto da amostra ou retirado no último. Não usar a lista atual de pares como prova do universo passado. Intervalos do catálogo usados apenas para delimitar o experimento devem ter essa interpretação visível, inclusive nos motivos de cobertura.

Fixar filtros da demonstração como **hipóteses sintéticas de execução**, não como regras históricas da Binance: BTC step/min_quantity `0.000001`; ETH step/min_quantity `0.00001`; min_notional `0` para ambos. Usar `rules_basis: SYNTHETIC_ASSUMPTION`, `rules_as_of: 2025-01-01T00:04:00+00:00` como referência do cenário e `rules_source` indicando a hipótese local. Taxa `0.001` e slippage `0` também são hipóteses, não reconstrução de comissões/spread históricos. Se forem usados filtros atuais em variante opcional, manter `CURRENT_RULES_ASSUMED_FOR_PERIOD` e o aviso correspondente.

Criar fixture separada com um par fictício retirado, descrita na seção 9. Uma retirada sintética testa o comportamento do motor; não substitui evidência de uma deslistagem real nem remove a restrição de sobrevivência da amostra externa.

## 7. Receitas de importação e integração com o motor

### 7.1. Importação real

Criar `experiments/sprint13-importacao-real.json` com exatamente a estrutura abaixo. Os caminhos são relativos à receita; a pasta `data/historicos/entrada` recebe a aquisição/copias locais. A lista pode ser permutada sem mudar a decisão lógica.

```json
{
  "schema_version": 1,
  "mode": "HISTORICAL_IMPORT",
  "adapter": "BINANCE_SPOT_KLINES_CSV_V1",
  "dataset_key": "sprint13-binance-btc-eth-transicao",
  "dataset_kind": "PUBLIC_HISTORICAL",
  "source": "BINANCE_SPOT",
  "quote_asset": "USDT",
  "interval": "1m",
  "catalog": "../data/catalogo/sprint13-real-instrumentos.json",
  "universe_evidence": "../data/catalogo/sprint13-real-universo.json",
  "window": {"start": "2024-12-31T23:56:00+00:00", "end": "2025-01-01T00:04:00+00:00"},
  "as_of": "2025-01-03T00:00:00+00:00",
  "input_order": "REQUIRE_ASCENDING_PER_FILE",
  "supersedes": null,
  "revision_reason": null,
  "raw_files": [
    {"symbol": "BTCUSDT", "path": "../data/historicos/entrada/BTCUSDT-1m-2024-12-31.zip", "member": "BTCUSDT-1m-2024-12-31.csv", "timestamp_unit": "ms", "checksum": "../data/historicos/entrada/BTCUSDT-1m-2024-12-31.zip.CHECKSUM"},
    {"symbol": "BTCUSDT", "path": "../data/historicos/entrada/BTCUSDT-1m-2025-01-01.zip", "member": "BTCUSDT-1m-2025-01-01.csv", "timestamp_unit": "us", "checksum": "../data/historicos/entrada/BTCUSDT-1m-2025-01-01.zip.CHECKSUM"},
    {"symbol": "ETHUSDT", "path": "../data/historicos/entrada/ETHUSDT-1m-2024-12-31.zip", "member": "ETHUSDT-1m-2024-12-31.csv", "timestamp_unit": "ms", "checksum": "../data/historicos/entrada/ETHUSDT-1m-2024-12-31.zip.CHECKSUM"},
    {"symbol": "ETHUSDT", "path": "../data/historicos/entrada/ETHUSDT-1m-2025-01-01.zip", "member": "ETHUSDT-1m-2025-01-01.csv", "timestamp_unit": "us", "checksum": "../data/historicos/entrada/ETHUSDT-1m-2025-01-01.zip.CHECKSUM"}
  ]
}
```

Validar JSON estrito, campos inesperados, duplicatas, finitude, tipos, UTC, limites, versões e identificadores seguros também na API. `supersedes` e `revision_reason` são ambos nulos na primeira publicação ou ambos preenchidos numa revisão. `PUBLIC_HISTORICAL` exige origem BINANCE_SPOT e evidência externa. `SYNTHETIC_FORMAT_FIXTURE` exige origem FICTICIA e aviso inequívoco; hashes calculados localmente nessa fixture não são checksums oficiais.

Validar integridade e estrutura do bruto integral antes de selecionar os oito minutos. O snapshot normalizado para replay contém somente candles elegíveis na janela/as_of/disponibilidade. A qualidade conserva contagens globais e exclusões, sem aquecer indicadores com linhas descartadas. Se os arquivos tiverem todos os minutos esperados na janela, a amostra terá **8 candles por par, 16 no total**; confirmar isso na aquisição, sem presumir o conteúdo de arquivos ainda não verificados.

### 7.2. Snapshot exportado e proveniência obrigatória

`importar-dados --config --repositorio --saida --formato` usa `repositorio/catalogo.sqlite` e armazenamento imutável sob esse repositório. `--saida` é um diretório de exportação exclusivo. `validar-dados --manifesto --formato` verifica offline manifesto, hashes de arquivos, catálogo, associação com a versão e qualidade, sem executar trades; aceita texto/JSON/Markdown/HTML. Reexportação usa `importar-dados` com a mesma receita e outro `--saida`, sem nova inserção de candles.

Exportar em cada saída bem-sucedida: `manifest.json`, `quality.json`, `quality.md`, `BTCUSDT.json`, `ETHUSDT.json`, `catalog.json`, `universe.json`, `individual.json`, `matriz.json` e `carteira.json`. Os dois JSONs de candles reutilizam o envelope schema 1. `manifest.json` fixa dataset_version, ingestion_id, hashes e nomes relativos desses arquivos, políticas, adaptador, código de transformação e evidências de origem; o manifesto não contém seu próprio hash nem cria referência circular. `quality.json` conserva detalhes por arquivo/instrumento e issues, e `quality.md` é sua projeção legível. Quantidades/listas vazias têm significado explícito.

Não tornar o banco um requisito para executar o snapshot exportado: resolver e verificar esses arquivos imutáveis é suficiente. Na API, aceitar objeto de proveniência validado. Para origem BINANCE_SPOT, exigir manifesto correspondente antes do replay:

- Individual schema 6: novo argumento `executar --dataset-manifest CAMINHO` associa dados, catálogo e versão.
- Matriz e carteira: datasets da receita real usam `{symbol, path, manifest}`; `manifest` aponta para o manifesto exportado. Receitas fictícias anteriores conservam `{symbol, path}` e sua validação original.
- Recusar ausência, versão desconhecida, hash divergente ou instrumento sem vínculo; não iniciar saída bem-sucedida nem consultar “latest”.

Incluir dataset_version, ingestion_id, qualidade, snapshot de universo e hashes de proveniência na identidade/manifestações do replay real. Repetições usando o mesmo snapshot fixo produzem os artefatos e HTML idênticos por bytes, independentemente da cwd ou do destino. Proveniência de aquisição com relógio de parede fica em recibo separado e não altera a identidade lógica do conteúdo. Não exigir igualdade binária de arquivos SQLite; comparar conteúdo lógico e exportações canônicas.

### 7.3. Configurações de demonstração

As receitas exportadas devem estar completas e funcionar de qualquer cwd, com caminhos relativos a elas e origem correspondente ao dataset. Parâmetros fixos, sem ajuste pelo lucro:

- Individual: schema 6, BTCUSDT, SMA_CROSS/1 2/3, capital 1000, janela importada, taxa 0.001, slippage 0; RiskParameters com risk_fraction 0.02, exposure_fraction 1, stop_fraction 0.5, target_fraction 0.9, daily_loss_fraction 0.9, drawdown_fraction 0.9 e max_price_age_seconds 60.
- Matriz: formato da Sprint 11, capital **independente** de 1000 por combinação; SMA_CROSS/1 e EMA_CROSS/1 2/3 nos dois pares, com os parâmetros de risco acima. Não agregar patrimônios dos filhos.
- Carteira: schema 7, ALLOCATED_BUDGETS_V1, capital global 1000, SMA prioridade 0 somente BTC e EMA prioridade 1 somente ETH, cada uma com allocation_fraction 0.5 e o risco acima. PortfolioLimits: exposure_fraction 0.03001, max_open_risk_fraction 0.03, daily_loss_fraction 0.9, drawdown_fraction 0.9, max_price_age_seconds 60. Limite por instrumento 0.8.

Manter BOUNDARY_MARKS_V1, STOP_FIRST, GLOBAL_GAP_INTERRUPT_V1, reservas e KEEP_OPEN. Distinguir horário de fechamento, ordem lógica e cotação da abertura seguinte; disponibilidade de arquivo histórico não autoriza acesso antecipado ao OHLC. Os benchmarks acompanham os horizontes aceitos e suas hipóteses anteriores.

## 8. Relatório de qualidade e apresentação

JSON, texto, Markdown e HTML devem apresentar origem real/fictícia, tipo do dataset, versão/ingestão, integridade, adapter/unidades, UTC, janela/as_of, cobertura, duplicatas/conflitos/incompletos, lacunas, disponibilidade, hipótese das regras/custos e restrição de sobrevivência. JSON é estrito, decimais são strings e indisponibilidades usam null com motivo. Mostrar a ligação entre linha bruta, candle e arquivo normalizado sem expor caminhos de máquina como identidade lógica.

Separar estado de qualidade (`PASSED`, `QUALITY_WARNINGS`, `REJECTED`) de estado financeiro do replay. Ter qualidade válida não garante rentabilidade, execução realista ou ausência de viés de seleção. Expor `FINAL_ARCHIVE_ASSUMED_AVAILABLE_AT_CLOSE` e revisões desconhecidas na época. Não anualizar oito minutos nem inferir correlação/hedge.

Os relatórios do motor real conservam curvas, custos, lotes, atribuições, risco e benchmarks já existentes, acrescidos de proveniência/qualidade/universo. Não trocar políticas financeiras para obter operação ou lucro. Inspecionar HTML de qualidade e de replay offline, desktop, tela estreita, print e sem JavaScript; preservar assets/licenças e evitar requisições externas.

## 9. Fixtures analíticas e variantes obrigatórias

### 9.1. Transição de unidade em dados sintéticos

Criar quatro CSVs pequenos e ZIPs/checksums determinísticos sob `data/fixtures/sprint13/`, com metadados `SYNTHETIC_FORMAT_FIXTURE`, origem FICTICIA e a janela de oito minutos da seção 7. Para cada par, quatro linhas de 31/12/2024 em ms e quatro de 01/01/2025 em us. Fixar metadados ZIP, ordem de membros e conteúdo para reprodução por bytes.

Usar preços BTC **100000, 90000, 80000, 100000, 120000, 100000, 80000, 80000**, ETH=BTC/50. Primeira abertura igual ao primeiro fechamento; demais aberturas iguais ao fechamento anterior. High=max(open,close), low=min(open,close), volume base 1, volume cotação=close, número de trades 4, volumes taker 0 e campo ignorado 0. Isso é fixture de formato/aritmética, não arquivo histórico externo.

Exemplos exatos de fronteira:

```text
2024-12-31T23:59:00Z: open_ms=1735689540000; close_ms=1735689599999
2025-01-01T00:00:00Z: open_us=1735689600000000; close_us=1735689659999999
close_time normalizado da primeira linha = 2025-01-01T00:00:00+00:00
```

Normalização esperada: oito candles únicos por par, sem lacuna, chaves contíguas, nenhuma diferença artificial de 1000× na passagem de unidade. Com as receitas da seção 7.3, a carteira deve reproduzir a aritmética multipar da Sprint 12: **quatro fills, dois lotes encerrados, caixa/patrimônio 989.95 USDT, taxas 0.05, quantidades 0.000166 BTC e 0.00420 ETH, retorno −1.005%, exposição conjunta 120 segundos e código 0**. A hora de compra passa a 00:01 e a venda a 00:03 UTC de 01/01/2025. Esse é o oráculo financeiro sintético; não atribuí-lo aos arquivos reais.

Criar `experiments/sprint13-importacao-fixture.json` completo, com catálogo/universo fictícios e arquivos locais; o exportador gera suas três receitas de replay. Fixar hashes realmente calculados quando os arquivos forem implementados.

### 9.2. Par retirado e universo temporal

Criar variante sintética com BTC disponível durante toda a janela e ETH disponível em `[2024-12-31T23:58:00Z, 2025-01-01T00:02:00Z)`. O catálogo auxiliar usa SYNTHETIC_FIXTURE, com início/fim de disponibilidade declarados. Preservar bruto anterior/posterior como exclusões, sem aquecimento fora da disponibilidade.

Esperar oito candles BTC e quatro ETH elegíveis. Ausência de ETH antes/depois desse intervalo não cria lacuna global. A disponibilidade do minuto final termina em 00:02 e não permite OPEN ETH nesse horário; o último candle válido ainda pode resolver proteção no seu CLOSE. Testar também posição ETH aberta antes da retirada, por solicitação tipada/controlada no motor, e conferir KEEP_OPEN, propriedade, marca/idade, liberação da reserva base e proteção indisponível, sem venda fictícia. Não exigir que os cruzamentos naturais dessa série abram essa posição.

### 9.3. Integridade, versões e causalidade

Exercitar, com resultados/contagens fixados nos testes:

- Duplicar uma linha final com escala decimal distinta: uma aceitação lógica, uma duplicata, mesmos candles e mesmo dataset_version. Reimportar o mesmo lote não aumenta contagens.
- Alterar uma linha duplicada para close=100001 com high compatível: CANDLE_CONFLICT, código 1, sem aceitação parcial. Não confundir com erro OHLC.
- Revisão de uma versão publicada: alterar consistentemente uma linha e declarar supersedes/revision_reason; novo dataset_version, pai intacto e receita antiga reproduzível. Sem revisão declarada, DATASET_CONFLICT.
- Unidade errada, fechamento inclusivo incorreto, data fora da faixa, ordem invertida, membro/símbolo incompatível, colunas extras/ausentes, decimal não representável, volume inválido, checksum/CRC divergente e ZIP inseguro: erro antes de aceitar a versão.
- Arquivo válido seguido de arquivo inválido no mesmo lote; erro SQL/falha de escrita injetada; preservação das versões anteriores e distinção explícita de falha pós-commit de exportação.
- Remover candle BTC com abertura 00:01 dentro da disponibilidade: qualidade com lacuna, importação código 2; carteira interrompe em 00:01 antes de OPEN de qualquer ativo, conserva sinais/reservas do fechamento e retorna 1.
- `as_of=2025-01-01T00:03:30Z`: o candle iniciado em 00:03 não é final. Fica fora da estratégia e aparece como CANDLE_NOT_FINAL; não completar silenciosamente o prefixo com seu OHLC.
- Alterar somente OHLC futuro sem mudar avaliação/reserva anterior; arquivo/API incremental equivalentes; nenhum acesso à rede durante validar/importar/replay.
- Ordenar TEXT decimal de forma enganosa (`9`, `10`, `100`), valores com zeros à direita, quantum não decimal e contexto Decimal hostil: finanças/comparações continuam exatas em Python.
- Lista de arquivos permutada, caminhos equivalentes, nova cwd, reabertura do SQLite e snapshot exportado sem banco: mesma versão lógica/candles e replay reproduzível.

## 10. Entregáveis e comandos de validação futura

Entregar código de aquisição/adaptação/persistência/proveniência, migração SQLite, fixtures, catálogo/universo, receitas e testes. Criar `docs/sprint13-glossario.md`, `docs/sprint13-validacao.md` e decisão de persistência/versões em `docs/decisoes/sprint13-ingestao.md`. Atualizar README e planejamento após implementar. Registrar ambiente, hashes concretos, fontes/datas, esperado/observado, comandos e códigos, inspeção visual, limitações e pendências. Não criar agora documentos de validação afirmando sucesso futuro.

Na raiz, antes da implementação, conferir entradas existentes e capturar cada código individualmente:

```bash
source .venv/bin/activate
python --version
python -m unittest discover -s tests -v
python -m replayquant --help
python -m replayquant executar --help
python -m replayquant comparar --help
python -m replayquant carteira --help
python -m replayquant demonstrar --formato json
python -m replayquant demonstrar --risco --estrategia sma --formato json
```

Os comandos seguintes são **contratos novos a implementar**. Exemplos usam diretórios novos. Redirecionar stdout não permite inferir o código anterior pelo último comando do bloco.

```bash
python -m replayquant obter-dados --help
python -m replayquant importar-dados --help
python -m replayquant validar-dados --help
sprint13_dir=$(mktemp -d)
python -m replayquant importar-dados --config experiments/sprint13-importacao-fixture.json --repositorio "$sprint13_dir/store-fixture" --saida "$sprint13_dir/fixture" --formato json > "$sprint13_dir/import-fixture.json"
python -m replayquant validar-dados --manifesto "$sprint13_dir/fixture/manifest.json" --formato html > "$sprint13_dir/qualidade-fixture.html"
python -m replayquant carteira --config "$sprint13_dir/fixture/carteira.json" --saida "$sprint13_dir/run-fixture" --formato html > "$sprint13_dir/run-fixture.html"
python -m replayquant importar-dados --config experiments/sprint13-importacao-fixture.json --repositorio "$sprint13_dir/store-fixture" --saida "$sprint13_dir/fixture-repetida" --formato json > "$sprint13_dir/import-fixture-repetida.json"
```

Esperado: ajudas, importações sintéticas e validação sem issues retornam 0; carteira sintética retorna 0 com os valores da seção 9.1. Conferir deduplicação SQLite e igualdade dos candles/versão nas duas exportações. Também executar quatro formatos e as variantes de qualidade/erro em testes e comandos registrados.

A única chamada de rede prevista na execução é explícita:

```bash
python -m replayquant obter-dados --config experiments/sprint13-aquisicao-real.json --destino data/historicos/entrada --formato json > "$sprint13_dir/aquisicao-real.json"
python -m replayquant importar-dados --config experiments/sprint13-importacao-real.json --repositorio "$sprint13_dir/store-real" --saida "$sprint13_dir/real" --formato json > "$sprint13_dir/import-real.json"
python -m replayquant validar-dados --manifesto "$sprint13_dir/real/manifest.json" --formato html > "$sprint13_dir/qualidade-real.html"
python -m replayquant executar --dados "$sprint13_dir/real/BTCUSDT.json" --config "$sprint13_dir/real/individual.json" --catalogo "$sprint13_dir/real/catalog.json" --dataset-manifest "$sprint13_dir/real/manifest.json" --saida "$sprint13_dir/real-individual" --formato html > "$sprint13_dir/real-individual.html"
python -m replayquant comparar --config "$sprint13_dir/real/matriz.json" --saida "$sprint13_dir/real-matriz" --formato html > "$sprint13_dir/real-matriz.html"
python -m replayquant carteira --config "$sprint13_dir/real/carteira.json" --saida "$sprint13_dir/real-carteira" --formato html > "$sprint13_dir/real-carteira.html"
python -m replayquant carteira --config "$sprint13_dir/real/carteira.json" --saida "$sprint13_dir/real-repetida" --analise --formato html > "$sprint13_dir/real-repetida.html"
```

Com arquivos fornecidos localmente, omitir obter-dados e registrar sua proveniência. Depois, bloquear rede por teste e reimportar em repositório novo; não apagar o anterior. Conferir o replay exportado com banco inacessível. Os resultados financeiros reais são **desconhecidos nesta especificação**; registrar valores e motivos observados sem exigir lucro, trade ou código 0 do replay.

Códigos dos comandos novos: **0** para aquisição/importação/validação completas sem issues operacionais de qualidade; **2** para qualidade advertida, lacunas/incompletos/nenhum candle elegível, com motivo; **1** para erro de entrada/integridade/conflito, rede/SQL/aritmética ou falha técnica. Advertências metodológicas declaradas, como sobrevivência e custos assumidos, devem aparecer sempre, mas isoladamente não tornam um arquivo íntegro QUALITY_WARNINGS. Os códigos dos replays preservam os contratos anteriores: 0 normal, 2 por rejeições/não execuções/indisponibilidade e 1 por interrupção/erro. argparse conserva código 2 para sintaxe inválida.

Conferir regressões e sintaxe após a implementação:

```bash
python -m replayquant carteira --config experiments/sprint12-compartilhada.json --saida "$sprint13_dir/legado-compartilhada" --formato json > "$sprint13_dir/legado-compartilhada.json"
python -m replayquant carteira --config experiments/sprint12-multipar.json --saida "$sprint13_dir/legado-multipar" --formato json > "$sprint13_dir/legado-multipar.json"
python -m replayquant carteira --config experiments/sprint12-limite.json --saida "$sprint13_dir/legado-limite" --formato json > "$sprint13_dir/legado-limite.json"
python -m replayquant comparar --config experiments/sprint11-matriz.json --saida "$sprint13_dir/legado-matriz" --formato json > "$sprint13_dir/legado-matriz.json"
python -m unittest discover -s tests -v
node --check replayquant/assets/chart.js
node --check replayquant/assets/equity.js
node --check replayquant/assets/indicators.js
git diff --check
```

As receitas Sprint 12 retornam respectivamente 0, 0 e 2; a matriz Sprint 11 retorna 2 conforme sua validação. Reexecutar os individuais e exemplos expandidos anteriores afetados pela generalização de source, comparando valores com os registros das Sprints 11/12. A repetição real deve preservar os quinze artefatos de carteira e o HTML por bytes para o mesmo snapshot/código; os recibos de aquisição são proveniência separada. Testar diretório existente, falha de escrita e manifesto divergente sem sobrescrita de saída aceita.

## 11. Critérios de aceite

1. Origem real e arquivos oficiais identificados com hashes observados, unidades por arquivo, referência e aquisição explícita; nenhuma rede no importador ou nos replays.
2. A mesma entrada pode ser importada offline em SQLite novo e exportada sem depender de relógio de parede ou caminho da máquina.
3. Camadas bruta e normalizada são imutáveis/rastreáveis; deduplicação é inócua, conflito não sobrescreve e revisão conserva o pai.
4. Lotes de vários arquivos têm atomicidade SQLite; falhas técnicas/aritméticas e de exportação distinguem fase/commit e preservam estados aceitos.
5. Precisão financeira/texto canônico é mantida em SQLite/JSON; nenhuma coerção REAL ou decisão baseada em ordenação de texto decimal.
6. Timestamp ms/us, fechamento inclusivo/exclusivo, UTC, as_of, volume base/cotação e prontidão de candle passam em casos analíticos exatos.
7. Qualidade informa contagens reconciliadas, lacunas e exclusões; replay preserva o prefixo e não negocia através de minuto ausente.
8. Fixture com par retirado respeita universo temporal, ausência de aquecimento excluído, propriedade e proteção indisponível, sem liquidar artificialmente.
9. Amostra real registra sobrevivência/cobertura observada e hipóteses de filtros/custos; não atribui ao histórico regras atuais/sintéticas como fatos conhecidos.
10. A fixture de formato reproduz 989.95 USDT, 0.05 de taxas, quatro fills e 120 segundos de exposição conjunta; resultados externos são medidos separadamente.
11. Schemas/comandos antigos mantêm resultados. Individual, matriz e carteira reais usam o mesmo núcleo, com proveniência fixa e reprodução por bytes dos snapshots repetidos.
12. Testes, documentação, comandos/códigos e inspeção visual são registrados com esperado/observado; a demonstração real offline é verificada ou permanece explicitamente pendente, impedindo declaração de conclusão integral.

## 12. Prompt autossuficiente de execução

Copiar o bloco completo. Os contratos versionados das seções 1 a 11 deste documento são parte do prompt e devem ser lidos integralmente antes de alterar o projeto.

```text
Implemente a Sprint 13 — Dados históricos reais do ReplayQuant em
/home/cams7/Dev/Cripto_Tests/replayquant. Evolua o projeto existente até entregar
código, fixtures, receitas, testes, demonstração real offline e documentação.

Inspecione HEAD, git status e AGENTS.md aplicáveis. A referência consultada é
0b2ba4f, com Sprint 12 implementada; preserve trabalho existente e posterior.
Leia docs/planejamento.md, docs/sprint13.md integralmente, docs/sprint11.md,
docs/sprint12.md e seus registros de validação, além dos contratos de precisão,
indicadores, risco, reservas e catálogo afetados. Confira a suíte e comandos de
entrada da seção 10. O registro anterior de 203 testes/Python 3.12.14 não substitui
verificação atual. Registre pré-requisito ausente antes do trabalho dependente.
Use Python >=3.11 em ambiente isolado, biblioteca padrão e unittest.

Implemente BINANCE_SPOT_KLINES_CSV_V1 para ZIP/CSV Spot final de BTCUSDT/ETHUSDT,
USDT e 1m. Crie obter-dados, importar-dados e validar-dados com argumentos,
formatos e códigos da seção 10. Rede somente em obter-dados explicitamente
acionado para os quatro ZIPs oficiais de 31/12/2024 e 01/01/2025 e seus checksums.
Consulte as fontes oficiais da seção 3 ao implementar. URLs/hashes de dados ainda
não foram verificados nesta especificação: obtenha e registre os reais, sem inventar.
Implemente timeout/tentativas, limites de tamanho, integridade SHA-256/CRC,
proteção de ZIP e publicação de downloads completos sem sobrescrever revisões.
Permita os mesmos arquivos locais; nenhum importador/backtest deve acessar rede.

Crie as duas receitas reais completas das seções 3.2 e 7.1, catálogos/evidências,
armazenamento bruto imutável e normalização rastreável. Valide todos os arquivos
inteiros antes do recorte. Aceite 12 colunas, unidades explícitas ms/us por arquivo,
ordem ascendente, OHLC/volumes/trades válidos e Decimal sem float. Mantenha volume
base no Candle e preserve campos auxiliares na proveniência. Converta tempo com
aritmética inteira: close_time inclusivo + uma unidade = fim exclusivo de minuto.
Use janela [start,end), UTC e as_of fixo. Não arredonde para encobrir erro de unidade.
Não use candles incompletos, não aqueça com exclusões e declare a hipótese de arquivo
final disponível no fechamento, sem afirmar reconstrução de revisões em tempo real.

Implemente catálogo/metadados e candles versionados em SQLite, conforme seção 5,
com migração PRAGMA user_version, chaves, foreign_keys e transações parametrizadas.
Preserve valores financeiros como TEXT decimal canônico, tempo inteiro ordenável
e contagens INTEGER. Não use REAL, CAST financeiro, soma financeira ou ordenação
lexicográfica de preço em SQL. Calcule finanças em Python com contexto local e razões
exatas. Mantenha biblioteca padrão; Parquet/DuckDB só se medição justificar decisão.

Separe dataset_version lógico e ingestion_id de proveniência. Fixe hashes de bruto,
normalizado, catálogo/universo, adaptador/código/políticas e receita original. Caminhos,
ordem de arquivos e relógio de obtenção não decidem identidade lógica. Duplicata final
numericamente equivalente é ignorada e rastreada; conteúdo final divergente no mesmo
lote é CANDLE_CONFLICT. Reimportação é inócua. Correção divergente de versão aceita
exige supersedes/revision_reason, gera novo ID e mantém pai intacto. Sem revisão
explícita, DATASET_CONFLICT. Experimentos nunca resolvem latest implicitamente.

Prepare todos os arquivos antes do commit SQLite único. Falha no último arquivo,
conflito ou erro técnico não aceita prefixo do lote. Blobs órfãos não representam
versões válidas. Distinga commit de ingestão e exportação: falha posterior de relatório
informa versão aceita/EXPORT_FAILED e conserva INCOMPLETE sem manifesto final.
Não prometa atomicidade distribuída entre arquivos e SQLite. API tipada segue as mesmas
regras de validação, deduplicação, precisão e preservação de estado.

Autorize BINANCE_SPOT contextualmente nos modelos/Catalog/configurações schemas 6/7,
sem renomear dado real como FICTICIA nem abrir os caminhos legados sem catálogo a
qualquer origem. Preserve schemas 1/2/4/5/6/7, análise 3, executar, comparar e carteira.
Reutilize os mesmos indicadores, execução, risco, reservas, ledger e relógio global.
Exija manifesto fixo para origem real: --dataset-manifest no individual e campo manifest
por dataset nas receitas reais de matriz/carteira. Verifique IDs/hashes/associações antes
do replay; não dependa do banco para executar o snapshot exportado. Gere os dez arquivos
de exportação e receitas completas da seção 7.2, com parâmetros fixos da seção 7.3.

Documente universo temporal em evidência auxiliar versionada. Para a amostra externa,
sem prova histórica completa, use OBSERVED_COVERAGE_ONLY e SURVIVORSHIP_RESTRICTION;
não infira listagem/deslistagem pela borda do arquivo nem pela lista atual de pares.
Declare filtros, taxa 0.001 e slippage zero como hipóteses da demonstração, não fatos
históricos da exchange. Conserve os modos e unidades dos relatórios legados.

Crie as fixtures sintéticas de formato ms/us, ZIPs/checksums determinísticos e a receita
sprint13-importacao-fixture.json da seção 9.1. São FICTICIA/SYNTHETIC_FORMAT_FIXTURE,
explicitamente separadas dos dados reais. Reproduza oito candles por par, compras às
00:01 e vendas às 00:03 de 01/01/2025, quatro fills, dois lotes, 0.000166 BTC/0.00420 ETH,
caixa 989.95 USDT, taxas 0.05, retorno -1.005%, 120 segundos conjuntos e código 0.
Implemente a fixture de retirada ETH [23:58,00:02) da seção 9.2: quatro candles ETH,
oito BTC, sem lacuna fora da disponibilidade; lote aberto continua atribuído,
com marca/idade e proteção indisponível, sem venda inventada.

Exercite todas as variantes da seção 9.3: duplicatas com escala distinta, conflito
válido de OHLC, revisão explícita e preservação do pai, checksum/ZIP/unidade/ordem
inválidos, incomplete/as_of, lacuna interna global conservando sinais/reservas,
rollback de lote multi-arquivo, falha SQL/escrita, contexto Decimal hostil, ordenação
TEXT enganosa, paridade arquivo/API, permutações e reabertura offline. Alterar OHLC
futuro não pode mudar decisão anterior. Teste ausência de qualquer chamada de rede
em validar/importar/replay. Verifique origem/unidades nos eventos e relatórios.

Crie relatório de qualidade JSON/texto/Markdown/HTML com integridade, contagens,
exclusões, duplicatas, lacunas, universo, hipóteses e proveniência; não confunda qualidade
com desempenho. Realize aquisição explícita ou forneça cópia local verificável dos
arquivos oficiais, fixe hashes reais e reproduza offline em banco novo e por snapshot
sem banco. Se a fonte estiver indisponível, conclua trabalho local e registre a
verificação real pendente; não declare conclusão integral nem use resultado sintético
como histórico. Lucro, quantidade de trades e código 0 no replay real não são exigidos.

Execute e registre cada comando da seção 10, códigos individuais, valores observados,
regressões e exemplos expandidos anteriores afetados. Compare snapshots/IDs/conteúdo
SQLite logicamente; compare quinze artefatos de carteira e HTML repetidos por bytes
para snapshot/código fixos. Verifique quatro formatos, outra cwd, manifesto divergente,
saída existente e falha de escrita. Inspecione HTML de qualidade/replay offline em
desktop, tela estreita, print e sem JavaScript, preservando assets/licenças.

Atualize README/planejamento e crie docs/sprint13-glossario.md,
docs/sprint13-validacao.md e docs/decisoes/sprint13-ingestao.md. Registre ambiente,
arquivos alterados, fontes/hashes concretos, modelos, comandos realmente executados,
esperado/observado, limitações e pendências. Corrija falhas no escopo e conclua a entrega;
não entregue apenas proposta. Não antecipe seleção temporal, walk-forward, novas
frequências/estratégias, otimização, paralelismo ou negociação conectada. Verificações
não realizadas devem permanecer explicitamente pendentes.
```
