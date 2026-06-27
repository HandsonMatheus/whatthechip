# Pesquisa SanDisk iNAND Tier 1 — Resultados (2026-06-26)

> Execução do prompt `docs/OPUS4_SANDISK_RESEARCH_PROMPT.md`.
> Saída de dados: **`docs/sandisk_inand_pesquisa_2026-06-26.csv`** (73 PNs, header + linhas).
> Pesquisa feita por 6 sub-agentes em paralelo sobre fontes Tier 1 (westerndigital.com,
> sandisk.com, product briefs, Mouser, DigiKey, Avnet, Octopart). Para import em
> `chips/management/commands/fix_known_parts.py`.
>
> **Regra de ouro respeitada:** nada foi escrito no banco. Claude edita; o usuário roda.

---

## 0. ⚠️ ACHADO CRÍTICO — `SDINB...` é eMMC, NÃO UFS

A maior descoberta da pesquisa **contradiz a gramática atual do WTC**.

O `populate_sandisk.py` e o `SANDISK.md` (§3.4, §8.7) classificam o prefixo **`SDINB`
como UFS** (`priority=40`). Os **product briefs oficiais da SanDisk/WD** mostram que as
três famílias `SDINB*` pedidas no prompt são, na verdade, **eMMC 5.1**:

| Prefixo | Linha de produto | Tipo real (fonte oficial) | Doc |
|---|---|---|---|
| `SDINBDG4` | iNAND **7250** | **eMMC 5.1** HS400, X2 MLC | PB02-iNAND-7250 |
| `SDINBDD4` | iNAND **7350** | **eMMC 5.1** 3D NAND | PB01-iNAND-7350 |
| `SDINBDA4` | iNAND **7550** | **eMMC 5.1** Gen4 SmartSLC | PB04-iNAND-7550 |

Confirmação **dupla e independente** para o SDINBDD4 (dois sub-agentes acharam o mesmo
product brief PB01-iNAND-7350). A regra mnemônica que emergiu:

> **`SDINB...` → eMMC (linha iNAND 72xx/73xx/75xx).**
> **UFS de verdade usa outros prefixos:** `SDINDDH4` (UFS 2.1), `SDINEDK4` (UFS 3.0),
> `SDINFDK4`/`SDINFDO4` (UFS 3.1), `SDINFDQ6` (UFS 3.1 automotivo).

**Impacto operacional:** com a regra atual, todo chip `SDINBDG4/BDD4/BDA4` (comuns —
Galaxy M20, Huawei Nova 2s, Honor 8X) é roteado para a **bancada UFS**, quando deveria ir
para a **bancada eMMC**. eMMC e UFS são eletricamente incompatíveis no socket → bin errado.

**Recomendação (NÃO aplicada — requer sua decisão):** rebaixar a prioridade do match
`SDINB`=UFS e/ou criar famílias explícitas `SDINBDG4`/`SDINBDD4`/`SDINBDA4` como eMMC,
**ou** confirmar cada PN como `KnownPart confirmed` (o que já o resolve no engine, camada 1,
sem mexer na gramática). As 12 linhas `SDINB*` do CSV já vêm com `chip_type=eMMC` e o aviso
`[!] NOT UFS` no campo `notes`. **Antes de alterar a gramática, valide os 3 product briefs.**

---

## 1. Resumo executivo

- **73 PNs novos** (nenhum entre os 28 já no banco; verificação programática — 0 colisões, 0 duplicatas).
- **Tipos:** 48 eMMC · 19 UFS · 6 eMCP.
- **Confiança:** 50 `confirmed` (Tier 1) · 11 `distributor` (Tier 2) · 12 `skip` (só Tier 3).
- PN normalizado **computado** a partir do `pn_raw` (`re.sub(r"[^A-Z0-9]","",upper)`) — sem
  normalização digitada à mão. Semântica de campos validada por script
  (eMCP: `capacity` vazio + `emcp_nand`/`emcp_ram` preenchidos + `interface` vazio;
  eMMC/UFS: `subtype`/`emcp_*` vazios). Acoplamento `confidence`↔`source_tier` checado.

---

## 2. Log de pesquisa por família

### Prioridade 1 — alto volume

| Família | Status | Resultado |
|---|---|---|
| **SDIN7DP2** | FOUND 2 | `-4G`, `-8G` confirmados (Mouser Tier 1 + Octopart; BGA153; doc# 80-36-03494, "iNAND Extreme e.MMC **4.5**"). Família **para em 8GB** — `-16G`/`-32G` não existem. **Não** é eMCP (BGA153). |
| **SDIN7DP4** | FOUND 2 + 1 lead | `-16G`, `-32G` confirmados (Mouser Tier 1 + datasheet doc# 80-36-03494). `-64G` só Jotrin (Tier 3 → `skip`). `-4G`/`-8G` não existem (DP4 é alta densidade). ⚠ Conflito de package: descrições dizem BGA153, campo estruturado do Octopart diz TFBGA-169 — verificar no datasheet completo. |
| **SDIN7DU2** | FOUND 2 | `-16G`, `-32G` confirmados (Mouser Tier 1; doc# 80-36-03666 iNAND Ultra eMMC 4.41). `-4G` não encontrado. **SDIN7DU4 não existe.** Package por SKU não confirmado (BGA153 vs 12×16/BGA169). |

### Prioridade 1 — continuação

| Família | Status | Resultado |
|---|---|---|
| **SDIN8DE1** | FOUND 3 | Família **8GB-only**. `-8G` (base) e `-8G-I` (industrial) confirmados Tier 1 (product brief + Mouser); `-8G-A` (automotivo) Tier 3 → `skip`. eMMC 4.51 HS200, BGA153. |
| **SDIN8DE4** | FOUND 2 + 1 skip | `-32G`, `-64G` confirmados Tier 1 (product brief; **BGA153 standalone eMMC**). `-16G` existe mas só Tier 3 → `skip`. ⚠ **Hipótese do prompt (12×16mm/RAM/eMCP) REFUTADA** — é eMMC BGA153, sem RAM. O part 12×16mm é o SDIN8C**E**4-128G (prefixo diferente). |
| **SDIN9DS2** | FOUND 4 | `-8G`/`-16G`/`-32G`/`-64G` todos confirmados Tier 1 (product brief; eMMC 5.0 HS400, BGA153). Sem `-4G`. HTC Desire 630 (o `-16G`). |
| **SDIN9DW4** | FOUND 1 | Só `-64G` é novo (16G/32G já no banco). Datasheet oficial **80-36-03680** enumera a família como **16/32/64GB apenas** — **`-4G`/`-8G` NUNCA existiram.** |

### Prioridade 2 — legado

| Família | Status | Resultado |
|---|---|---|
| **SDIN5D2** | FOUND 3 | `-4G`/`-8G`/`-16G` (X2 MLC, eMMC 4.41, BGA153) na ordering table do datasheet WD doc# 80-36-03462. |
| **SDIN5D1** | FOUND 3 (+1) | `-4G`/`-8G`/`-16G` (X3 MLC) + `-2G` (este é **X2**, exceção) — doc# 80-36-03462 V1.4 Dez/2011. |
| **SDIN5C1** | FOUND 5 | `-4G`/`-8G`/`-16G`/`-32G`/`-64G` (X3 MLC, eMMC 4.41, BGA169 12×16mm) — docs# 80-36-03433 + 80-36-03462; Elnec corrobora FBGA169. |
| **SDIN4C2** | TIER 3 ONLY | `-2G`/`-4G`/`-8G`/`-16G` → todos `skip`. eMMC FBGA169 confirmado (TI E2E + Elnec) **mas versão eMMC (4.3/4.4) não consta em nenhuma fonte** — não inferir. **SDIN4C4 não encontrado.** |

### Prioridade 3 — UFS (ver §0 para o achado dos eMMC)

| Família | Status | Resultado |
|---|---|---|
| **SDINBDG4 / BDD4 / BDA4** | FOUND 12 — porém **eMMC** | Ver §0. iNAND 7250/7350/7550, **eMMC 5.1**, product briefs oficiais. |
| **SDINDDH4** | FOUND 4 | UFS **2.1** real (iNAND 8521 / MC EU311), Gear3 2-lane, TFBGA-153 — product brief PB03-iNAND-8521. + `SDINDDH6-64G-I` (industrial, iNAND IX EU312, Tier 2). |
| **SDINEDK4** | FOUND 2 (+1) | UFS **3.0** (iNAND MC EU511); `-128G`/`-256G` confirmados; `-512G` via faixa de família → `distributor`. |
| **SDINFDK4 / FDO4** | FOUND 6 | UFS **3.1** (iNAND MC EU551); **resolve a pergunta aberta do prompt sobre `SDINFDK`** — é UFS 3.1, real. + automotivo `SDINFDQ6` (iNAND AT EU552, UFS 3.1). |
| **iNAND 8350 / 9350** | NOT FOUND | Nomes **não existem** no catálogo SanDisk. Confusão com a série eMMC iNAND 73xx e/ou UFS EU5xx. |
| **SDMAG** | NOT FOUND | **Não é peça de flash SanDisk** (Octopart só retorna itens não relacionados). |

### Prioridade 4 — eMCP SDAD

| Família | Status | Resultado |
|---|---|---|
| **SDADB48K** | NOT FOUND (faltantes) | Só existe `-16G` (já no banco). **`-8G`/`-32G` não existem** — família é 16GB-only. Nenhuma linha nova. |
| **SDADEP / SDADE** | NOT FOUND | **Família não existe** na SanDisk. A "geração LPDDR4 pós-SDADB" é a **SDADA4** (abaixo). |
| **SDADF4AP / SDADF** | FOUND 1 | `SDADF4AP-16G` = 16GB NAND + LPDDR3 2GB (221-ball), Huawei DRA-LX2 — `distributor` (RAM via regra de ball count, não datasheet Tier 1). |
| **SDADL2BP / SDADL** | PARTIAL (Tier 3 p/ RAM) | `SDADL2AP-16G` (16+2) e `SDADL2BP-32G` (32+3, Huawei FIG-LA1). NAND sólido; **RAM só Tier 3** → `skip`. Se rebaixar, tratar como eMMC. |
| **Outros SDAD\*** | FOUND (SDADA4) | `SDADA4CR-64G`, `SDADA4DR-64G` (64+4, 254-ball, LCSC/JLCPCB Tier 2 → `distributor`); `SDADA4CR-128G` (128+4, Tier 3 → `skip`). ⚠ **LPDDR4 vs LPDDR4X não resolvido** em toda a linha SDADA4. |

### Prioridade 5 — SD7-prefix / iNAND

| Família | Status | Resultado |
|---|---|---|
| **SD7DP26A** | TIER 3 ONLY | `-4G` → `skip`. Die-code de laser; Octopart retorna zero; tipo/versão não verificáveis. Já estava em SANDISK.md "aguardando confirmação". |
| **SD7DP41E** | TIER 3 ONLY | `-16G` → `skip`. Idem — só bundles de reparo Tier 3. |
| **iNAND 7232** | 0 novos | = família `SDINADF4`, **toda já no banco** (16/32/64/128G + variantes -H). Nenhum SKU novo. |
| **iNAND 7350** | (= SDINBDD4) | Coberto na Prioridade 3 — eMMC 5.1 (ver §0). |
| **iNAND MC EU511** | (= SDINEDK4) | UFS 3.0 — coberto na Prioridade 3. |
| **iNAND Ultra LS** | NOT FOUND | Linha **não existe**. "iNAND Ultra" = SDIN7DP2 (4.5) / SDIN7DU2 (4.41). |

---

## 3. Achados negativos — NÃO perseguir (economiza tempo)

Confirmado por fonte oficial que estes **não existem**; não criar registros especulativos:

- `SDIN7DP2-16G`, `SDIN7DP2-32G` — DP2 para em 8GB.
- `SDIN7DP4-4G`, `SDIN7DP4-8G` — DP4 começa em 16GB.
- `SDIN7DU2-4G` (não achado) e **`SDIN7DU4`** (não existe).
- `SDIN8DE1-4G`, `SDIN8DE1-16G` — DE1 é 8GB-only.
- `SDIN9DW4-4G`, `SDIN9DW4-8G` — datasheet 80-36-03680: família é 16/32/64GB.
- `SDADB48K-8G`, `SDADB48K-32G` — SDADB48K é 16GB-only.
- `SDADE` / `SDADEP` — família inexistente (a real é `SDADA4`).
- `SDIN4C4` — sem qualquer vestígio.
- **iNAND 8350 / 9350**, **iNAND Ultra LS**, **SDMAG** — nomes inexistentes no catálogo SanDisk.

---

## 4. Investigação manual pendente

1. **`SDINB*` = eMMC (§0)** — **prioridade máxima.** Validar os 3 product briefs
   (PB01-7350, PB02-7250, PB04-7550) e decidir como corrigir a gramática `SDINB=UFS`.
2. **SDIN7DP4 — ball count (BGA153 vs TFBGA-169):** descrições de distribuidor dizem 153;
   campo estruturado do Octopart diz 169. Abrir o datasheet completo (36 págs, doc# 80-36-03494).
3. **SDIN7DU2 — package por SKU:** Mouser omite package/versão; BGA153 (agente) vs 12×16/BGA169
   (notas WTC). Confirmar no datasheet doc# 80-36-03666.
4. **SDIN7DP4-64G** — só Jotrin; achar página Tier 1/2 com tabela de specs (Avnet/Arrow direto).
5. **SDIN8DE4-16G** — existe no mercado; falta página Tier 1/2 do SKU 16G. Ignorar o claim
   isolado de revendedor "eMMC 5.1 160/100" (contradiz o brief oficial 4.51/125-49).
6. **SDADA4 — LPDDR4 vs LPDDR4X:** confirmar em datasheet/DigiKey. Muda só o token de tipo
   (`subtype`/`emcp_ram`), não a capacidade.
7. **SDADL2AP-16G / SDADL2BP-32G — RAM:** NAND sólido (distribuidor), RAM só Tier 3.
   Se não confirmar a RAM em Tier 1/2, **importar como eMMC** (só NAND) em vez de chutar RAM.
8. **SD7DP26A-4G / SD7DP41E-16G** — die-codes de laser; ler a marcação física completa do chip
   e cruzar com tabela SanDisk antes de classificar como algo além de `skip`.
9. **SKUs `-512G` (SDINEDK4/SDINFDK4)** — confirmar PN individual no Mouser/DigiKey antes de
   subir de `distributor` para `confirmed`.

---

## 5. Convenções aplicadas (alinhadas ao `SANDISK.md`)

- `chip_type` ∈ {`eMMC`, `UFS`, `eMCP`}. **`SDINB*` gravado como `eMMC`** (não UFS) — ver §0.
- eMMC/UFS: `subtype`=vazio, `capacity` em GB, `emcp_*`=vazios.
- eMCP: `subtype`=geração RAM, `capacity`=vazio, `emcp_nand`=GB, `emcp_ram`=`"LPDDR{n} {x}GB"`
  (tipo ANTES da capacidade). Regra de ball count: 221→LPDDR3, 254→LPDDR4.
- `confidence`: `confirmed` (Tier 1) / `distributor` (Tier 2) / `skip` (só Tier 3 — incluído
  para investigação manual, conforme o prompt).
- PN normalizado sem traço (engine faz `re.sub(r"[^A-Z0-9]","")`). Em `fix_known_parts.py`
  usar a forma `pn_normalized`; `confidence` em `create_defaults`; só `confirmed`/`manual`
  vencem a gramática.

---

## 6. Próximos passos sugeridos

1. **Decidir o caso `SDINB`** (§0) — é o item de maior impacto operacional.
2. Importar as **50 linhas `confirmed`** em `fix_known_parts.py` (Tier 1, prontas).
3. Avaliar as **11 `distributor`** caso a caso (entram com `confidence=distributor`).
4. Tratar as **12 `skip`** como backlog de investigação (NÃO importar como confirmadas).
5. Rodar `fix_known_parts` (você executa) e verificar PNs representativos via shell.
6. Atualizar o histórico em `SANDISK.md` §10 quando os PNs forem para o banco.

> Fonte de dados: `docs/sandisk_inand_pesquisa_2026-06-26.csv`.
> Em conflito, **o código e os product briefs oficiais vencem** este relatório.
