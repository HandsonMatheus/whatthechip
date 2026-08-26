# Investigação — Nanya `NT5CC64M16GPD1` (debug ao vivo do estoque) + gap na die "G", 2026-08-20

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `NÃO RENTÁVEL` (1Gb DDR3L,
> abaixo do limiar mínimo de capacidade — mesmo padrão já visto na die "F" da rodada 3).**
> ⚠️ **PN exato da bancada (`NT5CC64M16GPD1`, com dígito "1" no final) NÃO resolve** com o
> known_part submetido — mas o candidato mais próximo (mesma die, sufixo "-DI" com letra "I")
> resolve por completo. Ver §2-3.

## 0. O gatilho

Debug ao vivo do estoque, 20/08/2026 13:34:27, PN `NT5CC64M16GPD1`: reconhecido pela gramática
(família `NT5CC`, `chip_type`/`subtype` = DDR3L) mas `known_exact:false`, `pn_not_in_db:true`,
`capacity:null`, `profitable:"INDETERMINADO"`, sem `fuzzy_suggestions` (lista vazia — diferente
da maioria das rodadas anteriores, o engine não achou nenhum candidato próximo desta vez).

## 1. Aritmética e cluster

`64M × 16bit = 1024Mbit = 1Gb`. Essa densidade já tinha known_parts confirmados na die "F"
(rodada 3: `NT5CC64M16FN-DHA`/`NT5CC64M16FP-DHA`, ambos `NÃO RENTÁVEL`), mas a die "G" do PN do
debug nunca tinha sido coberta. Índice Alldatasheet do bucket `NT5CC64M16G*`: **50 resultados**,
reconciliados exatos por sub-die: `GN(24) + GP(26) = 50`.

## 2. ⚠️ Sufixo "D1" (dígito) — não encontrado; "-DI" (letra) existe e é a leitura mais próxima

Busquei "D1" especificamente (dígito 1, não a letra I) e **não achei nenhuma fonte** com esse
sufixo literal — nem no Alldatasheet (bucket `GP*` = 26 resultados, todos com sufixo
`-DH*`/`-DI*`/`-EK*`, zero com dígito), nem em distribuidoras. O que existe, confirmado por 3
fontes convergentes (Alldatasheet direto, LCSC com estoque real, Octopart), é a die exata "GP"
com sufixo **"-DI"** (letra "I" maiúscula, não dígito "1") — visualmente muito próximo (I vs 1
são fáceis de confundir numa leitura de bancada), mas **não afirmo que é o mesmo PN**; só relato
a divergência e a proximidade, sem decidir por conta própria (mesma disciplina da rodada 6,
caso `NT5CB256M16BP` "-DG"/"-CG").

## 3. Teste comprobatório em sandbox — a diferença de UM caractere muda o resultado

Testei os dois casos lado a lado (§4, passos 7 e 8):

- `classify("NT5CC64M16GPD1")` (PN exato do debug, com dígito) → **continua
  `known_exact=False, profitable=INDETERMINADO`** mesmo após aprovar os 4 known_parts.
- `classify("NT5CC64M16GPDI")` (mesma leitura, trocando o dígito "1" pela letra "I") → **resolve
  por completo: `known_exact=True, profitable=NÃO RENTÁVEL, dram_density='1Gb por die [✓]'`**.

Ou seja: SE a marcação física do chip tiver a letra "I" (não o dígito "1"), o known_part
`NT5CC64M16GP-DI` resolve o caso exato. Se realmente for "1", nenhum dos 4 known_parts resolve —
sinalizar ao dono pra confirmar a leitura física, sem eu decidir qual é a correta.

## 4. known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CC64M16GP-DI | 1Gb | NÃO RENTÁVEL | Alldatasheet + LCSC + Octopart (candidato mais próximo do debug) |
| NT5CC64M16GP-DIT | 1Gb | NÃO RENTÁVEL | Alldatasheet + Octopart |
| NT5CC64M16GN-DHA | 1Gb | NÃO RENTÁVEL | Alldatasheet |
| NT5CC64M16GN-EKA | 1Gb | NÃO RENTÁVEL | Alldatasheet |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual,
   `catalog_version` sobe.
2. `classify("NT5CC64M16GPD1")` ANTES → `known_exact=False, chip_type='DDR3L', capacity=None,
   profitable='INDETERMINADO', pn_not_in_db=True` — reproduz o debug ao vivo exatamente.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada (`review_status="approved"` direto na tabela, equivalente ao admin).
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3L,
   dram_density='1Gb por die [✓]', profitable=NÃO RENTÁVEL`.
7. `classify("NT5CC64M16GPD1")` DE NOVO (PN exato da bancada, com dígito) → **continua
   `known_exact=False, profitable=INDETERMINADO`**.
8. `classify("NT5CC64M16GPDI")` (mesma leitura, letra "I" em vez de dígito) → **`known_exact=True,
   profitable=NÃO RENTÁVEL`** — confirma o §3.

Script terminou sem exceções.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cc64m16g.py
python manage.py submit_known_parts submissions/nanya_nt5cc_64m16g_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_64m16g_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cc64m16g.py`:
```bash
cat > precheck_nt5cc64m16g.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CC64M16GP-DI", "NT5CC64M16GP-DIT", "NT5CC64M16GN-DHA", "NT5CC64M16GN-EKA"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cc64m16g.py
```

## 6. Backlog (repetido de rodadas anteriores, ainda pendente)

- **Confirmar com o dono** se a marcação física do chip do debug é mesmo "...GPD1" (dígito) ou
  "...GP-DI" (letra I) — se for a letra, o known_part `NT5CC64M16GP-DI` já resolve o caso exato
  (confirmado em sandbox, §3).
- **`ChipFamily` type-only pra `NT5CB`**: decisão ainda pendente do dono.
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, `NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`.
- **`NT5CC256M16C*`/`D*`** (71 resultados, dies "C"/"D" do cluster 256M16) e **`NT5CC64M16GN`**
  restante (24 - 2 cobertas = 22 variantes) seguem sem known_part — backlog, só se novo sinal.

## 7. Fontes

- https://octopart.com/nt5cc64m16gp-dit-nanya-125127629
- https://www.lcsc.com/product-detail/C428582.html (NT5CC64M16GP-DI, estoque real)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145469/NANYA/NT5CC64M16GP-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145480/NANYA/NT5CC64M16GP-DIT.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145613/NANYA/NT5CC64M16GN-DHA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145625/NANYA/NT5CC64M16GN-EKA.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC64M16GP&sField=2 (26 resultados, sem "D1")
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC64M16G&sField=2 (50 = 24+26)
