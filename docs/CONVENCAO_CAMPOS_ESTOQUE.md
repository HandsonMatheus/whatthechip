# Convenção de campos para o estoque — preencher specs sem poluir o destino

> **Para os chats responsáveis por marcas (Samsung, SK Hynix, Micron, Kingston…).**
> Cole esta convenção no seu chat. Objetivo: padronizar como o `KnownPart` é
> preenchido para o rótulo da **caixa física** sair limpo na bancada do estoque —
> **sem perder nenhuma spec**. Depois, **adicione esta convenção ao seu `.md` de
> instruções** para que todo PN novo já nasça correto.

---

## 1. O problema

O estoque monta o rótulo da **caixa física** a partir dos campos do `KnownPart`.
Quando `subtype`/`interface` vêm com texto extra (densidade, barramento…), o
rótulo quebra. Exemplo real — Samsung `K4W4G1646Q`:

- Veio: `subtype = "gDDR3 4Gb x16"` → caixa exibida **`gDDR3 4Gb x16+4G`** ❌
- Deveria ser: **`GDDR3+4G`** ✅

O gateway do estoque está **correto** — ele apenas concatena os campos. **A
correção é nos dados.** Não mexam no estoque; alimentem os campos certos.

---

## 2. Como o rótulo é montado (não muda — só alimente certo)

O estoque escolhe o formato pelo `chip_type` e lê os campos abaixo:

| `chip_type` contém | Rótulo da caixa | Lê de |
|---|---|---|
| `uMCP` | `UMCP{nand}+{ram}` | `emcp_nand`, `emcp_ram` |
| `eMCP` (ou `is_emcp=True`) | `EMCP{nand}+{ram}` | `emcp_nand`, `emcp_ram` |
| `UFS` | `UFS{cap}GB` | `capacity` |
| `eMMC` | `EMMC{cap}GB` | `capacity` |
| `RAM` / `DDR` / `LPDDR` / `SDRAM` | **`{subtype}+{tamanho}G`** | `subtype` + densidade/capacidade |
| `NAND` | `NAND {cap}GB` | `capacity` |

Para **DRAM**, o `{tamanho}` depende da família:

- **LPDDR (móvel, pacote multi-die)** → capacidade do **pacote** em **GB** (lê de
  `capacity`): `4GB → 4G`.
- **DDR / GDDR (componente, 1 die)** → densidade do **die** em **Gb** (lê de
  `dram_density`; se vazio, deriva da `capacity`): `4Gb → 4G`, `256MB → 2G`.

> O `+` na caixa separa **geração** (esquerda) de **tamanho** (direita). Tudo à
> esquerda do `+` vem do `subtype`. Por isso o `subtype` tem que ser **só a
> geração**.

---

## 3. Regras de preenchimento do `KnownPart`

| Campo | O que vai | O que **NÃO** vai |
|---|---|---|
| `chip_type` | categoria: `RAM` (toda DRAM), `eMMC`, `UFS`, `eMCP`, `uMCP`, `NAND` | specs, densidade |
| `subtype` | **só a geração/variante, literal**: `DDR3`, `DDR3L`, `LPDDR3`, `LPDDR4`, `LPDDR4X`, `DDR4`, `GDDR3`, `GDDR5`… | densidade (`4Gb`), barramento (`x16`), voltagem, velocidade, `SDRAM` |
| `dram_density` | densidade do **die** em **Gb**: `4Gb`, `8Gb` (DDR/GDDR componente) | bytes; capacidade do pacote |
| `capacity` | capacidade total do **pacote** em bytes: `512MB`, `4GB` | gigabits |
| `interface` | barramento/elétrico: `x16`, `x32`, velocidade | a geração (não repita `DDR3` aqui) |
| `emcp_nand` / `emcp_ram` | (eMCP/uMCP) NAND e RAM em **GB**: `128GB`, `6GB` | — |
| `tip` | **todo o resto**: organização, voltagem, avisos, notas de densidade | — |

> O estoque remove `SDRAM` automaticamente quando há geração DDR (`"DDR3 SDRAM" →
> "DDR3"`), mas o ideal é o `subtype` já vir limpo.

---

## 4. Exemplos

**DRAM componente (DDR/GDDR) — `K4W4G1646Q` (4Gbit, x16):**
```
chip_type    = "RAM"
subtype      = "GDDR3"      # só a geração (ou "DDR3", conforme a spec real)
dram_density = "4Gb"        # densidade do die, em Gb
capacity     = "512MB"      # 4Gbit = 512MB
interface    = "x16"
tip          = "GDDR3 Samsung, x16, 1.5V, …"   # o resto vai aqui
```
→ caixa **`GDDR3+4G`** ✅

**DRAM móvel (LPDDR) — `H9CCNNNCLTML` (pacote de 4GB):**
```
chip_type    = "RAM"
subtype      = "LPDDR3"
capacity     = "4GB"        # capacidade do PACOTE (multi-die)
interface    = "x32"
```
→ caixa **`LPDDR3+4G`** ✅  (LPDDR usa a capacidade do pacote, não a densidade do die)

**eMCP:**
```
chip_type    = "eMCP"
is_emcp      = True
emcp_nand    = "16GB"
emcp_ram     = "1.5GB"
```
→ caixa **`EMCP16+1.5`** ✅

**eMMC:**
```
chip_type    = "eMMC"
capacity     = "16GB"
```
→ caixa **`EMMC16GB`** ✅

---

## 5. Regras críticas (não quebrar)

1. **Não perca specs.** Tudo que hoje está no `subtype`/`interface` e **não é a
   geração** deve **migrar** para `dram_density` / `interface` / `tip` — nunca
   apagar. A spec continua completa; só muda de campo.
2. **Unidades — a alma do projeto: die em `Gb` (gigabit), pacote em `GB`
   (gigabyte). Nunca troque.** 1GB = 8Gb. (Tratar a capacidade de um pacote LPDDR
   como densidade de 1 die gera `32G` no lugar de `4G`.)
3. **`subtype` = só a geração.** Sem densidade, sem `x16`, sem voltagem. É o que
   aparece antes do `+` na caixa.
4. **Não rebaixe `confirmed`/`manual`** (regra de ouro #6). Ao corrigir, preserve
   o `confidence` e `status="enriched"`.
5. Comandos que **escrevem no banco** são propostos por você, mas **rodados pelo
   usuário** (regra de ouro #1), idempotentes e com `--dry-run` antes. Depois de
   `populate_* --overwrite`, **reinicie o servidor** (regra #3).

---

## 6. O que fazer

1. **Corrija os registros da sua marca:** mova o excesso do `subtype`/`interface`
   para os campos certos; deixe `subtype` = só a geração; garanta `dram_density`
   (Gb) p/ DDR/GDDR e `capacity` (GB do pacote) p/ LPDDR.
2. **Adicione esta convenção ao seu `.md` de instruções.**
3. Proponha o comando de correção (com `--dry-run`); o **usuário** roda e reinicia
   o servidor.
