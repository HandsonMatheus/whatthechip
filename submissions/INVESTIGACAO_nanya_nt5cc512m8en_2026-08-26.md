# Investigação — Nanya `NT5CC512M8EN` (debug ao vivo do estoque), 2026-08-26

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `RENTÁVEL` (4Gb DDR3L).**
> Die "E" do cluster `NT5CC512M8` era gap novo (rodada 3 já havia coberto a die "C" — organização
> igual, densidade igual — mas não a "E").
> ⚠️ **PN exato da bancada (`NT5CC512M8EN`, sem sufixo) NÃO resolve** — mesma ressalva de sufixo
> já documentada em quase todas as rodadas com sufixo.

## 0. O gatilho

Debug ao vivo do estoque, 26/08/2026 14:29:32, PN `NT5CC512M8EN`: reconhecido pela gramática
(família `NT5CC`, `chip_type`/`subtype` = DDR3L) mas `known_exact:false`, `pn_not_in_db:true`,
`capacity:null`, `profitable:"INDETERMINADO"`, `confidence:"estimated"`. `fuzzy_suggestions`:
`NT5CB512M8CN` (prefixo diferente — já confirmado como known_part da marca-irmã `NT5CB`, não
`NT5CC`).

## 1. Identificação direta — `NT5CC512M8EN-DI`, confirmado no Alldatasheet

Aritmética: `512M × 8bit = 4096Mbit = 4Gb`. Achei o PN exato com sufixo diretamente no índice do
Alldatasheet: bucket `NT5CC512M8E*` = **53 resultados**, reconciliado exato por die completa:
`EN(7) + EQ(24) + ER(22) = 53`. `NT5CC512M8EN-DI` está listado diretamente ("Commercial and
Industrial DDR3(L) 4Gb SDRAM"). Reforçado por 2 fontes de distribuidor: AB Sunshine Electronics
(ficha dedicada pro mesmo PN) e Arrow (variante `-EK` da mesma die).

## 2. Cluster

Die "E" já estava presente no vocabulário (a rodada 3 cobriu a die "C" do mesmo cluster 512M8,
via `NT5CC512M8CN-DI`/`-DIA` — mesma organização/densidade), mas a die "EN" nunca tinha known_part.
Este debug fecha esse gap.

## 3. ⚠️ PN exato sem sufixo — ressalva de sufixo (confirmada em sandbox)

Não achei `NT5CC512M8EN` (sem sufixo) como entrada própria em nenhuma fonte. `normalize_pn` remove
só o hífen, não letras de sufixo — `"NT5CC512M8EN"` (bancada) e `"NT5CC512M8ENDI"` (known_part
normalizado) são strings diferentes. Confirmado em sandbox (§4, passo 7): mesmo depois de aprovar
os 4 known_parts, `classify("NT5CC512M8EN")` continua `known_exact=False, profitable=INDETERMINADO`.
**Resolve o chip físico SE a marcação tiver o "-DI" (ou similar) legível.**

## 4. known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CC512M8EN-DI | 4Gb | RENTÁVEL | Alldatasheet direto + AB Sunshine |
| NT5CC512M8EN-EK | 4Gb | RENTÁVEL | Alldatasheet + Arrow |
| NT5CC512M8EQ-DI | 4Gb | RENTÁVEL | Alldatasheet |
| NT5CC512M8EQ-DIA | 4Gb | RENTÁVEL | Alldatasheet |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual,
   `catalog_version` sobe.
2. `classify("NT5CC512M8EN")` ANTES → `known_exact=False, chip_type='DDR3L', capacity=None,
   profitable='INDETERMINADO', pn_not_in_db=True` — reproduz o debug ao vivo exatamente.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada (`review_status="approved"` direto na tabela, equivalente ao admin).
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3L,
   dram_density='4Gb por die [✓]', profitable=RENTÁVEL`.
7. `classify("NT5CC512M8EN")` DE NOVO (PN exato da bancada, sem sufixo) → **continua
   `known_exact=False, profitable=INDETERMINADO`** — confirma a ressalva do §3.

Script terminou sem exceções.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cc512m8e.py
python manage.py submit_known_parts submissions/nanya_nt5cc_512m8e_2026-08-26.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_512m8e_2026-08-26.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cc512m8e.py`:
```bash
cat > precheck_nt5cc512m8e.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CC512M8EN-DI", "NT5CC512M8EN-EK", "NT5CC512M8EQ-DI", "NT5CC512M8EQ-DIA"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cc512m8e.py
```

## 6. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: decisão ainda pendente do dono (5 debugs 100% em
  branco já vistos: rodadas 2, 6, 10, 11, 12).
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **`NT5CC512M8ER*`** (22 resultados, die "R" do mesmo cluster) não coberto nesta rodada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, `NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`.

## 7. Fontes

- https://www.alldatasheet.com/datasheet-pdf/pdf/1425615/NANYA/NT5CC512M8EN-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1425617/NANYA/NT5CC512M8EN-EK.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145506/NANYA/NT5CC512M8EQ-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145490/NANYA/NT5CC512M8EQ-DIA.html
- https://www.absunshine.com/en/parts/NT5CC512M8EN-DI-NANYA-5256687
- https://www.arrow.com/en/products/nt5cc512m8en-ek/nanya-technology
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC512M8E&sField=2 (53 = 7+24+22)
