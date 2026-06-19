# BRIEFING — Agente SK Hynix / WhatTheChip

> **Para o próximo chat.** Leia este arquivo inteiro antes de qualquer coisa.
> Sua única função neste projeto é **popular corretamente o banco SK Hynix** no
> WhatTheChip usando `add_confirmed_part.py`. Tudo que você precisa está aqui.

---

## 1. Contexto do projeto

**WhatTheChip (WTC)** — aplicação Django (Python 3.11 / Django 5.2 LTS) que
classifica Part Numbers (PNs) de chips de memória para o mercado de reciclagem /
refurbishing de eletrônicos. Operado pela **eMiner (Paraguai)**.

O engine (`chips/engine.py`) tenta, em ordem:
1. **Banco exato** — `KnownPart` com `status="enriched"`. Só conta se
   `confidence="confirmed"` ou `"manual"`.
2. **Gramática** — decode posicional via `ChipFamily` + `DecodeMap` (resultado
   `"estimated"`).

**Meta:** todo PN que o operador escaneia na bancada deve sair como
`confidence="confirmed"` (fonte humana/datasheet), não `"estimated"`.

**Script de injeção:** `add_confirmed_part.py` na raiz do projeto.
Idempotente (`update_or_create`). Roda local → commit → push → Render shell.

---

## 2. Convenção de campos do KnownPart (CRÍTICO — leia com cuidado)

O estoque monta o rótulo da caixa física assim:

| chip_type | Rótulo | Lê de |
|---|---|---|
| RAM / DDR / LPDDR | **`{subtype}+{tamanho}G`** | `subtype` + densidade/capacidade |
| eMMC | `EMMC{cap}GB` | `capacity` |
| UFS | `UFS{cap}GB` | `capacity` |
| eMCP | `EMCP{nand}+{ram}` | `emcp_nand`, `emcp_ram` |

### Regras de preenchimento

| Campo | O que vai | O que NÃO vai |
|---|---|---|
| `chip_type` | `RAM`, `eMMC`, `UFS`, `eMCP`, `uMCP`, `NAND` | specs |
| `subtype` | **só a geração**: `DDR3`, `DDR3L`, `DDR4`, `DDR5`, `LPDDR2`, `LPDDR3`, `LPDDR4`, `LPDDR4X`, `GDDR3` | densidade, barramento, voltagem, `SDRAM` |
| `dram_density` | densidade do **die** em **Gb**: `4Gb`, `8Gb` (para DDR/GDDR) | bytes |
| `capacity` | capacidade total do **pacote** em bytes: `512MB`, `4GB` | gigabits |
| `interface` | barramento elétrico: `DDR3`, `DDR4`, `LPDDR3`, `x16`, `x32` | a geração (não repetir) |
| `tip` | todo o resto: organização, voltagem, avisos técnicos | — |

**Regra de ouro das unidades:**
- Die (componente DDR/GDDR) → `dram_density` em **Gb**: `4Gb`, `8Gb`
- Pacote (LPDDR multi-die) → `capacity` em **GB**: `1GB`, `4GB`
- Nunca troque: 1GB = 8Gb. Um erro aqui gera `32G` no rótulo em vez de `4G`.

**Exemplo correto (DDR3 x4 — componente):**
```python
chip_type    = "RAM"
subtype      = "DDR3"       # só a geração
dram_density = "2Gb"        # die em Gb
capacity     = "256MB"      # pacote em MB (2Gbit ÷ 8 = 256MB)
interface    = "DDR3"
```
→ rótulo: **`DDR3+2G`** ✅

**Exemplo correto (LPDDR3 — pacote multi-die):**
```python
chip_type    = "RAM"
subtype      = "LPDDR3"
capacity     = "4GB"        # pacote completo
interface    = "LPDDR3"
```
→ rótulo: **`LPDDR3+4G`** ✅

---

## 3. Como adicionar um PN

### 3.1 Estrutura de cada entrada em `add_confirmed_part.py`

```python
dict(
    part_number   = "H5TQ2G63GFR",       # PN exato (case-sensitive, sem espaço)
    brand_name    = "SK Hynix",
    family_prefix = "H5TQ",              # prefixo da ChipFamily no banco
    chip_type     = "RAM",
    subtype       = "DDR3",              # SÓ a geração
    capacity      = "256MB",             # pacote em bytes
    interface     = "DDR3",
    confidence    = "confirmed",         # "confirmed" se datasheet/Octopart/iFixit
    notes         = (                    # string longa OK, concatene com +
        "pn[4:6]='2G' → 256MB (2Gbit ÷ 8). x8, FBGA-78, 1.5V. G-gen. "
        "Velocidades: -RDC (1866) · -PBC (1600). "
        "Fonte: Alldatasheet H5TQ2G63GFR ✓."
    ),
),
```

### 3.2 Fluxo de deploy

```bash
# 1. Rodar localmente
python add_confirmed_part.py

# 2. Commitar e enviar
git add add_confirmed_part.py
git commit -m "feat(chips): descrição dos chips adicionados"
git push origin main

# 3. No shell do Render (após deploy finalizar)
python add_confirmed_part.py
```

Não é necessário reiniciar o servidor — `add_confirmed_part.py` não altera
gramática, só insere/atualiza `KnownPart`.

### 3.3 Onde buscar dados (fontes por confiança)

| Confiança | Fonte |
|---|---|
| `confirmed` | Datasheet oficial SK Hynix (Alldatasheet, SK Hynix site) |
| `confirmed` | LCSC com specs completas |
| `confirmed` | Octopart com organização/voltagem |
| `confirmed` | iFixit teardown (chip reading no texto) |
| `confirmed` | Preduo com foto do chip |
| `confirmed` | Datasheets360, Datasheets.com |
| `manual` | OMO Electric (broker catalog, sem datasheet) |
| `manual` | AliExpress/Alibaba com descrição detalhada |
| `manual` | Operador confirmou fisicamente na bancada |
| **NÃO usar** | Dados de IA (confundem Gb/GB, invertem campos) |
| **NÃO usar** | HardDiskDirect para capacidade (escreve "8GB" quando é 8Gb) |

---

## 4. Famílias SK Hynix — decode e status no banco

### 4.1 DDR3 1.5V — H5TQ (family_prefix = "H5TQ")

```
H5TQ [dens] [org] [3] [gen] FR [-speed C]
      pn[4:6]  pn[6]        pn[8]
```

- `pn[4:6]` → capacidade: `1G`=128MB · `2G`=256MB · `4G`=512MB · `8G`=1GB
- `pn[6]` → organização: `4`=x4 · `8`=x8 · `6`=x16
- `pn[7]` = `3` (banks, fixo DDR3)
- `pn[8]` → geração: A, B, C, D, E, G, M, T (nem todos existem em todos os density/org)
- Sufixo de velocidade: `-G7C`=1066 · `-H9C`=1333 · `-PBC`=1600 · `-RDC`=1866 · `-TEC`=2133

**No banco (confirmados):**
- x8 sufixados: H5TQ2G63GFR-RDC, H5TQ4G63EFR-RDC/TEC, H5TQ4G83EFR-RDC, H5TQ4G63AFR-PBC, H5TQ2G83BFR-H9C, H5TQ4G83MFR-H9C, H5TQ8G63AMR-H9C, H5TQ1G83EFR-PBC
- x8 base (sem sufixo): H5TQ1G83EFR, H5TQ2G63GFR, H5TQ2G63FFR, H5TQ2G63DFR, H5TQ2G83BFR, H5TQ2G83CFR, H5TQ4G63AFR, H5TQ4G63EFR, H5TQ4G63MFR, H5TQ4G83AFR, H5TQ4G83EFR, H5TQ4G83MFR, H5TQ8G63AMR
- x4 (base): H5TQ1G43AFP, H5TQ1G43BFR, H5TQ1G43TFR, H5TQ2G43AFR, H5TQ2G43BFR, H5TQ2G43CFR, H5TQ2G43EFR, H5TQ4G43AFR, H5TQ4G43MFR, H5TQ4G43AMR (DDP), H5TQ4G43MMR (DDP)

**⚠ H5TQ8G43 não existe** — SK Hynix não fabricou 8Gb x4 em DDR3 1.5V.

### 4.2 DDR3L 1.35V — H5TC (family_prefix = "H5TC")

Mesmo decode que H5TQ; sufixos terminam em `A` (não `C`) para temp DDR3L.
- `pn[4:6]` → mesmas densidades
- `pn[6]` → `4`=x4 · `8`=x8 · `6`=x16

**No banco (confirmados):**
- x8 sufixados: H5TC4G83CFR-PBA, H5TC4G63CFR-PBA/RDA, H5TC4G83BFR-PBA, H5TC8G83AMR-PBA
- x8 base: H5TC4G83CFR, H5TC4G63CFR, H5TC4G83BFR, H5TC8G83AMR
- x4: H5TC1G43BFR, H5TC1G43TFR, H5TC2G43AFR/BFR/CFR/EFR, H5TC4G43AFR/BFR/DFR/MFR, H5TC8G43AMR (DDP 1GB), H5TC8G43MMR (DDP 1GB)

**⚠ H5TC8G43AMR = DDP** (dois dies de 4Gb empilhados = 1GB total). Sufixo `MR` indica multi-die.

### 4.3 DDR4 1.2V — H5AN Era 1 (family_prefix = "H5AN")

```
H5AN [dens] [org] [N] [gen] FR/JR [-speed C]
      pn[4:6]  pn[6]
```

- `pn[4:6]` → HYX_DDR4_CAP: `4G`=512MB · `8G`=1GB · `AG`=2GB
- `pn[6]` → organização: `4`=x4 · `6`=x16 · `8`=x8
- `pn[7]` = `N` (fixo DDR4 Era 1)
- `pn[8]` → die: `A`=A-die · `B`=B-die · `C`=C-die · `D`=D-die
- Sufixo: `-UHC`=2400 · `-VKC`=2666 · `-WMC`=2933 · `-XNC`=3200

**No banco (confirmados):**
- x8 sufixados: H5AN8G8NAFR-VKC/UHC, H5AN8G6NAFR-UHC, H5AN4G8NBJR-VKC, H5AN8G8NCJR-VKC, H5AN8G8NDJR-VKC, H5ANAG6NCJR-VKC
- x8 base: H5AN8G8NAFR, H5AN8G6NAFR, H5AN4G8NBJR, H5AN8G8NCJR
- **x4 (família servidor):** H5AN4G4NAFR (512MB A-die), H5AN4G4NBJR (512MB B-die), H5AN8G4NAFR (1GB A-die), H5AN8G4NCJR (1GB C-die)

### 4.4 DDR4 1.2V — H5AN Era 2 (family_prefix = "H5AN" — mesmo banco)

```
H5AN [gen_dens] N [rest]
      pn[3:5]
```

- `pn[3:5]` → HYX_DDR4_H5A_CAP: `G3`=1GB · `G4`=2GB · `G5`=4GB · `G6`=8GB
- ⚠ Decode diferente! Era 1 usa pn[4:6]; Era 2 usa pn[3:5].

**No banco:** H5ANAG6NCJR-VKC (2GB, Era 2)

### 4.5 DDR5 — H5CG / H5C (family_prefix = "H5CG" ou "H5C")

- `pn[3:5]` → HYX_DDR5_CAP: `G4`=2GB · `GD`=3GB · `G5`=4GB
- **No banco:** H5CG48MEBDX014N (2GB DDR5 confirmado por operador)

### 4.6 DDR2 1.8V — HY5PS (family_prefix = "HY5PS")

- `pn[5:7]` → HYX_DDR2_PS_CAP: `56`=32MB · `12`=64MB (últimas 2 chars do valor Mbit)
- Sufixo: `-25`=PC2-3200 · `-S5`=PC2-4200 · `-Y5`=PC2-5300
- **No banco:** HY5PS121621CFP-25, HY5PS1G831CFP-Y5/S5

### 4.7 DDR2 — H5PS (family_prefix = "H5PS")

- `pn[4:6]` → HYX_DDR2_H5PS_CAP: `25`=32MB · `51`=64MB · `1G`=128MB · `2G`=256MB
- **No banco:** H5PS1G83EFR-S6C, H5PS1G63EFR-S6C, H5PS5182KFR-S5C

### 4.8 DDR1 — HY5DU (family_prefix = "HY5DU")

- `pn[5:7]` → usa últimas 2 chars do valor Mbit: `64`=8MB · `28`=16MB · `56`=32MB · `12`=64MB
- **No banco:** HY5DU281622ET-25, HY5DU561622CTP-28, HY5DU121622CTP-J

### 4.9 LPDDR2 standalone — H9TK (family_prefix = "H9TK", FBGA-168)

- `pn[7]` → capacidade: `1`=128MB · `2`=256MB · `4`=512MB · `8`=1GB
- `pn[8]` → geração/nó: G=1ª gen · J=2ª gen (26nm) · K=3ª gen
- **No banco:** H9TKNNN8JDAP, H9TKNNN8JDAPLR-NGH (iFixit ✓), H9TKNNN8JDMPLR-NDM, H9TKNNN4GDMPLR-NDM, H9TKNNN4GDAP (manual), H9TKNNN2GDAP (manual)
- **H9DA** = die LPDDR2 dentro de eMCP (sufixo -4EM) — NÃO standalone

### 4.10 LPDDR3 standalone — H9CC (family_prefix = "H9CC", FBGA-178)

- `pn[7]` → HYX_LPDDR3_H9CC_CAP: `8`=1GB · `B`=2GB · `D`=3GB · `C`=4GB
- `pn[4:7]` = `NNN` (preenchimento fixo padrão)
- Usado em **tablets Windows / ultrabooks** (Surface, MacBook Air) — não em Android!
- Física: chip mostra PN de 12 chars sem sufixo AR-Nxx (ex: H9CCNNNCLTML)
- **⚠ Teto confirmado: C=4GB. LPDDR3 não vai a 6GB ou 8GB.**

**No banco:**
- 1GB: H9CCNNN8JTALAR-NTM (confirmed), H9CCNNN8JTML (manual base)
- 2GB: H9CCNNNBLTMLAR-NTM, H9CCNNNBLTML (manual), H9CCNNNBJTALAR-NVD, H9CCNNNBJTML (manual)
- 4GB: H9CCNNNCLTML (confirmado bancada eMiner), H9CCNNNCLTMLAR-NTD, H9CCNNNCLTMLAR-NUD

### 4.11 LPDDR4X standalone — H9HCNNN (family_prefix = "H9HCN", FBGA-200)

- `pn[7]` → capacidade: `4`=0.5GB · `8`=1GB · `B`=2GB · `C`=4GB · `F`=8GB
- `pn[8:10]` = código density+protocol: `KM`=LPDDR4X (VDDQ 0.6V) · `KU/BK/PU`=LPDDR4 (VDDQ 1.1V)
- Sufixo: `MMLXR`=4266Mbps (LPDDR4X alta vel.) · `MMLHR`=3733Mbps
- **⚠ H9HCNNNECMML (6GB) está no banco com `confidence="manual"` e flag de divergência.**
  6GB (48Gbit) NÃO existe na família H9HCNNN 200-ball — pertence ao H9HKNNN (376/556-ball).
  Aguarda confirmação física.

**No banco LPDDR4X:**
- H9HCNNNCPMMLXR-NEE (4GB, LCSC C19192462 ✓)
- H9HCNNNCPMMLHR-NME (4GB, iFixit Amazon Astro ✓)
- H9HCNNNBKMMLXR-NEE (2GB, iFixit DJI Mavic 3 Pro ✓)
- H9HCNNNBKMMLHR-NME (2GB, iFixit Amazon Astro ✓)
- H9HCNNNFAMMLXR-NEE (8GB, Glochip ✓)
- H9HCNNNCPMML (4GB, base — operador confirmou)

**No banco LPDDR4:**
- H9HCNNN8KUMLHR-NME (1GB), H9HCNNNBPUMLHR-NME (2GB), H9HCNNNBKUMLHR-NME (2GB), H9HCNNNCPUMLHR-NME (4GB)

### 4.12 eMCP — H9TQ (family_prefix = "H9TQ")

- `pn[4:6]` → NAND (HYX_EMCP_NAND_CAP)
- `pn[6:8]` → RAM (HYX_H9TQ_RAM_CAP): `A6`=768MB · `08`=1GB etc.
- **No banco:** H9TQ32A6BTMC (4GB+768MB), H9TQ17ABJTCC (16GB+2GB)

### 4.13 eMCP — H9DP (family_prefix = "H9DP")

- **No banco:** H9DP32A4JJBC (4GB+512MB LPDDR2)

### 4.14 eMCP / uMCP — H9HP (family_prefix = "H9HP")

- **No banco:** H9HP16AECMMD (128GB+6GB uMCP)

### 4.15 eMMC — H26M (family_prefix = "H26M")

- `pn[4]` → HYX_EMMC_CAP: `3`=4GB · `4`=8GB · `6`=16GB · `7`=32/64GB
- **No banco:** H26M31001HPR (4GB), H26M64103EMR (32GB), H26M74002HMR (64GB), H26M78103CCR (64GB)

### 4.16 eMMC — H26T (family_prefix = "H26T")

- **No banco:** H26T87001CMR (128GB)

### 4.17 UFS — H28U (family_prefix = "H28U")

- `pn[4]` → HYX_UFS_CAP: `6`=32GB
- **No banco:** H28U64222MMR (32GB), H28U88301AMR (128GB)

### 4.18 UFS — HN8T (family_prefix = "HN8T")

- **No banco:** HN8T05BZGR (128GB)

### 4.19 LPDDR4X — H54G (family_prefix = "H54G")

- Família atípica (nomenclatura legado)
- **No banco:** H54GE6CYRB (4GB)

### 4.20 LPDDR4X — K3UH (family_prefix = "K3UH")

- Samsung LPDDR4X multi-channel (PoP). `pn[3]` → densidade
- **No banco:** K3UH6M6 (4GB) — atenção: este é Samsung, não SK Hynix

---

## 5. Pegadinhas e armadilhas conhecidas

### 5.1 Sufixo de velocidade vs. PN base
Chips físicos em placas de PC/servidor frequentemente mostram **apenas o PN base**
(sem o sufixo `-RDC`, `-PBC` etc.). Ambos precisam estar no banco:
- Sufixado: H5TQ2G63GFR-RDC (para match exato se alguém copiar da etiqueta)
- Base: H5TQ2G63GFR (para match do chip físico)

### 5.2 H5TQ x4 vs x8 — capacidade igual, chip diferente
H5TQ2G43CFR (x4) e H5TQ2G63GFR (x8) têm a mesma capacidade (256MB) mas são
chips distintos. A gramática os decode igual; o banco os diferencia.

### 5.3 DDR3L sufixos terminam em 'A', DDR3 em 'C'
- H5TQ2G43CFR-**PBC** (DDR3 1.5V, temp. commercial `C`)
- H5TC2G43CFR-**PBA** (DDR3L 1.35V, temp. commercial `A`)

### 5.4 H5TC8G43 é DDP — não confunda com 8Gbit monolítico
H5TC8G43AMR tem 1GB mas é dois dies de 4Gb empilhados. O PN `8G` = 8Gbit total.
Sufixo `MR` (M = multi-die) identifica DDP. Tratar como 1GB por pacote.

### 5.5 H9HCNNNECMML (6GB) — suspeito
Está no banco com `confidence="manual"`. 6GB não existe em H9HCNNN 200-ball
(Glochip/SK Hynix 2021). Se o chip físico realmente mostrar este PN, é possível
que seja H9HKNNN (376/556-ball, maior). Verificar datasheet antes de confirmar.

### 5.6 H9CC é para tablets/ultrabooks, não smartphones Android
A família H9CC (FBGA-178, x32) aparece em Microsoft Surface, MacBook Air, etc.
Smartphones Android usam H9CK (PoP) ou Samsung/Elpida. O operador pode achar
H9CC em placas de laptop desmontado — isso é normal.

### 5.7 H9DA = eMCP, não standalone
H9DA tem sufixo `-4EM` = die LPDDR2 dentro de eMCP. Não é chip standalone.

### 5.8 Unidades em datasheets SK Hynix
- SK Hynix sempre usa `Gb` para densidade do die e `MB`/`GB` para capacidade total.
- HardDiskDirect escreve "(8GB)" quando é 8Gbit. Ignore a unidade deles; verifique
  pela organização (ex: 256Mx32 = 8Gbit = 1GB por chip → 1GB correto).

### 5.9 `subtype` não pode ter "standalone"
Já removido de todos os LPDDR chips. Conferir se novos chips não reincidem.
Errado: `"LPDDR3 standalone"`. Certo: `"LPDDR3"`.

### 5.10 Geração Samsung K3RH / K3LG / K3PH / K4L não existem
Pesquisa exaustiva confirmou que estes prefixos não são reais. Samsung LPDDR usa:
K3RG (LPDDR4), K3UH (LPDDR4X), K4E (LPDDR3 standalone), K4F (LPDDR4 standalone).
Ambos K3RG e K3UH já estão implementados na gramática do WTC.

---

## 6. O que ainda falta / próximas tarefas

1. **Confirmar H9HCNNNECMML**: verificar se realmente existe ou é confusão de
   família (H9HKNNN). O chip físico está na bancada do operador.

2. **Mais PNs H9CC x4 1GB e 2GB base** (H9CCNNN8JTML, H9CCNNNBLTML) — já
   adicionados como `manual`, aguardam scan de chip físico para `confirmed`.

3. **H9HCNNN 0.5GB e 1GB** — existem no catálogo Glochip (H9HCNNN4KMMLHR,
   H9HCNNN8KUMLHR) mas menos frequentes na bancada.

4. **DDR2 x4 SK Hynix** — não pesquisado ainda (HY5PS x4, H5PS x4).

5. **LPDDR5 SK Hynix** — família nova, não pesquisada.

6. **Samsung K3UH variants** — K3UH5H50MM, K3UH6H60AM já na gramática; verificar
   outros comuns.

---

## 7. Template rápido para novo PN

```python
# Cole no final de add_confirmed_part.py, antes de "# Adicione mais chips aqui"
dict(
    part_number   = "XXXXXXXX",          # PN exato
    brand_name    = "SK Hynix",
    family_prefix = "XXXX",             # prefixo da família (4-5 chars)
    chip_type     = "RAM",              # ou "eMMC", "UFS", "eMCP"
    subtype       = "DDRX",            # SÓ a geração, sem "SDRAM"
    # dram_density = "XGb",            # para DDR/GDDR: die em Gb
    capacity      = "XXXMB",           # pacote em bytes
    interface     = "DDRX",
    confidence    = "confirmed",        # ou "manual" se broker apenas
    notes         = (
        "pn[4:6]='XG' → XXXMB (XGbit ÷ 8). xY, FBGA-78, X.Xv. X-gen. "
        "Fonte: [fonte] ✓."
    ),
),
```

---

## 8. Fontes de pesquisa mais eficientes

| Quando buscar | Onde ir |
|---|---|
| PN específico com datasheet | `alldatasheet.com/view.jsp?Searchword=H5TQ2G43AFR` |
| Múltiplos PNs de uma família | `alldatasheet.com/view.jsp?Searchword=H5TQ2G43` |
| Preço/estoque atual | `octopart.com/search?q=H5TQ2G43CFR` |
| Família completa com foto | `preduo.com` (busca por prefixo) |
| Chip em produto real | `ifixit.com` + nome do produto |
| EOL checker SK Hynix | `skhynix.com/eolproducts.view.do` |
| Broker China com specs | `lcsc.com/search?q=H9HCNNNCPMMLXR` |
| Histórico de PN | `datasheets360.com` ou `datasheets.com` |

---

## 9. Regras de ouro do projeto (não quebrar)

1. O banco de produção não é acessível ao agente — Claude **propõe**, usuário **roda**.
2. Só `KnownPart` com `status="enriched"` conta no engine.
3. Depois de `populate_* --overwrite`, reiniciar o servidor (lru_cache).
4. Nunca rebaixe `confidence="confirmed"` ou `"manual"` sem motivo explícito.
5. `subtype` = só a geração. Sem densidade, sem barramento, sem voltagem.
6. Nunca confie em dado de distribuidor ou IA sem verificar datasheet/Octopart.
7. Unidades: die em **Gb**, pacote em **GB**. Nunca troque.

---

*Documento gerado em 2026-06-19 pela sessão de enriquecimento SK Hynix (eMiner).*
*Última atualização: adição de 27 chips x4 DDR3/DDR3L/DDR4 + 22 chips LPDDR mobile.*
