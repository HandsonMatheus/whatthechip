# Investigação — Nanya `NT5CB128M8CN` (debug ao vivo do estoque) + gap 128M8, 2026-08-20

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `NÃO RENTÁVEL` (1Gb DDR3).**
> `NT5CB` continua sem `ChipFamily` (decisão pendente do dono, backlog repetido) — o debug
> reproduz o mesmo "100% em branco" já visto nas rodadas 2 e 6.
> ⚠️ **PN exato da bancada (`NT5CB128M8CN`, sem sufixo) NÃO resolve** com o known_part
> submetido — mesma ressalva de sufixo já documentada em quase todas as rodadas com sufixo.

## 0. O gatilho

Debug ao vivo do estoque, 20/08/2026 13:50:18, PN `NT5CB128M8CN`: **100% em branco**
(`known:false`, todos os campos vazios/null, `in_review_queue:true`), com `fuzzy_suggestions`:
`NT5CB512M8CN` (já confirmado na rodada 2, mesmo sufixo "CN" mas profundidade diferente — 512M em
vez de 128M).

## 1. Identificação — `NT5CB128M8CN-CG`, confirmado por 2 fontes com página dedicada

Aritmética: `128M × 8bit = 1024Mbit = 1Gb`. Índice do Alldatasheet pro bucket `NT5CB128M8*`:
**105 resultados**, reconciliados exatos por die letter: `F(52) + G(53) = 105` — **sem bucket
"C"**, mesmo padrão já visto em várias rodadas anteriores (die real fora do crawl daquele índice
específico).

Busquei fora do Alldatasheet e achei o PN exato com sufixo confirmado por 2 fontes com página
dedicada (não resumo de busca):

1. **Kynix** — ficha estruturada completa, "In Stock: 1,056 units" (estoque real), atributos
   "Number of Words: 128000000" (= 128M), "Supply Voltage-Nom: 1.5V" (confirma **DDR3**, não
   DDR3L — bate com o próprio `tip` do engine: "NT5CB = DDR3 1.5V"), descrição técnica "1Gb
   Double-Data-Rate-3 (DDR3/L) B-die DRAM... transfer rates of up to 2133 Mb/sec/pin". (O título
   curto da página diz "DDR DRAM" genérico — categorização solta do distribuidor, não confiável
   por si só — mas a descrição técnica completa desambiguou para DDR3.)
2. **Ariat-tech** — PDF de datasheet dedicado ao mesmo PN exato `NT5CB128M8CN-CG`.

## 2. Cluster e known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CB128M8CN-CG | 1Gb | NÃO RENTÁVEL | Kynix (estrutura+estoque) + Ariat-tech (PDF) |
| NT5CB128M8FN | 1Gb | NÃO RENTÁVEL | Alldatasheet |
| NT5CB128M8FN-DH | 1Gb | NÃO RENTÁVEL | Alldatasheet |
| NT5CB128M8FN-EK | 1Gb | NÃO RENTÁVEL | Alldatasheet |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual (`NT5CB`
   segue sem família), `catalog_version` sobe.
2. `classify("NT5CB128M8CN")` ANTES → `known_exact=None, chip_type=None, profitable=None` —
   reproduz o debug 100% em branco, exatamente.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada (`review_status="approved"` direto na tabela, equivalente ao admin).
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3,
   dram_density='1Gb por die [✓]', profitable=NÃO RENTÁVEL`.
7. `classify("NT5CB128M8CN")` DE NOVO (PN exato da bancada, sem sufixo) → **continua
   `known_exact=None, profitable=None`** — confirma a ressalva de sufixo.

Script terminou sem exceções.

## 3. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cb128m8.py
python manage.py submit_known_parts submissions/nanya_nt5cb_128m8_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_128m8_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cb128m8.py`:
```bash
cat > precheck_nt5cb128m8.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CB128M8CN-CG", "NT5CB128M8FN", "NT5CB128M8FN-DH", "NT5CB128M8FN-EK"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb128m8.py
```

## 4. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: continua sinalizado, decisão pendente do dono — este é
  já o 3º debug ao vivo (rodadas 2, 6, 10) que chega "100% em branco" só por falta da família.
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, `NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`.
- **Bucket `NT5CB128M8G*`** (53 resultados, die "G") não coberto nesta rodada — só "F" e "C".

## 5. Fontes

- https://www.kynix.com/productdetails/23907044/nanya/nt5cb128m8cncg.html (estoque real, ficha estruturada)
- https://www.ariat-tech.com/datasheets/4748776955/NT5CB128M8CN-CG.pdf
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145457/NANYA/NT5CB128M8FN.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145461/NANYA/NT5CB128M8FN-DH.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145462/NANYA/NT5CB128M8FN-EK.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CB128M8&sField=2 (105 = 52+53, sem die "C")
