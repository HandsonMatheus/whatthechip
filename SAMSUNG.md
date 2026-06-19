# SAMSUNG.md — Bíblia Técnica e de Negócio
**WhatTheChip — documento vivo de referência**
Criado: 2026-06-19 | Atualizado: 2026-06-19
> Leia antes de tocar em qualquer arquivo relacionado à Samsung.
> Substitui AUDITORIA_SAMSUNG_2026.md, BRIEFING_DDR_SAMSUNG.md e SAMSUNG_PC_DRAM.md
> (os três permanecem em `docs/archive/` como histórico).
> Em conflito com qualquer outro doc, o **código é a fonte da verdade**
> (`chips/engine.py`, `populate_samsung.py`).
> Atualize este arquivo quando aprender algo duradouro.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro e limites de escopo

### 0.1 Arquivos que PODE editar (escopo Samsung)

```
chips/management/commands/populate_samsung.py   ← gramática mestre: ChipFamilies + DecodeMaps
chips/management/commands/fix_known_parts.py    ← somente entradas brand_name="Samsung"
chips/management/commands/import_samsung_psg.py ← importa CSVs do Samsung PSG
data/psg/*.csv                                  ← CSVs Samsung Product Selection Guide
```

### 0.2 Arquivos que NÃO PODE tocar sem revisão explícita do usuário

```
chips/engine.py                                    ← motor global — mudança afeta TODAS as marcas
estoque/views.py                                   ← gateway global — mudança afeta TODAS as marcas
chips/management/commands/populate_micron_mcp.py
chips/management/commands/populate_hynix.py
chips/management/commands/populate_kingston.py
chips/management/commands/populate_rayson.py
chips/management/commands/populate_toshiba.py
chips/management/commands/add_chip_families.py     ← compartilhado — editar só para famílias Samsung
chips/management/commands/fix_known_parts.py       ← seções de OUTRAS marcas (Micron, SK Hynix…)
```

> Se precisar de mudança em `engine.py` ou `estoque/views.py`, **proponha ao usuário**
> com justificativa e impacto — nunca edite silenciosamente.

### 0.3 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca execute `populate_*`,
   `import_*`, `fix_*` sem confirmação explícita do usuário.

2. **`--dry-run` antes de qualquer comando que escreve no banco.** Sempre.

3. **Reiniciar o servidor após `populate_samsung --overwrite`.** O `lru_cache` do engine
   não invalida automaticamente no processo do servidor web.

4. **`chip_type="RAM"` para todos os chips DDR/GDDR discretos** (K4H, K4T, K4B, K4A,
   K4RA, K4J, K4G, K4Z, K4W…). Nunca `"DDR3"`, `"DDR"`, `"GDDR5"` no `chip_type`.
   O gateway quebra se `chip_type` não for `"RAM"` para esses chips.

5. **`subtype` = SOMENTE a geração — sem mais nada.** `"DDR3"` ✓. `"DDR3 PC DRAM 8Gb x8"`,
   `"LPDDR4X Mobile"`, `"GDDR3 Graphics"` ✗. Qualquer qualificador além da geração
   vaza para o label da caixa física e trunca o display na esteira.

6. **`interface=""` (vazio) para LPDDR standalone e eMCP/uMCP.** Nunca colocar a
   geração de RAM no campo `interface`. `interface="LPDDR4"` é sempre ERRADO para
   esses tipos. Para DDR/GDDR discretos, `interface` = bus width: `"x8"`, `"x16"`, `"x4"`.

7. **`emcp_ram` = tipo ANTES da capacidade.** `"LPDDR3 1GB"` ✓ — nunca `"1GB LPDDR3"`.
   O campo `emcp_nand` é só GB: `"16GB"`, sem prefixo de tipo.

8. **Nunca inverta `val_primary`/`val_secondary` nos DecodeMaps.** Em SAM_EMCP_CAP:
   `val_primary`=NAND (GB), `val_secondary`=RAM (GB). Em DRAM_PC/DRAM_MOBILE:
   `val_primary`=densidade (Gb ou Mb), `val_secondary`=bytes/die (MB).
   Siga EXATAMENTE o padrão das linhas já existentes — nunca assuma sem verificar.

9. **Nunca escreva "por die" no `val_secondary`.** O engine já acrescenta " por die"
   automaticamente. Se vier no mapa, duplica: "por die por die".

10. **`decode_density_type` e `decode_cap_map` são mutuamente exclusivos.** K4F, K4U e
    K3U DEVEM ter `decode_density_type=""`. Configurar os dois na mesma família produz
    dados conflitantes no engine.

11. **Não confie em dados de distribuidor ou IA sem verificação.** Jotrin, WinSource,
    catálogos de Shenzhen e IAs generalistas confundem Gb/GB, invertem primary/secondary
    e alucinam capacidades. Sempre cruzar com Samsung Semiconductor Global ou datasheet.

### 0.4 Hierarquia de fontes (imutável)

```
1. Samsung Semiconductor Global: semiconductor.samsung.com
   → busca por PN → confirma specs (título com "(X Gb)" ou "(X GB)")
2. Datasheet Samsung oficial: download.semiconductor.samsung.com
   → fonte definitiva para specs de timing, tensão, package
3. Octopart com fonte Samsung
   → frequentemente inverte Gb/GB; sempre cruzar com Samsung Global
4. Distribuidor B2B rastreável (SBiT, Puris, parceiros confirmados)
   → só como apoio; nunca rebaixa um "confirmed" com dado de distribuidor
5. IA externa (Gemini, GPT, outro Claude)
   → ÚLTIMO RECURSO — verificar SEMPRE antes de usar
```

Nunca usar como fonte primária: Flash64Box, fóruns asiáticos de reparo, WinSource
sem rastreabilidade, catálogos genéricos de Shenzhen, output de IA sem verificação.

---

## 1. Visão Geral

Samsung é o maior fornecedor de chips no banco WTC. A cobertura inclui toda a linha
de DRAM móvel, eMCP/uMCP, eMMC, UFS, DDR PC, GDDR e NAND Flash.

| Categoria | Famílias mapeadas | Decode completo | Decode parcial | Sem decode |
|---|---|---|---|---|
| DRAM PC (SDRAM→DDR5) | 7 | 6 | 1 (K4RA) | 0 |
| LPDDR Mobile | 14 | 11 | 2 (K3QF, K4X) | 1 (K4M) |
| eMMC standalone | 1 | 1 | 0 | 0 |
| UFS standalone | 4 | 4 | 0 | 0 |
| eMCP (eMMC+LPDDR) | 11 | 11 | 0 | 0 |
| uMCP (UFS+LPDDR) | 8 | 8 | 0 | 0 |
| GDDR (GPU) | 4 | 1 (K4W) | 0 | 3 |
| NAND Flash (K9) | 8 | 0 | 0 | 8 |
| NOR / OneNAND | 3 | 1 (K5D) | 0 | 2 |
| SRAM | 1 | 0 | — | 1 |
| Especiais (ePoP, BGA SSD) | 2 | 1 (KUS) | 1 (KAT) | 0 |
| SoC / Sensor / PMIC | 5 | 0 | — | 5 |
| **TOTAL** | **68** | **43** | **4** | **21** |

**Arquivos que definem as famílias:**
- `chips/management/commands/populate_samsung.py` — gabarito mestre (ChipFamilies + DecodeMaps)
- `chips/management/commands/fix_known_parts.py` — correções pontuais de KnownParts no banco

---

## 2. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> Estabelecida em 2026-06-19 após auditoria completa. Quebrar estas regras
> produz labels errados no gateway de estoque.

### 2.1 Tabela canônica por tipo de chip

| Tipo de chip | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1 | `"RAM"` | `"DDR1"` | `"x8"` / `"x16"` / `"x4"` | `density_gbit` (Gb por die) |
| DDR2 | `"RAM"` | `"DDR2"` | `"x8"` / `"x16"` / `"x4"` | `density_gbit` |
| DDR3 | `"RAM"` | `"DDR3"` | `"x8"` / `"x16"` / `"x4"` | `density_gbit` |
| DDR3L | `"RAM"` | `"DDR3L"` | `"x8"` / `"x16"` | `density_gbit` |
| DDR4 | `"RAM"` | `"DDR4"` | `"x8"` / `"x16"` | `density_gbit` |
| DDR5 | `"RAM"` | `"DDR5"` | `"x8"` / `"x16"` | `density_gbit` |
| SDRAM / RDRAM | `"RAM"` | `"SDRAM"` / `"RDRAM"` | `"x8"` / `"x16"` | `density_gbit` |
| GDDR3 / gDDR3 | `"RAM"` | `"GDDR3"` | `"x16"` | `density_gbit` |
| GDDR5 | `"RAM"` | `"GDDR5"` | `"x8"` / `"x16"` | `density_gbit` |
| GDDR6 | `"RAM"` | `"GDDR6"` | `"x8"` / `"x16"` | `density_gbit` |
| LPDDR1 | `"LPDDR1"` | `"LPDDR1"` | `""` (vazio) | `capacity` (GB, **do pacote**) |
| LPDDR2 | `"LPDDR2"` | `"LPDDR2"` | `""` | `capacity` (GB, **do pacote**) |
| LPDDR3 | `"LPDDR3"` | `"LPDDR3"` | `""` | `capacity` (GB, **do pacote**) |
| LPDDR4 | `"LPDDR4"` | `"LPDDR4"` | `""` | `capacity` (GB, **do pacote**) |
| LPDDR4X | `"LPDDR4X"` | `"LPDDR4X"` | `""` | `capacity` (GB, **do pacote**) |
| LPDDR5 | `"LPDDR5"` | `"LPDDR5"` | `""` | `capacity` (GB, **do pacote**) |
| LPDDR5X | `"LPDDR5X"` | `"LPDDR5X"` | `""` | `capacity` (GB, **do pacote**) |
| eMMC | `"eMMC"` | `""` | `"eMMC"` (ou versão decodificada) | `capacity` (GB) |
| UFS | `"UFS"` | `""` | `"UFS 3.1"` (ou versão) | `capacity` (GB) |
| eMCP | `"eMCP"` | geração RAM (`"LPDDR3"`) | `""` | `emcp_nand` + `emcp_ram` |
| uMCP | `"uMCP"` | geração RAM (`"LPDDR5"`) | `""` | `emcp_nand` + `emcp_ram` |

### 2.2 Regras absolutas do `subtype`

- `subtype` = **SOMENTE a geração ou célula** (1–3 palavras) — ex.: `"DDR3"`, `"LPDDR4X"`, `"SLC NAND"`
- **NUNCA** colocar no `subtype`: densidade (`"8Gb"`), bus width (`"x8"`), tensão (`"1.35V"`),
  qualificadores verbosos (`"PC DRAM"`, `"Mobile"`, `"Multi-Channel"`, `"paralela industrial"`,
  `"Graphics DDR3"`, `"standalone"`).
- Qualquer qualificador além da geração/célula **vaza para o label do gateway** e
  trunca o display na esteira.

### 2.3 Campo `interface` — quando usar e o quê

- **DDR/GDDR:** bus width do chip — `"x8"`, `"x16"`, `"x4"`. Decodificado do PN (dígitos 5–6).
- **LPDDR standalone e eMCP/uMCP:** `""` (string vazia). O bus width não é operacionalmente
  relevante e a gramática não o decodifica. **Nunca** colocar geração de RAM no `interface`
  para esses tipos.
- **eMMC:** `"eMMC"` (genérico) ou `"eMMC 5.1"` / `"eMMC 4.5"` se a gramática o decode.
- **UFS:** `"UFS 3.1"` (ou versão correspondente).

### 2.4 Gateway de estoque — como o label é montado

O código em `estoque/views.py::_compute_destination` lê `chip_type` e `subtype` para montar
o label da caixa física:

```
Para chip_type "RAM" (DDR/GDDR):
  gen  = subtype  →  ex.: "DDR3"
  size = density_gbit  →  ex.: 8 (Gbit por die)
  label = f"{gen}+{size}G"  →  "DDR3+8G"

Para chip_type "LPDDR*":
  gen  = subtype  →  ex.: "LPDDR4X"
  size = capacity_gb  →  ex.: 4 (GB do pacote)
  label = f"{gen}+{size}G"  →  "LPDDR4X+4G"

Para eMCP/uMCP:
  label = f"{tipo}{emcp_nand}+{emcp_ram_gb}"  →  "EMCP16+1" / "UMCP128+8"
```

**Portanto:** um `subtype="DDR3 PC DRAM 8Gb x8"` produziria label `"DDR3 PC DRAM 8Gb x8+8G"` —
completamente errado. Use **somente** `"DDR3"`.

### 2.5 eMCP — campos `emcp_nand` e `emcp_ram`

- `emcp_nand` = capacidade NAND em GB, ex.: `"16GB"`, `"64GB"`
- `emcp_ram` = tipo **antes** da capacidade, ex.: `"LPDDR3 1GB"` — **nunca** `"1GB LPDDR3"`
- A gramática preenche esses campos via `decode_cap_map="SAM_EMCP_CAP"` com `val_primary`=NAND
  e `val_secondary`=RAM, e `decode_gen_map="SAM_EMCP_GEN"` para o tipo de RAM.

### 2.6 Tabela completa de campos — O que vai / O que NÃO vai

| Campo | O que vai | O que NÃO vai |
|-------|-----------|---------------|
| `chip_type` | `"RAM"`, `"eMMC"`, `"UFS"`, `"eMCP"`, `"uMCP"`, `"NAND Flash"`, `"LPDDR4"` (geração, para LPDDR standalone) | specs, densidades, tensão, `"DDR3"`, `"DDR"` |
| `subtype` | **só a geração**: `"DDR3"`, `"DDR3L"`, `"LPDDR4X"`, `"DDR5"`, `"GDDR6"`, `"SLC NAND"` | densidade (`"8Gb"`), barramento (`"x16"`), tensão (`"1.35V"`), qualificadores (`"Mobile"`, `"PC DRAM"`, `"Graphics"`, `"Multi-Channel"`) |
| `interface` | bus width para DDR/GDDR: `"x8"`, `"x16"`, `"x4"`; versão para eMMC/UFS: `"eMMC 5.1"`, `"UFS 3.1"` | a geração de RAM (`"LPDDR4"`, `"DDR3"`) — nunca repetir aqui; `""` vazio para LPDDR/eMCP/uMCP |
| `capacity` | capacidade total do **pacote** em bytes: `"512MB"`, `"4GB"`, `"16GB"` | gigabits; capacity de eMCP (usar `emcp_nand`/`emcp_ram`) |
| `density_gbit` | densidade do **die** para DDR/GDDR: `"8Gb"`, `"2Gb"` | bytes; capacidade de pacote; LPDDR |
| `emcp_nand` | (só eMCP/uMCP) NAND em GB: `"64GB"`, `"128GB"` | tipo de interface; RAM |
| `emcp_ram` | (só eMCP/uMCP) **tipo + GB**: `"LPDDR3 1GB"`, `"LPDDR5 8GB"` — tipo VEM ANTES | só o número (`"4GB"`) — perde a geração; ordem invertida (`"4GB LPDDR4"`) |
| `tip` | tudo que não couber acima: tensão, organização, avisos, notas de compatibilidade | — |

---

## 3. Anatomia do PN Samsung

### 3.1 PC DRAM (K4S / K4H / K4T / K4B / K4A / K4RA / K4RB)

```
K 4 [família] [densidade pn[3:5]] [bus pn[5:7]] [revisão pn[7]] - [sufixo]
│ │     │              │                │               │              │
│ │     │              └── pn[3:5] lido pelo DRAM_PC (2 chars)         └── Velocidade / tensão / grau
│ │     └── S=SDRAM · H=DDR1 · T=DDR2 · B=DDR3/3L · A=DDR4 · RA=DDR5
│ └── 4th-gen DRAM
└── Samsung Memory
```

**Sufixos K4B (DDR3/DDR3L):**

| Sufixo | Tipo | Tensão | `subtype` correto |
|--------|------|--------|-------------------|
| `BC`   | DDR3 | 1.5V | `"DDR3"` |
| `BY`   | DDR3L | 1.35V/1.5V dual | `"DDR3L"` |
| `MY`   | DDR3L | 1.35V | `"DDR3L"` |
| `MM`   | DDR3L Industrial | 1.35V ext. | `"DDR3L"` |

**Bus width (pn[5:7]):** `08`=x8 · `16`=x16 · `04`=x4 · `46`=x4

**Die revisions (pn[7]):** B, C, D, E, F, G, I, Q, W (K4A/K4RA)

**Sufixos K4A (DDR4) — velocidade:**

| Sufixo | Velocidade |
|--------|-----------|
| `BC**` | DDR4-2133/2400/2666/3200 |
| `BI**` | variante de grau |
| `M***` | grau especial |

**Sufixos K4RA/K4RB/K4RCH (DDR5):**

| Sufixo | Velocidade | Família |
|--------|-----------|---------|
| `BCQK` | DDR5-4800 | K4RA/K4RB |
| `BIQK` | DDR5-4800 | variante |
| `BCWM` | DDR5-5600 | K4RA/K4RB |
| `2CCM` | DDR5-5600 | K4RCH |
| `2CLP` | DDR5-6400 | K4RCH |

### 3.2 LPDDR Mobile

```
K [geração] [densidade/família] [detalhe…]
│     │            │
│     │            └── posição varia por família (pn[3], pn[3:5] ou pn[4:6])
│     └── 4=LPDDR1/2/3/4/4X · 3=LPDDR3/4X/5/5X multi-channel
└── Samsung Memory
```

| Família | Tipo | Posição decode | Mapa |
|---------|------|----------------|------|
| K4M | LPDDR1 legado | — | nenhum |
| K4X | LPDDR1 | pn[3:5] | DRAM_PC |
| K4P | LPDDR2 | pn[3] | DRAM_MOBILE |
| K3, K3R, K3Q | LPDDR2/3 | pn[3] | DRAM_MOBILE |
| K3QF | LPDDR3 sub-família | pn[4] | K3QF_CAP |
| K4E | LPDDR3 standalone | pn[3:5] | K4E_CAP |
| K4F | LPDDR4 | pn[3:5] | LPDDR4_CAP |
| K4U | LPDDR4X | pn[3:5] | LPDDR4_CAP |
| K3U | LPDDR4X multi-canal | pn[3:5] | LPDDR4_CAP |
| K3KL | LPDDR5 | pn[4:6] | LPDDR5_CAP |
| K3LK | LPDDR5X | pn[4:6] | LPDDR5_CAP |
| K3L | LPDDR5X fallback | pn[4:6] | LPDDR5_CAP |

> **K4EBE304EB — PN base artificial:** LPDDR3 PNs Samsung têm 14 chars no formato completo
> (ex.: `K4EBE304EB-EGCE`). O prefixo `K4EBE304EB` (10 chars) é o base artificial que
> existia no banco com subtype/interface errados. **Não recriar este registro** — use UPDATE-ONLY
> em `fix_known_parts` (sem `"create": True`). BE=4GB conforme K4E_CAP.

### 3.3 eMMC (KLM)

```
KLM [cap pn[3]] [sub pn[4:6]] [gen pn[6]] …
     └── SAM_FLASH_CAP     └── SAM_EMMC_GEN
         (1 char)              (1 char: F=4.5 · E=5.0 · J=5.1)
```

### 3.4 UFS (KLU / KLUDG / KLUCG / KLUFG)

```
KLU [cap pn[3]] [sub-tipo pn[3:5]] …
     └── SAM_FLASH_CAP
         (sub-prefixos mais longos têm prioridade: KLUDG=UFS2.1, KLUCG=UFS2.0, KLUFG=UFS3.1)
```

### 3.5 eMCP / uMCP (KM*)

```
KM [gen pn[2]] [cap pn[3:5]] [detalhe…]
    └── SAM_EMCP_GEN    └── SAM_EMCP_CAP
        (1 char)            (2 chars)
        gen RAM             val_primary=NAND, val_secondary=RAM
```

**Exceção uMCPs numéricos (KM1/KM2/KM4/KM5/KM8/KMV):** pn[2] é dígito numérico da série,
**não** código de geração. Nesses casos `decode_gen_pos=None` — o engine usa o `subtype` fixo
do `ChipFamily`. Não alterar sem revisar o behavior do engine.

---

## 4. DecodeMaps — Inventário Completo

### 4.1 SAM_FLASH_CAP
Posição `pn[3]`, 1 char. Usado por KLM (eMMC) e KLU (UFS).

| Chave | Valor | Cobertura |
|-------|-------|-----------|
| `2` | 2GB | Legado Smart TVs (~2010-2013) |
| `4` | 4GB | — |
| `8` | 8GB | — |
| `A` | 16GB | — |
| `B` | 32GB | — |
| `C` | 64GB | — |
| `D` | 128GB | — |
| `E` | 256GB | — |
| `F` | 512GB | — |
| `G` | 1TB | — |

**Status: ✅ COMPLETO.**

### 4.2 SAM_EMCP_CAP
Posição `pn[3:5]`, 2 chars. Todos os eMCP/uMCP (KMQ, KMR, KMG, KM8…).
`val_primary` = NAND (GB), `val_secondary` = RAM (GB).

**Geração legado (2012–2017):**

| Chave | NAND | RAM | Dispositivos típicos |
|-------|------|-----|----------------------|
| `11` | 4GB | 512MB | Entrada (~2013) |
| `72` | 8GB | 1GB | — |
| `7U` | 8GB | 1GB | KMK7U (confirmado) |
| `82` | 16GB | 1GB | — |
| `IS` | 16GB | 1GB | Galaxy S2 i9100 |
| `TU` | 16GB | 1GB | Galaxy S3 i9300 |
| `31` | 16GB | 2GB | — |
| `21` | 32GB | 2GB | — |
| `4Z` | 32GB | 2GB | KMQ4Z |
| `41` | 32GB | 4GB | — |

**Geração alfanumérica 1 (2017–2019):**

| Chave | NAND | RAM | Fonte | Status |
|-------|------|-----|-------|--------|
| `8X` | **16GB** | 1GB | KMQ8X000SA-B414 (SBiT) ✓ | ✅ CORRIGIDO (era 8GB) |
| `NW` | 8GB | 1GB | KMQNW000SM-B316 ✓ | ✅ |
| `N6` | 8GB | 1GB | KMFN60012MB214 Octopart ✓ | ✅ |
| `E1` | 16GB | 2GB | KMQE10013M-B318 ✓ | ✅ |
| `BT` | 16GB | 2GB | — | ⚠️ sem PN físico |
| `V7` | 16GB | 2GB | alias BT | ⚠️ |
| `V8` | 128GB | 4GB | Fabricante ✓ | ✅ |
| `GD` | 32GB | 3GB | — | ⚠️ sem PN físico |
| `W7` | 32GB | 3GB | alias GD | ⚠️ |
| `W8` | 32GB | 4GB | — | ⚠️ sem PN físico |
| `X1` | 32GB | 2GB | KMQX10013MB Octopart ✓ | ✅ |
| `H9` | 32GB | 2GB | alias X1 | ⚠️ |
| `C1` | 64GB | 4GB | KMRC10014M (IA ext.) | ⚠️ aguarda Octopart |
| `M4` | 128GB | 4GB | — | ⚠️ sem PN físico |
| `J2` | 128GB | 6GB | — | ⚠️ sem PN físico |
| `P5` | 256GB | 8GB | — | ⚠️ sem PN físico |
| `~~5X~~` | — | — | — | ❌ BLOQUEADO sem evidência |
| `~~NX~~` | — | — | IA externa | ❌ BLOQUEADO fonte distribuidor |

**Geração alfanumérica 2 (2020–2022, padrão `[X]6`):**

| Chave | NAND | RAM | Fonte |
|-------|------|-----|-------|
| `D6` | 32GB | 3GB | — |
| `E6` | 32GB | 3GB | alias D6 |
| `G6` | 32GB | 3GB | Gemini |
| `V6` | 32GB | 3GB | alias D6 |
| `U6` | 64GB | 3GB | — |
| `X6` | 32GB | 2GB | Octopart ✓ |
| `T6` | 64GB | 4GB | — |
| `Y6` | 128GB | 4GB | — |
| `H6` | 64GB | 4GB | KMRH60014A |
| `P6` | 64GB | 4GB | Datasheet ✓ |
| `P9` | 64GB | 4GB | Octopart ✓ |
| `L6` | 256GB | 8GB | uMCP S21 FE |
| `K6` | 128GB | 8GB | KML (S21 Exynos) |

**uMCP linha numérica KM5/KM8/KM2 (confirmados pelo fabricante):**

| Chave | NAND | RAM | Fonte |
|-------|------|-----|-------|
| `C7` | 64GB | 4GB | Fabricante ✓ |
| `L9` | 128GB | 6GB | Fabricante ✓ |
| `F9` | 256GB | 8GB | Fabricante ✓ |
| `F8` | 256GB | 12GB | Fabricante ✓ |

**Gaps conhecidos:** `Z6`, `T9`, `512GB+12GB` (S22 Ultra 512GB) — aguardam PN físico na esteira.
**Não adicionar sem evidência Tier 1.**

### 4.3 SAM_EMCP_GEN
Posição `pn[2]`, 1 char. Tipo de RAM nos eMCP/uMCP.

| Chave | RAM | Era |
|-------|-----|-----|
| `J` | LPDDR2 | 2013–2015 |
| `K` | LPDDR2 | 2010–2012 |
| `F` | LPDDR3 | 2015–2019 |
| `N` | LPDDR3 | 2014–2017 |
| `Q` | LPDDR3 | 2015–2019 |
| `R` | LPDDR4/4X | 2016–2021 |
| `S` | LPDDR4X | 2018–2021 |
| `D` | LPDDR4X | uMCP 2020+ |
| `E` | LPDDR4/4X | uMCP |
| `G` | LPDDR4X | uMCP |
| `L` | LPDDR5 | uMCP 2021+ |
| `V` | LPDDR5/5X | uMCP 2022+ |

**Status: ✅ COMPLETO.**

### 4.4 SAM_EMMC_GEN
Posição `pn[6]`, 1 char. Padrão eMMC (adicionado 2026-05-09).

| Chave | Interface |
|-------|-----------|
| `F` | eMMC 4.5 |
| `E` | eMMC 5.0 |
| `J` | eMMC 5.1 |

Engine usa `decode_gen → r["interface"]` para `is_emcp=False` (não eMCP). Permite
separar lotes eMMC 4.5 vs 5.1 sem interpretar o PN manualmente.

### 4.5 DRAM_PC
Posição `pn[3:5]`, 2 chars. Compartilhado (brand=None). Usado por K4S, K4H, K4T,
K4B, K4A, K4RA, K4X, K5D, K4W.

| Chave | val_primary (Gb/Mb) | val_secondary (MB/die) |
|-------|---------------------|------------------------|
| `64` | 64Mb | 8MB |
| `28` | 128Mb | 16MB |
| `56` | 256Mb | 32MB |
| `51` | 512Mb | 64MB |
| `1G` | 1Gb | 128MB |
| `2G` | 2Gb | 256MB |
| `4G` | 4Gb | 512MB |
| `8G` | 8Gb | 1GB |
| `AG` | 16Gb | 2GB |
| `AH` | 16Gb | 2GB |

**Gap DDR5 alta densidade:** DRAM_PC topa em 16Gb (AH). Chips K4RA ≥ 32Gb
(`BH`=32Gb, `CH`=64Gb, se existirem) vão para Gemini. Adicionar somente com PN
confirmado por Octopart/datasheet.

### 4.6 DRAM_MOBILE
Posição `pn[3]`, 1 char. Compartilhado (brand=None). Usado por K3, K3R, K3Q, K4P.

| Chave | val_primary (Gb) | val_secondary (MB/die) |
|-------|------------------|------------------------|
| `P` | 512Mb | 64MB |
| `1` | 1Gb | 128MB |
| `2` | 2Gb | 256MB |
| `4` | 4Gb | 512MB |
| `6` | 6Gb | 768MB |
| `8` | 8Gb | 1GB |
| `F` | 16Gb | 2GB |
| `B` | 12Gb | 1.5GB |
| `G` | 16Gb | 2GB |
| `H` | 32Gb | 4GB |

**Status: ✅ COMPLETO.**

**Atenção:** DRAM_MOBILE é compartilhado. Se outra marca usar prefixo de PN com
chaves conflitantes, haverá colisão. Monitorar ao expandir cobertura de outras marcas.

### 4.7 LPDDR4_CAP
Posição `pn[3:5]`, 2 chars. Usado por K4F, K4U, K3U.

| Chave | GB (capacidade) | Gb (total) |
|-------|-----------------|------------|
| `4E` | 512MB | 4Gb |
| `8E` | 1GB | 8Gb |
| `2E` | 1.5GB | 12Gb |
| `6E` | 2GB | 16Gb |
| `7E` | 3GB | 24Gb |
| `BE` | 4GB | 32Gb |
| `HE` | 4GB | 32Gb |
| `H6` | 4GB | 32Gb |
| `CE` | 8GB | 64Gb |
| `H7` | 8GB | 64Gb |
| `HD` | 16GB | 128Gb |

**Atenção:** K4F, K4U e K3U **devem** ter `decode_density_type=""`. Se "mobile",
o engine produz um campo `dram_density` redundante além da capacidade, gerando
conflito de dados. Verificar sempre que editar essas famílias.

### 4.8 LPDDR5_CAP
Posição `pn[4:6]`, 2 chars. Usado por K3KL, K3LK, K3L.

| Chave | GB | Gb | Exemplos reais |
|-------|----|----|----------------|
| `9L` | 2GB | 16Gb | K3KL9L90DMMGCU |
| `BK` | 4GB | 32Gb | K3LKBKB0BMMGCP |
| `8L` | 4GB | 32Gb | K3KL8L80EMMGCU |
| `7K` | 8GB | 64Gb | K3LK7K70BM (S22) |
| `CK` | 8GB | 64Gb | variante alternativa |
| `4K` | 12GB | 96Gb | K3LK4K40CM (S20 Ultra) |
| `5L` | 16GB | 128Gb | K3KL5L50DM |

**Status: ✅ BOM.** Cobre flagships 2020–2024.

### 4.9 K4E_CAP
Posição `pn[3:5]`, 2 chars. LPDDR3 standalone (K4E).

| Chave | GB | Gb |
|-------|----|----|
| `8E` | 1GB | 8Gb |
| `6E` | 2GB | 16Gb |
| `FE` | 3GB | 24Gb |
| `BE` | 4GB | 32Gb |

**Status: ✅ COMPLETO.**

### 4.10 K3QF_CAP
Posição `pn[4]`, 1 char. Sub-família K3QF (LPDDR3).

| Chave | GB | Gb | Destino |
|-------|----|----|---------|
| `1` | 1GB | 8Gb | Resíduo |
| `2` | 2GB | 16Gb | Reacondicional seletivo |

**Gap:** K3QF3 e K3QF4 aguardam PN físico confirmado. Não mapear sem evidência Octopart.

### 4.11 RDRAM_CAP
Posição `pn[3:5]`, 2 chars. Usado por K4R (Rambus).

| Chave | Densidade | Dispositivos |
|-------|-----------|--------------|
| `44` | 144Mb | PlayStation 2, Pentium 4 |
| `88` | 288Mb | PS2 / PC800 |
| `76` | 576Mb | Servidor Rambus |

**Status: ✅ COMPLETO** para PNs conhecidos.

### 4.12 KUS_CAP
Posição `pn[3:5]`, 2 chars. BGA NVMe SSD.

| Chave | Capacidade |
|-------|-----------|
| `02` | 128GB |
| `03` | 256GB |
| `04` | 512GB |
| `05` | 1TB |

**Gap:** Chave `01` (possível 64GB) não confirmada.

---

## 5. Famílias — Inventário Completo

### 5.1 DRAM PC / Desktop / Servidor

| Prefixo | Tipo (`chip_type`) | `subtype` | Decode | Prioridade | Status |
|---------|---------------------|-----------|--------|------------|--------|
| K4S | `"RAM"` | `"SDRAM"` | DRAM_PC | 100 | ✅ Completo |
| K4H | `"RAM"` | `"DDR1"` | DRAM_PC | 100 | ✅ Completo |
| K4T | `"RAM"` | `"DDR2"` | DRAM_PC | 100 | ✅ Completo |
| K4B | `"RAM"` | `"DDR3"` ou `"DDR3L"` | DRAM_PC | 100 | ✅ Completo |
| K4A | `"RAM"` | `"DDR4"` | DRAM_PC | 100 | ✅ Completo |
| K4RA | `"RAM"` | `"DDR5"` | DRAM_PC | 80 | ⚠️ Parcial (teto 16Gb) |
| K4RB | `"RAM"` | `"DDR5"` | DRAM_PC | 80 | ⚠️ Parcial |
| K4RCH | `"RAM"` | `"DDR5"` | nenhum | — | ❌ **SEM FAMÍLIA** — cai em K4R (RDRAM) |
| K4R | `"RAM"` | `"RDRAM"` | RDRAM_CAP | 100 | ✅ Fallback Rambus |

> **K4RCH (DDR5 32Gb C-die):** Não tem família própria na gramática. Sem entradas
> `confirmed` no `fix_known_parts`, aparece erroneamente como RDRAM. Entradas manuais
> são **obrigatórias** até a família K4RC ser criada em `populate_samsung.py`.

> **K4C:** ❌ DESCARTADO (2026-05-09). Zero PNs Samsung reais confirmados — provável
> fantasma ou confusão com SK Hynix. Não mapear.

### 5.2 LPDDR Mobile

| Prefixo | Tipo (`chip_type`) | `subtype` | Decode | Prioridade | Status |
|---------|---------------------|-----------|--------|------------|--------|
| K4M | `"LPDDR1"` | `"LPDDR1"` | nenhum | 100 | ℹ️ Routing apenas (resíduo) |
| K4X | `"LPDDR1"` | `"LPDDR1"` | DRAM_PC | 100 | ⚠️ Teto 512MB (resíduo) |
| K4P | `"LPDDR2"` | `"LPDDR2"` | DRAM_MOBILE | 100 | ✅ Completo |
| K3 | `"LPDDR3"` | `"LPDDR3"` | DRAM_MOBILE | 90 | ✅ Fallback adequado |
| K3R | `"LPDDR3"` | `"LPDDR3"` | DRAM_MOBILE | 40 | ✅ Completo |
| K3Q | `"LPDDR3"` | `"LPDDR3"` | DRAM_MOBILE | 40 | ✅ Completo |
| K3QF | `"LPDDR3"` | `"LPDDR3"` | K3QF_CAP | 40 | ⚠️ Parcial (1GB e 2GB) |
| K4E | `"LPDDR3"` | `"LPDDR3"` | K4E_CAP | 100 | ✅ Completo |
| K4F | `"LPDDR4"` | `"LPDDR4"` | LPDDR4_CAP | 100 | ✅ Completo |
| K4U | `"LPDDR4X"` | `"LPDDR4X"` | LPDDR4_CAP | 100 | ✅ Completo |
| K3U | `"LPDDR4X"` | `"LPDDR4X"` | LPDDR4_CAP | 40 | ✅ Completo (multi-canal) |
| K3KL | `"LPDDR5"` | `"LPDDR5"` | LPDDR5_CAP | 40 | ✅ Completo |
| K3LK | `"LPDDR5X"` | `"LPDDR5X"` | LPDDR5_CAP | 40 | ✅ Completo |
| K3L | `"LPDDR5X"` | `"LPDDR5X"` | LPDDR5_CAP | 60 | ✅ Fallback (K3LK/K3KL têm prioridade) |

> **K3LK — risco elétrico:** VDDQ=0.5V. Placa mal projetada pode queimar o chip.
> Anotar no tip: confirmar especificações da placa receptora antes de instalar.

> **K3KL sufixo `*EM`:** alguns SKUs são LPDDR5X — confirmar por datasheet antes
> de tratar junto com LPDDR5 padrão.

> **Interface de TODAS as famílias LPDDR acima:** `""` (string vazia). **Nunca** colocar
> geração de RAM (`"LPDDR3"`, `"LPDDR4"`) no campo `interface` para LPDDR standalone.
> Isso foi corrigido em 18 famílias no `populate_samsung.py` em 2026-06-19.

### 5.3 eMMC Standalone

| Prefixo | `chip_type` | Interface | Decode | Status |
|---------|-------------|-----------|--------|--------|
| KLM | `"eMMC"` | `"eMMC"` (ou SAM_EMMC_GEN) | SAM_FLASH_CAP (cap) | ✅ Completo |

SAM_EMMC_GEN decodifica `pn[6]`: F=eMMC 4.5 · E=eMMC 5.0 · J=eMMC 5.1.
Engine usa `decode_gen → r["interface"]` para `is_emcp=False`.

### 5.4 UFS Standalone

| Prefixo | `chip_type` | Interface | Decode | Status |
|---------|-------------|-----------|--------|--------|
| KLU | `"UFS"` | `"UFS 3.1"` | SAM_FLASH_CAP | ✅ Completo |
| KLUDG | `"UFS"` | `"UFS 2.1"` | SAM_FLASH_CAP | ✅ Completo |
| KLUCG | `"UFS"` | `"UFS 2.0"` | SAM_FLASH_CAP | ✅ Completo |
| KLUFG | `"UFS"` | `"UFS 3.1"` | SAM_FLASH_CAP | ✅ Completo |

**Gap:** UFS 4.0 standalone (2022+) não tem sub-prefixo mapeado. Chips novos caem
no KLU genérico com interface="UFS 3.1" — errado. Identificar o sub-prefixo correto
quando chip físico aparecer na esteira.

### 5.5 eMCP (eMMC + LPDDR)

| Prefixo | `chip_type` | RAM | Interface | Status |
|---------|-------------|-----|-----------|--------|
| KMJ | `"eMCP"` | LPDDR2 | eMMC | ✅ Completo (resíduo) |
| KMK | `"eMCP"` | LPDDR2 | eMMC | ✅ Completo (resíduo) |
| KMV (letra) | `"eMCP"` | LPDDR2 legado | eMMC | ✅ Completo (resíduo) |
| KMF | `"eMCP"` | LPDDR3 | eMMC 5.1 | ✅ Completo |
| KMN | `"eMCP"` | LPDDR3 | eMMC 5.1 | ✅ Completo |
| KMQ | `"eMCP"` | LPDDR3 | eMMC 5.1 | ✅ Completo (maior volume) |
| KMG | `"eMCP"` | LPDDR3 | eMMC 5.1 | ✅ Corrigido 2026-05-09 (era uMCP) |
| KMR | `"eMCP"` | LPDDR4/4X | eMMC 5.1 | ✅ Completo |
| KMS | `"eMCP"` | LPDDR1 | eMMC | ✅ Corrigido 2026-05-13 (era LPDDR4X — é legado ~2012) |
| KM4 | `"eMCP"` | LPDDR4 | eMMC 5.1 | ✅ Completo |
| KMD | `"eMCP"` | LPDDR4X | eMMC 5.1 | ✅ Completo |
| KM (fallback) | `"eMCP"` | variável | eMMC/UFS | ✅ Fallback robusto |

> **KMG:** datasheet KMGP6001BM confirma eMMC 5.1 + LPDDR3 (não uMCP).
> P6 em SAM_EMCP_CAP correto: 64GB + 3GB (não 4GB).

> **KMV — bifurcação:** KMV2.../KMV3... → uMCP flagship LPDDR5X (priority=30, testados
> primeiro). KMV + LETRA → eMCP legado LPDDR2 (priority=40). Sistema correto.

> **Interface eMCP = `""` em todos os registros.** Corrigido em 26 entradas em
> `fix_known_parts.py` em 2026-06-19.

### 5.6 uMCP (UFS + LPDDR)

| Prefixo | `chip_type` | RAM | Interface | Dispositivos | Status |
|---------|-------------|-----|-----------|--------------|--------|
| KML | `"uMCP"` | LPDDR5 | UFS 3.1 | Galaxy S21, S21 FE | ✅ Completo |
| KMV2 | `"uMCP"` | LPDDR5X | UFS 4.0 | Galaxy S22 série | ✅ Completo |
| KMV3 | `"uMCP"` | LPDDR5X | UFS 4.0 | S22 Ultra, S23 série | ✅ Completo |
| KM8 | `"uMCP"` | LPDDR4X/5X | UFS | Alta densidade | ✅ Completo |
| KM5 | `"uMCP"` | LPDDR4X/5X | UFS | Mid-premium 2021+ | ✅ Completo |
| KM2 | `"uMCP"` | LPDDR5 | UFS 3.1 | S21/S22 flagships | ✅ Completo |
| KM1 | `"uMCP"` | LPDDR5X | UFS 4.0 | S23/S24 ultra-premium | ✅ Completo |

### 5.7 GDDR (Memória Gráfica)

| Prefixo | `chip_type` | `subtype` | Decode | Status |
|---------|-------------|-----------|--------|--------|
| K4N | `"RAM"` | `"GDDR2"` | nenhum | ℹ️ Routing (resíduo) |
| K4J | `"RAM"` | `"GDDR3"` | nenhum | ✅ KnownParts (13 PNs, 2026-06-19) |
| K4W | `"RAM"` | `"GDDR3"` | DRAM_PC | ✅ Adicionado 2026-05-09 |
| K4G | `"RAM"` | `"GDDR5"` | nenhum | ❌ GAP IMPORTANTE — alto volume |
| K4Z | `"RAM"` | `"GDDR6"` | nenhum | ❌ GAP IMPORTANTE — alto volume |

> **K4J — GDDR3 Samsung (~2005–2012):**
> VRAM de GPUs ATI/AMD Radeon HD 4xxx/5xxx e Nvidia GeForce 9xxx/200. Usa refresh
> 8K/32ms (GDDR3-específico), diferente do DDR3 standard.
>
> **Anatomia do PN:**
> `K4J | [density 2ch pn[3:5]] | [org 2ch pn[5:7]] | [bank pn[7]] | [iface pn[8]] | [rev pn[9]] | - | [speed suffix]`
>
> **Density codes GDDR3-específicos — ⚠️ NÃO usar DRAM_PC:**
>
> | Código `pn[3:5]` | Capacidade | bytes/die | Label gateway |
> |-----------------|-----------|-----------|---------------|
> | `"10"` | 1Gb | **128MB** | `"GDDR3+1G"` |
> | `"52"` | 512Mb | **64MB** | `"GDDR3+0.5G"` |
> | `"55"` | 256Mb | **32MB** | `"GDDR3+0.25G"` |
>
> Fonte: Samsung Consumer Memory Product Guide, Abr. 2010 ✓ (Alldatasheet ref #347919).
> Os códigos "10", "52", "55" **não existem** no mapa DRAM_PC (que usa "1G", "51", "56").
> Por isso `decode_density_type` é vazio para K4J — `grammar_complete=false` é **by design**.
>
> **Campo correto em `fix_known_parts`:** `capacity` em bytes. O gateway `_density_g()`
> converte capacity em Gbit para o label (`128MB ÷ 128 = 1Gbit → "+1G"`).
>
> **PNs confirmados (fix_known_parts, 2026-06-19):**
> K4J10324KE (base, BC14, HC14, HC1A) · K4J10324QD (base, HC12) — 1Gb, 128MB
> K4J52324QH (base, HJ1A, HJ08) — 512Mb, 64MB
> K4J55323QF (base, GC16) · K4J55323QG (base, BC14) — 256Mb, 32MB

> **K4W — gDDR3 Graphics DDR3:** Classificação corrigida em 2026-05-09. K4W **NÃO** é
> DDR3L ultrabook — é VRAM dedicada em GPUs de entrada (ATI Radeon HD 4550, notebooks
> com vídeo discreto soldado). Densidade via DRAM_PC (`pn[3:5]`): 1G=1Gb=128MB /
> 2G=2Gb=256MB / 4G=4Gb=512MB. PNs confirmados: K4W1G1646D-EC12 (ATI HD4550),
> K4W2G1646C-HC11 (Dell N4110).

> **K4G e K4Z:** GPU GDDR5 (RX470, RX580, GTX 1060) e GDDR6 (RTX série, RX 6000)
> são os chips de GPU de **maior volume** na esteira de reciclagem. Sem decode de
> capacidade, o operador não sabe se é 4GB ou 8GB — valor completamente diferente.
> Sprint B prioritário: confirmar chaves `pn[3:5]` por Octopart e criar GDDR5_CAP/GDDR6_CAP.
> **Nunca criar o mapa sem confirmar ao menos 3–4 chaves por Octopart/datasheet.**

> **Enquanto não há decode — preenchimento manual em `fix_known_parts`:**
> K4J: coberto por KnownParts (13 PNs, 2026-06-19). Para K4G/K4Z individuais confirmados
> por Octopart, preencha `density_gbit` (ex.: `"8Gb"`) — é o campo que o gateway lê para
> montar `"GDDR5+8G"`. Não usar `capacity` para GDDR5/6 (reservado para LPDDR/eMMC/UFS).

### 5.8 NAND Flash (K9)

| Prefixo | Tipo célula | Decode | Status |
|---------|-------------|--------|--------|
| K9F | SLC NAND | nenhum | ⚠️ Identificação OK, capacidade não |
| K9G | MLC NAND | nenhum | ⚠️ Identificação OK, capacidade não |
| K9H | MLC Large Page | nenhum | ⚠️ Identificação OK, capacidade não |
| K9K | SLC/MLC | nenhum | ⚠️ Identificação OK, capacidade não |
| K9L | MLC/TLC | nenhum | ⚠️ Identificação OK, capacidade não |
| K9W | SLC Industrial | nenhum | ⚠️ Identificação OK, capacidade não |
| K9X | MLC Expandido | nenhum | ⚠️ Identificação OK, capacidade não |
| K9Z | MLC/TLC Especial | nenhum | ⚠️ Identificação OK, capacidade não |

**Sprint A:** Criar mapa `NAND_FLASH_CAP` com chaves `pn[3:5]`: 1G=1Gb(128MB),
2G=2Gb, 4G=4Gb, 8G=8Gb, AG=16Gb, BG=32Gb, CG=64Gb, DG=128Gb. Aplicar às 8 famílias K9.
Confirmar ao menos as chaves mais comuns por datasheet antes de criar.

> **Enquanto não há decode — preenchimento manual em `fix_known_parts`:**
> Para chips K9 individuais confirmados por datasheet, preencha `capacity`
> (ex.: `"512MB"`, `"4GB"`) — é o campo que o gateway lê para montar `"SLC NAND 512MB"`.
> Sem ele, o label sai sem tamanho e `profitable='INDETERMINADO'`. O `subtype`
> deve ser `"SLC NAND"`, `"MLC NAND"` ou `"TLC NAND"` — nunca só `"NAND"`.

### 5.9 NOR Flash / OneNAND / Mask ROM

| Prefixo | Tipo | Decode | Status |
|---------|------|--------|--------|
| K5D | OneNAND | DRAM_PC (density) | ✅ Completo |
| K5 | NOR Flash | nenhum | ℹ️ Routing apenas |
| K8 | Mask ROM/NOR | nenhum | ℹ️ Routing apenas |

K5D usa DRAM_PC intencionalmente: `pn[3:5]` = 1G/2G/4G/8G para densidade em bits —
as chaves coincidem e o decode funciona corretamente.

### 5.10 Empacotamentos Especiais

| Prefixo | Tipo | Decode | Status |
|---------|------|--------|--------|
| KAT | ePoP (Package-on-Package) | nenhum | ⚠️ Sem decode capacidade |
| KUS | BGA NVMe SSD | KUS_CAP | ✅ Completo (chave 01 pendente) |
| K7 | SRAM | nenhum | ℹ️ Routing para resíduo |

### 5.11 SoC / Sensor / PMIC

| Prefixo | Tipo | Decode | Status |
|---------|------|--------|--------|
| S5E | Exynos SoC | nenhum | ℹ️ Routing apenas |
| S5K | ISOCELL Camera | nenhum | ℹ️ Routing apenas |
| S2M / S2A / S2D | PMIC | nenhum | ℹ️ Routing apenas |

---

## 6. fix_known_parts — Template e Regras

### 6.1 Template correto (convenção 2026-06-19)

```python
# CHIP DDR (K4B DDR3 x8 — 8Gb = 1GB por die)
{
    "pn": "K4B8G0846D",        # PN BASE (sem sufixo) — OBRIGATÓRIO
    "create": True,
    "create_defaults": {
        "brand_name": "Samsung",
        "chip_type":  "RAM",         # sempre "RAM" para DDR/GDDR
        "subtype":    "DDR3",        # SOMENTE a geração — sem bus width, tensão ou qualificadores
        "status":     "enriched",
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "RAM",
        "subtype":    "DDR3",        # "DDR3", "DDR3L", "DDR4", "DDR5", "GDDR5"…
        "interface":  "x8",          # bus width do chip — "x8", "x16", "x4"
        "capacity":   "1GB",         # por die, em MB ou GB (nunca em Gbit)
        "confidence": "confirmed",
        "status":     "enriched",
    },
    "reason": "Samsung Semiconductor Global: K4B8G0846D (8Gb DDR3) ✓. Fonte Tier 1.",
},
{
    "pn": "K4B8G0846D-MYK0",   # variante com sufixo — mesmos campos
    "create": True,
    "create_defaults": { ... },
    "fields": { ... },
    "reason": "...",
},
```

```python
# CHIP LPDDR STANDALONE (K4E LPDDR3 — 4GB)
{
    "pn": "K4EBE304EB-EGCE",
    "create": True,
    "create_defaults": {
        "brand_name": "Samsung",
        "chip_type":  "LPDDR3",      # tipo LPDDR vai no chip_type (não "RAM")
        "subtype":    "LPDDR3",      # mesmo que chip_type
        "status":     "enriched",
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "LPDDR3",
        "subtype":    "LPDDR3",
        "interface":  "",            # VAZIO para LPDDR standalone e eMCP — SEMPRE
        "capacity":   "4GB",
        "confidence": "confirmed",
        "status":     "enriched",
    },
    "reason": "K4E_CAP: BE=4GB (32Gb) LPDDR3. Samsung Semiconductor Global ✓.",
},
```

```python
# UPDATE-ONLY (sem create: True) — para registro que já existe no banco
# mas precisa de correção de campo
{
    "pn": "K4EBE304EB",
    # SEM "create": True — só atualiza se o registro existir
    "fields": {
        "chip_type":  "LPDDR3",
        "subtype":    "LPDDR3",
        "interface":  "",
        "capacity":   "4GB",
        "confidence": "confirmed",
        "status":     "enriched",
    },
    "reason": "Correção convenção 2026-06-19: subtype era 'LPDDR3 Mobile', interface era 'LPDDR3'.",
},
```

### 6.2 Regras de `capacity`

- **DDR/GDDR:** `capacity` = bytes por die, em MB ou GB. Conversão: `density_Gbit ÷ 8 = GB`.
  Ex.: 8Gb → `"1GB"`, 512Mb → `"64MB"`.
- **LPDDR standalone:** `capacity` = GB do pacote completo (mesmo valor que vai para o gateway).
- **eMCP/uMCP:** NÃO preencher `capacity` — usar `emcp_nand` e `emcp_ram`.
- **NUNCA** usar Gbit no campo `capacity` (ex.: `"8Gbit"` → errado).

### 6.3 Regra dos dois PNs (base + variante)

Ao confirmar um chip DDR, sempre adicionar:
1. O **PN base** (sem sufixo) — ex.: `K4B4G1646D`
2. Cada **variante com sufixo** com confirmação Tier 1 — ex.: `K4B4G1646D-BYK0`

O operador pode ver o PN com ou sem sufixo no laser marking físico. Se só a variante
com sufixo estiver no banco, a busca pelo PN base cai na gramática
(`confidence="estimated"`, `known_exact=false`) — errado para chip já pesquisado.

### 6.4 Hierarquia de fontes (imutável)

Samsung Semiconductor Global (título indexado `(X Gb)`) > Datasheet Samsung oficial >
Octopart com fonte Samsung > Distribuidor B2B rastreável > IA/estimativa.

**Nunca aceitar como fonte única:** Flash64Box, fóruns asiáticos de reparo, WinSource,
catálogos de Shenzhen, análise de IA local.

---

## 7. assess_profitability — Limiares DDR

| Parâmetro ProfitabilityConfig | Default | Significado |
|-------------------------------|---------|-------------|
| `ddr_min_gen` | 3 | DDR1/DDR2 (gen < 3) → **NÃO RENTÁVEL** sempre |
| `ddr3_min_gbit` | 2.0 | DDR3 < 2 Gb (256MB/die) → **NÃO RENTÁVEL** |
| `ddr4plus_min_gbit` | 8.0 | **⚠️ AJUSTAR para 1.0** no admin (1 Gbit = 0.125 GB) |

O default de 8.0 para DDR4 classifica DDR4 4Gb como NÃO RENTÁVEL incorretamente.
O limiar correto confirmado pelo usuário é 1 Gb — praticamente todas as densidades
DDR4 existentes ficam RENTÁVEL.

**Como o engine lê a capacidade para profitability:**
1. Tenta `dram_density` field → extrai Gb diretamente
2. Fallback: `capacity` field → `_extract_gib()` converte para GB → divide por 0.125

**Por isso `capacity` deve estar em MB ou GB**, nunca em Gbit.

### Destinos comerciais por tipo

| Categoria | Destino |
|-----------|---------|
| uMCP UFS 64GB+ (KM5/KM8/KM2) | Bancada reacondicional uMCP — Prioridade Diamante |
| uMCP UFS (KMD/KML/KMG) | Bancada reacondicional uMCP Premium |
| eMCP 32GB+3GB / 64GB+4GB+ | Bancada reacondicional eMCP |
| LPDDR5/5X (K3KL/K3LK) 4GB+ | Bancada reacondicional mobile — tolerância zero para resíduo |
| LPDDR4/4X 2GB+ | Bancada reacondicional mobile |
| LPDDR3 2GB (K3Q, K3R, K4E) | Reacondicional seletivo — checar demanda B2B |
| LPDDR3 ≤ 1GB | Resíduo (moagem) — sem liquidez B2B |
| DDR1 / DDR2 (K4H, K4T) | Resíduo — geração < 3 → sempre NÃO RENTÁVEL |
| DDR3 K4B 1Gb (128MB/die) | Resíduo |
| DDR3 K4B ≥ 2Gb (256MB+) | Checar demanda — a definir por mercado |
| DDR4 K4A — qualquer densidade | Reacondicional — alta liquidez B2B |
| DDR5 K4RA/K4RB | Reacondicional — premium |
| GDDR3 K4W | Bancada GPU (junto com K4J/K4G) |
| GDDR5 K4G / GDDR6 K4Z | Bancada GPU — decode cap ausente |
| SRAM K7 / DDR1/2 / RDRAM | Resíduo (moagem/refino) |

---

## 8. Armadilhas e Decisões Arquiteturais

### 8.1 Interface de LPDDR — erro histórico sistêmico

**Antes de 2026-06-19:** todas as famílias LPDDR standalone em `populate_samsung.py`
usavam a geração como `interface` (ex.: `interface="LPDDR4"`). Isso é **errado** —
interface deve ser o bus width ou vazio.

**Corrigido em 2026-06-19:** 18 famílias em `populate_samsung.py`, 6 em `populate_rayson.py`,
11 em `populate_hynix.py`, 26 entradas em `fix_known_parts.py`. Total: 61 correções.

Se você encontrar `interface="LPDDR*"` em qualquer arquivo, **é um bug** — corrija.

### 8.2 chip_type="DDR" era errado

**Antes de 2026-06-19:** fix_known_parts usava `chip_type="DDR"` para chips DDR discretos.
**Corrigido:** 41 entradas (K4B x4, K4H DDR1, K4T DDR2) alteradas para `chip_type="RAM"`.

O gateway de estoque precisa de `chip_type="RAM"` para montar o label correto.
`chip_type="DDR"` não é reconhecido pelo gateway e produz label vazio/errado.

### 8.3 subtype verboso quebra o label do gateway

Qualquer qualificador além da geração/célula **vaza** para o label e trunca o display.
Exemplos de subtypes **errados** que foram corrigidos:
- `"DDR3 PC DRAM 8Gb x8"` → label `"DDR3 PC DRAM 8Gb x8+8G"` — truncado
- `"LPDDR3 Mobile"` → label `"LPDDR3 Mobile+4G"` — errado
- `"LPDDR4X Multi-Channel"` → label `"LPDDR4X Multi-Channe…"` — truncado
- `"SLC NAND paralela industrial"` → label com texto verboso

Use **sempre** a forma curta: `"DDR3"`, `"LPDDR4X"`, `"SLC NAND"`.

### 8.4 K4EBE304EB — PN base artificial

`K4EBE304EB` (10 chars) é um PN base **artificial** criado antes para representar
a família K4E BE. PNs Samsung LPDDR3 reais têm 14 chars no formato completo
(ex.: `K4EBE304EB-EGCE`). O registro 10-char existia no banco com dados errados.

**Regra:** Não recriar este registro via `fix_known_parts` (sem `"create": True`).
Usar UPDATE-ONLY para corrigir os campos do registro existente. Se quiser adicionar
novos chips K4E, usar o PN completo de 14 chars com sufixo.

### 8.5 decode_gen_pos=None nos uMCPs numéricos

KM8, KM5, KM2, KM1, KM4, KMV usam `decode_gen_pos=None` intencionalmente.
Nesses prefixos, pn[2] é um dígito numérico da série (1/2/4/5/8), não código de
geração RAM. O engine faz fallback ao `subtype` fixo do `ChipFamily`.
**Não alterar sem revisar o comportamento do engine.**

### 8.6 decode_density_type + decode_cap_map juntos — conflito

K4F, K4U e K3U **devem** ter `decode_density_type=""`. São mutuamente exclusivos
com `decode_cap_map`. Se `decode_density_type="mobile"` e `decode_cap_map` forem
configurados na mesma família, o engine produz dados conflitantes.

### 8.7 K4Z — conflito de nomenclatura resolvido

K4Z Samsung é **GDDR6/GDDR6X** (mapeado em `populate_samsung.py`).
Não confundir com LPDDR4X — esse seria SK Hynix, não Samsung.
K4Z foi erroneamente listado como "LPDDR4X Surface/Chromebooks" em documentação
anterior. Resolvido.

### 8.8 KMV — bifurcação de prefixo

Dois chips completamente diferentes compartilham o prefixo KMV:
- `KMV2...` / `KMV3...` → uMCP flagship LPDDR5X (2022+) — priority=30
- `KMV` + LETRA → eMCP legado LPDDR2 (2010–2013) — priority=40

Prefixos mais longos têm prioridade — sistema correto.

### 8.9 K4R — bifurcação de prefixo

K4RA (priority=80) → DDR5 vence sobre K4R (priority=100) → RDRAM.
Correto — o DDR5 tem prefixo mais longo mas prioridade numericamente menor.

### 8.10 DRAM_MOBILE compartilhado

K3, K3R, K3Q e K4P (Samsung) compartilham DRAM_MOBILE com `brand=None`.
Se outra marca usar prefixo de PN com as mesmas chaves e valores diferentes,
haverá colisão. Monitorar ao expandir para novas marcas.

### 8.11 Armadilhas de dados externos

| Armadilha | Descrição |
|-----------|-----------|
| **Gb vs GB** | IA confunde sempre. Verificar: "32Gb LPDDR4X" → 32÷8 = 4GB |
| `"por die"` duplicado | Não colocar `"por die"` no val_secondary — engine já acrescenta |
| **lru_cache** | Após `populate_samsung --overwrite`, **reiniciar o servidor**. Só assim as famílias novas aparecem |
| **AI inventando cap_keys** | AI sugeriu "KBKB" (4 chars) quando era "BK" (2 chars). Verificar sempre |
| **AI trocando primary/secondary** | LPDDR5_CAP inicial tinha Gb em val_primary — UI mostrava "64Gb" em vez de "8GB" |
| **Distribuidor vs. datasheet** | Jotrin, Censtry, Wolfchip: dados frequentemente errados |
| **"Galaxy MX6432"** | Código interno Samsung (64=eMMC cap, 32=Gb RAM). Não é nome de celular — limpar `device` |

---

## 9. Gaps e Roadmap

### Sprint A — Impacto imediato, risco baixo

**NAND Flash K9 — decode capacidade:**
Criar mapa `NAND_FLASH_CAP` com chaves padrão `pn[3:5]`:
1G=1Gb(128MB) · 2G=2Gb · 4G=4Gb · 8G=8Gb · AG=16Gb · BG=32Gb · CG=64Gb · DG=128Gb.
Aplicar às 8 famílias K9. Confirmar ao menos as mais comuns por datasheet.

### Sprint B — Impacto alto, requer pesquisa Tier 1

**GDDR5 decode (K4G):**
Confirmar chaves `pn[3:5]` para ao menos 4 PNs comuns de GPU (buscar K4G41325FC no
Octopart). Criar GDDR5_CAP. Atualizar tip com destino GPU.
Prováveis chaves: BG=4Gb(512MB), CG=8Gb(1GB), DG=16Gb(2GB), EG=32Gb(4GB).
**Confirmar antes de criar o mapa.**

**GDDR6 decode (K4Z):**
Idem K4G. Buscar K4Z80165QB ou similar no Octopart.

### Sprint C — Qualidade de dados

**SAM_EMCP_CAP — gaps Z6, T9, 512GB+12GB:**
Aguardar PN físico escaneado na esteira + confirmação Octopart.
Não adicionar sem evidência (regra de ouro: sem PN físico real = não mapear).

### Sprint D — Long-tail

**K4RCH — criar família K4RC em populate_samsung.py:**
Por enquanto coberta por entradas confirmed em fix_known_parts (workaround).
Fix definitivo: criar família K4RC com gramática própria.

**K4RA DDR5 alta densidade:**
Adicionar entradas ao DRAM_PC: "BH"=32Gb(4GB) / "CH"=64Gb(8GB) se PNs K4RA
confirmados existirem.

**UFS 4.0 sub-prefixo:**
Identificar e mapear quando chip UFS 4.0 standalone aparecer na esteira.

**K3QF3/K3QF4:**
Aguardar chip físico com PN K3QF3F30... Confirmar por Octopart, então adicionar.

### Completude por categoria

```
CATEGORIA              COMPLETUDE    PRÓXIMO PASSO
─────────────────────────────────────────────────────
eMCP                   ████████░░ 95%   gaps: Z6, T9, 512GB+12GB
uMCP                   ████████░░ 95%   gaps: T9, 512GB+12GB
LPDDR4/4X/5/5X         ████████░░ 95%   gap: K3QF3/4 pendente
LPDDR3                 ██████████100%   completo
DDR4                   ██████████100%   K4A cobre; K4C descartado
DDR3                   ██████████100%   K4B; DDR3L via sufixo BY/MY
eMMC/UFS               ████████░░ 95%   decode geração pn[6] resolvido
DDR5                   ██████░░░░ 60%   K4RCH sem família; DRAM_PC topa em 16Gb
GDDR                   █████░░░░░ 50%   K4W OK; K4G/K4Z sem decode cap
NAND Flash K9          █████░░░░░ 50%   sem decode capacidade
NOR / OneNAND          ███████░░░ 70%   K5D OK, K5/K8 routing
DDR1/DDR2/RDRAM/SDRAM  ██████████100%   completo, resíduo
SoC/PMIC/Sensor        ████████░░ 80%   routing OK, decode modelo ausente
```

---

## 10. Histórico de Correções

| Data | PN / Família | Ação | Fonte | Motivo |
|------|-------------|------|-------|--------|
| 2026-05-08 | K4B, K4A | Refinamento completo: suffix_rules, reasoning, tip comercial | Octopart | Famílias PC DDR3/DDR4 corrigidas |
| 2026-05-09 | K4W | Corrigido: NÃO é DDR3L — é gDDR3 GPU | Esquemáticos Dell/ATI | Auditoria classificação errada |
| 2026-05-09 | K4C | Descartado: família fantasma, zero PNs Samsung reais | Varredura Octopart | Zero evidência |
| 2026-05-09 | KMG | Corrigido: eMCP LPDDR3 (era uMCP) | Datasheet KMGP6001BM | Família mal categorizada |
| 2026-05-09 | SAM_EMCP_CAP 8X | Corrigido 8GB → **16GB** NAND | SBiT B2B ✓ | Valor errado há muito tempo |
| 2026-05-09 | SAM_EMCP_CAP 5X/NX | Bloqueados sem evidência | — | Regra de ouro |
| 2026-05-09 | SAM_EMCP_CAP P6 | Corrigido 4GB → 3GB RAM | Datasheet KMG | KMG usa P6=64GB+3GB, não 4GB |
| 2026-05-09 | KLM | SAM_EMMC_GEN criado; decode_gen_pos=6 | Catálogo Samsung | F=eMMC 4.5 / E=5.0 / J=5.1 |
| 2026-05-13 | KMS | Corrigido: LPDDR1 legado (era LPDDR4X) | — | Galaxy Centura ~2012 |
| 2026-06-19 | **61 famílias** | `interface="LPDDR*"` → `""` em populate_samsung/rayson/hynix + fix_known_parts | Auditoria convenção | Interface deve ser bus width, não geração |
| 2026-06-19 | **41 entradas** | `chip_type="DDR"` → `"RAM"` em fix_known_parts (K4B x4, K4H, K4T) | Auditoria convenção | Gateway precisa de "RAM" para montar label |
| 2026-06-19 | **Subtypes verbosos** | `"DDR1 PC DRAM 256Mb x16"` → `"DDR1"` etc. | Auditoria convenção | Label gateway truncava com texto longo |
| 2026-06-19 | K4EBE304EB | UPDATE-ONLY: subtype `"LPDDR3 Mobile"` → `"LPDDR3"`, interface `"LPDDR3"` → `""` | Auditoria conveção | Registro antigo com dados fora de convenção |
| 2026-06-19 | LPDDR5_CAP K3KL subtype | engine.py: subtype sync com `_decoded_gen` para eMCP | — | subtype de eMCP não era preenchido pela gramática |
| 2026-06-19 | K4J (13 PNs) | KnownParts GDDR3 adicionados: K4J10324KE/QD, K4J52324QH, K4J55323QF/QG | Samsung Product Guide Abr. 2010, Alldatasheet ref #347919, Octopart | grammar_complete=false by design — density codes "10"/"52"/"55" não estão no DRAM_PC |
| 2026-06-19 | K3RG (7 PNs) | KnownParts LPDDR4 adicionados: BMCGCJ, CAMGCJ, CMFGCJ, CMCGCJ, 4G40MMMGCJ, 4G40MMMGCJT00E, 6G60MMMGCJ | PSG Samsung 1H 2017, Octopart (Worldway/Win Source) | pn_not_in_db=true apesar de grammar_complete=true |

### Chips confirmados individuais (histórico)

| PN | Tipo | Valor | Fonte | Ação |
|----|------|-------|-------|------|
| KMQX10013MB | eMCP 3 | X1=32GB+2GB | Octopart | corrigido (era 64GB+4GB) |
| KM5P9001DMB424 | uMCP | P9=64GB+4GB | Octopart | novo |
| KM5V8001DM-B622 | uMCP | V8=128GB+4GB | Fabricante | corrigido (era 8GB) |
| KM5C7001DM-B622 | uMCP | C7=64GB+4GB | Fabricante | novo |
| KM2L9001CM-B518 | uMCP | L9=128GB+6GB | Fabricante | novo |
| KM8F9001JM-B813 | uMCP | F9=256GB+8GB | Fabricante | novo |
| KM8F8001MM-B813 | uMCP | F8=256GB+12GB | Fabricante | novo |
| KMFN60012MB214 | eMCP | N6=8GB+1GB | Octopart | novo |
| K3KL9L90DMMGCU | LPDDR5 | 9L=2GB | Octopart | novo + fix_known_parts |
| K3LKBKB0BMMGCP | LPDDR5X | BK=4GB | Octopart | novo |
| K3KL8L80EMMGCU | LPDDR5 | 8L=4GB | Octopart | novo |
| K3QF1F10DMAGCE000 | LPDDR3 | K3QF_CAP: 1=1GB | Octopart | nova sub-família K3QF |
| KMDP6001DA | eMCP | P6=64GB+4GB LPDDR4X | Datasheet | device corrigido |
| KMGP6001BM | eMCP | P6=64GB+3GB LPDDR3 | Datasheet | KMG=eMCP LPDDR3 (não uMCP) |
| K4W1G1646D-EC12 | GDDR3 | 1G=1Gb=128MB | Esquemático/Octopart | K4W classificação corrigida |
| K4B1G1646G-BCK0 | DDR3 | 1Gb x16 128MB | Octopart | tip com destino por densidade |
| K4A8G165WC-BCRC | DDR4 | 8Gb x16 1GB DDR4-2400 | Octopart | tip com guia comercial |
| KMQ8X000SA-B414 | eMCP | 8X=16GB NAND+1GB LPDDR3 | SBiT B2B | 8X corrigido de 8GB→16GB |
| KMR8X0001M | eMCP | 8X=16GB NAND, emcp_ram=2GB | fix_known_parts | variante KMR com RAM diferente |

---

## 11. Pipeline de trabalho

### Para atualizar gramática (famílias + DecodeMaps)

```bash
# 1. Editar populate_samsung.py (ChipFamily ou DecodeMap)
# 2. Propor ao usuário — que roda:
python manage.py populate_samsung --dry-run      # revisar antes
python manage.py populate_samsung --overwrite    # usuário executa

# 3. REINICIAR O SERVIDOR — obrigatório; lru_cache não invalida automaticamente

# 4. Verificar resultado:
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('KMQ8X000SA-B414'), indent=2, ensure_ascii=False))
"
```

### Para corrigir registros individuais (sem alterar gramática)

```bash
# 1. Editar fix_known_parts.py (somente seção Samsung)
# 2. Propor ao usuário — que roda:
python manage.py fix_known_parts    # usuário executa
# NÃO requer reinício do servidor (não altera gramática/lru_cache)
```

### Para importar PNs do Samsung PSG

```bash
# 1. Colocar o CSV em data/psg/
# 2. Registrar o arquivo em import_samsung_psg.py (se necessário)
# 3. Propor ao usuário — que roda:
python manage.py import_samsung_psg --all    # usuário executa
# Não altera gramática — não requer restart
```

### Ordem típica de uma sessão de atualização Samsung

```bash
python manage.py populate_samsung --overwrite   # usuário
python manage.py fix_known_parts                # usuário
# → REINICIAR SERVIDOR ←
# verificar chips representativos no shell (ver §12)
# git add + git commit
```

---

## 12. Como verificar se um chip Samsung está correto

### Verificação via shell

```bash
# eMCP — esperado: chip_type='eMCP', emcp_nand='16GB', emcp_ram='LPDDR3 1GB'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('KMQ8X000SA-B414'), indent=2, ensure_ascii=False))
"

# DDR3 — esperado: chip_type='RAM', subtype='DDR3', dram_density='8Gb = 1GB por die [~]'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('K4B8G1646D'), indent=2, ensure_ascii=False))
"

# LPDDR4 — esperado: chip_type='LPDDR4', subtype='LPDDR4', capacity='4GB', interface=''
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('K4F8E304HB-MGCH'), indent=2, ensure_ascii=False))
"

# URL alternativa: /chips/decode/?pn=<PN>
# No estoque: botão "Debug" → JSON completo + fonte de cada campo
```

### Checklist de chip correto

- [ ] `known=true`
- [ ] `confidence="confirmed"` ou `"manual"`
- [ ] `chip_type` correto para o tipo (ver tabela §2.1)
- [ ] `subtype` é apenas a geração — sem qualificadores, máximo 3 palavras
- [ ] `interface=""` para LPDDR/eMCP/uMCP; bus width (`"x8"`, `"x16"`) para DDR/GDDR
- [ ] Campo de capacidade preenchido: `emcp_nand`+`emcp_ram` para eMCP/uMCP; `dram_density` para DDR; `capacity` para LPDDR/eMMC/UFS
- [ ] `profitable != "INDETERMINADO"` — INDETERMINADO significa campo de capacidade ausente → **bloqueador de produção**
- [ ] Label do estoque correto: `DDR3+8G`, `LPDDR4X+4G`, `EMCP64+4`, `EMMC64GB`, `UFS128GB`

---

## 13. Arquivos-chave Samsung

```
chips/management/commands/
  populate_samsung.py         ← GRAMÁTICA: ChipFamilies + DecodeMaps (SAM_FLASH_CAP,
                                 SAM_EMCP_CAP, SAM_EMCP_GEN, SAM_EMMC_GEN, DRAM_PC,
                                 DRAM_MOBILE, LPDDR4_CAP, LPDDR5_CAP, K4E_CAP,
                                 K3QF_CAP, RDRAM_CAP, KUS_CAP).
                                 Editar para adicionar novas chaves ou famílias confirmadas.
  fix_known_parts.py          ← Correções pontuais de KnownParts Samsung no banco.
                                 Entradas com brand_name="Samsung" ou PNs que começam
                                 com K4, K3, KL, KM, K9, K7, K5, K8, KAT, KUS.
  import_samsung_psg.py       ← Importa CSVs do Samsung Product Selection Guide.
                                 Preenche KnownParts com dados oficiais Samsung.

data/psg/
  *.csv                       ← CSVs por categoria: mobile_dram, emmc, ufs, lpddr5,
                                 emcp_lpddr3, emcp_lpddr4x, umcp_lpddr4x, umcp_lpddr5…

Referências cruzadas:
  CLAUDE.md §2                ← regras de ouro do projeto inteiro (não violar)
  CLAUDE.md §4                ← arquitetura do engine (classify, lru_cache, precedência)
  CLAUDE.md §5                ← pipeline de comandos completo do projeto
  CLAUDE.md §6                ← convenção canônica de campos por tipo de chip (projeto inteiro)
  HANDOFF.md                  ← histórico de decisões arquiteturais (BUG-1…BUG-6)
  docs/CONVENCAO_MICRON_ESTOQUE.md ← convenção canônica de campos (referência cross-marca)
```

---

> **Regra de trabalho:** Claude edita arquivos. O usuário roda os comandos.
> Nunca execute `populate_*`, `import_*`, `fix_*`, `migrate` sem o usuário confirmar.
> Sempre `--dry-run` antes de qualquer comando que escreve no banco de dados.
