# Investigação — SanDisk cluster `SDIN8DR1` (backlog SDIN8xx), PN `SDIN8DR116G` (2026-08-26)

> ✅ **Resultado: 2 known_parts, `confidence=distributor`.** Sem datasheet oficial POR-PN
> encontrado — evidência via distribuidor autorizado (Mouser + Octopart/Avnet) + categoria Preduo.
> Arquivo: `sandisk_sdin8dr1_2026-08-26.yaml`.

## 0. O gatilho

Debug do estoque, 26/08/2026 14:42:57, PN: `SDIN8DR116G`. Família = `SDIN` (fallback genérico,
priority 80), `known_exact=false`, `confidence=estimated`, `profitable=INDETERMINADO`,
`pn_not_in_db=true`. Fuzzy sugeriu `SDIN5D116G` (já confirmado hoje mais cedo) e `SDIN8DE216G`
(sub-código irmão dentro do mesmo bucket "8xx", investigado parcialmente — ver §4).

O tip da família já sinalizava `SDIN8xx = e.MMC 4.51 HS200 (backlog, sem datasheet lido ainda)` —
esta rodada tentou fechar esse backlog e só fechou parcialmente (ver §3).

## 1. Identidade — SDIN8DR1 é real, distinto de SDIN8DE1/DE2/DE4

Confusão inicial: buscar "SDIN8DR1" no alldatasheet.com só retorna, por fuzzy match, entradas
"SDIN8DE1"/"SDIN8DE2" (1 letra de diferença, E↔R). Mas `SDIN8DR1` é confirmado como produto
DISTINTO via evidência de mercado real e estruturada:

- **Mouser** (distribuidor autorizado): `SDIN8DR1-8G-V` — campo estruturado "Memory Size: 8 GB",
  "Sequential Read: 4.5 MB/s", "Sequential Write: 100 MB/s", Tradename "iNAND", Packaging "Tray",
  ECCN 5A992, país de origem China, ciclo de vida Obsolete.
- **Octopart/Avnet**: `SDIN8DR1-16G` (SEM sufixo "-V") — descrição estruturada de distribuidor
  autorizado: "SDIN8DR1-16G,VFBGA 11.5X1X1.0,GENERIC". Bate exatamente com o PN normalizado do
  debug (sem sufixo).
- **Preduo**: categoriza `SDIN8DR1-8G` sob a URL `emmc/emmc-4-51` — confiável pra TIPO (CLAUDE.md
  §6), corrobora a suposição já registrada no tip ("SDIN8xx = e.MMC 4.51"), mas não é fonte de
  specs elétricos.

Nenhum datasheet oficial WD/SanDisk foi encontrado **especificamente** pra `SDIN8DR1`. O único doc
oficial indexado no alldatasheet.com pra qualquer PN começando com "SDIN8D" (IDs sequenciais
1452029-1452043) é um **brief de marketing genérico** — "SanDisk Commercial Embedded Storage
Solutions" — que descreve as LINHAS de produto `iNAND 5130` (16-64GB, eMMC 5.0 HS400) e
`iNAND 7232` (16-128GB, eMMC 5.1 HS400) em termos gerais, sem tabela de ordering por PN. Esse MESMO
PDF está anexado a ~9 PNs diferentes no índice do alldatasheet (`SDIN8DE1-8G`, `SDIN8DE2-8G/16G`,
`SDIN8DE4-32G/64G`, `SDIN8CE4-128G`, `SDIN9DS2-*`, `SDIN7DP2-4G`/`SDIN7DP4-16G`, `SDINADB4-16G`) —
confirma que é um catch-all de indexação, não evidência específica de `SDIN8DR1`.

## 2. Sufixo — "-V" presente no 8G, ausente no 16G

`SDIN8DR1-8G-V` (Mouser) vs `SDIN8DR1-16G` (Octopart/Avnet, sem sufixo). Diferente do padrão "-L"
(SDIN5D1, sempre presente/opcional-uniforme — ver rodada anterior de hoje), aqui a presença do
sufixo VARIA por capacidade nas fontes encontradas — não investigado a fundo se é grade/variante
real ou só inconsistência de como cada distribuidor lista o PN. PN normalizado do debug (`SDIN8DR116G`,
sem sufixo) bate com a fonte Octopart/Avnet — submetido sem sufixo, consistente com o resto da marca.

## 3. Interface — corroborada, NÃO confirmada por leitura direta

Preduo categoriza sob "emmc-4-51", consistente com o tip pré-existente ("SDIN8xx = e.MMC 4.51
HS200"). Mas isso é uma categoria de URL de distribuidor, não uma leitura de datasheet — **não
fecha a barra de `manual`/`confirmed`** (regra SANDISK.md §0.3: exige 3 fontes de engenharia
convergentes OU leitura direta de datasheet; aqui não há nenhuma das duas). Por isso os 2
known_parts entram como `confidence=distributor`, com o campo `interface` já sinalizando
explicitamente a incerteza ("categoria Preduo — não confirmado por datasheet lido").

## 4. Achado de bônus — SDIN8DE1/DE2/DE4 (backlog, não pesquisado a fundo)

O fuzzy sugeriu `SDIN8DE216G`. Confirmado como cluster real (Mouser: `SDIN8DE2-8G-A` HS200,
4/8/16GB, FBGA153, -25°C~85°C; outras fontes mencionam `SDIN8DE1`/`SDIN8DE4` até 64GB, sufixos de
grade `-I`/`-XA` vistos) — mas **não pesquisado a fundo hoje** (fora do escopo do PN do caso).
Mesmo "brief genérico" problema do §1 se aplica: sem ordering table específica encontrada. Fica
como backlog pra rodada futura — dedicar uma investigação própria, incluindo tentar achar um
datasheet mais específico (busca direcionada em domínios sandisk.com/westerndigital.com, não só
agregadores).

## 5. known_parts submetidos (2)

| PN | Capacidade | Confidence | Fonte principal |
|---|---|---|---|
| SDIN8DR116G | 16GB | distributor | Octopart/Avnet |
| SDIN8DR18G | 8GB | distributor | Mouser |

## 6. Limitações

- Nenhum datasheet oficial POR-PN encontrado — teto de confiabilidade é `distributor`.
- Interface "e.MMC 4.51" é corroborada (Preduo) mas não confirmada por leitura direta.
- Cluster de capacidades: só 8G/16G encontrados; busca por 4G/32G/64G não achou nada.
- Sufixo "-V" não investigado a fundo (presente no 8G, ausente no 16G nas fontes encontradas).
- `SDIN8DE1`/`SDIN8DE2`/`SDIN8DE4` — achado de bônus, backlog não pesquisado a fundo (ver §4).

## 7. Fontes

- https://octopart.com/sdin8dr1-16g-western+digital-107717569
- https://www.mouser.com/ProductDetail/SanDisk/SDIN8DR1-8G-V
- https://www.preduo.com/product/emmc/emmc-4-51/sdin8dr1-8g
- https://www.alldatasheet.com/view.jsp?Searchword=SDIN8DR1 (confirma ausência de doc POR-PN)
- https://www.arrow.com/en/products/sdin8dr1-8g-v/sandisk.html

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDIN, tip atualizado).
