# SAMSUNG_PC_DRAM.md — Referência de PNs Samsung PC DRAM para WhatTheChip

> Documento de instrução para agentes Claude trabalhando no WTC.
> Atualizado: 2026-06-19.

---

## ⚠ Regra de Ouro — SUFIXO NÃO IMPORTA

**Ao adicionar qualquer PN ao `fix_known_parts.py`, adicione SEMPRE:**
1. O **PN base** (sem sufixo) — ex.: `K4B4G1646D`
2. Cada **variante com sufixo** que tiver confirmação Tier 1 — ex.: `K4B4G1646D-BYK0`, `K4B4G1646D-BCK0`

**Por quê:** O operador na bancada lê o laser marking físico do chip. Ele pode ver
`K4B4G1646D` (sem sufixo legível) ou `K4B4G1646D-BYK0` (sufixo visível). O sistema deve
confirmar nos dois casos. Se só o PN com sufixo estiver no banco, a busca pelo PN base
cai na gramática (`confidence="estimated"`, `known_exact=false`), o que é errado
para um chip já pesquisado e confirmado.

---

## Anatomia do PN Samsung PC DRAM

```
K 4 [família] [densidade] [largura] [revisão] - [sufixo]
│ │     │         │          │         │            │
│ │     │         │          │         │            └── Velocidade / tensão / grau
│ │     │         │          │         └── Die revision (letra)
│ │     │         │          └── Bus width (08=x8, 16=x16, 04=x4)
│ │     │         └── Densidade (pn[3:5] via DRAM_PC decode map)
│ │     └── Família / geração
│ └── 4th-gen DRAM
└── Samsung Memory
```

### Mapa de densidade DRAM_PC (pn[3:5])

| Código | Capacidade | Bytes/die |
|--------|-----------|-----------|
| `28`   | 128 Mb    | 16 MB     |
| `56`   | 256 Mb    | 32 MB     |
| `51`   | 512 Mb    | 64 MB     |
| `1G`   | 1 Gb      | 128 MB    |
| `2G`   | 2 Gb      | 256 MB    |
| `4G`   | 4 Gb      | 512 MB    |
| `8G`   | 8 Gb      | 1 GB      |
| `AG`   | 16 Gb     | 2 GB      |
| `AH`   | 16 Gb     | 2 GB      |

---

## Famílias PC DRAM Samsung

### K4H — DDR1 (~2000–2007)

- `chip_type="DDR"`, `subtype="DDR1 PC DRAM XMb xNN"`, `interface="DDR1"`
- **assess_profitability:** gen=1 < ddr_min_gen(3) → **NÃO RENTÁVEL** sempre
- Destino: moagem / recuperação de metais
- Sufixo: menos comum nesta família — muitos chips têm o PN base como nome completo

**Exemplos confirmados:**
- `K4H510438G` — 512 Mb x4 (64MB/die) — datasheet Samsung Rev 1.1 Nov 2009
- `K4H510838G` — 512 Mb x8 (64MB/die) — mesmo datasheet
- `K4H511638G` — 512 Mb x16 (64MB/die) — mesmo datasheet
- `K4H561638D-TCB3` — 256 Mb x16 (32MB/die) — Octopart confirmed

---

### K4T — DDR2 (~2004–2010)

- `chip_type="DDR"`, `subtype="DDR2 PC DRAM XGb xNN"`, `interface="DDR2"`
- **assess_profitability:** gen=2 < ddr_min_gen(3) → **NÃO RENTÁVEL** sempre
- Destino: moagem / recuperação de metais
- Sufixo: `-BI` = variant grade; `-BHF8`/`-BFF8` = USA market code

**Exemplos confirmados:**
- `K4T51163QN` — 512 Mb x16 (64MB/die)
- `K4T51083QN` — 512 Mb x8 (64MB/die)
- `K4T1G084QJ` — 1 Gb x8 (128MB/die)
- `K4T1G164QJ` — 1 Gb x16 (128MB/die)

---

### K4B — DDR3 / DDR3L (~2007–2016)

- `chip_type="DDR3"` (sufixo BC) ou `chip_type="DDR3L"` (sufixo BY/MY/MM)
- Para o **PN base** (sem sufixo), use `chip_type="DDR3L"` salvo se só variantes DDR3 existirem
- **assess_profitability:** gen=3 ≥ ddr_min_gen(3) → avalia densidade:
  - ddr3_min_gbit default=2.0 Gb → mínimo 256 MB/die
  - ≥ 256 MB → RENTÁVEL / < 256 MB (ex.: 1Gb=128MB) → NÃO RENTÁVEL

**Decode de sufixo:**

| Sufixo | Tipo | Tensão |
|--------|------|--------|
| `BC`   | DDR3 | 1.5V |
| `BY`   | DDR3L | 1.35V / 1.5V dual |
| `MY`   | DDR3L | 1.35V |
| `MM`   | DDR3L Industrial | 1.35V temp. estendida |

**Decode de largura (pn[5:7]):**
- `08` = x8 (DIMMs desktop/servidor)
- `16` = x16 (SO-DIMM laptop/embarcado)

**Die revisions (pn[7]):** B, C, D, E, F, G, I, Q, …

**Exemplos confirmados:**
- `K4B4G1646E` — 4 Gb x16 (512MB), E-die — Samsung Semiconductor Global ✓
- `K4B8G1646D` — 8 Gb x16 (1GB), D-die — Samsung Semiconductor Global ✓
- `K4B2G1646F` — 2 Gb x16 (256MB), F-die — Samsung Semiconductor Global ✓
- `K4B1G1646I` — 1 Gb x16 (128MB), I-die — NÃO RENTÁVEL (128MB < 256MB limiar)

---

### K4A — DDR4 (~2014–presente)

- `chip_type="DDR4"`, `interface="DDR4"`, `1.2V`
- **assess_profitability:** gen=4 ≥ ddr_min_gen(3) → avalia densidade:
  - ddr4plus_min_gbit default=8.0 Gb → mínimo 1GB/die com default
  - ⚠ **O usuário confirmou: limiar real = 1 Gigabit (0.125 GB).** Ajustar
    `ddr4plus_min_gbit` para `1.0` no admin ProfitabilityConfig.
  - Com limiar correto (1 Gb): **TODAS as densidades DDR4 confirmadas = RENTÁVEL**

**Decode de sufixo:**

| Sufixo | Velocidade | Notas |
|--------|-----------|-------|
| `BCPB` | DDR4-2133 | BC=commercial standard |
| `BCRC` | DDR4-2400 | |
| `BCTD` | DDR4-2666 | |
| `BCWE` | DDR4-3200 | |
| `BI**` | mesma velocidade | variante de grau/ECC |
| `M***` | qualquer  | grau especial |

**Decode de densidade (pn[3:5]):**
- `4G` = 4 Gb (512 MB/die)
- `8G` = 8 Gb (1 GB/die)
- `AG` / `AH` = 16 Gb (2 GB/die)

**Die revisions (pn[7]):** WB (B-die), WC (C-die), WE (E-die), WF (F-die), WG (G-die)

**Exemplos confirmados:**
- `K4A8G085WB-BCPB` — 8Gb x8, B-die, DDR4-2133 — Samsung + datasheet ✓
- `K4AAG165WA-BCWE` — 16Gb x16, A-die, DDR4-3200 — Samsung Global ✓

---

### K4RA — DDR5 16Gb (~2021–presente)

- `chip_type="DDR5"`, `interface="DDR5"`, `1.1V`
- Gramática K4RA existe em populate_samsung.py (priority=80)
- **assess_profitability:** gen=5 → **RENTÁVEL** (todas densidades DDR5)
- Densidade pn[3:5]: `AH` = 16 Gb (2 GB/die)
- Bus width pn[5:7]: `08`=x8, `16`=x16 → `086`=x8, `165`=x16

---

### K4RB — DDR5 32Gb (~2022–presente)

- Gramática K4RB existe em populate_samsung.py (priority=80)
- Densidade: 32 Gb (4 GB/die)
- Bus width pn[5:7]: `04`=x4, `08`=x8

---

### K4RCH — DDR5 32Gb nova revisão (C-die) ⚠ CRÍTICO

- **SEM FAMÍLIA NA GRAMÁTICA** → cai em K4R (RDRAM, priority=100) → classificação ERRADA
- Sem entradas `confirmed` em `fix_known_parts`, aparece como RDRAM
- Entradas K4RCH no fix_known_parts são **obrigatórias**
- Futuramente: criar família K4RC em populate_samsung.py para cobrir variantes novas

**Sufixos K4RA/K4RB/K4RCH:**

| Sufixo | Velocidade | Notas |
|--------|-----------|-------|
| `BCQK` | DDR5-4800 | |
| `BIQK` | DDR5-4800 | variante |
| `BCWM` / `BIWM` | DDR5-5600 | |
| `BCCP` | DDR5-4800 | K4RBH |
| `2CCM` | DDR5-5600 | K4RCH |
| `2CLP` | DDR5-6400 | K4RCH |

---

## fix_known_parts — Regras de entrada DDR

```python
{
    "pn": "K4XXXXXX",           # PN BASE (sem sufixo) — OBRIGATÓRIO
    "create": True,
    "create_defaults": {
        "brand_name": "Samsung",
        "chip_type":  "DDR4",   # DDR / DDR3 / DDR3L / DDR4 / DDR5
        "subtype":    "DDR4 PC DRAM 8Gb x8",
        "status":     "enriched",
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "DDR4",
        "subtype":    "DDR4 PC DRAM 8Gb x8",
        "capacity":   "1GB",    # MB ou GB — _extract_gib() parseia os dois
        "interface":  "DDR4",
        "confidence": "confirmed",
        "status":     "enriched",
    },
    "reason": "Samsung Semiconductor Global: K4XXXXXX(8 Gb) ✓. ...",
},
{
    "pn": "K4XXXXXX-BCPB",     # VARIANTE COM SUFIXO — mesmos campos
    ...
},
```

**Regras de capacidade:**
- `capacity` = bytes por die (não total do módulo)
- DDR1/2: use MB (`"64MB"`, `"128MB"`)
- DDR3+: use MB ou GB (`"512MB"`, `"1GB"`, `"2GB"`)
- Conversão: densidade Gbit ÷ 8 = capacidade em GB

**Fonte mínima Tier 1:**
- Samsung Semiconductor Global (título indexado com `(X Gb)` ✓)
- Datasheet Samsung em download.semiconductor.samsung.com
- Octopart com fonte Samsung

**NÃO aceitar como fonte única:** Flash64Box, fóruns asiáticos de reparo,
WinSource, catálogos B2B de Shenzhen, análise de IA local.

---

## assess_profitability — Limiares DDR

| Parâmetro ProfitabilityConfig | Default | Significado |
|-------------------------------|---------|-------------|
| `ddr_min_gen` | 3 | DDR1/DDR2 (gen < 3) → NÃO RENTÁVEL |
| `ddr3_min_gbit` | 2.0 | DDR3 < 2 Gb (256MB) → NÃO RENTÁVEL |
| `ddr4plus_min_gbit` | 8.0 | **Ajustar para 1.0** (1 Gbit = 0.125 GB) |

**Como o engine lê a capacidade:**
1. Tenta `dram_density` field → extrai Gb diretamente
2. Fallback: `capacity` field → `_extract_gib()` converte para GB → divide por 0.125 para obter Gb

**Por isso `capacity` deve estar em MB ou GB**, nunca em Gbit.

---

## Issues Conhecidos

1. **K4RCH sem gramática** — família K4RC ausente em populate_samsung.py.
   Fix temporário: entradas confirmed em fix_known_parts.
   Fix definitivo: criar família K4RC em populate_samsung.py.

2. **ddr4plus_min_gbit incorreto** — default=8.0 Gb classifica DDR4 4Gb como NÃO RENTÁVEL.
   Ajuste no admin: ProfitabilityConfig → `ddr4plus_min_gbit` = `1.0`.

3. **Cache após populate** — após rodar `populate_samsung --overwrite`, reiniciar servidor.
   O fix_known_parts NÃO requer reinício (só grava KnownParts, não toca no lru_cache).

4. **Gramática K4B usa chip_type="DDR"** — o engine retorna subtype="DDR3/DDR3L" pela gramática.
   Entries no fix_known_parts usam chip_type="DDR3" ou "DDR3L" mais específico — isso é correto
   e o engine prioriza o KnownPart confirmed sobre a gramática.
