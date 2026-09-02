# Investigação — SanDisk família NOVA `SDED` (mDOC H3 / DiskOnChip), PN `SDED5001G` (2026-09-02)

> ✅ **Resultado: família nova `SDED` (magra, chip_type=eMMC com ressalva) + 6 known_parts
> `confidence=confirmed`.** Datasheet oficial SanDisk lido na íntegra (86 págs, mirror
> alldatasheet.com). Arquivos: `chips/knowledge/sandisk.yaml` (família), `sandisk_sded5_2026-09-02.yaml`
> (known_parts), golden anchor `SDED5001G` em `chips/tests.py::_SD_GOLDEN`.

## 0. O gatilho

Debug do estoque, 02/09/2026 13:43:34, PN `SDED5001G`. Resultado: `known: false`, nenhuma família
bateu (`Família: —`), `fuzzy_suggestions: []` — primeira vez nesta marca que uma família inteira
está ausente do catálogo (nem fallback genérico SDIN casava o prefixo).

## 1. Descoberta do cluster

Busca inicial ("SDED5001G" SanDisk) trouxe pouco direto, mas um catálogo de distribuidor
(findcomponents.net/catalog/cat/SDE) revelou uma família INTEIRA nunca vista: dezenas de PNs
`SDEDx-xxx-xx` (e primos `SDEG`, `SDEH1`, `SDEP3`, `SDE04/07/08/13/15/25/26/45/48/72`), vários
atribuídos a "MSYSTEM" ou "Sandisk", um até a "TOSHIBA" (`SDEP3032M1TT`). Isso é claramente
tecnologia da **M-Systems** (empresa israelense adquirida pela SanDisk em 2006, pioneira do
"DiskOnChip") — muito mais antiga que qualquer coisa já catalogada nesta marca (SD5DH/SDIN começam
~2007-2013).

## 2. Confirmação via datasheet oficial

Busca dedicada ("SDED5-001G" SanDisk datasheet) achou o documento oficial, indexado (com
atribuição de fabricante ERRADA — "Sanken electric") em alldatasheet.com:
`SDED5-001G-NAT`, doc **92-DS-1205-10 Rev.1.3**, "mDOC H3 EFD Featuring Embedded TrueFFS Data
Sheet", **maio/2008**, 86 páginas, **© 2007 SanDisk® Corporation** (cabeçalho da pág.1 — a
atribuição a "Sanken" é só um erro de indexação do agregador; o conteúdo é inequivocamente
SanDisk). Lido via técnica de mirror HTML já usada nesta marca (`alldatasheet.com/html-pdf/...`,
página por página).

**Página 1** confirma o produto: "mDOC H3 is an Embedded Flash Drive (EFD) designed for mobile
handsets and consumer electronics devices... the new generation of SanDisk's successful mDOC
product family, enabling tens of millions of handsets... since the year 2000... hybrid device
combining an embedded thin flash controller and standard flash memory... uses advanced
Multi-Level Cell (MLC) and binary (SLC) NAND flash technologies, enhanced by SanDisk's proprietary
TrueFFS embedded flash management software".

**Página 2** dá os dados técnicos usados nesta submissão: "1Gb (128MB) – 64Gb (8GB) data storage
capacity, with device cascading options for up to 128Gb (16GB)"; "Low voltage: 1.8V Core and I/O /
3.3V Core and 3.3V/1.8V I/O (auto-detect)"; pacote "mDOC H3 1Gb/2Gb - 115-ball FBGA 9x12mm" /
"mDOC H3 4Gb/8Gb - 115-ball FBGA 10x14mm".

**Página 9** (índice de seções) mostra que a interface é **paralela/memory-mapped** — "9.3 Demux
(Standard) Interface", "9.4 Multiplexed Interface", "6.4 128KB Memory Window", "6.5 8KB Memory
Window" — **NÃO** é protocolo serial MMC. Isso é a diferença crítica em relação a todo o resto do
catálogo SanDisk (que é tudo eMMC/UFS de verdade).

Corroboração independente pra `SDED5001G` especificamente: distribuidor (Jotrin/veswin) lista
"SDED5-001G-NA(T/Y)" como "IC FLASH 8GBIT 115BGA", 1.65V~1.95V, -25°C~85°C — 8Gbit = 1GB, bate com
a densidade do datasheet e com o sufixo "001G" do PN.

## 3. Decisão de classificação — chip_type=eMMC com ressalva

mDOC H3 não é MMC — é um dispositivo NAND gerenciado (controlador + TrueFFS embarcado) com
interface proprietária paralela. Nosso vocabulário fechado (`chips/chip_types.py`) não tem
categoria "DiskOnChip"/"mDOC" própria. Decisão: classificar como `chip_type=eMMC` (categoria mais
próxima — NAND gerenciado com controlador embutido) com ressalva ⚠⚠ bem visível no tip, mesmo
tratamento já dado à `SDIN2xx` (SD1.1/2.0+SPI, também "não é eMMC de verdade" mas fica na mesma
família por proximidade de categoria). Não criei chip_type novo — decisão de vocabulário fica pro
dono se um dia for necessário.

**Implicação operacional:** avisado no tip que esse chip pode precisar de leitor/adaptador
compatível DiskOnChip, não um leitor eMMC padrão — informação que o operador de bancada precisa
antes de tentar ler o chip.

## 4. Escopo — só SDED5 (geração H3) confirmada, resto é backlog

O catálogo do distribuidor mostrou também `SDED7xxx` (mesmas capacidades ~128M-2G) e as famílias
irmãs `SDEG`/`SDEH1`/`SDEP3`/`SDE04/07/08/13/15/25/26/45/48/72` — não pesquisadas nesta rodada.
Podem ser gerações mDOC anteriores (o datasheet menciona "since the year 2000", ou seja, várias
gerações antes da H3) e/ou produtos de 2ª fonte (um deles aparece atribuído a "TOSHIBA" no
catálogo). Ficam como backlog explícito no tip da família — mesmo tratamento dado a
SDINHDL6/SDINBDG4/etc. em rodadas anteriores.

## 5. known_parts submetidos (6)

| PN | Capacidade | Pacote | Confidence |
|---|---|---|---|
| SDED5001G | 1GB | 115-ball FBGA 9x12mm | confirmed |
| SDED5002G | 2GB | 115-ball FBGA 9x12mm | confirmed |
| SDED5004G | 4GB | 115-ball FBGA 10x14mm | confirmed |
| SDED5008G | 8GB | 115-ball FBGA 10x14mm | confirmed |
| SDED5512M | 512MB | 115-ball FBGA 9x12mm | confirmed |
| SDED5256M | 256MB | 115-ball FBGA 9x12mm | confirmed |

## 6. Limitações

- Código de 2 letras antes do sufixo de embalagem (ex.: "NA"/"NC"/"AC" em
  `SDED5-002G-AC(Y)`/`SDED5-002G-NC(T/Y)`) **não decodificado** — não achei a tabela de ordering
  information formal dentro do datasheet (86 páginas, não vasculhado por completo). Não acho que
  isso mude capacidade/tipo, só possivelmente tensão ou tecnologia SLC/MLC.
- `SDED7xxx` e famílias irmãs (`SDEG`/`SDEH1`/`SDEP3`/etc.) — backlog, zero pesquisa própria.
- Golden test (`SDED5001G` em `chips/tests.py::_SD_GOLDEN`) **não testado contra a suíte real** —
  sandbox sem venv utilizável (limitação já conhecida desta sessão). Tupla inferida por analogia
  direta com `SD5DH24A4G` (mesmo padrão: família magra, sem known_part no banco de teste →
  `("eMMC", "", "", "", "", "INDETERMINADO")`). Se não bater, é ajuste de 1 linha — pedir ao dono
  rodar `python manage.py test chips --settings=core.settings_test` pra confirmar.
- 512MB/256MB quase certamente caem em NÃO RENTÁVEL por capacidade — não forcei o veredito, deixei
  o `assess_profitability` decidir sozinho como de costume.

## 7. Fontes

- Datasheet oficial (lido via mirror): https://www.alldatasheet.com/html-pdf/520032/SANKEN/SDED5-001G-NAT/452/2/SDED5-001G-NAT.html (pág.2) e páginas 1, 9 do mesmo doc (92-DS-1205-10 Rev.1.3).
- https://findcomponents.net/catalog/cat/SDE (catálogo do cluster completo, achado do backlog)
- https://www.veswin.com/product-SDED5-001G-NA.html (distribuidor, corrobora 1GB/115BGA)
- Jotrin, elcodis, avaq.com, tech-electr.com — listagens de distribuidor pros demais PNs do cluster (capacidade/sufixo, não specs elétricos completos)

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDIN, pra confirmar
ausência de conflito de prefixo), `chips/tests.py` (`_SD_GOLDEN`, padrão de tupla pra família
magra sem known_part de teste).
