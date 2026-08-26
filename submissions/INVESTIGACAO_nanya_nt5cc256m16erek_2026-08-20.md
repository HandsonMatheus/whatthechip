# Investigação — Nanya `NT5CC256M16EREK` (debug ao vivo do estoque) + gap 256M16/4Gb, 2026-08-20

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `RENTÁVEL` (4Gb DDR3L).**
> Densidade `256M×16=4Gb` era um gap total na família `NT5CC` (outras densidades já cobertas:
> `64M16`/1Gb, `256M8`/2Gb, `512M8`/4Gb, `512M4`/2Gb — mas `256M16` nunca tinha known_part).
> ✅ **DIFERENTE de todas as rodadas anteriores com sufixo: o PN exato da bancada
> (`NT5CC256M16EREK`, sem hífen) RESOLVE por completo após a aprovação.** Ver §3.

## 0. O gatilho

Debug ao vivo do estoque, 20/08/2026 13:02:21, PN `NT5CC256M16EREK`: reconhecido pela gramática
(família `NT5CC`, `chip_type`/`subtype` = DDR3L) mas `known_exact:false`, `pn_not_in_db:true`,
`capacity:null`, `profitable:"INDETERMINADO"`, `confidence:"estimated"`. `fuzzy_suggestions`:
`NT5CC256M16EPEK`, `NT5CC256M16EPEKT`. O próprio `tip` do engine já contextualizava o padrão:
"Ex: NT5CC256M16EP-DI = 256M×16bit = 4Gb DDR3L" — confirmando de saída a organização/densidade
esperada, só faltava confirmar a die exata do PN.

## 1. Identificação direta — `NT5CC256M16ER-EK`, confirmado por 9+ fontes

Busca direta pelo PN "NT5CC256M16EREK" achou o PN **exato** com sufixo em texto corrido: 10
fontes independentes na primeira busca (Jotrin, Octopart, LCSC ×2 páginas, JLCPCB, Rutronik24
×2 regiões, Win Source, Arrow — e o Arrow também listou a variante `-EKI`), todas descrevendo
"DRAM Chip DDR3L SDRAM 4Gbit 256Mx16 1.35V 96-Pin TFBGA". Confirmado também no índice do
Alldatasheet: bucket `NT5CC256M16ER*` = 24 resultados, com `NT5CC256M16ER-EK` listado
diretamente ("Commercial and Industrial DDR3(L) 4Gb SDRAM"). Aritmética: `256M × 16bit =
4096Mbit = 4Gb` (bate com a descrição em todas as fontes).

**Diferente das rodadas anteriores** (`NT6CL`, `NT5CB256M16BP`, `NT5CC256M8`), aqui a die "ER"
**já aparece no próprio índice do Alldatasheet** — não foi preciso corroboração externa pra
provar que a die existe, só pra confirmar o PN completo com sufixo.

## 2. Cluster `NT5CC256M16` — reconciliação exata em duas camadas

- Total do bucket `NT5CC256M16*`: **124** resultados, quebrado exato por die letter:
  `C(33) + D(38) + E(53) = 124`.
- Dentro do sub-bucket `E(53)`: quebrado exato por die completa:
  `EP(7) + EQ(22) + ER(24) = 53`.

A die do debug (`ER`) é a maior fatia do bucket "E" (24 de 53). O próprio engine já havia
sugerido `NT5CC256M16EPEK` como fuzzy match — die vizinha real (`EP`), confirmando que a família
de dies "E" (EP/EQ/ER) é toda a mesma densidade/organização.

## 3. ✅ PN exato COM sufixo — resolve completo (diferente das rodadas de sufixo anteriores)

Nas rodadas `NT6CL512M4GN-CG`, `NT5CB256M16BP-DI/-CG` e `NT5CC256M8GN-DI`, o PN da bancada vinha
**sem nenhum sufixo** (ex.: `NT5CC256M8GN`), então o known_part com sufixo (`-DI`) nunca batia
exato — `normalize_pn` remove só o hífen, não letras, então `"NT5CC256M8GN"` e
`"NT5CC256M8GNDI"` são strings diferentes.

Aqui o cenário é diferente: o PN da bancada **já veio com o sufixo colado** (`NT5CC256M16EREK`
= `ER` + `EK` grudados, sem hífen). Como `normalize_pn` remove hífens, o known_part
`"NT5CC256M16ER-EK"` normaliza para `"NT5CC256M16EREK"` — **idêntico** ao PN da bancada.
Confirmado em sandbox (§4, passo 7): depois de aprovar, `classify("NT5CC256M16EREK")` retorna
`known_exact=True, profitable=RENTÁVEL, dram_density='4Gb por die [✓]'` — resolve o caso exato,
não só o cluster ao redor.

## 4. known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CC256M16ER-EK | 4Gb | RENTÁVEL | 9+ fontes (Octopart/LCSC/JLCPCB/Alldatasheet) + Alldatasheet direto |
| NT5CC256M16ER-DI | 4Gb | RENTÁVEL | Alldatasheet (mesma die, grade de velocidade diferente) |
| NT5CC256M16EP-DI | 4Gb | RENTÁVEL | Alldatasheet (die vizinha, 1º fuzzy_suggestion do engine) |
| NT5CC256M16EQ-DIA | 4Gb | RENTÁVEL | Alldatasheet (die vizinha, variante Automotive) |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual,
   `catalog_version` sobe.
2. `classify("NT5CC256M16EREK")` ANTES → `known_exact=False, chip_type='DDR3L', capacity=None,
   profitable='INDETERMINADO', pn_not_in_db=True` — reproduz o debug ao vivo exatamente.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada (`review_status="approved"` direto na tabela, equivalente ao admin).
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3L,
   dram_density='4Gb por die [✓]', profitable=RENTÁVEL`.
7. `classify("NT5CC256M16EREK")` DE NOVO (PN exato da bancada) → **`known_exact=True,
   profitable=RENTÁVEL, dram_density='4Gb por die [✓]'`** — resolve o caso exato.

Script terminou sem exceções.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cc256m16.py
python manage.py submit_known_parts submissions/nanya_nt5cc_256m16_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_256m16_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cc256m16.py`:
```bash
cat > precheck_nt5cc256m16.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CC256M16ER-EK", "NT5CC256M16ER-DI", "NT5CC256M16EP-DI", "NT5CC256M16EQ-DIA"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cc256m16.py
```

## 6. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: decisão ainda pendente do dono.
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, e prefixos vistos de passagem
  (`NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`) — backlog, sem reabrir sem novo sinal.
- **`NT5CC256M16C*`/`D*`** (33+38=71 resultados): dies "C"/"D" do mesmo cluster 256M16 ainda
  sem known_part — não coberto nesta rodada (só o sub-bucket "E", que é onde caía o PN do
  debug). Considerar se aparecer novo sinal de bancada.

## 7. Fontes

- https://octopart.com/nt5cc256m16er-ek-nanya-96079461
- https://www.lcsc.com/product-detail/DDR-SDRAM_Nanya-Tech-NT5CC256M16ER-EK_C428584.html
- https://jlcpcb.com/partdetail/NanyaTech-NT5CC256M16EREK/C428584
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145514/NANYA/NT5CC256M16ER-EK.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145512/NANYA/NT5CC256M16ER-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1425621/NANYA/NT5CC256M16EP-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145506/NANYA/NT5CC256M16EQ-DIA.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC256M16ER&sField=2 (24 resultados)
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC256M16E&sField=2 (53 = 7+22+24)
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC256M16&sField=2 (124 = 33+38+53)
