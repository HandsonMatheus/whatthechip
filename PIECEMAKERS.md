# PIECEMAKERS.md — Bíblia técnica PieceMakers Technology no WTC

> Leia este arquivo quando a tarefa envolver chips PieceMakers:
> anatomia do PN, famílias, mapas de decode, rentabilidade, armadilhas.
> Para regras gerais do WTC, consulte `CLAUDE.md`.

---

## 1. Quem é PieceMakers Technology

| Campo | Info |
|---|---|
| País | Taiwan (sede em Hsinchu) |
| Fundação | 2006 |
| Tipo | Fabless DRAM design company |
| Fundador | Tah-Kang Joseph Ting (>40 anos IC, >60 patentes) |
| Certificações | ISO 9001, ISO 14001 |
| Representantes | China, Japão, França, Israel, Turquia |
| Site | https://www.piecemakers.com.tw |

### Portfólio (relevância para reciclagem)

| Linha | Relevância |
|---|---|
| Standard DRAM — DDR/DDR2/DDR3/DDR3L/DDR4 | **Alta** — aparece na esteira |
| PSRAM | Baixa — nicho, raro na reciclagem de massa |
| KGD DRAM (Known Good Die) | Baixa — sem encapsulamento, raro |
| HBLL-RAM / HiBaLL-RAM / PIM-DDR3 | **Nula** — nicho industrial/AI |

---

## 2. Prefixos e famílias no WTC

| Prefixo | Família WTC | Tipo | Tensão | Obs |
|---|---|---|---|---|
| `PMF5xx` | `PMF5` | DDR3 | 1.5V | Decode posicional ativo |
| `PMF4xx` | `PMF4` | DDR3L | 1.35V | Decode posicional ativo |
| `PMF` | `PMF` (fallback) | DDR3 | ambos | Routing; captura PMF sem decode |
| `PMA` | `PMA` | DDR4 | 1.2V | Routing apenas (decode pendente) |
| `PME` | `PME` | DDR2 | 1.8V | Routing apenas; NÃO RENTÁVEL |
| `PMD` | `PMD` | DDR1 | 1.8V/2.5V | Routing apenas; NÃO RENTÁVEL |
| `PMS` | `PMS` | SDRAM | 3.3V | Routing apenas; NÃO RENTÁVEL |

Famílias criadas em: `chips/management/commands/populate_piecemakers.py`

---

## 3. Anatomia do PN DDR3 (PMF)

```
P  M  F  [V]  [DD]  [B]  [WW]  [R]  B  R  -  [sufixo]
0  1  2   3    4-5   6    7-8   9   10 11
```

| Posição | Campo | Valores conhecidos |
|---|---|---|
| 0-2 | Família | `PMF` = DDR3/DDR3L PieceMakers |
| 3 | Tensão (V) | `5`=1.5V (DDR3) · `4`=1.35V (DDR3L) |
| 4-5 | Densidade (DD) | `10`=1Gb · `11`=2Gb · `12`=4Gb (log₂ de Mbit) |
| 6 | Bancos (B) | `8` = 8 banks |
| 7-8 | Barramento (WW) | `08`=x8 · `16`=x16 |
| 9 | Revisão (R) | `B`/`C`/`D`/`E`/`F`/`G` (revisão de silício) |
| 10-11 | Package | `BR` = FBGA (96-FBGA para x16 · 78-FBGA para x8) |
| 13+ | Sufixo | Speed bin / temperatura / grade (ex.: `KADN`, `KAIN`, `MBIN`) |

### Exemplos confirmados

| PN | Capacidade | Barramento | Tensão | Fonte |
|---|---|---|---|---|
| PMF510816DBR | 1Gb (128MB) | x16 | DDR3 1.5V | glochip ✓ |
| PMF511816EBR | 2Gb (256MB) | x16 | DDR3 1.5V | glochip ✓ + element14 ✓ + piecemakers.com.tw ✓ |
| PMF511816EBR-KADN | 2Gb (256MB) | x16 | DDR3 1.5V | element14 (Arty S7-50) ✓ + operador WTC ✓ |
| PMF512816CBR | 4Gb (512MB) | x16 | DDR3 1.5V | glochip ✓ |
| PMF511808EBR | 2Gb (256MB) | x8 | DDR3 1.5V | glochip ✓ |

---

## 4. DecodeMap: PMF_DDR3_CAP

Mapa de capacidade para DDR3/DDR3L PieceMakers (posição pn[4:6]):

| `char_key` | `val_primary` | Densidade | Obs |
|---|---|---|---|
| `10` | `128MB` | 1Gb por die | `PMF510xxx` |
| `11` | `256MB` | 2Gb por die | `PMF511xxx` — principal |
| `12` | `512MB` | 4Gb por die | `PMF512xxx` |

Conversão: densidade em Mb = 2^N × 1Mb → capacidade em bytes = densidade ÷ 8.

---

## 5. Rentabilidade esperada

| Família | density_gbit | Rentabilidade via `assess_profitability` |
|---|---|---|
| PMF5 / PMF4 (DDR3) — 1Gb | 1Gb | **NÃO RENTÁVEL** (< ddr3_min_gbit de 2Gb) |
| PMF5 / PMF4 (DDR3) — 2Gb | 2Gb | **RENTÁVEL** (= ddr3_min_gbit — limiar) |
| PMF5 / PMF4 (DDR3) — 4Gb | 4Gb | **RENTÁVEL** (> ddr3_min_gbit) |
| PMA (DDR4) | qualquer | **RENTÁVEL** (DDR4 gen > ddr_min_gen) |
| PME (DDR2) | qualquer | **NÃO RENTÁVEL** (gen DDR2 < 3) |
| PMD (DDR1) | qualquer | **NÃO RENTÁVEL** (gen DDR1 < 3) |
| PMS (SDRAM) | qualquer | **NÃO RENTÁVEL** (gen < 3) |

> Limiar exato de `ddr3_min_gbit` é configurável via `ProfitabilityConfig` no admin.
> Nunca reimplemente regra de rentabilidade — consulte `assess_profitability`.

---

## 6. Decode para DDR4 (PMA) — pendente

Catálogo atual PieceMakers DDR4 (PMA):

| PN | Capacidade | Barramento | Fonte |
|---|---|---|---|
| PMA212508ABR | 4Gb (512MB) | x8 | piecemakers.com.tw ✓ |
| PMA212816ABR | 4Gb (512MB) | x16 | piecemakers.com.tw ✓ |

Estrutura suspeita do PMA (não confirmada com volume suficiente para decode):
```
P  M  A  [2]  [12]  [5/8]  [08/16]  [A/B]  BR
               ↑ 4Gb (log₂ de Gbit = 2^12 Mbit?)
```
pn[3]="2" — possivelmente revisão ou voltagem. pn[4:6]="12" — possivelmente 4Gb.
**Não implementar decode sem confirmar 2 densidades distintas em fonte Tier 1.**

---

## 7. Hierarquia de fontes PieceMakers

| Nível | Fonte | Status |
|---|---|---|
| Tier 1 | piecemakers.com.tw (oficial, catálogo) | Disponível ✓ |
| Tier 1 | Datasheet oficial PDF (piecemakers.com.tw/api/v1/file/…) | PDF não retornou conteúdo (2026-06-20) |
| Tier 1 | DigiKey / Mouser (listagem com specs) | Não encontrado ainda |
| Tier 2 | element14 community (engineers documentando hardware) | Arty S7-50 ✓ |
| Tier 2 | glochip.com — tabela DDR3 PieceMakers | Consultar com cuidado |
| Tier 3 | IA / distribuidores não rastreáveis | **Nunca usar** |

---

## 8. Como adicionar mais KnownParts PieceMakers

1. Confirme o PN em fonte Tier 1 ou Tier 2 cruzada.
2. Decodifique pn[4:6] para `capacity` (ver §4) e pn[7:9] para `interface`.
3. Adicione entrada em `fix_known_parts.py` com:
   - `brand_name="PieceMakers"`
   - `chip_type="RAM"`, `subtype="DDR3"` (ou `"DDR3L"` se pn[3]="4")
   - `interface="x8"` ou `"x16"`
   - `capacity` em MB (ex.: `"256MB"` para 2Gb)
   - `density_gbit` em Gb (ex.: `"2Gb"`)
   - `confidence="manual"` (se Tier 2) ou `"confirmed"` (se DigiKey/datasheet)
     ← **obrigatório** `confirmed`/`manual` para o engine tratar como autoritativo
     (banco vence a gramática). Com `distributor`/`estimated` o engine usa o decode
     posicional. *(Não há mais campo `status`; foi removido em jun/2026.)*

---

## 9. Armadilhas específicas PieceMakers

- **`decode_density_type="pc"` NÃO funciona** para PMF: a densidade está em pn[4:6],
  mas o engine hardcodeia `pn[3:5]` para "pc". Usar `decode_cap_map="PMF_DDR3_CAP"`
  com `decode_cap_pos=4, decode_cap_len=2`.
- **PMF5 vs PMF4 no engine**: o engine escolhe família por prefix match (mais longo
  vence). `PMF5` (4 chars) vence `PMF` (3 chars) → decode correto.
- **Sufixo no PN não altera specs**: `PMF511816EBR-KADN` e `PMF511816EBR` são
  o mesmo chip. Adicione ambos como KnownPart se o operador os digita com sufixo.
- **DDR3L suporta 1.5V também**: PMF4xx (nominalmente DDR3L 1.35V) pode operar
  a 1.5V — não confundir com PMF5xx (DDR3 puro). O gateway usa o `subtype` para
  label (`"DDR3L"` vs `"DDR3"`), então manter a distinção.
- **Fonte de dados escassa**: PieceMakers é fabricante pequeno; IA frequentemente
  alucina specs. Exigir sempre fonte cruzada antes de adicionar KnownPart.
- **PDF do datasheet**: a URL `piecemakers.com.tw/api/v1/file/e0a55febeeb036f135c7698e33aed1e8.pdf`
  retornou conteúdo vazio em 2026-06-20. Tentar novamente em sessão futura ou
  via download direto pelo operador.

---

## 10. Comandos relevantes

```bash
# Rodar populate (Brand + DecodeMap + ChipFamily)
python manage.py populate_piecemakers --dry-run
python manage.py populate_piecemakers --overwrite
# ⚠ REINICIAR o servidor após --overwrite (lru_cache do engine)

# Aplicar KnownParts (fix_known_parts não precisa reiniciar)
python manage.py fix_known_parts --dry-run
python manage.py fix_known_parts

# Testar decode do PN
python manage.py shell -c "from chips.engine import classify; print(classify('PMF511816EBR'))"
python manage.py shell -c "from chips.engine import classify; print(classify('PMF511816EBR-KADN'))"
```

---

*Criado em 2026-06-20 | Sessão PieceMakers | eMiner / WhatTheChip*
