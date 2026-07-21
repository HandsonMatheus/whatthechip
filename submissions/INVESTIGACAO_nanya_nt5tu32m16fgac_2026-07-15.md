# Investigação — Nanya `NT5TU32M16FG-AC` (debug ao vivo do estoque) + família `NT5TU` nova, 2026-07-15

> ✅ **Resultado: família `NT5TU` (DDR2 SDRAM) criada na gramática + 6 known_parts submetidos.**
> Prefixo era um dos "leads CMS" já sinalizados na priorização original (item 4 do onboarding:
> `NT5DS`/`NT5TU`/`NT5SV`/`NT5W`/`NT6*` citados no site institucional, não confirmados em Tier-1 até
> agora). Confirmado: é **DDR2** (PC/desktop, geração legada). **Diferente das 4 famílias Nanya
> anteriores**: DDR2 fica **NÃO RENTÁVEL já só com a gramática** (sem precisar de known_part) — é
> geração abaixo do mínimo comercial do projeto, então a família sozinha já resolve o triage.

## 0. O gatilho

Debug do estoque, PN `NT5TU32M16FG-AC`: **100% em branco** (`known:false`, `in_review_queue:true`,
JSON com todos os campos `null`) — mesmo padrão dos casos `NT5CB64M16FP`/`NT6CL256M32AM`: prefixo sem
`ChipFamily` nenhuma, nem reconhecimento de tipo.

## 1. `NT5TU32M16FG-AC` identificado — Tier-1 direto

Alldatasheet indexa o PN exato do debug como entrada própria — abri a página diretamente (não só o
resumo de busca): `alldatasheet.com/datasheet-pdf/pdf/1145608/NANYA/NT5TU32M16FG-AC.html` —
"Description: Commercial and Industrial DDR2 512Mb SDRAM", Manufacturer=NANYA, Direct Link=nanya.com.
Aritmética: 32M × 16bit = 512Mbit = **512Mb** (bate, mesma fórmula profundidade×largura já validada nas
3 rodadas anteriores — agora confirmada também em DDR2).

## 2. Cluster `NT5TU` — 146 resultados no Alldatasheet, mapeado por densidade

| Sub-prefixo | Resultados | Organização | Densidade |
|---|---|---|---|
| `NT5TU3*` (=`NT5TU32*`) | 36 | 32M×16 | **512Mb** ← o PN do caso |
| `NT5TU6*` (=`NT5TU64*`) | 72 | 64M×16 | 1Gb |
| `NT5TU1*` | 38 | 128M×4 (C-die legado) OU 128M×8 (G/H-die) | 512Mb OU 1Gb (bucket misto) |

**36 + 72 + 38 = 146 — bate exato com o total.** O cluster `NT5TU` vai de 512Mb a 1Gb — não há
variante maior (nenhum sub-prefixo além desses 3).

## 3. Família nova na gramática — `NT5TU`

Adicionei ao `nanya.yaml` (Trilha A): `chip_type: DDR2`, `subtype: DDR2`, sem decode de capacidade
(mesmo padrão magro das outras 4 famílias Nanya), `reasoning` preenchido em formato JSON (lição da
rodada `NT6CL` — o campo é JSON, texto livre falha silenciosamente). **Golden obrigatório**: adicionei
`'NT5TU32M16FG-AC': ('DDR2', '', '', '', '', 'NÃO RENTÁVEL')` ao `_NANYA_GOLDEN`.

**Diferença importante em relação às outras 4 famílias Nanya**: `NT5AD`/`NT5CC`/`NT5PA`/`NT6CL` ficam
`INDETERMINADO` na gramática sozinha (precisam de known_part pra sair do limbo). `NT5TU` **NÃO** — DDR2
está abaixo de `ddr_min_gen` (limiar = 3, ou seja DDR3 é o mínimo comercial) → **`NÃO RENTÁVEL` e
`is_dead_by_generation=True` já só com a família cadastrada, sem nenhum known_part.** Confirmado em
sandbox (§5, passo 2). Ou seja: **a família sozinha já resolve o triage de QUALQUER PN `NT5TU` atual ou
futuro** — os known_parts do §4 só agregam detalhe de capacidade/densidade, não mudam o resultado
comercial.

## 4. known_parts submetidos (6)

| PN | Densidade | Interface | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|---|
| **NT5TU32M16FG-AC** (PN do caso) | 512Mb | x16 | NÃO RENTÁVEL | Alldatasheet |
| NT5TU32M16EG-AC | 512Mb | x16 | NÃO RENTÁVEL | Alldatasheet |
| NT5TU32M16CG-25C | 512Mb | x16 | NÃO RENTÁVEL | Alldatasheet (C-die, 2007) |
| NT5TU64M16HG | 1Gb | x16 | NÃO RENTÁVEL | Alldatasheet |
| NT5TU64M16GG | 1Gb | x16 | NÃO RENTÁVEL | Alldatasheet (G-die, 2013) |
| NT5TU128M8HE | 1Gb | x8 | NÃO RENTÁVEL | Alldatasheet |

Todos `NÃO RENTÁVEL` — esperado e correto (geração, não capacidade, é o motivo). Usei `density_gbit`
(Gb/die) aqui, **não** `capacity` (GB/pacote) — DDR2 é "DDR discreta" (convenção do CLAUDE.md §6), campo
diferente do usado na rodada `NT6CL` (LPDDR3 avulso usa `capacity`). Não repeti o erro da rodada
anterior.

## 5. Validação em sandbox

1. `load_brands --brand nanya --commit --skip-known-parts` (yaml com `NT5TU` novo) → família criada.
2. `classify("NT5TU32M16FG-AC")` só com gramática → `('DDR2', '', '', '', '', 'NÃO RENTÁVEL')`,
   `is_dead_by_generation=True` — bate com o golden novo. **Grande diferença das rodadas anteriores**:
   aqui o triage já está correto ANTES de qualquer known_part.
3. `submit_known_parts` dry-run → portão aceitou os 6 (sem erro de JSON desta vez).
4. `--commit` → gravou como `submitted` (oculto), `density_gbit` certo.
5. Aprovação simulada + `classify()` de novo → os 6 saem `known_exact=True`, `dram_density` certo,
   `profitable=NÃO RENTÁVEL` em todos (consistente com o §4).

## 6. Comandos para o dono

```bash
# Trilha A — gramática (família NT5TU nova + golden em tests.py)
git add chips/knowledge/nanya.yaml chips/tests.py
git commit -m "catalog: nanya +familia NT5TU (DDR2 SDRAM, PC legado)"
git push origin main
python manage.py test chips --settings=core.settings_test   # roda o golden novo, deve passar
python manage.py load_brands --brand nanya --commit          # publica no banco de prod

# Trilha B — known_parts (precheck antes, depois submit)
python manage.py shell < precheck_nt5tu.py
python manage.py submit_known_parts submissions/nanya_nt5tu_2026-07-15.yaml
python manage.py submit_known_parts submissions/nanya_nt5tu_2026-07-15.yaml --commit
# aprovar em /admin/chips/knownpart/ (filtro review_status → Submetido)
python manage.py guard_catalog
```

`precheck_nt5tu.py`:
```bash
cat > precheck_nt5tu.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = [
    "NT5TU32M16FG-AC", "NT5TU32M16EG-AC", "NT5TU32M16CG-25C",
    "NT5TU64M16HG", "NT5TU64M16GG", "NT5TU128M8HE",
]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 6 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5tu.py
```

**Nota**: se o dono só quiser o resultado de triage rápido (NÃO RENTÁVEL), a Trilha A sozinha (publicar
a família) já resolve — a Trilha B (known_parts) é opcional/complementar, útil pra densidade aparecer no
card de busca mas não muda o destino comercial.

## 7. Backlog

- **`NT5TU1*` (bucket misto, 38 resultados)** — não separei individualmente 128M4(512Mb C-die) vs
  128M8(1Gb G/H-die) além do 1 PN já incluído (`NT5TU128M8HE`); suficiente pra esta rodada.
- **`NT6DM32M16BD`** apareceu de relance na busca ("Commercial and Industrial Mobile DDR 512Mb SDRAM")
  — outro prefixo Nanya (Mobile DDR de 1ª geração, pré-LPDDR) não investigado; backlog se aparecer PN
  de bancada.
- **Outros leads CMS ainda pendentes**: `NT5DS`/`NT5SV`/`NT5W` (citados no onboarding original, item 4)
  — nenhum PN de bancada apareceu ainda pra esses três.

## 8. Fontes completas

- https://www.alldatasheet.com/datasheet-pdf/pdf/1145608/NANYA/NT5TU32M16FG-AC.html (PN do caso)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145592/NANYA/NT5TU32M16EG-AC.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1820402/NANYA/NT5TU32M16CG-25C.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145659/NANYA/NT5TU64M16HG.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1772685/NANYA/NT5TU64M16GG.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145658/NANYA/NT5TU128M8HE.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5TU&sField=2 (índice completo, 146 resultados)
- `chips/models.py` (`ProfitabilityConfig.ddr_min_gen`, default 3 = DDR3 mínimo)
