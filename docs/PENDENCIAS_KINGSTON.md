# Pendências Kingston — identificação para a convenção WhatTheChip

> **Para o chat da Kingston.** Estes 7 PNs estão no banco do WhatTheChip como
> `chip_type="RAM"` genérico — **sem geração e sem capacidade** (confidence
> `estimated`, baixa confiança). Preciso da identificação autoritativa para aplicar
> a convenção única de tipos. Devolva no **formato do §3**.

---

## 1. Convenção (como a resposta deve vir)

- **`chip_type` canônico** — a **GERAÇÃO vai no `chip_type`**: `DDR1` `DDR2` `DDR3`
  `DDR3L` `DDR4` `DDR5` · `LPDDR2` `LPDDR3` `LPDDR4` `LPDDR4X` `LPDDR5`.
- **`subtype`** = espelha a geração.
- **Unidades:** densidade do **die** em **Gb**; capacidade do **pacote** em **GB**.

---

## 2. PNs a identificar

| PN | `chip_type` atual | observação (a confirmar) |
|---|---|---|
| `KFC1G16U2C` | `RAM` | `1G×16`? |
| `KFFN60012M` | `RAM` | — |
| `KFG1G16U2C` | `RAM` | `1G×16`? |
| `KFG1GN6W2D` | `RAM` | — |
| `KFG1GNGW2D` | `RAM` | — |
| `KFM4G16Q4B` | `RAM` | `4G×16`? |
| `KFMNX0012M` | `RAM` | — |

**Perguntas:**

1. Estes são **chips** (componentes DRAM avulsos, BGA) ou **módulos** (DIMM/SO-DIMM)?
   Se forem **módulos**, eles **não** entram na triagem de chips do estoque — confirme
   para eu **remover** do banco de chips (ou marcar como catálogo).
2. Se forem chips: qual a **geração** de cada um (DDR3/DDR4/…) e a **densidade do die
   (Gb)** / capacidade?

---

## 3. Formato da resposta (uma linha por PN)

```
PN | chip_type | subtype | density(Gb die) | capacity | é módulo? (sim/não) | obs
```

> Tudo que não for geração/densidade (organização, barramento `x16`, voltagem,
> velocidade) vai na coluna **obs** — não no `subtype`.
