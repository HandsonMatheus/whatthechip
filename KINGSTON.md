# KINGSTON — bíblia técnica (WhatTheChip)

> ⚠️ **O CONHECIMENTO É YAML.** As famílias e PNs confirmados da Kingston vivem em
> **`chips/knowledge/kingston.yaml`**, carregado por `load_brands`. Para **adicionar ou corrigir
> um chip, edite o yaml** seguindo o **`CONTRATO_AUTORIA_YAML.md`** — NÃO edite Python.

## Visão geral

**Kingston Technology** — EUA, fundada 1987. Diferente das outras marcas, a Kingston é
majoritariamente uma **montadora de módulos** (DIMM/SO-DIMM), não fabricante de dies. No
mercado de reciclagem, o que chega em forma de **chip** dela é o **eMCP** (eMMC + LPDDR num
package), usado em produtos embarcados. Brand `code = KST`.

## Famílias (decode em `kingston.yaml`)

**eMCP — as reais (ATIVAS):** prefixo numérico = capacidade eMMC em GB; dígitos após `EMCP` =
RAM em Gbit ÷ 8. Ex.: `16EMCP08-...` → 16GB eMMC + 08Gb÷8 = 1GB LPDDR3.

| Prefixo | chip_type | Nota |
|---|---|---|
| `04EMCP` / `08EMCP` / `16EMCP` / `32EMCP` / `64EMCP` | eMCP | capacidade no prefixo |
| `EMCP` | eMCP | fallback genérico (raro casar) |

**Módulos — DESATIVADOS (`active: false`), NÃO mexer:** `KVR` (ValueRAM), `KF` (Fury), `ACR`.
São **códigos de MÓDULO DIMM, não chip** — foram marcados `active=false` de propósito (bogus).
⚠ **NÃO reative nem adicione capacidade a eles.** `KF9` (Samsung NAND) NÃO é Kingston Fury —
cuidado com o prefixo `KF`.

## Como popular

O foco da Kingston é o **eMCP embarcado**. Confirme o PN em datasheet Kingston (kingston.com,
seção embedded/industrial) ou Octopart. Ver o **`CONTRATO_AUTORIA_YAML.md`** (§4 famílias eMCP,
§6 known_parts). Não crie famílias de DRAM avulsa — a Kingston não fabrica dies de DRAM.
