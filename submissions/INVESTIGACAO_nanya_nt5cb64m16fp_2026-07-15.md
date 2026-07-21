# Investigação — Nanya `NT5CB64M16FP` (debug ao vivo do estoque) + cluster `NT5CB`, 2026-07-15

> ✅ **Resultado: 5 known_parts `NT5CB` submetidos, todos `confirmed`.** O PN do caso
> (`NT5CB64M16FP`) identificado: **DDR3 1.5V, 1Gb (64M×16), NÃO RENTÁVEL.** Cluster ampliado com uma
> densidade nova (4Gb/512M×8, RENTÁVEL) que não existia no catálogo local. Validado ponta-a-ponta em
> sandbox — reproduzi o debug em branco ANTES de submeter (prova de que é exatamente esse o buraco) e
> confirmei o resultado certo DEPOIS de aprovar. Arquivo: `nanya_nt5cb_2026-07-15.yaml`.

## 0. O gatilho

Debug do estoque, 15/07/2026 15:06:36, PN `NT5CB64M16FP`: **tudo em branco** (`known_exact=false`,
`chip_type` vazio, `in_review_queue=true`, JSON com `known:false` e todos os campos `null`) — pior que o
padrão INDETERMINADO das outras famílias Nanya (que ao menos mostram o tipo). Motivo, já documentado no
`NANYA.md` §3: **`NT5CB` não tem `ChipFamily` na gramática** (só `NT5AD`/`NT5CC`/`NT5PA` existem no yaml)
— um PN `NT5CB` sem `known_part` confirmado é 100% invisível ao `classify()`, nem reconhecimento de tipo.

## 1. `NT5CB64M16FP` identificado — Tier-1 direto

Alldatasheet indexa a **própria forma que apareceu no debug** (`NT5CB64M16FP`, sem sufixo) como entrada
de catálogo: "Commercial, Industrial and Automotive DDR3(L) 1Gb SDRAM" — não é um PN que eu compus, é a
entrada canônica do fabricante. Aritmética: 64M×16bit = 1024Mbit = **1Gb** (bate). `NT5CB` = DDR3 1.5V
(convenção já estabelecida do projeto, ≠ `NT5CC` = DDR3L 1.35V).

## 2. Cluster `NT5CB` — 679 resultados no Alldatasheet, mapeado por densidade

Busquei o prefixo inteiro (não só o PN do caso). O índice de busca do Alldatasheet quebra por
sub-prefixo, o que deu uma visão completa da família de uma vez:

| Sub-prefixo | Resultados | Organização | Densidade |
|---|---|---|---|
| `NT5CB6*` | 108 | 64M×16 | **1Gb** ← o PN do caso |
| `NT5CB1*` (=`NT5CB12*`) | 194 | 128M×16 | 2Gb |
| `NT5CB2*` (=`NT5CB25*`) | 220 | 256M×16 | 4Gb |
| `NT5CB5*` (=`NT5CB51*`) | 133 | 512M×8 | 4Gb |
| `NT5CBC*` | 24 | não investigado | — |

Confirmei que **não existe variante 1024M/8Gb** (o sub-prefixo "1" é 100% `128M`, não `1024M`) — o
cluster `NT5CB` vai de 1Gb a 4Gb, ponto. `128M×16` (2Gb) e `256M×16`/`512M×8` (4Gb) **já tinham
known_part no catálogo local** (seed) — não resubmeti pra não duplicar (ver precheck no §5). O que
faltava e ficou coberto agora: **1Gb (64M16, o PN do caso) e a densidade 4Gb via 512M×8** (organização
diferente da 256M×16 já catalogada, mesma densidade).

`NT5CBC*` (24 resultados) não foi aberto — prefixo/sufixo fora do padrão M-x-largura, backlog.

## 3. known_parts submetidos (5)

| PN | Densidade | Interface | Rentabilidade (após aprovar, sandbox) | Fonte |
|---|---|---|---|---|
| **NT5CB64M16FP** (PN do caso) | 1Gb | x16 | **NÃO RENTÁVEL** | Alldatasheet |
| NT5CB64M16FP-DH | 1Gb | x16 | NÃO RENTÁVEL | Alldatasheet |
| NT5CB64M16FN-DHA | 1Gb | x16 | NÃO RENTÁVEL | Alldatasheet |
| NT5CB512M8CN | 4Gb | x8 | RENTÁVEL | Alldatasheet |
| NT5CB512M8CN-DI | 4Gb | x8 | RENTÁVEL | Alldatasheet |

**O chip que está na bancada agora (`NT5CB64M16FP`) é DDR3 1.5V de 1Gb — NÃO RENTÁVEL** pelo limiar atual
do `ProfitabilityConfig` (valor não citado aqui de propósito, é dado mutável — ver `NANYA.md` §4).

## 4. Validação em sandbox (mesma metodologia da rodada `NT5AD`)

1. `classify("NT5CB64M16FP")` ANTES de qualquer known_part → `known_exact=None, chip_type=None,
   family=None, profitable=None` — **reproduz exatamente o debug em branco do estoque**, confirmando o
   diagnóstico (não é só "sem capacidade", é "sem reconhecimento nenhum").
2. `submit_known_parts` dry-run → portão aceitou os 5.
3. `--commit` → gravou como `submitted` (oculto), `density_gbit` salvo certo (1Gb/4Gb).
4. Aprovação simulada + `classify()` de novo → os 5 saem `known_exact=True`, `chip_type=DDR3`,
   `dram_density` certo, rentabilidade conforme a tabela do §3.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cb.py   # ver abaixo — pega NT5CB128M16/256M16/256M8 já existentes
python manage.py submit_known_parts submissions/nanya_nt5cb_2026-07-15.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_2026-07-15.yaml --commit
# aprovar em /admin/chips/knownpart/ (filtro review_status → Submetido)
python manage.py guard_catalog
```

`precheck_nt5cb.py`:
```bash
cat > precheck_nt5cb.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = [
    "NT5CB64M16FP", "NT5CB64M16FP-DH", "NT5CB64M16FN-DHA",
    "NT5CB512M8CN", "NT5CB512M8CN-DI",
]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 5 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb.py
```

## 6. Backlog / próxima rodada (se o dono quiser mais NT5CB)

- **`NT5CBC*`** (24 resultados) — padrão de nome não investigado, pode ser variante/automotive.
- **Considerar `ChipFamily` type-only pra `NT5CB`** (sem decode de capacidade, igual `NT5AD`/`NT5CC`/
  `NT5PA`) — resolveria o "100% invisível" pra QUALQUER `NT5CB` futuro sem known_part, não só os 5 de
  hoje. É Trilha A (gramática), decisão à parte — sinalizando, não fiz sozinho.
- **`NT5CB128M16`/`NT5CB256M16`/`NT5CB256M8`** — prováveis já aprovados (estavam no seed local); o
  precheck acima confirma antes do commit.

## 7. Fontes completas

- https://www.alldatasheet.com/datasheet-pdf/pdf/1145458/NANYA/NT5CB64M16FP.html (PN do caso, forma base)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145464/NANYA/NT5CB64M16FP-DH.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145617/NANYA/NT5CB64M16FN-DHA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145481/NANYA/NT5CB512M8CN.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145485/NANYA/NT5CB512M8CN-DI.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CB (índice completo, 679 resultados, usado pra
  mapear a família inteira por sub-prefixo)
