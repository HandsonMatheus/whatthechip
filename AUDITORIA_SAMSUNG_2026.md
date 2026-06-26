# Auditoria Samsung — WhatTheChip

> ⚠️ HISTÓRICO — menções a Gemini e ao campo `status` estão obsoletas (removidos jun/2026). Ver CLAUDE.md §4 e docs/archive/2026-06-26-remocao-gemini-status.md.

**Data:** 2026-05-09 · **Auditor:** Claude (revisão pré-release)  
**Objetivo:** Panorama completo de tudo que existe, tudo que falta, e o caminho para Samsung 100%.

---

## Resumo Executivo

| Categoria | Famílias mapeadas | Decode completo | Decode parcial | Sem decode |
|---|---|---|---|---|
| DRAM PC (SDRAM→DDR5) | 7 | 6 | 1 (K4RA) | 0 |
| LPDDR Mobile | 14 | 11 | 2 (K3QF, K4X) | 1 (K4M) |
| eMMC standalone | 1 | 1 | 0 | 0 |
| UFS standalone | 4 | 4 | 0 | 0 |
| eMCP (eMMC+LPDDR) | 11 | 11 | 0 | 0 |
| uMCP (UFS+LPDDR) | 8 | 8 | 0 | 0 |
| GDDR (GPU) | 4 | 0 | 0 | 4 |
| NAND Flash (K9) | 8 | 0 | 0 | 8 |
| NOR / OneNAND | 3 | 1 (K5D) | 0 | 2 |
| SRAM | 1 | 0 | — | 1 (resíduo) |
| Especiais (ePoP, BGA SSD) | 2 | 1 (KUS) | 1 (KAT) | 0 |
| SoC / Sensor / PMIC | 5 | 0 | — | 5 (routing) |
| **TOTAL** | **68** | **43** | **4** | **21** |

**Famílias completamente ausentes** (não mapeadas em nenhum nível): ~~K4W~~ → adicionada como gDDR3 em 2026-05-09. ~~K4C~~ → abortada: nenhum PN Samsung real confirmado (provavelmente fantasma).

---

## Parte 1 — DecodeMaps: inventário completo

### 1.1 SAM_FLASH_CAP — 10 entradas
Posição pn[3], 1 char. Usado por KLM (eMMC) e KLU (UFS).

| Chave | Valor | Cobertura |
|---|---|---|
| 2 | 2GB | Legado Smart TVs / modems (~2010-2013) |
| 4 | 4GB | — |
| 8 | 8GB | — |
| A | 16GB | — |
| B | 32GB | — |
| C | 64GB | — |
| D | 128GB | — |
| E | 256GB | — |
| F | 512GB | — |
| G | 1TB | — |

**Status: ✅ COMPLETO.** Cobre toda a gama Samsung eMMC/UFS desde 2GB até 1TB.

**Gap pn[6]: ✅ RESOLVIDO 2026-05-09** — Criado mapa `SAM_EMMC_GEN` (posição pn[6], 1 char): F=eMMC 4.5 · E=eMMC 5.0 · J=eMMC 5.1. Adicionado `decode_gen_pos=6, decode_gen_map="SAM_EMMC_GEN"` ao KLM. O engine (is_emcp=False) usa decode_gen → `r["interface"]` direto, sem tocar no engine.py. Impacto: interface exibida automaticamente por chip; operador separa lotes sem ler o PN manualmente.

---

### 1.2 SAM_EMCP_CAP — 46 entradas
Posição pn[3:5], 2 chars. Usado por todos os eMCP/uMCP (KMQ, KMR, KMG, KM8…).  
val_primary = NAND (eMMC/UFS), val_secondary = RAM (LPDDR).

**Geração legado — matriz direta (2012-2017):**

| Chave | NAND | RAM | Dispositivos típicos |
|---|---|---|---|
| 11 | 4GB | 512MB | Entrada (~2013) |
| 72 | 8GB | 1GB | — |
| 7U | 8GB | 1GB | KMK7U (confirmado usuário) |
| 82 | 16GB | 1GB | — |
| IS | 16GB | 1GB | Galaxy S2 i9100 |
| TU | 16GB | 1GB | Galaxy S3 i9300 |
| 31 | 16GB | 2GB | — |
| 21 | 32GB | 2GB | — |
| 4Z | 32GB | 2GB | KMQ4Z (Gemini) |
| 41 | 32GB | 4GB | — |

**Geração alfanumérica 1 (2017-2019):**

| Chave | NAND | RAM | Fonte | Status |
|---|---|---|---|---|
| ~~5X~~ | ~~8GB~~ | ~~1GB~~ | — | ❌ BLOQUEADO 2026-05-09 — sem PN físico real |
| 8X | **16GB** | 1GB | KMQ8X000SA-B414 (SBiT) ✓ | ✅ CORRIGIDO 2026-05-09 (era 8GB) — KMR8X variante 2GB em fix_known_parts |
| NW | 8GB | 1GB | KMQNW000SM-B316 ✓ | ✅ Confirmado |
| N6 | 8GB | 1GB | KMFN60012MB214 — Octopart ✓ | ✅ Confirmado |
| ~~NX~~ | ~~8GB~~ | ~~1GB~~ | IA externa (Win Source/Arrow) | ❌ BLOQUEADO 2026-05-09 — fonte distribuidor, sem confirmação |
| E1 | 16GB | 2GB | KMQE10013M-B318 ✓ | ✅ Confirmado |
| BT | 16GB | 2GB | — | ⚠️ Sem PN físico |
| V7 | 16GB | 2GB | alias BT | ⚠️ Alias não confirmado independente |
| V8 | 128GB | 4GB | Fabricante ✓ | ✅ Confirmado |
| GD | 32GB | 3GB | — | ⚠️ Sem PN físico |
| W7 | 32GB | 3GB | alias GD | ⚠️ Alias não confirmado independente |
| W8 | 32GB | 4GB | — | ⚠️ Sem PN físico |
| X1 | 32GB | 2GB | KMQX10013MB — Octopart ✓ | ✅ Confirmado |
| H9 | 32GB | 2GB | alias X1 | ⚠️ Alias não confirmado independente |
| C1 | 64GB | 4GB | KMRC10014M — IA externa | ⚠️ Aguarda Octopart |
| M4 | 128GB | 4GB | — | ⚠️ Sem PN físico |
| J2 | 128GB | 6GB | — | ⚠️ Sem PN físico |
| P5 | 256GB | 8GB | — | ⚠️ Sem PN físico |

> **Auditoria 2026-05-09:** 5X e NX bloqueados por falta de evidência. 8X corrigido de 8GB → 16GB NAND (confirmado por B2B SBiT). Chaves sem PN físico (BT, V7, GD, W7, W8, M4, J2, P5) permanecem ativas pois não há conflito confirmado — serão auditadas quando chips físicos chegarem na esteira.

**Geração alfanumérica 2 (2020-2022, padrão [X]6):**

| Chave | NAND | RAM | Fonte |
|---|---|---|---|
| D6 | 32GB | 3GB | — |
| E6 | 32GB | 3GB | alias D6 |
| G6 | 32GB | 3GB | Gemini |
| V6 | 32GB | 3GB | alias D6 |
| U6 | 64GB | 3GB | — |
| X6 | 32GB | 2GB | Octopart ✓ |
| T6 | 64GB | 4GB | — |
| Y6 | 128GB | 4GB | — |
| H6 | 64GB | 4GB | KMRH60014A |
| P6 | 64GB | 4GB | Datasheet ✓ |
| P9 | 64GB | 4GB | Octopart ✓ |
| L6 | 256GB | 8GB | uMCP S21 FE |
| K6 | 128GB | 8GB | KML (S21 Exynos) |

**uMCP linha numérica KM5/KM8/KM2 (confirmados pelo fabricante):**

| Chave | NAND | RAM | Fonte |
|---|---|---|---|
| C7 | 64GB | 4GB | Fabricante ✓ |
| L9 | 128GB | 6GB | Fabricante ✓ |
| F9 | 256GB | 8GB | Fabricante ✓ |
| F8 | 256GB | 12GB | Fabricante ✓ |

**Gaps SAM_EMCP_CAP conhecidos (vão para Gemini):**
- `Z6` — evidência insuficiente. Omitido intencionalmente.
- `T9` — não confirmado por PN real + Octopart.
- `512GB+12GB` — S22 Ultra 512GB / S23 Ultra. Cap_key desconhecida.

---

### 1.3 SAM_EMCP_GEN — 12 entradas
Posição pn[2], 1 char. Decodifica o tipo de RAM nos eMCP/uMCP.

| Chave | RAM | Era |
|---|---|---|
| J | LPDDR2 | 2013-2015 |
| K | LPDDR2 | 2010-2012 |
| F | LPDDR3 | 2015-2019 |
| N | LPDDR3 | 2014-2017 |
| Q | LPDDR3 | 2015-2019 |
| R | LPDDR4/4X | 2016-2021 |
| S | LPDDR4X | 2018-2021 |
| D | LPDDR4X | uMCP 2020+ |
| E | LPDDR4/4X | uMCP |
| G | LPDDR4X | uMCP |
| L | LPDDR5 | uMCP 2021+ |
| V | LPDDR5/5X | uMCP 2022+ |

**Status: ✅ COMPLETO** para todas as gerações conhecidas.

**Gap observado:** Famílias KM8, KM5, KM2, KM1, KM4, KMV usam decode_gen_pos=None intencionalmente — a 3ª posição nesses é dígito numérico (1/2/4/5/8), não letra de geração. O engine faz fallback ao subtype do ChipFamily. Correto por design.

---

### 1.4 RDRAM_CAP — 3 entradas
Posição pn[3:5], 2 chars. Usado por K4R (Rambus).

| Chave | Densidade | Dispositivos |
|---|---|---|
| 44 | 144Mb | PlayStation 2, Pentium 4 |
| 88 | 288Mb | PS2 / PC800 |
| 76 | 576Mb | Servidor Rambus |

**Status: ✅ COMPLETO** para PNs conhecidos. Chave "27" omitida por falta de evidência.

---

### 1.5 KUS_CAP — 4 entradas
Posição pn[3:5], 2 chars. BGA NVMe SSD.

| Chave | Capacidade |
|---|---|
| 02 | 128GB |
| 03 | 256GB |
| 04 | 512GB |
| 05 | 1TB |

**Gap:** Chave `01` (possível 64GB) não confirmada. Se KUS01 existe na natureza, vai para Gemini.

---

### 1.6 DRAM_PC — 10 entradas (compartilhado, brand=None)
Posição pn[3:5], 2 chars. Usado por K4S, K4H, K4T, K4B, K4A, K4RA, K4X, K5D.

| Chave | val_primary | val_secondary |
|---|---|---|
| 64 | 64Mb | 8MB |
| 28 | 128Mb | 16MB |
| 56 | 256Mb | 32MB |
| 51 | 512Mb | 64MB |
| 1G | 1Gb | 128MB |
| 2G | 2Gb | 256MB |
| 4G | 4Gb | 512MB |
| 8G | 8Gb | 1GB |
| AG | 16Gb | 2GB |
| AH | 16Gb | 2GB |

**Gap para DDR5 (K4RA):** DDR5 comercial já chega a 32Gb (4GB) e 64Gb (8GB) por die, mas DRAM_PC topa em AH=16Gb. PNs K4RA de alta densidade (K4RA4G085VA, 32Gb) vão para Gemini. Baixo impacto no momento — DDR5 ainda é volume pequeno na esteira de reciclagem.

---

### 1.7 DRAM_MOBILE — 10 entradas (compartilhado, brand=None)
Posição pn[3], 1 char. Usado por K3, K3R, K3Q, K4P.

| Chave | val_primary | val_secondary |
|---|---|---|
| P | 512Mb | 64MB |
| 1 | 1Gb | 128MB |
| 2 | 2Gb | 256MB |
| 4 | 4Gb | 512MB |
| 6 | 6Gb | 768MB |
| 8 | 8Gb | 1GB |
| F | 16Gb | 2GB |
| B | 12Gb | 1.5GB |
| G | 16Gb | 2GB |
| H | 32Gb | 4GB |

**Status: ✅ COMPLETO** para faixas de mercado existentes.

---

### 1.8 K3QF_CAP — 2 entradas
Posição pn[4], 1 char. Sub-família K3QF.

| Chave | GB | Gb | Destino |
|---|---|---|---|
| 1 | 1GB | 8Gb | Resíduo |
| 2 | 2GB | 16Gb | Reacondicional seletivo |

**Gap:** K3QF3 e K3QF4 aguardam confirmação por Octopart/datasheet. Não mapear sem evidência.

---

### 1.9 K4E_CAP — 4 entradas
Posição pn[3:5], 2 chars. LPDDR3 standalone.

| Chave | GB | Gb |
|---|---|---|
| 8E | 1GB | 8Gb |
| 6E | 2GB | 16Gb |
| FE | 3GB | 24Gb |
| BE | 4GB | 32Gb |

**Status: ✅ COMPLETO** para o range comercialmente relevante.

---

### 1.10 LPDDR4_CAP — 11 entradas
Posição pn[3:5], 2 chars. Usado por K4F, K4U, K3U.

| Chave | GB | Gb |
|---|---|---|
| 2E | 1.5GB | 12Gb |
| 4E | 512MB | 4Gb |
| 8E | 1GB | 8Gb |
| 6E | 2GB | 16Gb |
| 7E | 3GB | 24Gb |
| BE | 4GB | 32Gb |
| HE | 4GB | 32Gb |
| H6 | 4GB | 32Gb |
| CE | 8GB | 64Gb |
| H7 | 8GB | 64Gb |
| HD | 16GB | 128Gb |

**Status: ✅ COMPLETO** para toda a gama LPDDR4/4X mobile.

---

### 1.11 LPDDR5_CAP — 7 entradas
Posição pn[4:6], 2 chars. Usado por K3KL, K3LK, K3L.

| Chave | GB | Gb | Exemplos reais |
|---|---|---|---|
| 9L | 2GB | 16Gb | K3KL9L90DMMGCU |
| BK | 4GB | 32Gb | K3LKBKB0BMMGCP |
| 8L | 4GB | 32Gb | K3KL8L80EMMGCU |
| 7K | 8GB | 64Gb | K3LK7K70BM (S22) |
| CK | 8GB | 64Gb | Variante alternativa |
| 4K | 12GB | 96Gb | K3LK4K40CM (S20 Ultra) |
| 5L | 16GB | 128Gb | K3KL5L50DM |

**Status: ✅ BOM.** Cobre flagships 2020-2024. Gap: chips LPDDR5 de 6GB (48Gb, se existirem como standalone Samsung) e eventual 20GB não mapeados — mas não há evidência de PNs K3KL/K3LK nessas densidades ainda.

---

## Parte 2 — Famílias: inventário por categoria

### 2.1 DRAM PC / Desktop / Server

| Prefixo | Tipo | Decode | Prioridade | Status |
|---|---|---|---|---|
| K4S | SDRAM PC-66/100/133 | DRAM_PC (density) | 100 | ✅ Completo |
| K4H | DDR1 | DRAM_PC (density) | 100 | ✅ Completo |
| K4T | DDR2 | DRAM_PC (density) | 100 | ✅ Completo |
| K4B | DDR3/DDR3L | DRAM_PC (density) | 100 | ✅ Completo (refinado 2026-05-08) |
| K4A | DDR4 | DRAM_PC (density) | 100 | ✅ Completo (refinado 2026-05-08) |
| K4RA | DDR5 | DRAM_PC (density) | 80 | ⚠️ Parcial (DRAM_PC topa em 16Gb; DDR5 vai além) |
| K4R | RDRAM Rambus (fallback) | RDRAM_CAP | 100 | ✅ Completo |

**Famílias PC ausentes:** nenhuma pendente após 2026-05-09.
> **Nota:** K4W não é DDR3L de ultrabook — é **gDDR3 (Graphics DDR3)**, mapeado na seção 2.7 GDDR. K4C descartado: nenhum PN Samsung real confirmado (fantasma).

---

### 2.2 LPDDR Mobile

| Prefixo | Tipo | Decode | Prioridade | Status |
|---|---|---|---|---|
| K4M | LPDDR1 | Nenhum | 100 | ℹ️ Sem decode (resíduo — OK) |
| K4X | LPDDR1 | DRAM_PC (density) | 100 | ⚠️ Parcial (teto 512MB — resíduo) |
| K4P | LPDDR2 | DRAM_MOBILE | 100 | ✅ Completo |
| K3 | LPDDR2/3 (fallback) | DRAM_MOBILE | 90 | ✅ Fallback adequado |
| K3R | LPDDR3 | DRAM_MOBILE | 40 | ✅ Completo |
| K3Q | LPDDR3 | DRAM_MOBILE | 40 | ✅ Completo |
| K3QF | LPDDR3 (sub-fam) | K3QF_CAP | 40 | ⚠️ Parcial (só 1GB e 2GB) |
| K4E | LPDDR3 | K4E_CAP | 100 | ✅ Completo |
| K4F | LPDDR4 | LPDDR4_CAP | 100 | ✅ Completo |
| K4U | LPDDR4X | LPDDR4_CAP | 100 | ✅ Completo |
| K3U | LPDDR4X Multi-Ch. | LPDDR4_CAP | 40 | ✅ Completo |
| K3L | LPDDR5X (fallback) | LPDDR5_CAP | 60 | ✅ Completo |
| K3KL | LPDDR5 | LPDDR5_CAP | 40 | ✅ Completo |
| K3LK | LPDDR5X | LPDDR5_CAP | 40 | ✅ Completo |

**Famílias LPDDR ausentes:** nenhuma. K4W é gDDR3 (GPU, seção 2.7), não LPDDR. K4C descartado.

---

### 2.3 eMMC Standalone

| Prefixo | Interface | Decode | Status |
|---|---|---|---|
| KLM | eMMC 5.1 | SAM_FLASH_CAP (cap) | ✅ Completo |

**Gap de granularidade:** pn[6] não decodificado (J=eMMC 5.1 · F=eMMC 4.5 · E=eMMC 5.0). Compradores especializados pagam premium por 5.1 vs 4.5 — ver Seção 3 (gaps de alta prioridade).

---

### 2.4 UFS Standalone

| Prefixo | Interface | Decode | Status |
|---|---|---|---|
| KLU | UFS 3.1 | SAM_FLASH_CAP (cap) | ✅ Completo |
| KLUDG | UFS 2.1 | SAM_FLASH_CAP (cap) | ✅ Completo |
| KLUCG | UFS 2.0 | SAM_FLASH_CAP (cap) | ✅ Completo |
| KLUFG | UFS 3.1 | SAM_FLASH_CAP (cap) | ✅ Completo |

**Gap:** UFS 4.0 standalone (2022+) não tem sub-prefixo mapeado. Se aparecer como KLUVG ou similar, cai no KLU genérico (priority=50) — que já resolve capacidade, mas anuncia interface="UFS 3.1" em vez de "UFS 4.0". Impacto baixo até aparecer chip físico.

---

### 2.5 eMCP (eMMC + LPDDR)

| Prefixo | RAM | Interface | Status |
|---|---|---|---|
| KMJ | LPDDR2 | eMMC | ✅ Completo (resíduo) |
| KMK | LPDDR2 | eMMC | ✅ Completo (resíduo) |
| KMV | LPDDR2 (legado) | eMMC | ✅ Completo (resíduo) |
| KMF | LPDDR3 | eMMC 5.1 | ✅ Completo |
| KMN | LPDDR3 | eMMC 5.1 | ✅ Completo |
| KMQ | LPDDR3 | eMMC 5.1 | ✅ Completo (maior volume) |
| KMG | LPDDR3 | eMMC 5.1 | ✅ Corrigido 2026-05-09 (era incorretamente uMCP) |
| KMR | LPDDR4/4X | eMMC 5.1 | ✅ Completo |
| KMS | LPDDR1 | eMMC | ⚠ Corrigido 2026-05-13 (era incorretamente LPDDR4X — família legado ~2012-2013, ex: Galaxy Centura) |
| KM4 | LPDDR4 | eMMC 5.1 | ✅ Completo |
| KMD | LPDDR4X | eMMC 5.1 | ✅ Completo |
| KM (fallback) | variável | eMMC/UFS | ✅ Fallback robusto |

**Status geral eMCP: ✅ EXCELENTE.** Cobertura de geração LPDDR2 até LPDDR4X sem lacunas. Gaps residuais são de cap_keys individuais no SAM_EMCP_CAP (Z6, T9, 512GB+12GB).
> **Nota 2026-05-09:** KMG foi movido de uMCP para eMCP. Datasheet KMGP6001BM confirma: eMMC 5.1 + LPDDR3. O fix_known_parts KMGD6001BM foi revertido. P6 em SAM_EMCP_CAP corrigido de 4GB → 3GB.

---

### 2.6 uMCP (UFS + LPDDR)

| Prefixo | RAM | Interface | Dispositivos | Status |
|---|---|---|---|---|
| KML | LPDDR5 | UFS 3.1 | Galaxy S21, S21 FE | ✅ Completo |
| KMV2 | LPDDR5X | UFS 4.0 | Galaxy S22 série | ✅ Completo |
| KMV3 | LPDDR5X | UFS 4.0 | S22 Ultra, S23 série | ✅ Completo |
| KM8 | LPDDR4X/5X | UFS | Alta densidade | ✅ Completo |
| KM5 | LPDDR4X/5X | UFS | Mid-premium 2021+ | ✅ Completo |
| KM2 | LPDDR5 | UFS 3.1 | S21/S22 flagships | ✅ Completo |
| KM1 | LPDDR5X | UFS 4.0 | S23/S24 ultra-premium | ✅ Completo |

**Status geral uMCP: ✅ EXCELENTE.** Toda a linha uMCP está mapeada, desde KML até ultra-flagships (KM1). KMG foi removido desta seção — é eMCP LPDDR3 (ver seção 2.5). Gaps residuais: cap_keys T9, 512GB+12GB.

---

### 2.7 GDDR (Memória Gráfica)

| Prefixo | Tipo | Decode | Status |
|---|---|---|---|
| K4N | GDDR2 | Nenhum | ℹ️ Sem decode (resíduo — OK) |
| K4J | GDDR3 | Nenhum | ⚠️ Sem decode de capacidade |
| K4W | gDDR3 (Graphics DDR3) | DRAM_PC (density) | ✅ Adicionado 2026-05-09 — PNs reais confirmados |
| K4G | GDDR5/GDDR5X | Nenhum | ❌ GAP IMPORTANTE — alto volume |
| K4Z | GDDR6/GDDR6X | Nenhum | ❌ GAP IMPORTANTE — alto volume |

> **Nota K4W (2026-05-09):** A auditoria anterior classificou K4W erroneamente como "DDR3L ultrabook". Evidências de esquemáticos reais (Dell N4110, ATI Radeon HD 4550) confirmam K4W = gDDR3, VRAM dedicada. Density decode via DRAM_PC (pn[3:5]): 1G=1Gb=128MB · 2G=2Gb=256MB · 4G=4Gb=512MB. PNs validados: K4W1G1646D-EC12, K4W2G1646C-HC11.

**Gap crítico:** K4G e K4Z são os chips GDDR de maior volume no mercado de reciclagem (GPUs RX470-RX580 DDR5, RTX série GDDR6). Sem decode de capacidade, classificação vai 100% para Gemini. Os chips chegam identificados apenas como "GDDR5" ou "GDDR6" sem capacidade — o operador não sabe se é 4GB ou 8GB.

**Esquema de capacidade GDDR5 (K4G):** pn[3:5] — chaves prováveis (a confirmar por Octopart antes de mapear): BG=4Gb(512MB), CG=8Gb(1GB), DG=16Gb(2GB), EG=32Gb(4GB), FG=32Gb(4GB). Cada die é tipicamente 512MB a 1GB; GPUs empilham múltiplos dies.

**Esquema de capacidade GDDR6 (K4Z):** Similar mas densidades maiores — a confirmar.

---

### 2.8 NAND Flash (K9)

| Prefixo | Tipo | Decode | Status |
|---|---|---|---|
| K9F | SLC NAND | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9G | MLC NAND | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9H | MLC Large Page | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9K | SLC/MLC | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9L | MLC/TLC | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9W | SLC Industrial | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9X | MLC Expandido | Nenhum | ⚠️ Identificação OK, capacidade não |
| K9Z | MLC/TLC Especial | Nenhum | ⚠️ Identificação OK, capacidade não |

**Situação atual:** O sistema identifica o chip como "NAND Flash SLC/MLC" e dá destino correto (bancada reacondicional Flash). Mas capacidade retorna null → Gemini faz o preenchimento.

**Gap de valor:** O mercado de NAND raw diferencia preço por densidade. K9F com 256Mb vai para industrial/embedded barato; K9F com 16Gb é flash de alto valor. Sem decode, o operador trata tudo igual.

**Esquema de capacidade K9 (a confirmar antes de mapear):** pn[3:5] — padrão: 1G=1Gb, 2G=2Gb, 4G=4Gb, 8G=8Gb, AG=16Gb, BG=32Gb, CG=64Gb, DG=128Gb. Confirmar com datasheets reais antes de criar NAND_CAP map.

---

### 2.9 NOR Flash / OneNAND / Mask ROM

| Prefixo | Tipo | Decode | Status |
|---|---|---|---|
| K5D | OneNAND | DRAM_PC (density) | ✅ Completo |
| K5 | NOR Flash | Nenhum | ℹ️ Routing apenas |
| K8 | Mask ROM/NOR | Nenhum | ℹ️ Routing apenas |

**K5D** usa DRAM_PC intencionalmente: pn[3:5] = 1G/2G/4G/8G para densidade em bits — as chaves coincidem e o decode funciona corretamente.

---

### 2.10 SRAM

| Prefixo | Tipo | Decode | Status |
|---|---|---|---|
| K7 | SRAM Samsung | Nenhum | ℹ️ Routing para resíduo — sem decode necessário |

---

### 2.11 Empacotamentos Especiais

| Prefixo | Tipo | Decode | Status |
|---|---|---|---|
| KAT | ePoP (PoP) | Nenhum | ⚠️ Sem decode de capacidade |
| KUS | BGA NVMe SSD | KUS_CAP | ✅ Completo (chave 01 pendente) |

**KAT ePoP:** Package-on-Package montado sobre o SoC (comum em iPhones / SoCs compactos). Fora da reciclagem convencional — destino: reacondicional especial. Sem decode é aceitável dado o volume baixo.

---

### 2.12 SoC / Sensor / PMIC

| Prefixo | Tipo | Decode | Status |
|---|---|---|---|
| S5E | Exynos SoC | Nenhum | ℹ️ Routing apenas |
| S5K | ISOCELL Camera | Nenhum | ℹ️ Routing apenas |
| S2M | PMIC | Nenhum | ℹ️ Routing apenas |
| S2A | PMIC | Nenhum | ℹ️ Routing apenas |
| S2D | PMIC | Nenhum | ℹ️ Routing apenas |

**Gap de granularidade:** S5E (Exynos) tem modelo no PN (ex: S5E8895=Exynos 8895, S5E9825=Exynos 2100). O decode de número de modelo agrega valor (operador sabe exatamente o processador), mas requer mapa próprio. Baixa prioridade — SoCs vão para bancada de teste manual de qualquer forma.

---

## Parte 3 — Gaps Priorizados: o caminho para Samsung 100%

### Prioridade 1 — Alto impacto comercial imediato

#### 3.1 K4W — gDDR3 Graphics DDR3 ✅ CONCLUÍDO 2026-05-09
- **Classificação corrigida:** K4W NÃO é DDR3L ultrabook. É **gDDR3 (Graphics DDR3)** — VRAM dedicada em GPUs de entrada e notebooks com vídeo discreto soldado.
- **PNs confirmados:** K4W1G1646D-EC12 (1Gb, ATI Radeon HD 4550), K4W2G1646C-HC11 (2Gb, Dell N4110 VRAM +1.5V_GFX), K4W4G1646 (4Gb).
- **DDR3L (1.35V) em K4B:** a distinção DDR3 vs DDR3L na linha Samsung sistema já vive em K4B via sufixo (BC=1.5V, BY=1.35V). K4W não é esse chip.
- **Ação aplicada:** ChipFamily K4W criada como chip_type="GDDR3", subtype="gDDR3 (Graphics DDR3)", decode_density_type="pc". Roteamento: bancada GPU (junto com K4J/K4G).

#### 3.2 GDDR5 K4G — Decode de Capacidade
- **Impacto:** Alto. GPU GDDR5 (RX470, RX580, GTX 1060…) é o chip de GPU mais comum na esteira.
- **Ação:** Criar mapa GDDR5_CAP, mapear pn[3:5] com entradas confirmadas por datasheet Samsung.
- **Requer:** Confirmar pelo menos 3-4 chaves por Octopart antes de criar o mapa. Ex: K4G41325FC-HC28 (RX470) — confirmar cap_key.

#### 3.3 GDDR6 K4Z — Decode de Capacidade
- **Impacto:** Alto. GPU GDDR6 (RTX série, RX 6000…) volume crescente.
- **Ação:** Igual ao K4G, criar GDDR6_CAP após confirmação.

#### 3.4 SAM_EMCP_CAP gaps (Z6, T9, 512GB+12GB)
- **Impacto:** Médio-alto. Chips S22 Ultra 512GB ainda vão ao Gemini.
- **Ação:** Aguardar PN físico escaneado + Octopart. Não adicionar sem evidência (regra de ouro).

---

### Prioridade 2 — Melhoria de qualidade de dados

#### 3.5 KLM — Decode de Geração eMMC (pn[6]) ✅ CONCLUÍDO 2026-05-09
- **Situação anterior:** tip mencionava pn[6] mas engine não decodificava automaticamente.
- **Ação aplicada:** Criado mapa `SAM_EMMC_GEN` (pos pn[6]): F="eMMC 4.5" · E="eMMC 5.0" · J="eMMC 5.1". KLM atualizado: `decode_gen_pos=6, decode_gen_map="SAM_EMMC_GEN"`, `interface="eMMC"` (fallback genérico). Engine usa decode_gen → `r["interface"]` para `is_emcp=False` — sem alterar engine.py.
- **Resultado:** Interface exibida automaticamente no resultado. Operador enxerga "eMMC 4.5" ou "eMMC 5.1" sem interpretar o PN. Lotes podem ser separados por geração antes da venda.

#### 3.6 NAND Flash K9 — Decode de Capacidade
- **Situação:** 8 famílias K9 sem decode de capacidade. Gemini preenche, mas com latência e custo de API.
- **Impacto:** Médio. Volume de NAND raw na esteira de reciclagem industrial pode ser alto.
- **Ação:** Criar mapa `NAND_FLASH_CAP`, pn[3:5]: 1G=1Gb(128MB), 2G=2Gb, 4G=4Gb, 8G=8Gb, AG=16Gb, BG=32Gb, CG=64Gb, DG=128Gb. Aplicar a todas as famílias K9.
- **Requer:** Confirmar pelo menos as chaves mais comuns por datasheet. O esquema é mais padronizado que DRAM, probabilidade de erros é baixa.

#### 3.7 K3QF — Ampliar para K3QF3/K3QF4
- **Situação:** Apenas 1GB e 2GB mapeados. K3QF3 e K3QF4 citados mas sem confirmação.
- **Ação:** Aguardar chip físico com PN K3QF3F30... e confirmar por Octopart. Adicionar somente então.

---

### Prioridade 3 — Completude de long-tail

#### 3.8 K4C — DDR4 Variante ❌ DESCARTADO 2026-05-09
- **Situação:** Varredura em Octopart e bases de datasheets retornou zero PNs Samsung válidos com prefixo K4C. Provável alucinação do revisor anterior ou confusão com nomenclatura SK Hynix (que tem linhas DDR4 mais fragmentadas).
- **Regra de ouro aplicada:** não mapear sem PN físico real. K4C removido de todos os gaps pendentes. Se um chip com inscrição K4C e logo Samsung cair na esteira, abrir investigação na hora.

#### 3.9 K4RA — Ampliar DRAM_PC para DDR5 alta densidade
- **Situação:** DRAM_PC topa em 16Gb (AG/AH). DDR5 de servidor já tem 32Gb e 64Gb por die.
- **Ação:** Adicionar entradas ao DRAM_PC: "BH"=32Gb(4GB), "CH"=64Gb(8GB) — se existirem PNs K4RA com essas chaves.
- **Requer:** Confirmar por datasheet ou Octopart.

#### 3.10 KUS01 — 64GB NVMe SSD
- **Situação:** KUS_CAP começa em 02 (128GB). Se KUS01 existir, vai para Gemini.
- **Ação:** Buscar KUS01* em Octopart. Se confirmado, adicionar "01"="64GB" ao KUS_CAP.

#### 3.11 UFS 4.0 Standalone — Sub-prefixo específico
- **Situação:** Não há KLUVG ou similar para UFS 4.0. Chips novos caem no KLU genérico (interface="UFS 3.1" — errado).
- **Ação:** Identificar o sub-prefixo correto para UFS 4.0 Samsung. Criar entrada com interface="UFS 4.0".

#### 3.12 S5E — Decode de Modelo Exynos
- **Situação:** Routing correto (SoC→bancada), mas sem identificação do modelo.
- **Ação (baixa prioridade):** Criar mapa `EXYNOS_MODEL` com pn[3:7] → nome do chip. Ex: 8895=Exynos 8895, 9825=Exynos 990, 2100=Exynos 2100. Alta granularidade, impacto operacional baixo.

---

## Parte 4 — Matriz de completude por categoria

```
CATEGORIA              COMPLETUDE    AÇÃO NECESSÁRIA
─────────────────────────────────────────────────────
eMCP completo          ████████░░ 95%   gaps: Z6, T9, 512GB+12GB
uMCP completo          ████████░░ 95%   gaps: T9, 512GB+12GB
LPDDR4/4X/5/5X         ████████░░ 95%   gap: K3QF3/4 pendente
LPDDR3                 ██████████100%   K4W era gDDR3 (não LPDDR) — nenhum gap real
DDR4                   ██████████100%   K4C descartado (fantasma) — K4A cobre linha
DDR3                   ██████████100%   K4W era gDDR3 (GPU), DDR3L vive em K4B sufixo
eMMC/UFS               ██████████ 95%   decode geração pn[6] resolvido (SAM_EMMC_GEN)
GDDR                   █████░░░░░ 50%   K4W adicionado (gDDR3); K4G/K4Z sem decode cap
NAND Flash K9          █████░░░░░ 50%   gap: sem decode capacidade
NOR / OneNAND          ███████░░░ 70%   K5D OK, K5/K8 routing apenas
DDR1/2/RDRAM/SDRAM     ██████████100%   completo, resíduo
SoC/PMIC/Sensor        ████████░░ 80%   routing OK, sem decode modelo
```

---

## Parte 5 — O que fazer primeiro (plano de sprint)

### Sprint A — Impacto imediato, risco baixo
1. ~~**K4W DDR3L**~~ → ✅ **CONCLUÍDO** como K4W gDDR3 (Graphics DDR3, bancada GPU). K4C descartado.
2. **NAND Flash CAP map** — Criar NAND_FLASH_CAP com as chaves padrão (1G/2G/4G/8G/AG/BG/CG/DG) e aplicar às 8 famílias K9. Reduz drasticamente chamadas ao Gemini para chips industriais.

### Sprint B — Impacto alto, requer pesquisa
3. **GDDR5 decode (K4G)** — Confirmar chaves pn[3:5] para pelo menos 4 PNs comuns de GPU (buscar K4G41325FC no Octopart). Criar GDDR5_CAP, atualizar tip com destino GPU.
4. **GDDR6 decode (K4Z)** — Idem, confirmar chaves para K4Z80165QB ou similar.

### Sprint C — Qualidade de dados
5. ~~**KLM decode geração eMMC**~~ → ✅ **CONCLUÍDO** — SAM_EMMC_GEN criado, KLM atualizado. F/E/J decodificados automaticamente.
6. **SAM_EMCP_CAP: aguardar PNs físicos** — Z6, T9, 512GB+12GB. Não adicionar sem chip real.

### Sprint D — Long-tail
7. ~~**K4C confirmação**~~ → ❌ **DESCARTADO** — família fantasma, zero PNs Samsung confirmados.
8. **K4RA DDR5 alta densidade** — Adicionar entradas ao DRAM_PC se PNs confirmados.
9. **UFS 4.0 sub-prefixo** — Identificar e mapear.

---

## Parte 6 — Pontos de atenção arquitetural

### 6.1 K4Z — Conflito de nomenclatura resolvido
O BRIEFING_DDR_SAMSUNG.md listava "K4Z — LPDDR4X variante (Surface, Chromebooks)" como família não mapeada. Na realidade, K4Z está mapeado em populate_samsung.py como **GDDR6/GDDR6X**. Isso é correto — K4Z Samsung é GDDR6. A confusão com LPDDR4X provavelmente era outra empresa (SK Hynix?). **Ação:** Atualizar o BRIEFING para remover K4Z da lista de pendentes LPDDR.

### 6.2 KMV — Bifurcação de prefixo
KMV tem três interpretações:
- KMV2.../KMV3... → uMCP flagship LPDDR5X (2022+) — priority=30, testados primeiro
- KMV + LETRA → eMCP legado LPDDR2 (2010-2013) — priority=40
Sistema está correto e robusto.

### 6.3 K4R — Bifurcação de prefixo
K4RA (priority=80) → DDR5 vence sobre K4R (priority=100) → RDRAM. Sistema correto.

### 6.4 decode_gen_pos=None nos uMCPs numéricos
KM8, KM5, KM2, KM1, KM4, KMV usam decode_gen_pos=None. Correto por design — a 3ª posição é dígito numérico da família, não código de geração RAM. O engine usa fallback via subtype do ChipFamily. **Não alterar sem revisar o comportamento do engine.**

### 6.5 DRAM_MOBILE compartilhado (brand=None)
K3, K3R, K3Q e K4P (Samsung) compartilham DRAM_MOBILE com outras marcas. Se alguma outra marca usar o mesmo prefixo de PN com chaves diferentes, haverá colisão. Monitorar quando começar mapeamento de outras marcas (ex: SK Hynix H9).

---

## Resumo Final: onde estamos vs. Samsung 100%

**O que está excelente (não mexer):**
- Toda a linha eMCP (KMQ a KMD) — cobertura de geração completa
- Toda a linha uMCP (KMG a KM1, KMV2/3) — Samsung uMCP é o melhor mapeado do mercado
- LPDDR4/4X/5/5X (K4F, K4U, K3U, K3KL, K3LK, K3L) — coverage 95%+
- DDR3/4 PC (K4B, K4A) — coverage 100% com reasoning completo

**O que está funcional mas pode melhorar:**
- GDDR5/6 (K4G, K4Z) — identificação correta, decode de capacidade ausente
- NAND Flash K9 — identificação correta, decode de capacidade ausente
- eMMC KLM — capacidade OK, geração (4.5 vs 5.1) não decodificada

**O que está ausente:**
- K4W (DDR3L) ~~família não mapeada~~ → **corrigido**: K4W é gDDR3 GPU, já mapeado.
- K4C ~~pendente confirmação~~ → **descartado**: nenhum PN Samsung real encontrado.

**Estado atual vs. meta "maior do mercado":**  
Para DRAM mobile, eMCP/uMCP e GDDR básico Samsung, o WhatTheChip já está no nível mais completo disponível publicamente. Os gaps restantes (decode de capacidade GDDR5/6 K4G/K4Z, decode NAND K9) são os próximos passos naturais do Sprint B/C.

---
*Gerado por auditoria automática em 2026-05-09. Próxima revisão recomendada após Sprint B (GDDR decode).*
