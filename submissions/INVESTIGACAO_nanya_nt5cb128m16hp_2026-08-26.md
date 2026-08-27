# Investigação — Nanya `NT5CB128M16HP` (debug ao vivo do estoque), 2026-08-26

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `RENTÁVEL` (2Gb DDR3).**
> `NT5CB` continua sem `ChipFamily` (backlog pendente) — debug 100% em branco, mesmo padrão já
> visto nas rodadas 2/6/10/11/12.
> ⚠️ **PN exato da bancada (`NT5CB128M16HP`, sem sufixo) NÃO resolve** — mesma ressalva de sufixo
> de sempre.

## 0. O gatilho

Debug ao vivo do estoque, 26/08/2026 14:35:33, PN `NT5CB128M16HP`: **100% em branco**
(`known:false`, todos os campos vazios/null, `in_review_queue:true`), com `fuzzy_suggestions`
mistas: `NT5CB128M16` (sem sufixo), `NT5CB128M16JR` (sibling da rodada 11, cluster 128M16),
`NT5CC128M16FP`/`NT5CC128M16IP` (sugestões da marca-irmã `NT5CC`, prefixo diferente).

## 1. Identificação direta — `NT5CB128M16HP-DI`, confirmado por 5+ fontes

Aritmética: `128M × 16bit = 2048Mbit = 2Gb`. A die "H" **não aparece no índice principal** do
Alldatasheet (bucket `NT5CB128M16` = 89, reconciliado exato `F(8) + I(40) + J(41) = 89`, sem
"H") — mesmo padrão já visto muitas vezes: die real fora do crawl daquele índice específico.

Busquei fora do índice principal e achei o PN exato com sufixo confirmado por 5+ fontes
independentes convergentes: **Powerline Microelectronics, Veswin, Ariat-Tech, Ovaga
Technologies**, e o próprio **Alldatasheet** (datasheet dedicado, indexado por busca de
"marking" em vez do índice principal por part number). Descrição técnica consistente: "DDR3
SDRAM, 2Gbit, 128Mx16, 8 bancos internos, bus 16-bit, 1.425V-1.575V" (1.5V nominal — confirma
**DDR3**, não DDR3L, padrão já estabelecido para `NT5CB`).

## 2. known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CB128M16HP-DI | 2Gb | RENTÁVEL | Powerline/Veswin/Ariat-Tech/Ovaga/Alldatasheet (5+ fontes) |
| NT5CB128M16HP-EK | 2Gb | RENTÁVEL | Datasheets360 |
| NT5CB128M16HP-CG | 2Gb | RENTÁVEL | Worldway + Datasheets360 |
| NT5CB128M16HP-DII | 2Gb | RENTÁVEL | Jotrin |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual (`NT5CB`
   segue sem família), `catalog_version` sobe.
2. `classify("NT5CB128M16HP")` ANTES → `known_exact=None, chip_type=None, profitable=None` —
   reproduz o debug 100% em branco.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada.
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3,
   dram_density='2Gb por die [✓]', profitable=RENTÁVEL`.
7. `classify("NT5CB128M16HP")` DE NOVO (PN exato da bancada, sem sufixo) → **continua
   `known_exact=None, profitable=None`** — confirma a ressalva de sufixo.

Script terminou sem exceções.

## 3. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cb128m16h.py
python manage.py submit_known_parts submissions/nanya_nt5cb_128m16h_2026-08-26.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_128m16h_2026-08-26.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cb128m16h.py`:
```bash
cat > precheck_nt5cb128m16h.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CB128M16HP-DI", "NT5CB128M16HP-EK", "NT5CB128M16HP-CG", "NT5CB128M16HP-DII"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb128m16h.py
```

## 4. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: já o 6º debug ao vivo (rodadas 2, 6, 10, 11, 12, 14)
  que chega 100% em branco só por falta da família.
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, `NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`.

## 5. Fontes

- https://www.ariat-tech.com/parts/NANYA/NT5CB128M16HP-DI
- https://www.powerlinemicroelectronics.com/products/nt5cb128m16hp-di-72298
- https://www.veswin.com/product-NT5CB128M16HP-DI.html
- https://www.ovaga.com/products/detail/nt5cb128m16hp-di
- https://www.datasheets360.com/part/detail/nt5cb128m16hp-ek/
- https://www.datasheets360.com/part/detail/nt5cb128m16hp-cg/
- https://www.worldwayelec.com/pro/nanya/nt5cb128m16hp-cg/5021087
- https://www.jotrin.com/product/parts/NT5CB128M16HP-DII
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CB128M16&sField=2 (89 = 8+40+41, sem die "H")
