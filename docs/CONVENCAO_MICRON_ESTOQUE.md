# Padrão de campos do estoque — Micron

> **Para o chat responsável pela Micron.** Recorte da convenção geral
> (`docs/CONVENCAO_CAMPOS_ESTOQUE.md`) aplicado aos tipos de chip da Micron.
> **Adote em todos os registros e adicione este padrão à sua base de
> conhecimento (`.md`).** O objetivo é o rótulo da **caixa física** sair limpo na
> bancada do estoque, **sem perder nenhuma spec**.

---

## 1. O alvo: `JW464` está exemplar

Esse registro é o modelo a seguir — campos limpos, cada info no seu lugar:

```
chip_type = "NAND Flash"
subtype   = "SLC NAND"
capacity  = "512MB"
interface = "Parallel NAND (8-bit)"
tip       = "4 Gbit SLC NAND paralela (x8), Industrial Temp, raw (sem controlador), variante -5…"
```

→ caixa **`SLC NAND 512MB`** ✅

Mantenha **todos** os registros da Micron neste nível.

---

## 2. Como a caixa é montada por tipo (alimente os campos certos)

O estoque escolhe o formato pelo `chip_type` e concatena os campos abaixo. **Não
mexa no estoque; alimente os campos.**

| Tipo Micron | `chip_type` | Campos-chave | Caixa resultante |
|---|---|---|---|
| NAND raw | `NAND Flash` | `subtype` = célula (`SLC NAND` / `MLC NAND` / `TLC NAND`); `capacity` = bytes (`512MB`, `4GB`) | `SLC NAND 512MB` |
| eMMC | `eMMC` | `capacity` = total em **GB** (`16GB`) | `EMMC16GB` |
| eMCP | `eMCP` (+ `is_emcp=True`) | `emcp_nand` = `16GB`; `emcp_ram` = `1.5GB` | `EMCP16+1.5` |
| uMCP | `uMCP` (+ `is_emcp=True`) | `emcp_nand`, `emcp_ram` | `UMCP…+…` |
| UFS | `UFS` | `capacity` = **GB** | `UFS128GB` |
| DRAM | `RAM` | `subtype` = **só a geração** (`DDR3` / `LPDDR4`); `dram_density` = die em **Gb** (DDR); `capacity` = pacote em **GB** (LPDDR); `interface` = barramento | `DDR3+8G` / `LPDDR4+4G` |

---

## 3. Regras (não quebrar)

1. **`subtype` carrega só a identidade do tipo** — a **célula** (NAND: `SLC NAND`)
   ou a **geração** (DRAM: `DDR3`). Nada de densidade, bus width ou voltagem
   cravados nele.
2. **Todo o resto** (Gbit, temperatura, organização, `x8`, variante, ECC) vai no
   `tip` / `interface` — **mover, nunca apagar**. A spec continua completa; só
   muda de campo.
3. **Unidades — a alma do projeto:** densidade de die DRAM em **Gb** (gigabit);
   capacidade/pacote em **GB** (gigabyte). NAND raw usa a capacidade em bytes
   verbatim (`512MB`, `4GB`). 1GB = 8Gb — nunca troque.
4. **Não rebaixe `confirmed` / `manual`** (regra de ouro #6). Ao corrigir,
   preserve `confidence` e `status="enriched"`.

---

## 4. Específico Micron — FBGA (crítico)

- Seus chips são resolvidos por **FBGA code** (`JW464` → `MT29C4G48MAZAPAKD5IT`).
  Preencha os campos no `KnownPart` resolvido.
- **NÃO use o `part-name` da API Micron FBGA como fonte do tipo de RAM/densidade**
  (BUG-8). A API devolve strings como `"MLC EMMC/LPDDR2 72G VFBGA"` que misturam
  famílias relacionadas com RAM diferente. O **prefixo do PN** define o tipo;
  confirme em **datasheet oficial** ou **DigiKey** — nunca no `part-name` da API.

---

## 5. O que fazer

1. **Audite a base Micron:** cada registro no padrão do `JW464` (subtype limpo,
   specs no `tip`, unidades certas).
2. **Adicione este padrão à sua base de conhecimento (`.md`)**, para todo PN novo
   já nascer correto.
3. **Correções no banco:** proponha o comando com `--dry-run`; o **usuário** roda
   e reinicia o servidor (regra de ouro #1 e #3).
