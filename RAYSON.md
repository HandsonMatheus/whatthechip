# RAYSON — bíblia técnica (WhatTheChip)

> ⚠️ **O CONHECIMENTO É YAML.** As famílias e PNs confirmados da Rayson vivem em
> **`chips/knowledge/rayson.yaml`**, carregado por `load_brands`. Para **adicionar ou corrigir
> um chip, edite o yaml** seguindo o **`CONTRATO_AUTORIA_YAML.md`** — NÃO edite Python.

## Visão geral

**Rayson HI-TECH (SZ) Co., Ltd.** — Shenzhen, China, fundada 2016 (também 晶存科技). Fabricante
de memória de **baixo custo** (LPDDR3/4/4X/5, eMMC, UFS, eMCP, MCP). Prefixo principal: **`RS`**.
Brand `code` no yaml.

⚠ **Destino na reciclagem:** produtos Rayson **não são aceitos como substitutos** de
Samsung/Hynix/Micron no B2B premium → **lote segregado Rayson/budget**. Registre isso no
`tip`/`notes` ao popular.

## Famílias (decode em `rayson.yaml`)

| Prefixo | chip_type | Nota |
|---|---|---|
| `RS1G32L` / `RS2G32L` / `RS256M32L` / `RS512M32L` | LPDDR4 | LPDDR4/4X, capacidade no prefixo (32L = x32) |
| `RS256M32LD3` / `RS512M32LD3` | LPDDR3 | variantes LPDDR3 |
| `RS70B08G`…`RS70BT7G` | eMMC | eMMC 5.1, 8GB → 128GB (sufixo = capacidade) |
| `RS70B` | eMMC | fallback (capacidade a identificar) |

## Como popular

Rayson tem datasheets em **rayson-tech.com** (Tier-1) — confirme capacidade/geração ali e
adicione em `known_parts` (`confidence: confirmed`, fonte em `notes`). LPDDR4/4X: cuide da
distinção 4 vs 4X (o portão reduz `LPDDR4/4X`→`LPDDR4` no subtype; a geração exata do chip
específico vem da KnownPart). Ver o **`CONTRATO_AUTORIA_YAML.md`**.
