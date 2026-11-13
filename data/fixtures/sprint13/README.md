# Fixture sintética de formato — Sprint 13

Estes CSVs, ZIPs e checksums foram gerados localmente para conferir a normalização ms/us e a aritmética da Sprint 12 em outra janela temporal. A origem é FICTICIA e o tipo é SYNTHETIC_FORMAT_FIXTURE. Não são arquivos históricos externos; seus checksums não são assinaturas nem checksums oficiais da Binance.

Os ZIPs usam timestamp interno fixo em 01/01/2025 00:00 UTC e um membro CSV. Os CSVs correspondentes facilitam conferência manual. BTC fecha em 100000, 90000, 80000, 100000, 120000, 100000, 80000, 80000; ETH é BTC/50. A janela é 31/12/2024 23:56 até 01/01/2025 00:04 UTC. O primeiro arquivo de cada par usa milissegundos; o segundo usa microssegundos, conforme o dia declarado na receita.

Receitas: `experiments/sprint13-importacao-fixture.json` e variante temporal `experiments/sprint13-importacao-retirada.json`. A segunda limita ETH a [23:58,00:02) e conserva o mesmo bruto, registrando exclusões de disponibilidade.
