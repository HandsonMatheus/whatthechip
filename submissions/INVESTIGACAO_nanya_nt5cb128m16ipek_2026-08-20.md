# Investigação — Nanya `NT5CB128M16IPEK` (debug ao vivo do estoque), 2026-08-20

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `RENTÁVEL` (2Gb DDR3).**
> `NT5CB` continua sem `ChipFamily` (backlog pendente) — debug 100% em branco, mesmo padrão já
> visto nas rodadas 2/6/10.
> ✅ **O PN exato da bancada (`NT5CB128M16IPEK`, sem hífen) RESOLVE por completo** após aprovar —
> mesmo padrão positivo já visto na rodada `NT5CC256M16EREK` (o sufixo já vinha colado ao PN, só
> faltava o separador). Ver §3.

## 0. O gatilho

Debug ao vivo do estoque, 20/08/2026 16:34:16, PN `NT5CB128M16IPEK`: **100% em branco**
(`known:false`, todos os campos vazios/null, `in_review_queue:true`), com `fuzzy_suggestions`:
`NT5CB128M16IPFL` (die "IP" com sufixo diferente, já existente em produção como known_part
aprovado — fora do escopo desta submissão).

## 1. Identificação direta — `NT5CB128M16IP-EK`, confirmado por 8+ fontes

Busca direta pelo PN achou o PN exato com sufixo em texto corrido, confirmado por 8 fontes
independentes convergentes: LCSC (com estoque real), Alibaba, Kynix, Rutronik24, Arrow, Worldway,
SemiKey, Nyang-tech — todas descrevendo "Commercial, Industrial and Automotive DDR3(L) 2Gb
SDRAM" / "DDR3 2Gb 128Mx16 933MHz BGA96". Reforçado indiretamente pelo Alldatasheet, que tem a
die vizinha `NT5CB128M16IP-EKT` (mesma die "IP", sufixo com "T" extra) com datasheet direto —
confirma que a die "IP" é real e documentada oficialmente. Aritmética: `128M × 16bit = 2048Mbit
= 2Gb` (bate).

## 2. Cluster `NT5CB128M16I`

Índice Alldatasheet do bucket `NT5CB128M16I*`: 40 resultados, quebrado `IN(18) + IP(21) = 39`
(pequena discrepância de indexação de 1 unidade — já vista antes nesta série, não é motivo de
alarme dado o volume de fontes convergentes que confirmam a die "IP" diretamente).

## 3. ✅ PN exato COM sufixo — resolve completo

Como o PN da bancada já veio com o sufixo colado (`NT5CB128M16IPEK` = `IP` + `EK` grudados, sem
hífen), e `normalize_pn` remove hífens, o known_part `"NT5CB128M16IP-EK"` normaliza para
`"NT5CB128M16IPEK"` — **idêntico** ao PN da bancada. Confirmado em sandbox (§4, passo 7): depois
de aprovar, `classify("NT5CB128M16IPEK")` retorna `known_exact=True, profitable=RENTÁVEL,
dram_density='2Gb por die [✓]'` — resolve o caso exato, não só o cluster ao redor. Mesmo padrão
positivo já visto na rodada `NT5CC256M16EREK` (2026-08-20, mais cedo).

## 4. known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CB128M16IP-EK | 2Gb | RENTÁVEL | 8+ fontes (LCSC/Alibaba/Kynix/Rutronik/Arrow/etc) + Alldatasheet (die vizinha) |
| NT5CB128M16IP-DI | 2Gb | RENTÁVEL | Alldatasheet |
| NT5CB128M16IN-DIA | 2Gb | RENTÁVEL | Alldatasheet |
| NT5CB128M16IN-EKA | 2Gb | RENTÁVEL | Alldatasheet |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual (`NT5CB`
   segue sem família), `catalog_version` sobe.
2. `classify("NT5CB128M16IPEK")` ANTES → `known_exact=None, chip_type=None, profitable=None` —
   reproduz o debug 100% em branco, exatamente.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada (`review_status="approved"` direto na tabela, equivalente ao admin).
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3,
   dram_density='2Gb por die [✓]', profitable=RENTÁVEL`.
7. `classify("NT5CB128M16IPEK")` DE NOVO (PN exato da bancada) → **`known_exact=True,
   profitable=RENTÁVEL, dram_density='2Gb por die [✓]'`** — resolve o caso exato.

Script terminou sem exceções.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cb128m16i.py
python manage.py submit_known_parts submissions/nanya_nt5cb_128m16i_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_128m16i_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cb128m16i.py`:
```bash
cat > precheck_nt5cb128m16i.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CB128M16IP-EK", "NT5CB128M16IP-DI", "NT5CB128M16IN-DIA", "NT5CB128M16IN-EKA"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb128m16i.py
```

## 6. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: já o 4º debug ao vivo (rodadas 2, 6, 10, 11) que chega
  100% em branco só por falta da família — backlog cada vez mais recorrente, decisão pendente do
  dono.
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, `NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`.
- **`NT5CB128M16IP-FL`**: sinalizado pelo fuzzy_suggestion do próprio engine como já existente em
  produção (fora do escopo desta submissão — não investigado aqui).

## 7. Fontes

- https://www.lcsc.com/product-detail/ddr-sdram_nanya-tech-nt5cb128m16ip-ek_C2846879.html (estoque real)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145504/NANYA/NT5CB128M16IP-EKT.html (die vizinha)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145485/NANYA/NT5CB128M16IP-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145595/NANYA/NT5CB128M16IN-DIA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145599/NANYA/NT5CB128M16IN-EKA.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CB128M16I&sField=2 (40 = 18+21≈39)
