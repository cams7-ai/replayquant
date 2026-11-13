# Glossário da Sprint 13 — Dados históricos reais

| Termo | Significado nesta implementação |
| --- | --- |
| Bruto imutável | Bytes originais de ZIP/checksum, identificados por SHA-256, sem correção em lugar. |
| Adaptador | BINANCE_SPOT_KLINES_CSV_V1: traduz as 12 colunas em Candle e metadados, sem executar operações. |
| Unidade temporal | ms ou us por arquivo; não é inferida pela quantidade de dígitos. |
| Fim inclusivo/exclusivo | Fonte inclui a última unidade do candle; o motor usa o limite exclusivo, uma unidade depois. |
| as_of | Instante UTC fixo que determina quais candles já terminaram; não é o relógio real do importador. |
| Volume base/cotação | Quantidade negociada na base e nocional na moeda de cotação; volume do Candle é somente base. |
| Candle final | Intervalo integralmente encerrado até as_of. Um arquivo final obtido hoje não prova a versão disponível na época. |
| Duplicata equivalente | Mesma chave e campos numéricos equivalentes, inclusive metadados; escala decimal distinta é inócua. |
| Conflito | Valores finais diferentes na mesma chave; o lote é recusado, sem escolher a última linha. |
| dataset_version | Identidade lógica do conteúdo selecionado e seus contratos de catálogo/universo/tempo/políticas; revisões têm linhagem explícita. |
| ingestion_id | Identidade da transformação e dos bytes/evidências que produziram uma versão. |
| supersedes | ID do pai que uma correção explicitamente revisa; o pai continua imutável. |
| Proveniência | Relação entre linha/membro/arquivo, hashes, unidade, normalização e versão executada. |
| TEXT canônico | Decimal sem notação científica ou zeros fracionários redundantes. Não é ordenado como número em SQL. |
| Blobs órfãos | Objetos preparados que não têm versão/lote aceito no banco após falha; não são datasets publicados. |
| EXPORT_FAILED | A ingestão já foi aceita; a exportação falhou. Reexportação não exige apagar nem duplicar a versão. |
| Snapshot portátil | Manifesto e nove arquivos associados, suficientes para replay sem banco ou rede. |
| OBSERVED_COVERAGE_ONLY | Autorização restrita à cobertura da amostra; as bordas não provam listagem ou retirada histórica. |
| SURVIVORSHIP_RESTRICTION | Ausência de prova do universo histórico completo; conclusões limitam-se aos pares observados. |
| SYNTHETIC_FORMAT_FIXTURE | CSV/ZIP didático no formato do adaptador, com origem FICTICIA; não é dado real Binance. |
| QUALITY_WARNINGS | Estrutura válida com issues operacionais, por exemplo lacuna/incompleto/sem observações; código 2. |

Qualidade, integridade e rentabilidade são conceitos distintos. As hipóteses de custos, liquidez, risco e execução das sprints anteriores continuam vigentes. Referências completas em [sprint13.md](sprint13.md) e resultados em [sprint13-validacao.md](sprint13-validacao.md).
