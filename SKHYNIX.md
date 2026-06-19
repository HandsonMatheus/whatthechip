# SK Hynix — Bíblia Técnica e de Negócio

> **Referência permanente para WhatTheChip.**
> Cobre todas as famílias SK Hynix presentes ou esperadas na bancada da eMiner:
> decode de PN, campos corretos no banco, rentabilidade, fontes, pegadinhas.
> Para convenção geral de campos: **`docs/CONVENCAO_CAMPOS_ESTOQUE.md`**.
> Para regras do projeto: **`CLAUDE.md`**.

---

## 1. Identidade da marca

- **Nome oficial:** SK hynix Inc. (antes: Hynix Semiconductor)
- **País:** Coreia do Sul
- **Prefixo histórico DDR:** `HY5…` (Hynix era) → `H5…` / `H9…` (SK Hynix era)
- **Segmentos produzidos:** DRAM (DDR1–5, LPDDR2–5X), NAND (eMMC, UFS), eMCP, uMCP
- **Relevância para eMiner:** SK Hynix é a **2ª maior fabricante global de DRAM**;
  seus chips aparecem em praticamente todos os dispositivos desmontados na bancada.

---

## 2. Tabela mestre de famílias

| Prefixo PN | Família WTC | Tipo | Subtipo | Pacote | Decode pos. |
|---|---|---|---|---|---|
| `HY5DU` | HY5DU | RAM | DDR1 | TSOP | pn[5:7] |
| `HY5PS` | HY5PS | RAM | DDR2 | FBGA | pn[5:7] |
| `H5PS` | H5PS | RAM | DDR2 | FBGA | pn[4:6] |
| `H5TQ` | H5TQ | RAM | DDR3 | FBGA-78 | pn[4:6] |
| `H5TC` | H5TC | RAM | DDR3L | FBGA-78 | pn[4:6] |
| `H5AN` | H5AN | RAM | DDR4 | FBGA-78/96 | pn[4:6] (Era1) / pn[3:5] (Era2) |
| `H5CG` | H5CG | RAM | DDR5 | FBGA | pn[3:5] |
| `H9TK` | H9TK | RAM | LPDDR2 | FBGA-168 | pn[7] |
| `H9CC` | H9CC | RAM | LPDDR3 | FBGA-178 | pn[7] |
| `H9HCN` | H9HCN | RAM | LPDDR4/4X | FBGA-200 | pn[7] |
| `H54G` | H54G | RAM | LPDDR4X | BGA | pn[4] (escala alfa) |
| `H9TQ` | H9TQ | eMCP | eMCP LPDDR3 | BGA | pn[4:6]+pn[6:8] |
| `H9DP` | H9DP | eMCP | eMCP LPDDR2 | BGA | pn[4:6]+pn[6:8] |
| `H9HP` | H9HP | uMCP | uMCP | BGA | — |
| `H26M` | H26M | eMMC | eMMC | FBGA-153 | pn[4] |
| `H26T` | H26T | eMMC | eMMC (alta cap.) | FBGA-153 | pn[4] |
| `H28U` | H28U | UFS | UFS standalone | FBGA-153 | pn[4] |
| `HN8T` | HN8T | UFS | UFS 4D NAND | BGA | pn[4:6] |

---

## 3. Decode técnico por família

### 3.1 DDR1 — HY5DU (1.8V, TSOP)

```
pn[5:7] → HYX_DDR1_CAP
  64 = 8MB   (64Mbit)
  28 = 16MB  (128Mbit — últimas 2 chars de "128")
  56 = 32MB  (256Mbit)
  12 = 64MB  (512Mbit — "512" → "12")
```

### 3.2 DDR2 — HY5PS e H5PS (1.8V, FBGA)

```
HY5PS — pn[5:7] → HYX_DDR2_PS_CAP
  56 = 32MB · 12 = 64MB · 1G = 128MB

H5PS — pn[4:6] → HYX_DDR2_H5PS_CAP
  25 = 32MB · 51 = 64MB · 1G = 128MB · 2G = 256MB
```

### 3.3 DDR3 1.5V — H5TQ (FBGA-78)

```
H5TQ [dens] [org] 3 [gen] FR [-speedC]
      [4:6]   [6]
```

| pn[4:6] | Capacidade | pn[6] | Organização | pn[8] | Geração |
|---|---|---|---|---|---|
| 1G | 128MB | 4 | x4 | A | 2ª gen |
| 2G | 256MB | 6 | x16 | B | 3ª gen |
| 4G | 512MB | 8 | x8 | C | 4ª gen |
| 8G | 1GB | — | — | D/E | 5ª/6ª gen |
| — | — | — | — | G/M/T | gens posteriores |

**pn[7] = sempre `3`** (8 banks, fixo DDR3).

**Sufixos de velocidade** (após `-`):
`G7` = DDR3-1066 · `H9` = DDR3-1333 · `PB` = DDR3-1600 · `RD` = DDR3-1866 · `TE` = DDR3-2133

**⚠ H5TQ8G43 não existe.** SK Hynix não produziu 8Gbit x4 DDR3 1.5V. Se aparecer = suspeito.

### 3.4 DDR3L 1.35V — H5TC (FBGA-78)

Decode idêntico ao H5TQ, mesma posição e valores. Diferenças:
- Sufixos de temperatura terminam em **`A`** (DDR3L) em vez de `C` (DDR3).
  Ex: `-PBA` (DDR3L) vs `-PBC` (DDR3).
- `H5TC8G43AMR` = DDP (Dual Die Package): dois dies 4Gbit empilhados = 1GB total.
  Sufixo `MR` (M = multi-die) identifica DDP. Capacidade por pacote = 1GB.

### 3.5 DDR4 1.2V — H5AN (FBGA-78/96)

**Era 1** (pn[4:6]):
```
H5AN [dens] [org] N [gen] FR/JR [-speedC]
      [4:6]   [6]
```

| pn[4:6] | Cap. | pn[6] | Org | pn[8] | Die |
|---|---|---|---|---|---|
| 4G | 512MB | 4 | x4 | A | A-die |
| 8G | 1GB | 6 | x16 | B | B-die |
| AG | 2GB | 8 | x8 | C | C-die |
| — | — | — | — | D | D-die |

**Era 2** (pn[3:5]) — atenção: decode diferente:
```
H5AN [gen_dens] N [rest]
      [3:5]
  G3 = 1GB · G4 = 2GB · G5 = 4GB · G6 = 8GB
```

**Sufixos velocidade:** `UH` = DDR4-2400 · `VK` = DDR4-2666 · `WM` = DDR4-2933 · `XN` = DDR4-3200

### 3.6 DDR5 — H5CG (FBGA)

```
pn[3:5] → HYX_DDR5_CAP
  G4 = 2GB · GD = 3GB · G5 = 4GB
```

### 3.7 LPDDR2 standalone — H9TK (FBGA-168, 26nm)

```
H9TK NNN [cap] [gen] [org] [pkg] - [suffix]
          [7]   [8]
```

| pn[7] | Capacidade | pn[8] | Geração/nó |
|---|---|---|---|
| 1 | 128MB | G | 1ª geração (planar) |
| 2 | 256MB | J | 2ª gen (26nm, mais comum) |
| 4 | 512MB | K | 3ª geração |
| 8 | 1GB | — | — |

`pn[4:7]` = `NNN` (preenchimento fixo padrão).
Sufixo: `-NGH` = lead-free, grade G (1066), temp H. Não afeta capacidade.
**H9DA = die LPDDR2 dentro de eMCP** (sufixo `-4EM`). NÃO standalone. Não confundir.

### 3.8 LPDDR3 standalone — H9CC (FBGA-178, x32, 1.2V)

```
H9CC NNN [cap] [config] - suffix
          [7]
```

| pn[7] | Capacidade | Configuração |
|---|---|---|
| 8 | 1GB | 8Gb DDP (8J, 8K…) |
| B | 2GB | 16Gb DDP/QDP (BJ, BK, BL…) |
| D | 3GB | 24Gb QDP — **assimétrico** (24Gbit) |
| C | 4GB | 32Gb QDP |

**⚠ Chip físico mostra 12 chars** sem sufixo AR-Nxx. Ex: `H9CCNNNCLTML` (não `H9CCNNNCLTMLAR-NTD`).
**⚠ Teto: C=4GB. LPDDR3 não vai a 6GB ou 8GB.**
**⚠ Contexto:** H9CC é de **tablets Windows e ultrabooks** (Surface, MacBook Air 2018),
não de smartphones Android. Não confundir com H9CK (PoP de smartphone).

### 3.9 LPDDR4 / LPDDR4X standalone — H9HCNNN (FBGA-200)

```
H9HCNNN [cap2] [speed] ML [pkg] - [suffix]
          [7:9]
```

| pn[7] | Capacidade | pn[8] = código | Protocolo | VDDQ |
|---|---|---|---|---|
| 4 | 0.5GB | K → 4K | LPDDR4X ou LPDDR4 | 0.6V / 1.1V |
| 8 | 1GB | K → 8K | LPDDR4 | 1.1V |
| B | 2GB | K/P/R → BK/BP/BR | LPDDR4X ou LPDDR4 | — |
| C | 4GB | P/R → CP/CR | LPDDR4X ou LPDDR4 | — |
| F | 8GB | A/B → FA/FB | LPDDR4X | 0.6V |

**Protocolo pelo sufixo do pkg:**
- `MMLXR` = LPDDR4X 4266 Mbps (alta vel.)
- `MMLHR` = LPDDR4X 3733 Mbps
- `MLUHR`/`MLHR` com `KU/PU/BU` = LPDDR4 (VDDQ 1.1V)

**⚠ H9HCNNNECMML (6GB) está no banco com `confidence="manual"` e flag de divergência.**
6GB (48Gbit) NÃO existe na família H9HCNNN 200-ball (confirmado por Glochip/SK Hynix 2021).
O código `E` a 6GB pertence à família **H9HKNNN** (376/556-ball, pacote maior).
Pendente confirmação física do chip da bancada.

### 3.10 eMCP — H9TQ / H9DP

```
H9TQ: pn[4:6] → NAND (HYX_EMCP_NAND_CAP) · pn[6:8] → RAM (HYX_H9TQ_RAM_CAP)
  NAND: 08=1GB · 17=2GB · 32=4GB · 64=8GB · 1A=16GB
  RAM:  08=1GB · A4=512MB · A6=768MB · B8=1.5GB · F8=2GB

H9DP: decode similar, LPDDR2 (legacy)
```

### 3.11 eMMC — H26M / H26T

```
pn[4] → HYX_EMMC_CAP
  3 = 4GB · 4 = 8GB · 6 = 16GB · 7 = 32GB/64GB · 8 = 64GB · B = 128GB
```

### 3.12 UFS — H28U / HN8T

```
H28U pn[4] → HYX_UFS_CAP: 6 = 32GB · 8 = 64GB
HN8T pn[4:6] → prefixo numérico: 05 = 128GB
```

---

## 4. Convenção de campos no KnownPart

> Fonte canônica: **`docs/CONVENCAO_CAMPOS_ESTOQUE.md`** — leia se tiver dúvida.
> Resumo prático abaixo.

O estoque monta o rótulo da caixa física assim:
- **RAM/DDR/LPDDR** → `{subtype}+{tamanhoG}` — ex: `DDR3+2G`, `LPDDR3+4G`
- **eMMC** → `EMMC{cap}GB`  |  **UFS** → `UFS{cap}GB`
- **eMCP** → `EMCP{nand}+{ram}`  |  **uMCP** → `UMCP{nand}+{ram}`

### Regras de preenchimento

| Campo | O que vai | O que NÃO vai |
|---|---|---|
| `chip_type` | `RAM`, `eMMC`, `UFS`, `eMCP`, `uMCP` | specs |
| `subtype` | **só a geração**: `DDR3`, `DDR3L`, `DDR4`, `LPDDR3`, `LPDDR4`, `LPDDR4X`… | densidade, barramento, `SDRAM`, `standalone`, voltagem |
| `dram_density` | die em **Gb**: `2Gb`, `4Gb`, `8Gb` (DDR/GDDR) | bytes; capacidade de pacote |
| `capacity` | pacote em **bytes**: `256MB`, `4GB` | gigabits |
| `interface` | barramento elétrico: `DDR3`, `DDR4`, `LPDDR3`, `x16` | a geração já em subtype |
| `emcp_nand`/`emcp_ram` | NAND e RAM em **GB**: `4GB`, `768MB` | — |
| `notes` | todo o resto: organização, voltagem, avisos, fontes | — |

**Regra mestra de unidades (crítico):**
- Componente DDR/GDDR → `dram_density` em **Gb** (gigabit)
- Pacote LPDDR (multi-die) → `capacity` em **GB** (gigabyte)
- 1GB = 8Gb. Confundir gera `32G` no rótulo em vez de `4G`.

### Exemplos corretos

```python
# DDR3 componente (H5TQ2G43AFR — 2Gbit, x4)
chip_type    = "RAM"
subtype      = "DDR3"
dram_density = "2Gb"          # die em Gb
capacity     = "256MB"        # 2Gbit ÷ 8
interface    = "DDR3"
# → rótulo: DDR3+2G ✅

# LPDDR3 pacote (H9CCNNNCLTML — 4GB)
chip_type    = "RAM"
subtype      = "LPDDR3"
capacity     = "4GB"          # pacote completo
interface    = "LPDDR3"
# → rótulo: LPDDR3+4G ✅

# eMCP (H9TQ32A6BTMC — 4GB NAND + 768MB RAM)
chip_type    = "eMCP"
emcp_nand    = "4GB"
emcp_ram     = "768MB"
# → rótulo: EMCP4+0.75 ✅
```

---

## 5. Rentabilidade por família

> As regras exatas vivem no `ProfitabilityConfig` (singleton editável no admin).
> Os valores abaixo refletem a regra vigente no projeto — confirme no admin
> antes de comunicar ao operador.

| Família | Tipo | Rentabilidade típica | Observação |
|---|---|---|---|
| H9HCNNN LPDDR4X | RAM | **RENTÁVEL** | Alta demanda refurb smartphones premium |
| H9HCNNN LPDDR4 | RAM | **RENTÁVEL** | Boa demanda |
| H9CC LPDDR3 | RAM | **RENTÁVEL** | Tablets premium 2016–2019 |
| H5AN DDR4 | RAM | **RENTÁVEL** | PC/servidor atual |
| H5TQ DDR3 | RAM | **RENTÁVEL** (checar limiar) | DDR3 x8 ainda vende; x4 servidor é nicho |
| H5TC DDR3L | RAM | **RENTÁVEL** (checar limiar) | DDR3L laptop, boa liquidez |
| H9TK LPDDR2 | RAM | **NÃO RENTÁVEL** / limiar | LPDDR2 geração morta na maioria dos mercados |
| HY5PS / H5PS DDR2 | RAM | **NÃO RENTÁVEL** | Geração morta |
| HY5DU DDR1 | RAM | **NÃO RENTÁVEL** | Descarte / moagem |
| H26M / H26T eMMC | eMMC | **RENTÁVEL** ≥ 16GB | < 8GB = sucata |
| H28U / HN8T UFS | UFS | **RENTÁVEL** | Alta demanda |
| H9TQ / H9DP eMCP | eMCP | **RENTÁVEL** se LPDDR3+ | LPDDR2 eMCP = descarte |
| H9HP uMCP | uMCP | **RENTÁVEL** | UFS + LPDDR5 = premium |

**Regra `is_dead_by_generation`** — o engine testa se um chip é não rentável
independente da capacidade (ex: DDR2 de qualquer tamanho = NÃO RENTÁVEL).
Isso manda chips de geração morta para descarte diretamente, sem confirmar no banco.

---

## 6. O que está no banco hoje

### Confirmados (confidence = "confirmed" ou "manual")

**DDR1 — HY5DU:**
HY5DU281622ET-25 (16MB), HY5DU561622CTP-28 (32MB), HY5DU121622CTP-J (64MB)

**DDR2 — HY5PS / H5PS:**
HY5PS121621CFP-25 (64MB), HY5PS1G831CFP-Y5/S5 (128MB),
H5PS1G83EFR-S6C, H5PS1G63EFR-S6C (128MB), H5PS5182KFR-S5C (64MB)

**DDR3 — H5TQ x8:**
Sufixados: H5TQ1G83EFR-PBC (128MB), H5TQ2G63GFR-RDC (256MB), H5TQ2G83BFR-H9C (256MB),
H5TQ4G63EFR-RDC/TEC (512MB), H5TQ4G83EFR-RDC (512MB), H5TQ4G63AFR-PBC (512MB),
H5TQ4G83MFR-H9C (512MB), H5TQ8G63AMR-H9C (1GB)
Base: H5TQ1G83EFR, H5TQ2G63GFR/FFR/DFR (256MB), H5TQ2G83BFR/CFR (256MB),
H5TQ4G63AFR/EFR/MFR (512MB), H5TQ4G83AFR/EFR/MFR (512MB), H5TQ8G63AMR (1GB)

**DDR3 — H5TQ x4 (servidor RDIMM):**
H5TQ1G43AFP/BFR/TFR (128MB), H5TQ2G43AFR/BFR/CFR/EFR (256MB),
H5TQ4G43AFR/MFR (512MB), H5TQ4G43AMR/MMR (512MB DDP)

**DDR3L — H5TC x8:**
Sufixados: H5TC4G83CFR-PBA, H5TC4G63CFR-PBA/RDA, H5TC4G83BFR-PBA, H5TC8G83AMR-PBA
Base: H5TC4G83CFR/BFR, H5TC4G63CFR, H5TC8G83AMR

**DDR3L — H5TC x4 (servidor RDIMM):**
H5TC1G43BFR/TFR (128MB), H5TC2G43AFR/BFR/CFR/EFR (256MB),
H5TC4G43AFR/BFR/DFR/MFR (512MB), H5TC8G43AMR/MMR (1GB DDP)

**DDR4 — H5AN x8/x16:**
Sufixados: H5AN8G8NAFR-VKC/UHC (1GB), H5AN8G6NAFR-UHC (1GB), H5AN4G8NBJR-VKC (512MB),
H5AN8G8NCJR-VKC (1GB), H5AN8G8NDJR-VKC (1GB), H5ANAG6NCJR-VKC (2GB)
Base: H5AN8G8NAFR, H5AN8G6NAFR, H5AN4G8NBJR, H5AN8G8NCJR

**DDR4 — H5AN x4 (servidor):**
H5AN4G4NAFR/NBJR (512MB), H5AN8G4NAFR/NCJR (1GB)

**DDR5 — H5CG:**
H5CG48MEBDX014N (2GB)

**LPDDR2 — H9TK:**
H9TKNNN8JDAP (1GB base), H9TKNNN8JDAPLR-NGH (1GB iFixit ✓),
H9TKNNN8JDMPLR-NDM (1GB), H9TKNNN4GDMPLR-NDM (512MB),
H9TKNNN4GDAP (512MB manual), H9TKNNN2GDAP (256MB manual)

**LPDDR3 — H9CC:**
Base 12 chars: H9CCNNNCLTML (4GB ✓ bancada), H9CCNNN8JTML (1GB manual), H9CCNNNBLTML/BJTML (2GB manual)
Sufixados: H9CCNNN8JTALAR-NTM (1GB), H9CCNNNBLTMLAR-NTM (2GB), H9CCNNNBJTALAR-NVD (2GB),
H9CCNNNCLTMLAR-NTD/NUD (4GB)

**LPDDR4/4X — H9HCNNN:**
LPDDR4X: H9HCNNNCPMMLXR-NEE (4GB), H9HCNNNCPMMLHR-NME (4GB), H9HCNNNBKMMLXR-NEE (2GB),
H9HCNNNBKMMLHR-NME (2GB), H9HCNNNFAMMLXR-NEE (8GB)
LPDDR4: H9HCNNN8KUMLHR-NME (1GB), H9HCNNNBPUMLHR-NME (2GB), H9HCNNNBKUMLHR-NME (2GB),
H9HCNNNCPUMLHR-NME (4GB)
Manual/base: H9HCNNNCPMML (4GB), H9HCNNNECMML (6GB — ⚠ suspeito, ver §3.9)

**LPDDR4X — H54G:**
H54GE6CYRB (4GB)

**eMCP — H9TQ:** H9TQ32A6BTMC (4GB+768MB), H9TQ17ABJTCC (16GB+2GB)
**eMCP — H9DP:** H9DP32A4JJBC (4GB+512MB)
**uMCP — H9HP:** H9HP16AECMMD (128GB+6GB)
**eMMC — H26M:** H26M31001HPR (4GB), H26M64103EMR (32GB), H26M74002HMR (64GB), H26M78103CCR (64GB)
**eMMC — H26T:** H26T87001CMR (128GB)
**UFS — H28U:** H28U64222MMR (32GB), H28U88301AMR (128GB)
**UFS — HN8T:** HN8T05BZGR (128GB)

---

## 7. Como adicionar um PN confirmado

### 7.1 Template completo

```python
# Em add_confirmed_part.py, antes de "# Adicione mais chips aqui"
dict(
    part_number   = "H5TQ2G43CFR",      # PN exato, sem espaço
    brand_name    = "SK Hynix",
    family_prefix = "H5TQ",             # 4-5 chars — deve existir em ChipFamily
    chip_type     = "RAM",
    subtype       = "DDR3",             # SÓ a geração
    # dram_density = "2Gb",             # descomente para DDR/GDDR (die em Gb)
    capacity      = "256MB",            # pacote em bytes
    interface     = "DDR3",
    confidence    = "confirmed",        # "confirmed" = datasheet/iFixit/LCSC ✓
    notes         = (                   # strings concatenadas com +
        "pn[4:6]='2G' → 256MB (2Gbit ÷ 8). x4, FBGA-78, 1.5V. C-gen. "
        "Velocidades: -G7C · -H9C · -PBC · -RDC · -TEC. "
        "Fonte: Alldatasheet H5TQ2G43CFR ✓ · Octopart -PBC ✓."
    ),
),
```

### 7.2 Quando usar `dram_density`

- **DDR1/2/3/3L/4/5** → sempre preencher `dram_density` em Gb
  - H5TQ2G63GFR: `dram_density = "2Gb"`, `capacity = "256MB"`
- **LPDDR** (pacote multi-die) → deixar `dram_density` em branco
  - H9CCNNNCLTML: `capacity = "4GB"`, sem `dram_density`
- **eMCP/uMCP** → usar `emcp_nand` e `emcp_ram` em GB

### 7.3 Níveis de confiança

| confidence | Quando usar |
|---|---|
| `confirmed` | Datasheet oficial · LCSC com specs · Octopart · iFixit (texto do chip) · Preduo com foto · Datasheets360 |
| `manual` | Operador confirmou fisicamente · Broker sem datasheet (OMO, AliExpress detalhado) · Base PN inferida por padrão |
| **Nunca rebaixar** | Não trocar `confirmed` → `manual` sem motivo documentado |

### 7.4 Fluxo completo

```bash
# 1. Local
python add_confirmed_part.py

# 2. Git
git add add_confirmed_part.py
git commit -m "feat(chips): SK Hynix — descrição"
git push origin main

# 3. Render (após deploy)
python add_confirmed_part.py
# não precisa reiniciar — KnownPart não usa lru_cache
```

---

## 8. Fontes de pesquisa (rankeadas)

| Fonte | Melhor para | URL |
|---|---|---|
| Alldatasheet | Datasheets SK Hynix completos | `alldatasheet.com/view.jsp?Searchword=H5TQ2G43AFR` |
| SK Hynix EOL | Confirmar que PN existe/existiu | `skhynix.com/eolproducts.view.do` |
| LCSC | Estoque atual + specs | `lcsc.com/search?q=H9HCNNNCPMMLXR` |
| Octopart | Preço/estoque multi-distribuidor | `octopart.com/search?q=H5TC4G43MFR` |
| Preduo | Catálogo LPDDR/eMMC com fotos | `preduo.com` |
| iFixit | Teardown de produtos (chip reading) | `ifixit.com/Teardown/[produto]` |
| Datasheets360 | PNs antigos / EOL | `datasheets360.com/part/detail/[pn]` |
| Datasheets.com | Alternativa ao 360 | `datasheets.com` |
| OMO Electric | Broker China — muitos PNs x4 | `omo-ic.com/tags/H9TK.html` |
| Glochip | Página oficial SK Hynix LPDDR | `glochip.com/en/h-nd-559.html` |

**Fontes a evitar para capacidade:** HardDiskDirect escreve "(8GB)" para 8Gbit.
Sempre verificar organização (ex: 256Mx32 = 8Gbit = 1GB).

---

## 9. Pegadinhas e armadilhas

### 9.1 PN físico vs. PN distribuidor
Chips em PCB mostram **PN base** (sem sufixo de velocidade):
- Físico: `H5TQ2G63GFR` → banco precisa deste PN
- Distribuidor: `H5TQ2G63GFR-RDC` → banco precisa deste também
Ambos devem estar no banco para `known_exact = true` funcionar.

### 9.2 H9CC — chip físico mostra 12 chars, não 16
`H9CCNNNCLTML` (12 chars) é o que o operador lê. O PN completo do distribuidor é
`H9CCNNNCLTMLAR-NTD` (16 chars). Adicionar os dois.

### 9.3 Sufixos DDR3 vs DDR3L
- DDR3 temp commercial: `-PB**C**`, `-H9**C**`
- DDR3L temp commercial: `-PB**A**`, `-H9**A**`
Parece só uma letra — mas é a diferença entre 1.5V e 1.35V.

### 9.4 H5TQ x4 vs x8 — mesmo `dram_density`, chip diferente
`H5TQ2G43CFR` (x4) e `H5TQ2G63GFR` (x8) = ambos 256MB. Gramática os decode igual.
O banco os diferencia. x4 vai em RDIMM de servidor; x8 vai em DIMM desktop/laptop.

### 9.5 H5TC8G43AMR = DDP, 1GB total
Dois dies de 4Gb empilhados. Sufixo `MR` = multi-die package. Capacidade 1GB por pacote.
Não existem chips monolíticos H5TQ 8Gbit x4 (DDR3 1.5V).

### 9.6 H9HCNNN não tem 6GB
`H9HCNNNECMML` (6GB) está no banco com `confidence="manual"` e **flag de divergência**.
6GB (48Gbit) pertence à família H9HKNNN (376/556-ball, pacote maior).
Pendente confirmação física.

### 9.7 H9CC é de tablets/ultrabooks, não smartphones
A família H9CC FBGA-178 x32 aparece em Microsoft Surface, MacBook Air 2018,
Pine64, etc. Smartphones Android usam H9CK (PoP stacked) — família diferente.

### 9.8 H9DA não é standalone
H9DA tem sufixo `-4EM` = die LPDDR2 dentro de eMCP. Não é chip discreto.

### 9.9 Samsung K3RH / K3LG / K3PH / K4L não existem
Prefixos inexistentes confirmados por pesquisa exaustiva. Samsung LPDDR real:
`K3RG` (LPDDR4 multi-ch), `K3UH` (LPDDR4X multi-ch), `K4E` (LPDDR3 standalone),
`K4F` (LPDDR4 standalone). Ambos K3RG e K3UH já estão na gramática do WTC.

### 9.10 `subtype` nunca tem "standalone", "SDRAM", densidade ou barramento
Errado: `"LPDDR3 standalone"` / `"DDR3 SDRAM"` / `"LPDDR4X 4GB x32"`
Certo: `"LPDDR3"` / `"DDR3"` / `"LPDDR4X"`

---

## 10. O que ainda falta confirmar

| Família | Status | Ação sugerida |
|---|---|---|
| H9HCNNNECMML (6GB) | ⚠ Manual — suspeito | Checar chip físico na bancada; se for H9HKNNN, corrigir família |
| H9CC 1GB/2GB base | Manual (inferido) | Scan de chip físico para confirmar 12-char format |
| H9HCNNN 0.5GB/1GB (4K/8K) | Não no banco | Adicionar se aparecer na bancada |
| LPDDR5 SK Hynix | Não pesquisado | — |
| DDR2 x4 (HY5PS/H5PS x4) | Não pesquisado | — |
| H9CC 3GB (pn[7]='D') | Teoria confirmada, PN não catalogado | Buscar em Preduo/Octopart |
| H5AN DDR4 Era 2 | Apenas 1 PN (H5ANAG6NCJR) | Completar família 16GB/32GB se aparecer |

---

## 11. Pacotes físicos (identificação na bancada)

| Pacote | Ball count | Tamanho aprox. | Famílias |
|---|---|---|---|
| FBGA-78 | 78 balls | 8×9mm | H5TQ, H5TC, H5AN (DDR3/4/5) |
| FBGA-96 | 96 balls | 8×12mm | H5AN x16 (DDR4) |
| FBGA-153 | 153 balls | 11.5×13mm | H26M, H28U (eMMC/UFS) |
| FBGA-168 | 168 balls | 9×9mm | H9TK (LPDDR2) |
| FBGA-178 | 178 balls | 11×11.5mm | H9CC (LPDDR3) |
| FBGA-200 | 200 balls | 11×12mm | H9HCNNN (LPDDR4/4X) |
| BGA (var.) | — | — | H9TQ, H9HP (eMCP/uMCP) |

---

*Última atualização: 2026-06-19*
*Status do banco SK Hynix: ~115 PNs confirmados/manual em `add_confirmed_part.py`*
