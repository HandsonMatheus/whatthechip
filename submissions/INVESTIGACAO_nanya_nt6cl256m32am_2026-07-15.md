# Investigação — Nanya `NT6CL256M32AM` (debug ao vivo do estoque) + família `NT6CL` nova, 2026-07-15

> ✅ **Resultado: família `NT6CL` (LPDDR3 mobile) criada na gramática + 6 known_parts submetidos.**
> Prefixo não existia no `nanya.yaml` — PN 100% invisível (pior que os casos anteriores, nem
> reconhecimento de tipo). Identifiquei em Tier-1 (datasheet oficial Nanya, tabela "Ordering
> Information"), descobri que a família usa empilhamento de die (SDP/DDP/QDP) codificado numa LETRA
> dentro do PN — achado novo, documentado em detalhe no §2. **Autocorreção importante no meio do
> trabalho:** a 1ª tentativa de submissão usava o campo errado (`density_gbit`, Gb/die) e dava
> `RENTÁVEL` pros 6 PNs; ao conferir a convenção usei `capacity` (GB/pacote, correta pra LPDDR avulso) e
> o resultado real é bem diferente — ver §4. O PN exato do caso (`NT6CL256M32AM`, 1GB) é **NÃO
> RENTÁVEL**.

## 0. O gatilho

Debug do estoque, PN `NT6CL256M32AM`: **100% em branco** (`known:false`, `in_review_queue:true`, todos
os campos do JSON `null`) — igual ao caso `NT5CB64M16FP` da 2ª rodada, mas por um motivo AINDA mais
básico: o prefixo `NT6CL` não existe em `nanya.yaml` (só `NT5AD`/`NT5CC`/`NT5PA`) — nem reconhecimento de
tipo. Instrução do dono: "mesmo trabalho" (identificar Tier-1 + coletar cluster).

## 1. `NT6CL256M32AM` identificado — Tier-1 direto, forma base é entrada própria

Busca inicial achou `NT6CL256M32AM-H1` — datasheet oficial Nanya via Alldatasheet. Mas o PN **exato** do
debug (`NT6CL256M32AM`, sem sufixo) também é uma entrada de catálogo própria e independente no
Alldatasheet (mesmo padrão já visto em `NT5CB64M16FP` na 2ª rodada):
`alldatasheet.com/datasheet-pdf/pdf/1145669/NANYA/NT6CL256M32AM.html` — "Commercial Mobile LPDDR3
8Gb(SDP) / 16Gb(DDP) SDRAM".

## 2. Achado novo — a LETRA depois da profundidade codifica o empilhamento (SDP/DDP/QDP)

A descrição do Alldatasheet ("8Gb(SDP) / 16Gb(DDP)") **parece** dizer que o PN é ambíguo entre duas
densidades — mas isso é só porque UM datasheet documenta VÁRIOS PNs junto. Abri a página 2 do datasheet
oficial diretamente (não o resumo, o CONTEÚDO real — "Ordering Information", tabela oficial Nanya):

```
LPDDR3 8Gb(SDP)/16Gb(DDP) SDRAM        8Gb: NT6CL256M32AM(Q)      16Gb: NT6CL512T32AM(Q), NT6CL256T64AR(4)

Density      Organization    Part Number              Package        Speed
8Gb  (SDP)   256M x 32       NT6CL256M32AQ-H11         168-Ball PoP   1866 Mb/s/pin
                             NT6CL256M32AM-H01         178-Ball       2133 Mb/s/pin
                             NT6CL256M32AM-H1                         1866 Mb/s/pin
16Gb (DDP)   512M x 32       NT6CL512T32AQ-H11         168-Ball PoP   1866 Mb/s/pin
                             NT6CL512T32AM-H01         178-Ball       2133 Mb/s/pin
                             NT6CL512T32AM-H1                         1866 Mb/s/pin
             256M x 64(2-CH) NT6CL256T64AR-H11         216-Ball PoP   1866 Mb/s/pin
                             NT6CL256T64A4-H11         256-Ball PoP   1866 Mb/s/pin
```

**A cada PN individual corresponde UMA densidade só** — a letra logo depois do número de profundidade
diz qual:

| Letra | Significado | Exemplo | Aritmética |
|---|---|---|---|
| `M` | SDP — 1 die | `256M32` | 256M × 32bit = 8192Mbit = 8Gb (1 die) |
| `T` | DDP — 2 dies empilhados | `512T32` | 512 × 32bit = 16384Mbit = 16Gb (2 dies) |
| `F` | QDP — 4 dies empilhados | `1024F32` | 1024 × 32bit = 32768Mbit = 32Gb (4 dies) |

O PN do caso (`NT6CL256M32AM`) usa a letra **"M"** → **SDP, 8Gb de die, 1GB de pacote — não é
ambíguo.** Esse achado (letra de profundidade = multiplicador de die) é novo neste projeto — as famílias
Nanya vistas até agora (`NT5AD`/`NT5CB`/`NT5CC`) são discretas de 1 die só, sem essa dimensão.

**Não virou mecanismo de decode automático** (`decode_cap_map`) — o mecanismo atual do engine é só
tabela de posição→valor, não suporta "ler uma letra como multiplicador"; precisaria de lógica nova no
`engine.py`, fora do escopo do chat de marca. Sinalizando como possível melhoria futura, com aval do
dono. Por ora, cada PN entra individualmente como `known_part`.

## 3. Família nova na gramática — `NT6CL`

Adicionei ao `nanya.yaml` (Trilha A): `chip_type: LPDDR3`, `subtype: LPDDR3`, sem decode de capacidade
(mesmo padrão magro das outras 3 famílias — "reconhece o tipo, capacidade só via known_part"),
`reasoning` preenchido citando a tabela Ordering Information (as 3 famílias antigas não tinham
`reasoning` — não mexi nelas, fora do escopo de hoje). **Golden obrigatório**: adicionei
`'NT6CL256M32AM': ('LPDDR3', '', '', '', '', 'INDETERMINADO')` ao `_NANYA_GOLDEN` em `chips/tests.py`
— confirma que a família sozinha (sem known_part) reconhece o TIPO mas fica `INDETERMINADO` até ter
known_part, igual às outras 3.

## 4. ⚠️ Autocorreção — campo errado na 1ª tentativa (Gb/die vs GB/pacote)

Na 1ª versão da submissão usei `density_gbit` (ex.: `"8Gb"`) — o mesmo campo que uso pra `NT5AD`/
`NT5CB`/`NT5CC` (DDR discreta). Validei em sandbox e os 6 PNs saíram **todos `RENTÁVEL`**, incluindo o de
menor capacidade (4Gb) — resultado suspeito. Reli o `CLAUDE.md` §6 (tabela de convenção de campos):

> **LPDDR avulso** | a geração ("LPDDR4"/"LPDDR4X"/"LPDDR5"…) | espelha o `chip_type` | **`capacity` =
> pacote em GB** | "LPDDR4+4GB"

Ou seja: **LPDDR "avulso" (não-eMCP) usa `capacity` em GB (pacote), não `density_gbit` em Gb
(die)** — diferente de `NT5AD`/`NT5CB`/`NT5CC` (DDR discreta), que usam `density_gbit`. Conferi também
no `chips/engine.py` (bloco `_fam == "lpddr"`, linha ~1192):
`cap_gb = _extract_gib(result.get("capacity") or result.get("dram_density") or "")` — o limiar de
rentabilidade pra LPDDR3 avulso é **`< 2GB → NÃO RENTÁVEL`** (comentário do próprio código, linha 1059).
Com `density_gbit="4Gb"` sem `capacity`, o engine caiu no fallback `dram_density` (string tipo "4Gb por
die"), que aparentemente extraiu um número maior do que devia — dando `RENTÁVEL` incorretamente pros 6.

**Corrigido**: reescrevi a submissão usando `capacity` (GB, convertendo Gb→GB ÷8) e re-validei em
sandbox — resultado agora bate com o limiar documentado (ver tabela §5). **Se eu não tivesse conferido a
convenção antes de entregar, o PN exato da bancada (1GB) teria sido aprovado como RENTÁVEL quando na
verdade é NÃO RENTÁVEL** — o tipo de erro que este processo de validação em sandbox existe pra pegar
antes de chegar no dono.

## 5. known_parts submetidos (6) — capacidade corrigida

| PN | Organização | Capacidade (pacote) | Empilhamento | Rentabilidade (sandbox, pós-aprovação) |
|---|---|---|---|---|
| **NT6CL256M32AM** (PN do caso) | 256M×32 | **1GB** | SDP (1 die) | **NÃO RENTÁVEL** |
| NT6CL256M32AM-H01 | 256M×32 | 1GB | SDP | NÃO RENTÁVEL |
| NT6CL256M32AM-H1 | 256M×32 | 1GB | SDP | NÃO RENTÁVEL |
| NT6CL512T32AM-H1 | 512×32 | 2GB | DDP (2 dies) | **RENTÁVEL** |
| NT6CL128M32DM | 128M×32 | 512MB | SDP | NÃO RENTÁVEL |
| NT6CL1024F32AP | 1024×32 | 4GB | QDP (4 dies) | RENTÁVEL |

**O chip que está na bancada agora (`NT6CL256M32AM`) é LPDDR3 mobile de 1GB — NÃO RENTÁVEL** (abaixo do
limiar de 2GB pra LPDDR3 avulso, `ProfitabilityConfig` — valor não citado de propósito, é dado mutável).

`NT6CL512T32AM-H1` e `NT6CL1024F32AP` (RENTÁVEL) são fisicamente PEÇAS DIFERENTES do PN do caso — mesma
organização base (256M×32/1024×32) mas mais dies empilhados no encapsulamento, não a mesma peça
escaneada na bancada. Incluí pra dar cobertura ao cluster inteiro (SDP/DDP/QDP), não porque resolvem o
caso específico de hoje.

## 6. Validação em sandbox (migrate → load_brands com família nova → golden → submit → aprova → reclassify)

1. `load_brands --brand nanya --commit --skip-known-parts` (yaml com `NT6CL` novo) → família criada sem
   erro; aviso de "sem density source" não se aplica a `NT6CL` (é tipo LPDDR, não DDR-kind).
2. **GOLDEN check**: `classify("NT6CL256M32AM")` só com gramática → `('LPDDR3', '', '', '', '',
   'INDETERMINADO')` — bate exatamente com o anchor adicionado em `chips/tests.py`. `known_exact=False`
   mas já reconhece `chip_type=LPDDR3` (antes da família existir, isso era `None` — melhoria real mesmo
   sem known_part).
3. `submit_known_parts` dry-run → portão aceitou os 6 (após a correção do §4).
4. `--commit` → gravou como `submitted` (oculto).
5. Aprovação simulada + `classify()` de novo → os 6 saem `known_exact=True`, `capacity` certo em GB,
   rentabilidade conforme a tabela do §5 (confirmado NÃO ser mais todo-RENTÁVEL).

**Observação (mesmo bug já reportado nas rodadas anteriores, não é novo):** `interface="x32"` gravado
nos known_parts não aparece no `classify()` (`interface` sai `''`) — mesma causa já reportada
(família com `interface=''` não repassa o do known_part). Não mexi em `engine.py`.

## 7. Comandos para o dono

Esta rodada tem **as DUAS trilhas** (gramática nova + known_parts) — publicar em ordem:

```bash
# Trilha A — gramática (família NT6CL nova + golden em tests.py):
git add chips/knowledge/nanya.yaml chips/tests.py
git commit -m "catalog: nanya +familia NT6CL (LPDDR3 mobile, SDP/DDP/QDP)"
git push origin main
python manage.py test chips --settings=core.settings_test   # roda o golden novo, deve passar
# publica no banco de prod (local, apontando DATABASE_URL ao Render):
python manage.py load_brands --brand nanya --commit

# Trilha B — known_parts (precheck antes, depois submit):
python manage.py shell < precheck_nt6cl.py
python manage.py submit_known_parts submissions/nanya_nt6cl_2026-07-15.yaml
python manage.py submit_known_parts submissions/nanya_nt6cl_2026-07-15.yaml --commit
# aprovar em /admin/chips/knownpart/ (filtro review_status → Submetido)
python manage.py guard_catalog
```

`precheck_nt6cl.py`:
```bash
cat > precheck_nt6cl.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = [
    "NT6CL256M32AM", "NT6CL256M32AM-H01", "NT6CL256M32AM-H1",
    "NT6CL512T32AM-H1", "NT6CL128M32DM", "NT6CL1024F32AP",
]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 6 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt6cl.py
```

## 8. Backlog / próxima rodada

- **Mecanismo de decode automático pro empilhamento SDP/DDP/QDP** (§2) — exigiria lógica nova no
  engine (ler letra como multiplicador), fora do escopo do yaml; sinalizando, não decidi sozinho.
- **`NT6CL256M16*`/`NT6CL256T64*`** (x16 e 2-canal/x64) — vistos na busca mas não submetidos nesta
  rodada (fora do organismo do PN do caso, x32); considerar se aparecer um PN de bancada.
- **`NT6CL2*`/`NT6CL5*`** (buckets Alldatasheet ainda não totalmente abertos) — mapeados por descrição
  agregada, não PN a PN; suficiente pra esta rodada mas dá pra aprofundar.
- **Outros prefixos `NT6*`** (`NT6AN`=LPDDR legado, `NT6AP`=LPDDR4X, `NT6TL`=LPDDR2 — vistos de relance
  na seção "Similar Description" do Alldatasheet) — família Nanya mobile é maior do que só `NT6CL`;
  backlog pra rodada futura se aparecer PN de bancada.

## 9. Fontes completas

- https://www.alldatasheet.com/datasheet-pdf/pdf/1145669/NANYA/NT6CL256M32AM.html (PN do caso, forma base)
- https://www.alldatasheet.com/html-pdf/1145677/NANYA/NT6CL256M32AM-H1/373/2/NT6CL256M32AM-H1.html
  (página 2 do datasheet oficial — tabela "Ordering Information", fonte do achado do §2)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145686/NANYA/NT6CL256M32AM-H0NA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145677/NANYA/NT6CL256M32AM-H1.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145668/NANYA/NT6CL128M32DM.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145670/NANYA/NT6CL1024F32AP.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT6CL&sField=2 (índice do prefixo, 113 resultados)
- https://www.alldatasheet.com/view.jsp?Searchword=NT6CL2&sField=2 (bucket 45 resultados)
- CLAUDE.md §6 (convenção de campos — LPDDR avulso usa `capacity`, não `density_gbit`)
- `chips/engine.py` linha ~1177 (bloco `_fam == "lpddr"`, limiares de rentabilidade)
