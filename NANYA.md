# NANYA — bíblia técnica (WhatTheChip)

> ⚠️ **O CONHECIMENTO É YAML.** As famílias e PNs confirmados da Nanya vivem em
> **`chips/knowledge/nanya.yaml`**, carregado por `load_brands`. Para **adicionar ou corrigir
> um chip, edite o yaml** seguindo o **`CONTRATO_AUTORIA_YAML.md`** — NÃO edite Python.

## Visão geral

**Nanya Technology** — Taiwan, fundada 1995 (spin-off da Formosa Plastics). Fabricante de
**DRAM** (DDR/DDR3/DDR3L/DDR4, LPDDR). Prefixo principal do PN: **`NT5`**. Brand `code = NANYA`.

Mercado de reciclagem: DRAM de PC/embarcado de segundo escalão — aceita, mas menor liquidez
B2B que Samsung/Hynix/Micron.

## Famílias (decode completo em `nanya.yaml`)

As famílias Nanya são **magras** — reconhecem o tipo pelo prefixo; a **capacidade vem das
KnownParts** confirmadas (a gramática não decodifica capacidade posicionalmente).

| Prefixo | chip_type | Nota |
|---|---|---|
| `NT5CC` | DDR3 | Ex.: `NT5CC256M16DP-DI` = 256M×16 = 4Gb DDR3 |
| `NT5AD` | DDR4 | Geração posterior ao NT5CC |
| `NT5PA` | DDR3L | Variante low-voltage do NT5CC (notebooks) |

**36 known_parts** confirmados (a maioria NT5CC, via Octopart — página do fabricante Nanya).

## Como popular

Pesquise o PN em **Octopart / datasheet Nanya (nanya.com.tw)**, confirme densidade × largura
(`128Mx16 = 2Gbit`, etc.) e adicione em `known_parts` com `confidence: confirmed` e a fonte em
`notes`. Anatomia típica: `NT5[geração][densidade][organização]-[velocidade/temp]`. Ver o
**`CONTRATO_AUTORIA_YAML.md` §6** pro formato dos campos.
