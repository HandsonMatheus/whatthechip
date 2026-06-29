# Convenção de campos do estoque — OPÇÃO 1 (a geração vai no `chip_type`)

> **Para os chats de marca (Samsung, SK Hynix, Micron, Kingston, Toshiba…).** Cole
> esta convenção no seu chat e **mantenha-a no seu `.md` de marca** — todo PN novo
> deve nascer já correto. **A FONTE ÚNICA de tipos é o código `chips/chip_types.py`;**
> esta página é a versão em prosa dele.
>
> ⚠ **Endurecida em 2026-06-29 — OPÇÃO 1.** A **geração** da DRAM discreta agora vai
> no **`chip_type`** (antes ficava `chip_type="RAM"`). Quem ainda tiver registros no
> dialeto antigo não precisa reescrever à mão: o engine resolve `"RAM"`+subtype em
> tempo de leitura, e o comando `normalize_convention` migra em massa (reversível).

---

## 0. A regra de ouro (decore isto)

| Grupo | `chip_type` | `subtype` |
|---|---|---|
| **DRAM discreta** — DDR · LPDDR · GDDR · SDRAM · RDRAM | **a GERAÇÃO**: `DDR3`, `DDR4`, `DDR3L`, `LPDDR4`, `LPDDR4X`, `GDDR5`, `SDRAM`… | **espelha** o `chip_type` (mesma geração) |
| **Gerenciada** — eMMC · UFS | `eMMC` / `UFS` | vazio |
| **Gerenciada multi-die** — eMCP · uMCP | `eMCP` / `uMCP` | **geração da LPDDR** (`LPDDR3`, `LPDDR4`…) |
| **NAND cru** — NAND · NOR | `NAND Flash` / `NOR Flash` | **célula**: `SLC NAND` / `MLC NAND` / `TLC NAND` |

❌ **NUNCA** `chip_type="RAM"`, nem `chip_type="DDR"` genérico, nem deixar a geração só no `subtype`.

**Por que a geração no `chip_type`, e não no `subtype`?** Porque o `chip_type` é o
**único** campo de tipo que o `InventoryEntry` (a entrada no estoque) **persiste**. Se a
geração ficasse só no `subtype`, a caixa física perderia a informação ao lançar o chip.
Por isso a geração vive no `chip_type` e o `subtype` apenas a espelha (o `subtype` ainda
aparece no card de busca, então mantenha-o limpo).

---

## 1. O problema que isto resolve

O estoque monta o rótulo da **caixa física** a partir dos campos do `KnownPart`. Quando
`subtype`/`interface` trazem texto extra (densidade, barramento…), o rótulo quebra.
Exemplo real — Samsung `K4W4G1646Q`:

- Veio: `subtype = "gDDR3 4Gb x16"` → caixa **`gDDR3 4Gb x16+4G`** ❌
- Deveria ser: **`GDDR3+4G`** ✅

O gateway está **correto** — ele só concatena os campos. **A correção é nos dados.** Não
mexa no gateway; alimente os campos certos.

---

## 2. Como o rótulo é montado (não muda — só alimente certo)

O gateway (`estoque/views.py::_compute_destination`) escolhe o formato via
`chip_types.py::label_kind(canonical_chip_type(chip_type, subtype))` e lê os campos:

| Tipo | Rótulo da caixa | Lê de |
|---|---|---|
| uMCP | `UMCP{nand}+{ram}` | `emcp_nand`, `emcp_ram` |
| eMCP | `EMCP{nand}+{ram}` | `emcp_nand`, `emcp_ram` |
| UFS | `UFS{cap}GB` | `capacity` |
| eMMC | `EMMC{cap}GB` | `capacity` |
| DDR / GDDR / SDRAM / RDRAM | `{geração}+{tamanho}G` | `chip_type` (+`subtype`) + `dram_density` |
| LPDDR avulso | `{geração}+{tamanho}G` | `chip_type` (+`subtype`) + `capacity` |
| NAND | `{célula} {cap}` | `subtype` + `capacity` |

Para **DRAM**, o `{tamanho}`:

- **LPDDR (móvel, pacote multi-die)** → capacidade do **pacote** em **GB** (lê `capacity`): `4GB → 4G`.
- **DDR / GDDR (componente, 1 die)** → densidade do **die** em **Gb** (lê `dram_density`/`density_gbit`; se vazio, deriva da `capacity`): `4Gb → 4G`.

---

## 3. Regras de preenchimento do `KnownPart`

| Campo | O que vai | O que **NÃO** vai |
|---|---|---|
| `chip_type` | **DRAM discreta: a GERAÇÃO** (`DDR3`, `DDR3L`, `DDR4`, `DDR5`, `LPDDR3`, `LPDDR4`, `LPDDR4X`, `GDDR5`, `SDRAM`, `RDRAM`…). Gerenciada: `eMMC`/`UFS`/`eMCP`/`uMCP`. NAND: `NAND Flash`/`NOR Flash`. | `"RAM"`, `"DDR"` genérico, densidade, specs |
| `subtype` | DRAM: **espelha o `chip_type`** (a mesma geração). eMCP/uMCP: a geração da **LPDDR**. NAND: a **célula** (`SLC/MLC/TLC NAND`). eMMC/UFS: vazio. | densidade (`4Gb`), barramento (`x16`), voltagem, `Mobile`, `SDRAM` colado |
| `dram_density` / `density_gbit` | densidade do **die** em **Gb**: `4Gb`, `8Gb` (DDR/GDDR) | bytes; capacidade do pacote |
| `capacity` | capacidade do **pacote** em bytes: `512MB`, `4GB` | gigabits |
| `interface` | barramento: `x8`, `x16`, `x32` | a geração (não repita `DDR3` aqui) |
| `emcp_nand` / `emcp_ram` | (eMCP/uMCP) em **GB**; `emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo **antes** da capacidade) | — |
| `tip` | **todo o resto**: organização, voltagem, temperatura, avisos | — |

> `density_gbit` é o campo do **modelo** `KnownPart` (densidade DDR em Gb); `dram_density`
> é o campo **calculado** pelo engine — não confunda. Escreva em `density_gbit`.

---

## 4. Exemplos (opção 1)

**DDR componente (PC) — `K4B4G1646E` (4Gbit, x16):**
```
chip_type    = "DDR3"       # a GERAÇÃO no chip_type
subtype      = "DDR3"       # espelha
density_gbit = "4Gb"        # densidade do die, em Gb
interface    = "x16"
```
→ caixa **`DDR3+4G`** ✅

**GDDR componente — `K4W4G1646Q` (4Gbit, x16):**
```
chip_type    = "GDDR3"
subtype      = "GDDR3"
density_gbit = "4Gb"
capacity     = "512MB"      # 4Gbit = 512MB
interface    = "x16"
tip          = "GDDR3 Samsung, 1.5V, …"
```
→ caixa **`GDDR3+4G`** ✅

**LPDDR avulso — `H9CCNNNCLTML` (pacote de 4GB):**
```
chip_type    = "LPDDR3"
subtype      = "LPDDR3"
capacity     = "4GB"        # capacidade do PACOTE (multi-die)
interface    = "x32"
```
→ caixa **`LPDDR3+4G`** ✅

**eMCP (a geração da RAM vai no `subtype`, não no `chip_type`):**
```
chip_type    = "eMCP"
is_emcp      = True
subtype      = "LPDDR3"     # geração da LPDDR
emcp_nand    = "16GB"
emcp_ram     = "LPDDR3 1.5GB"
```
→ caixa **`EMCP16+1.5`** ✅

**eMMC:**
```
chip_type = "eMMC"
capacity  = "16GB"
```
→ caixa **`EMMC16GB`** ✅

**NAND cru — `MT29F…`:**
```
chip_type = "NAND Flash"
subtype   = "SLC NAND"      # a célula
capacity  = "512MB"
```
→ caixa **`SLC NAND 512MB`** ✅

---

## 5. Regras críticas (não quebrar)

1. **`chip_type` = a geração** (DRAM discreta); `subtype` espelha. Gerenciada/NAND seguem a tabela §0.
2. **Unidades — a alma do projeto: die em `Gb` (gigabit), pacote em `GB` (gigabyte). Nunca troque.** 1GB = 8Gb.
3. **Não perca specs.** Tudo que não é a geração (densidade, `x16`, voltagem) migra para `density_gbit`/`interface`/`tip` — nunca apague.
4. **Tipos legados são sempre NÃO RENTÁVEL:** DDR1, DDR2, LPDDR2, SDRAM, RDRAM, EDO DRAM. (O engine já trata por geração; só preencha o `chip_type` certo.)
5. **Não rebaixe `confirmed`/`manual`** (regra de ouro #6). Para um chip vencer a gramática, use `confidence="confirmed"`/`"manual"`. Não inclua `status`/`ai_*` (removidos jun/2026).
6. **O usuário roda os comandos de banco** (regra de ouro #1): `--dry-run` antes; reinicie o servidor após `populate_* --overwrite`.

---

## 6. O que fazer

1. **Garanta que os PNs da sua marca seguem a §0:** `chip_type` = a geração; `subtype` espelha; specs nos campos certos.
2. **Mantenha esta convenção no seu `.md` de marca** (atualizado em 2026-06-29 para a opção 1).
3. **Valide:** `python manage.py validate_convention` (read-only) aponta o que foge da convenção; `normalize_convention` migra o legado (reversível). Proponha; o **usuário** roda.
