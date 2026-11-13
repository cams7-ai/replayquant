# Sprint 13 — Ingestão, versões e persistência

Estado: implementado. Referência de entrada: `71c25ac`. Escopo: arquivos Spot finais, USDT, 1m, BTCUSDT/ETHUSDT; Python padrão.

## Fronteiras

`archive.py` contém a única fronteira de rede, acionada por `obter-dados`. `historical_models.py` valida receitas/API; `historical_adapter.py` lê e normaliza o bruto integral; `historical_store.py` aceita lotes em SQLite; `historical.py` exporta snapshots e relatórios; `provenance.py` verifica snapshots portáteis e eventos autorizados. Importação, validação e replay não precisam de conexão à internet.

O motor financeiro é o mesmo das Sprints 06–12. Os modelos de mercado/catálogo autorizam `BINANCE_SPOT`, mas os parsers legados sem catálogo mantêm sua restrição fictícia. Configurações reais exigem `DatasetProvenance` validado; a API incremental confere eventos com o snapshot fixo. O objeto é imutável e sua projeção de identidade não expõe bytes/caminhos. A serialização de dataclasses percorre campos diretamente, preservando essa projeção; proveniência ausente não acrescenta campos aos payloads antigos.

## Normalização

O importador exige CSV de 12 colunas, sem cabeçalho, membro/nome coerentes e unidade explícita por arquivo. O timestamp é convertido por epoch UTC e microssegundos inteiros. O fechamento inclusivo da fonte soma uma unidade para chegar ao fechamento exclusivo do Candle; datas, minuto e duração são validados, sem heurística de magnitude. Nenhuma linha fora da janela é dispensada da validação estrutural.

O snapshot de replay contém apenas candles finais selecionados. O bruto completo e `bar_origin` conservam as outras linhas. Estatísticas por instrumento obedecem `raw_rows = unique_rows + duplicates` e `unique_rows = selected + incomplete + before_window + after_window + outside_availability`. Na tabela por arquivo, `incomplete` conta ocorrências brutas, enquanto selecionadas/exclusões contam a primeira ocorrência aceita. Volume cotação, trades, taker e campo ignorado ficam em metadados auxiliares; Candle.volume é volume base.

As estratégias continuam recebendo somente fechamentos liberados. O snapshot final não demonstra quais revisões eram conhecidas na época: a política é `FINAL_ARCHIVE_ASSUMED_AVAILABLE_AT_CLOSE`. O estado de qualidade não implica aprovação financeira.

## IDs e revisões

`dataset_version` deriva de conteúdo normalizado selecionado, metadados de mercado, origem/tipo, catálogo/universo, janela, as_of e políticas/adaptador. Uma revisão explícita também inclui seu pai e justificativa na identidade: restaurar preços de uma versão antiga continua sendo uma revisão distinta, sem ciclo ou edição retroativa.

`ingestion_id` acrescenta hashes brutos/checksums, associação por símbolo/membro/unidade, estatísticas do lote e hash do código de transformação. Caminhos e relógio de obtenção não participam. Receita textual original fica em `ingestion.recipe_hash`, fora da identidade lógica. Escala decimal equivalente ou duplicação inócua pode criar outra proveniência bruta sem outra versão lógica de candles. O primeiro registro da versão e dos lotes aceitos não é alterado.

Uma versão divergente do mesmo dataset exige `supersedes` e `revision_reason`; o pai deve pertencer ao mesmo dataset e janela. Não há seleção implícita por latest. Objetos são armazenados por SHA-256, publicados com temporário e link exclusivo, sem substituir conteúdo anterior.

## SQLite e atomicidade

`PRAGMA user_version=1` cria `dataset`, `dataset_version`, `raw_object`, `ingestion`, `ingestion_file`, `candle`, `bar_origin`, `instrument`, `universe_evidence` e `quality_issue`. Bancos de versão desconhecida ou bancos não vazios sem versão são recusados. Não há dependência de SQLite externa ao Python.

Valores financeiros usam TEXT canônico, sem expoente/zeros fracionários redundantes/zero negativo. Tempo usa INTEGER em microssegundos UTC; trades/linhas usam INTEGER. Não existem consultas financeiras por REAL, CAST ou soma/ordenação textual de preços. As decisões usam Decimal/Fraction em Python.

Todos os arquivos são preparados antes da transação. `BEGIN IMMEDIATE` protege a publicação de versão, candles e proveniência num único commit, com foreign_keys habilitado. Falha de validação ou SQL não aceita prefixo do lote. Blobs preparados podem ficar órfãos após falha; sua existência não significa versão aceita. Não há coleta automática destrutiva de órfãos nesta sprint.

SQLite e arquivos não compartilham transação distribuída. A exportação acontece depois do commit. Falha de exportação informa `EXPORT_FAILED` e o ID já aceito, conserva INCOMPLETE quando o diretório pôde ser criado e não publica manifesto de sucesso. Reexportar para outro diretório não repete candles. Falha anterior ao commit deixa as versões aceitas intactas. Uma falha de stdout posterior à publicação não apaga dados aceitos.

## Snapshot portátil e relatórios

A exportação contém dez arquivos; o manifesto é escrito por último e referencia hashes dos outros nove, sem ciclo. As receitas internas usam caminhos relativos. Leitura do snapshot verifica arquivos, IDs, catálogo, universo, contagens selecionadas, finalização e identidade dos candles; não depende de SQLite. O manifesto e recibos não são assinatura criptográfica ou prova de autenticidade independente do snapshot confiado pelo usuário.

Execuções individuais usam `--dataset-manifest`; matriz/carteira reais usam `manifest` em cada dataset. Eventos reais permanecem vinculados ao snapshot; catálogos divergentes são recusados. Os manifestos do motor incluem proveniência e o hash de código/assets normal. Relatórios reais exibem origem, qualidade, política de disponibilidade e universo; o exemplo fictício permanece identificado como tal.

A persistência e o replay pequeno não exigiram Parquet/DuckDB. Não foram medidos históricos extensos: a preparação mantém registros em memória e o coordenador compartilhado continua usando snapshots completos por fronteira. A demonstração real limita o replay a oito minutos, embora valide quatro arquivos completos de um dia cada.

## Universo e condições de uso

Os oito minutos reais são uma cobertura observada, com `OBSERVED_COVERAGE_ONLY` e `SURVIVORSHIP_RESTRICTION`. As bordas do catálogo limitam o cenário; não representam datas comprovadas de listagem/deslistagem. O teste de retirada ETH é separado e sintético. Filtros, taxa 0.001 e slippage zero são hipóteses de execução; não se afirmam históricos.

Os ZIPs/checksums oficiais e o recibo de aquisição são conservados localmente para reprodução offline, com atribuição e referência aos termos em `data/historicos/NOTICE.md`. Nenhum serviço foi publicado e nenhuma ordem foi enviada.
