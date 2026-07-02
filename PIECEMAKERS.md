> ⚠️ **O CONHECIMENTO É YAML** (desde jul/2026). As famílias, decode maps e PNs confirmados da
> PieceMakers vivem em **`chips/knowledge/piecemakers.yaml`**, carregado por `load_brands`. Para
> **adicionar ou corrigir um chip, edite o yaml** seguindo o contrato de autoria (via `CLAUDE.md`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do yaml (decode key→valor, inventário de
> famílias, listas de known_parts) nem valores mutáveis (rentabilidade): esses vivem só no yaml / código
> / admin. Aqui: **anatomia do PN, armadilhas, convenção, fontes, o *porquê***. **`CLAUDE.md`** é o único
> `.md` cross-marca mantido (convenção, comandos §5, arquitetura + aponta pro contrato de autoria).

---

# PIECEMAKERS.md — Bíblia Técnica PieceMakers Technology

**PieceMakers Technology** — Taiwan (Hsinchu), fabless DRAM design, fundada 2006 (fundador Tah-Kang
Joseph Ting). Faz **standard DRAM** (DDR/DDR2/DDR3/DDR3L/DDR4 — aparece na esteira) + PSRAM/KGD/HBLL-RAM
(nicho, raros). Fabricante pequeno → **dado escasso, IA alucina specs** (ver armadilhas). A lista viva
de famílias/mapas/known_parts está na **`piecemakers.yaml`**.

---

## 1. Convenção (OPÇÃO 1 — regras estáveis)

Fonte única da convenção: `chips/chip_types.py` (código). **DRAM discreta: a geração vai no `chip_type`,
espelhada no `subtype`** (❌ nunca `"RAM"`/`"DDR"` genérico). Densidade do **die** em `Gb`; pacote em `GB`.
Legados (DDR1/2, SDRAM) = sempre NÃO RENTÁVEL. Detalhes gerais: CLAUDE.md.

---

## 2. Anatomia do PN — como LER um chip PieceMakers

**DDR3/DDR3L (`PMF…`):**
```
P  M  F  [V]  [DD]  [B]  [WW]  [R]  B  R  -[sufixo]
0  1  2   3    4-5   6    7-8   9   10 11
```
- `pn[3]` = **tensão/geração**: `5`=1.5V (DDR3) · `4`=1.35V (DDR3L).
- `pn[4:6]` = **densidade** (codificada como log₂ de Mbit) → chaves no mapa `PMF_DDR3_CAP` do yaml.
- `pn[7:9]` = **barramento**: `08`=x8 · `16`=x16. `pn[9]` = revisão de silício. `BR` = package (96-FBGA x16 / 78-FBGA x8). Sufixo = speed/temp/grade (não altera specs).

**Outras famílias (routing por prefixo, geração pelo prefixo):** `PMF5`=DDR3 · `PMF4`=DDR3L · `PMF`=fallback
DDR3 · `PMA`=DDR4 · `PME`=DDR2 · `PMD`=DDR1 · `PMS`=SDRAM. Os valores de capacidade vivem nos mapas do yaml.

> **PMA (DDR4) — decode pendente:** estrutura posicional NÃO confirmada com volume suficiente
> (só `PMA212508ABR`/`PMA212816ABR` = 4Gb conhecidos). **Não implementar decode sem 2 densidades
> distintas em Tier 1.** Por ora é routing (classifica como DDR4).

---

## 3. Armadilhas específicas (o durável)

- **`decode_density_type="pc"` NÃO serve pro PMF** — a densidade está em `pn[4:6]`, mas o engine
  hardcodeia `pn[3:5]` no modo "pc". Usar `decode_cap_map="PMF_DDR3_CAP"` com `decode_cap_pos=4, len=2`.
- **PMF5 vs PMF4 vs PMF:** o engine casa o prefixo mais longo primeiro (`PMF5`/`PMF4` vencem `PMF`) → decode correto.
- **Sufixo não altera specs:** `PMF511816EBR-KADN` = `PMF511816EBR` (mesmo chip). Cadastre os dois se o operador digita com sufixo.
- **DDR3L opera a 1.5V também:** `PMF4xx` (DDR3L 1.35V) pode rodar 1.5V — não confundir com `PMF5xx` (DDR3 puro). O `subtype` (`"DDR3L"` vs `"DDR3"`) faz o label, então manter a distinção.
- **Fabricante pequeno → dado escasso:** IA frequentemente alucina specs PieceMakers. **Exigir fonte cruzada** antes de qualquer known_part.

---

## 4. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` (código) + `ProfitabilityConfig` (admin, editável — muda com o mercado).
Não citar limiares aqui. Padrão durável: DDR3 de baixa densidade e DDR2/DDR1/SDRAM = NÃO RENTÁVEL; DDR4 (PMA)
= rentável. `capacity`/`density_gbit` corretos (nunca Gbit no `capacity`) senão → INDETERMINADO (bloqueador).

---

## 5. Fontes de pesquisa

Tier 1: **piecemakers.com.tw** (catálogo oficial), DigiKey/Mouser (quando houver). Tier 2: element14 community
(engenheiros documentando hardware — ex.: Arty S7-50), glochip.com (tabela DDR3 — com cuidado). Tier 3 (IA /
distribuidor não rastreável): **nunca**. ⚠ O PDF oficial do datasheet (`piecemakers.com.tw/api/v1/file/…`)
voltou vazio em 2026-06 — tentar download direto pelo operador.

> Inventário de famílias/chaves e provenância por-PN: **`piecemakers.yaml`**. Comandos, convenção completa,
> rentabilidade, contrato de autoria: **CLAUDE.md**.
