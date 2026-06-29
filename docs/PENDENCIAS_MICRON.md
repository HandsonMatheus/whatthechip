# Pendências Micron — identificação para a convenção WhatTheChip

> **Para o chat da Micron.** Estes 13 PNs estão confirmados no banco do WhatTheChip,
> mas **sem `chip_type`** (não classificam) ou com tipo **errado**. Preciso da
> identificação autoritativa de cada um para aplicar a convenção única de tipos.
> Por favor devolva no **formato do §3** para eu aplicar direto.

---

## 1. Convenção (como a resposta deve vir)

- **`chip_type` canônico** — para **DRAM discreta a GERAÇÃO vai no `chip_type`**:
  `DDR3` `DDR3L` `DDR4` `DDR5` · `LPDDR2` `LPDDR3` `LPDDR4` `LPDDR4X` `LPDDR5` ·
  `GDDR5`/`GDDR6`. Memória **gerenciada**: `eMMC` `UFS` `eMCP` `uMCP` `NAND Flash`.
- **`subtype`** = espelha a geração (DRAM) **ou** a célula no NAND (`SLC NAND` /
  `MLC NAND` / `TLC NAND`).
- **Unidades (inviolável):** densidade do **die** em **Gb**; capacidade do **pacote**
  em **GB**. Para eMCP/uMCP: `emcp_nand` (ex.: `"eMMC 5.1 64GB"`) + `emcp_ram`
  (ex.: `"LPDDR4 4GB"`).

---

## 2. PNs a identificar

### Grupo A — `MT29C4G48MAZAPA…` (8 PNs, têm FBGA, `chip_type` VAZIO)
Pista: o FBGA `JW464` aparece na nossa documentação como **"SLC NAND 512MB"**
(4 Gbit). Suspeita: família **MCP** (NAND + RAM móvel) ou NAND raw — **confirmar**.

| PN | FBGA |
|---|---|
| `MT29C4G48MAZAPAKD-5 E IT` | `JW699` |
| `MT29C4G48MAZAPAKD-5 IT` | `JW464` |
| `MT29C4G48MAZAPAKD-5 IT ES` | `JY464` |
| `MT29C4G48MAZAPAKD-6 IT` | `JW454` |
| `MT29C4G48MAZAPAKD-6 IT ES` | `JY454` |
| `MT29C4G48MAZAPAMC-5 IT` | `JW456` |
| `MT29C4G48MAZAPAMC-5 IT ES` | `JY456` |
| `MT29C4G48MAZAPAMC-6 IT` | `JW455` |

**Perguntas:** o que é a família `MT29C4G48MAZAPA`? Qual `chip_type`? Se for MCP:
qual NAND (eMMC ou raw? capacidade?) e qual RAM (LPDDR qual geração? capacidade?).
Se for NAND raw: célula (SLC/MLC) + capacidade.

### Grupo B — `MT42L384M32D3LP…` (4 PNs, têm FBGA, `chip_type` VAZIO)
Hipótese (confirmar): `MT42L` = **LPDDR2**; `384M×32` = pacote de **1.5 GB**.

| PN | FBGA |
|---|---|
| `MT42L384M32D3LP-18 WT:A` | `D9RRD` |
| `MT42L384M32D3LP-18 WT ES:A` | `Z9RRC` |
| `MT42L384M32D3LP-25 WT:A` | `D9RRB` |
| `MT42L384M32D3LP-25 WT ES:A` | `Z9RQZ` |

**Perguntas:** confirmar `chip_type` = `LPDDR2`? Capacidade do pacote (GB)?

### Grupo C — `MT41K64M16TW` (1 PN, `chip_type="Flash"` ERRADO)
Hipótese (confirmar): `MT41K` = **DDR3L**; `64M×16` = **1 Gbit/die**.

| PN | campo `fbga` (suspeito) | confidence |
|---|---|---|
| `MT41K64M16TW` | `DDR3L` (valor estranho neste campo) | distributor |

**Perguntas:** confirmar `chip_type` = `DDR3L`? Densidade do die (Gb)?

---

## 3. Formato da resposta (devolva assim, uma linha por PN)

```
PN | chip_type | subtype | capacity(GB pacote) | density(Gb die) | emcp_nand | emcp_ram | obs
```

Exemplos de preenchimento:
- DRAM discreta: `MT42L384M32D3LP-18 WT:A | LPDDR2 | LPDDR2 | 1.5GB |  |  |  | 384Mx32`
- NAND raw:      `<PN> | NAND Flash | SLC NAND |  | (ou capacity em MB/GB) |  |  | ...`
- MCP/eMCP:      `<PN> | eMCP | LPDDR3 |  |  | eMMC 5.1 4GB | LPDDR3 2GB | ...`

> Tudo que não for geração/célula/capacidade (organização, temperatura, voltagem,
> tensão, package) pode ir na coluna **obs** — não no `subtype`.
