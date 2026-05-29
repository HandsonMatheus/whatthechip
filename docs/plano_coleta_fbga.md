# Plano de Coleta FBGA — WhatTheChip

> Objetivo: construir uma base de KnownParts densa o suficiente para que qualquer  
> chip Micron que chegue à bancada de reciclagem já esteja no banco de dados.

---

## Contexto

Os chips que chegam na esteira são majoritariamente de 2015–2021.  
O identificador físico gravado a laser no chip é o **FBGA code** (5 chars alfanuméricos, ex: `JY941`, `D9TVH`).  
Um mesmo PN base (ex: `MT29PZZZ8D5BKFTF`) pode ter 3+ variantes de silício, cada uma com FBGA distinto.

A estratégia é rodar o pipeline abaixo **manualmente, ~1× por mês**, acumulando cobertura progressivamente.

---

## Arquitetura do Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — Micron oficial (CSV + FBGA API)                confidence: confirmed  │
│  Script: import_micron_catalog + enrich_micron_fbga                  │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 2 — Datasheets PDF                                 confidence: confirmed  │
│  Script: python scripts/collect_datasheets.py                        │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 3 — Octopart API                                   confidence: distributor│
│  Script: python manage.py collect_octopart                           │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 4 — Preduo bulk crawl                              confidence: distributor│
│  Script: python manage.py collect_preduo_bulk                        │
├──────────────────────────────────────────────────────────────────────┤
│  STAGE 5 — Wayback Machine (último recurso)               confidence: estimated  │
│  Script: python scripts/collect_wayback.py                           │
└──────────────────────────────────────────────────────────────────────┘
```

Cada stage enriquece o banco sem sobrescrever dados de confidence maior.  
Rodá-los na ordem garante que fontes mais confiáveis têm prioridade.

---

## Stage 1 — Micron oficial

### Scripts
| Comando | Descrição |
|---|---|
| `python manage.py import_micron_catalog` | Importa CSVs baixados do site Micron |
| `python manage.py populate_micron_mcp` | Cria ChipFamilies e DecodeMap MIC_MCP_CAP |
| `python manage.py enrich_micron_fbga` | Para cada KnownPart raw, consulta FBGA API Micron |
| `python scripts/fix_micron_mcp_capacity.py` | Corrige capacity em registros MT29VZZZ*/MT30AZZZ* |

### Fluxo
1. Baixe os CSVs de https://www.micron.com/products/mobile-storage-and-computing
   (seções: emmc-based-mcp, ufs-based-mcp, lpddr4, lpddr5, emmc, ufs)
2. Coloque em `data/micron_csvs/`
3. `python manage.py import_micron_catalog data/micron_csvs/`
4. `python manage.py populate_micron_mcp --overwrite`
5. `python manage.py enrich_micron_fbga --delay 1.5`

### Resultado esperado
- KnownParts com `status=enriched`, `confidence=confirmed`, `fbga_code` preenchido
- Um registro por FBGA — identificador físico definitivo

---

## Stage 2 — Datasheets PDF

### Script
```bash
python scripts/collect_datasheets.py [--dry-run] [--limit N] [--delay N]
```

### O que faz
1. Consulta a API FBGA da Micron para obter `pageurl` de cada produto
2. Acessa a página do produto e localiza o link do datasheet PDF
3. Baixa o PDF (cache local em `data/datasheets/`)
4. Usa `pdfplumber` para extrair a tabela "Ordering Information"
5. Para cada linha: extrai PN completo + FBGA code
6. Salva no banco com `status=confirmed`, `confidence=confirmed`

### Dependência
```bash
pip install pdfplumber
```

### Por que é valiosa
Um único datasheet de família (ex: MT29PZZZ família) contém **todas** as variantes  
(gerações, densidades, temperaturas, embalagens) — dezenas de chips em um PDF.

---

## Stage 3 — Octopart API

### Script
```bash
python manage.py collect_octopart [--dry-run] [--limit N] [--chip-type eMCP]
```

### Pré-requisito
Obtenha uma chave gratuita em https://octopart.com/api/home  
(ou https://nexar.com/api para a v4 GraphQL)

```bash
# .env ou variável de ambiente
OCTOPART_API_KEY=sua_chave_aqui
```

### O que faz
1. Envia queries GraphQL para a API Octopart v4 paginando por fabricante "Micron Technology"
2. Para cada chip retornado: salva PN + specs + link para datasheet
3. Links de datasheet são adicionados à fila do Stage 2 (`data/datasheet_urls.txt`)
4. Chips não encontrados nos stages 1/2 entram como `confidence=distributor`

### Papel duplo
- Fonte direta de dados (specs, PN) — confidence: distributor  
- Descobridor de datasheets novos para o Stage 2 — alimenta a fila PDF

---

## Stage 4 — Preduo bulk crawl

### Script
```bash
python manage.py collect_preduo_bulk [--dry-run] [--max-pages N] [--delay N]
```

### O que faz
1. Raspa preduo.com filtrando todos os chips com prefixo Micron (MT, D9, NW)
2. Tipos cobertos: eMCP, eMMC, UFS, LPDDR4, LPDDR5, NAND Flash, DRAM
3. Deduplication: não cria duplicatas se PN já existe com confidence >= distributor
4. Alimenta a fila do Stage 2 com datasheets encontrados nos anúncios

### Diferencial vs. scrape_preduo
`scrape_preduo.py` é para consultas pontuais.  
`collect_preduo_bulk.py` é otimizado para coleta em volume:
- Foco exclusivo em chips Micron (mais rápido)
- Exporta lista de datasheets para Stage 2
- Relatório de cobertura por tipo

---

## Stage 5 — Wayback Machine (último recurso)

### Script
```bash
python scripts/collect_wayback.py [--dry-run] [--years 2015-2021] [--limit N]
```

### O que faz
1. Usa a CDX API gratuita do Wayback Machine para encontrar snapshots de:
   - Páginas de produto Micron arquivadas (2015–2021)
   - Páginas de distribuidores com Micron chips (Preduo, Farnell, DigiKey archivados)
   - Páginas de catálogos de reciclagem com FBGAs listados
2. Para cada snapshot, extrai PNs e FBGAs do HTML arquivado
3. Salva com `confidence=estimated` — sinaliza que precisa de verificação

### Quando usar
Apenas para chips que não foram encontrados nos stages 1–4.  
Dados com `confidence=estimated` requerem confirmação manual antes de confiar.

---

## Tabela de confidence

| Fonte | confidence | Quando usar |
|---|---|---|
| Micron CSV + FBGA API | `confirmed` | Stage 1 — fonte primária |
| Datasheet PDF (Ordering Info) | `confirmed` | Stage 2 — máxima fidelidade |
| Octopart API | `distributor` | Stage 3 — confiável mas não fabricante |
| Preduo bulk crawl | `distributor` | Stage 4 — grande volume, boa precisão |
| Wayback Machine | `estimated` | Stage 5 — último recurso, verificar manualmente |

---

## Frequência recomendada

| Frequência | Stages |
|---|---|
| Mensal | Stages 3 + 4 (novos chips nos distribuidores) |
| A cada nova série | Stage 1 (novos CSVs da Micron) |
| Pontual | Stage 2 (novos datasheets descobertos) |
| Raro | Stage 5 (chips "fantasma" que chegam na bancada) |

---

## Estrutura de diretórios

```
chipdocs/
├── data/
│   ├── micron_csvs/          ← CSVs baixados do site Micron (Stage 1)
│   ├── datasheets/           ← PDFs em cache (Stage 2)
│   └── datasheet_urls.txt    ← Fila de URLs para Stage 2 (alimentada por 3+4)
├── docs/
│   └── plano_coleta_fbga.md  ← Este arquivo
└── scripts/
    ├── collect_datasheets.py  ← Stage 2
    └── collect_wayback.py     ← Stage 5
chips/management/commands/
    ├── import_micron_catalog.py   ← Stage 1
    ├── enrich_micron_fbga.py      ← Stage 1
    ├── collect_octopart.py        ← Stage 3
    └── collect_preduo_bulk.py     ← Stage 4
```

---

## Chips fantasma conhecidos

Chips que chegaram na bancada e **não** foram encontrados no banco (referência):

| FBGA | Observação |
|---|---|
| JY941 | Encontrado mas sem capacidade |
| D9TVH | Encontrado mas sem capacidade |
| JZ109 | Não encontrado — priority Stage 2 + 5 |
| D9RRD | Não encontrado |
| JWB13 | Não encontrado |
| JWA6  | Não encontrado |

Estes devem ser re-verificados após rodar os stages 2–5 completos.
