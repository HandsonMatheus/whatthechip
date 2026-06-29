# Caracterização baseline — banco inteiro (insumo do plano da convenção)

> **Snapshot:** `prod_data.json` (26/06/2026) · **7021 KnownParts** · 14 marcas.
> **Gerado:** caracterização read-only de 2026-06-29. Roda o banco inteiro pelo
> pipeline real `classify()` → `_compute_destination` (etiqueta da caixa) →
> `assess_profitability` → `is_dead_by_generation`, e projeta a forma canônica
> da **opção 1** (geração no `chip_type`). **Não tocou em produção:** carga em
> SQLite descartável, sem populate/fix/migrate, efeitos de log desligados.
> É o **baseline "antes"** do refactoring — a rede de segurança para provar que
> a refatoração não muda nenhuma saída.

---

## 1. Conclusão de uma linha

A geração da DRAM **é recuperável**: de **4868** registros de DRAM discreta,
**4867 têm geração recuperável** (de `subtype`/gramática) e só **1**
não tem. Ou seja, a migração da opção 1 é **re-tipagem mecânica, não arqueologia de
dados**. A opção 1 muda o `chip_type` de **4465 registros (64%)**.

---

## 2. O mosaico hoje vs. a forma canônica (opção 1)

`chip_type` **atual** (genérico domina) → **proposto** (autodescritivo):

| `chip_type` ATUAL | n | | `chip_type` PROPOSTO | n |
|---|---|---|---|---|
| `RAM` | 2338 | | `LPDDR4X` | 1474 |
| `LPDDR` | 2003 | | `eMMC` | 1070 |
| `eMMC` | 1070 | | `LPDDR4` | 1065 |
| `eMCP` | 618 | | `LPDDR5` | 848 |
| `uMCP` | 252 | | `eMCP` | 618 |
| `UFS` | 119 | | `DDR4` | 312 |
| `DDR` | 118 | | `DDR3` | 299 |
| `LPDDR3` | 99 | | `LPDDR3` | 280 |
| `LPDDR4` | 69 | | `uMCP` | 252 |
| `LPDDR2` | 56 | | `DDR5` | 218 |
| `DDR4` | 55 | | `UFS` | 119 |
| `LPDDR4X` | 48 | | `LPDDR2` | 100 |
| `NOR Flash` | 27 | | `DDR3L` | 93 |
| `MCP` | 24 | | `DDR2` | 74 |

**Leitura:** hoje `RAM` (2338) + `LPDDR` (2003) + `DDR`
(118) ≈ 4459
registros genéricos escondem a geração no `subtype`. Na opção 1 cada um vira um token
de geração específico — exatamente o que sobrevive à linha salva do estoque e ao Excel.

Exemplos reais (raw → proposto → etiqueta da caixa → rentabilidade):

| PN | raw `chip_type` | proposto | etiqueta | rentab. |
|---|---|---|---|---|
| `K3KL8L80EMMGCU` | LPDDR5 | **LPDDR5X** | `LPDDR5X+4GB` | RENTÁVEL |
| `KA8G16` | DDR4 SDRAM | **DDR4** | `x16+64G` | RENTÁVEL |
| `K4D551638FTC40` | GDDR SDRAM | **SDRAM** | `GDDR SDRAM` | NÃO RENTÁVEL |
| `H54GE6CYRB` | RAM | **LPDDR4X** | `LPDDR4X+4GB` | RENTÁVEL |
| `K4B4G1646E` | RAM | **DDR3** | `DDR3+4G` | RENTÁVEL |
| `K4B4G1646D` | RAM | **DDR3L** | `DDR3L+4G` | RENTÁVEL |
| `K4B2G16` | DDR | **DDR3** | `DDR3+2G` | RENTÁVEL |
| `H9HCNNNECMML` | RAM | **LPDDR4X** | `LPDDR4X+6GB` | RENTÁVEL |

---

## 3. Raio de impacto por marca

| Marca | Registros | Muda `chip_type` | DRAM | sem specs | PN c/ sufixo (`:`/`.`) |
|---|---:|---:|---:|---:|---:|
| Micron | 5507 | 4054 | 4055 | 3598 | 3898 |
| Samsung | 1236 | 250 | 636 | 178 | 0 |
| SK Hynix | 182 | 104 | 115 | 9 | 0 |
| Nanya | 39 | 39 | 39 | 2 | 0 |
| Kingston | 13 | 7 | 7 | 7 | 0 |
| SanDisk | 11 | 0 | 0 | 3 | 0 |
| Toshiba | 10 | 1 | 1 | 4 | 0 |
| Rayson | 8 | 0 | 5 | 1 | 0 |
| GigaDevice | 7 | 7 | 7 | 0 | 0 |
| KIOXIA | 3 | 0 | 0 | 2 | 0 |
| PieceMakers | 3 | 3 | 3 | 0 | 0 |
| AMD (Xilinx) | 1 | 0 | 0 | 0 | 0 |
| Kioxia | 1 | 0 | 0 | 1 | 0 |

> **Micron é o centro de gravidade:** 5507 registros (78%),
> 4054 mudam de tipo. **Marcas fora da auditoria dos 9 populate_**:
> AMD (Xilinx) (1), KIOXIA (3), Kioxia (1), Nanya (39) — precisam entrar na convenção.

---

## 4. Achados sistêmicos do banco (além do dialeto)

### 4.1 Gap de normalização de PN — **3898 registros (56%)**
Part numbers armazenados com caracteres além de `[A-Z0-9- espaço]` — chars ofensores:
`:`×3450, `.`×448, `_`×1. O `classify()` tira TODO
não-alfanumérico do input, mas o fallback normalizado no banco só tira `-` e espaço
(não `:` nem `.`). Resultado: esses PNs **não dão round-trip** — ex.:
`MT42L256M32D2LG-18 WT:A`, `MT29GZ5A3BPGGA-046AAT.87K`. **1908 registros**
caem em tipo vazio / etiqueta `?` na bancada (quase todos Micron). O dado tem tipo;
é a **busca** que erra. A convenção precisa normalizar o PN no write-time (ou estender
o fallback).

### 4.2 Registros sem specs reais — **3805 (54%)**
Sem capacidade real no resultado (placeholder ou vazio). 3598
são Micron — bate com a nota do CLAUDE.md: `enrich_micron_fbga` cria o KnownPart sem
`emcp_ram`/`emcp_nand`/`capacity` até o `fill_capacity_from_micron_api` rodar. Há
**265** registros com placeholder explícito ("não mapeado / consultar
datasheet") no resultado.

### 4.3 `subtype` de memória gerenciada a limpar — **334**
eMCP/uMCP com `subtype` verboso (`"LPDDR3 + eMMC 5.1"`, `"LPDDR4X + UFS 2.1"`) que deve
virar geração pura (`"LPDDR3"`); eMMC/UFS que devem ficar `""`.

### 4.4 Confiança e tipos-lixo
Distribuição de `confidence`: `confirmed` 6245, `estimated` 605, `manual` 138, `ai_high` 21, `distributor` 12.
Ainda há **21 `ai_high`** + **12 `distributor`**
+ **605 `estimated`** (não-autoritativos). **18** registros com
`chip_type` lixo/anômalo (12 vazios, e `EDO DRAM`, `DDR4 SDRAM`, `GDDR SDRAM`,
`Appliance Part`, `SoC`, `DRAM` avulsos). **15** registros precisam de
canonicalização manual do tipo (a whitelist não resolve sozinha).

---

## 5. Rentabilidade (estado atual)

| Veredito | n | % |
|---|---:|---:|
| RENTÁVEL | 2200 | 31% |
| INDETERMINADO | 4081 | 58% |
| NÃO RENTÁVEL | 740 | 11% |

`is_dead_by_generation`=True em **655**. O INDETERMINADO alto correlaciona com os
3805 sem specs (§4.2) — não é erro da regra, é dado faltando.

---

## 6. O que isto significa para o plano

1. **Opção 1 é segura e mecânica:** 4867/4868 DRAM têm geração recuperável.
   A migração re-tipa ~4465 registros sem perda — o validador (`validate_convention`)
   confirma cobertura antes e depois.
2. **Micron primeiro:** 78% do banco; é onde a re-tipagem e o
   preenchimento de specs (§4.2) concentram o trabalho.
3. **A normalização de PN (§4.1) entra no escopo da convenção** — 3898 registros
   com `:`/`.` é grande demais para deixar de fora; afeta a busca do operador, não só o label.
4. **Limpeza paralela:** 21 `ai_high` + tipos-lixo (§4.4) saem na mesma
   migração reversível.
5. **Este baseline é a rede de segurança:** a planilha anexa (1 linha por PN) é o "antes"
   exato; após o refactor, re-rodar e exigir saída idêntica nos campos não afetados pela convenção.

---

## 7. Caveats da caracterização

- O `proposto chip_type` usa `canonical_gen` (mesma fonte do gateway). Casos de borda
  (`GDDR SDRAM`→`SDRAM`, `EDO DRAM`, `DRAM`) — 15 registros — são lixo que
  exige decisão manual; não invalidam a projeção dos outros 4450.
- Etiquetas/rentabilidade refletem o pipeline ATUAL (com seus bugs). O objetivo aqui é
  fotografar o "antes", não corrigir.
- Planilha `caracterizacao_baseline.xlsx`: 1 linha por PN, com filtro — ordene por
  `chip_type_changes`, `gen_recoverable`, `brand`, `has_cap` para auditar caso a caso.
