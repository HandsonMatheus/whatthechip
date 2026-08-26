# Investigação — Nanya `NT5CC256M8GN` (debug ao vivo do estoque) + gap 256M8/2Gb, 2026-08-20

> ✅ **Resultado: 4 known_parts submetidos, todos `confirmed`, todos `RENTÁVEL` (2Gb DDR3L).**
> Densidade `256M×8=2Gb` era um gap total na família `NT5CC` (rodadas anteriores cobriram
> `64M16`/1Gb, `512M8`/4Gb e `512M4`/2Gb via organização diferente — 512×4, não 256×8).
> ⚠️ **PN exato da bancada (`NT5CC256M8GN`, sem sufixo) NÃO resolve** com o known_part
> submetido — mesma ressalva de sufixo já documentada nas rodadas `NT6CL`/`NT5CB`. Ver §3.

## 0. O gatilho

Debug ao vivo do estoque, 20/08/2026 11:38:09, PN `NT5CC256M8GN`: reconhecido pela gramática
(família `NT5CC` já existe, `chip_type`/`subtype` = DDR3L) mas `known_exact:false`,
`pn_not_in_db:true`, `capacity:null`, `profitable:"INDETERMINADO"`, `confidence:"estimated"`,
sem `fuzzy_suggestions`. Ou seja: a família reconhece o prefixo, mas não tem nenhum known_part
que cubra essa organização — igual ao padrão já visto para `256M16` (rodada `NT5CB`) antes de
ser coberto.

## 1. Aritmética e identificação do cluster

`256M × 8bit = 2048Mbit = 2Gb` — densidade nova dentro da família `NT5CC`, nunca coberta antes.

Índice do Alldatasheet pro bucket `NT5CC256M8*`: **80 resultados totais**, reconciliados exatos
por die letter — `F(4) + I(38) + J(38) = 80`. **Sem bucket "G"** — mesmo padrão já visto três
vezes nesta série (`NT6CL512M4GN-CG`, `NT5CB256M16BP-DI/-CG`): die real, mas fora do crawl
daquele índice específico, não uma peça inexistente.

## 2. `NT5CC256M8GN-DI` — die "G" confirmada por 3 fontes convergentes (não pelo Alldatasheet)

Como a die "G" não aparece no índice do Alldatasheet, busquei corroboração fora dele antes de
submeter:

1. **Octopart** — página aberta diretamente (não resumo de busca): peça listada com estoque
   real em 5 distribuidoras (Win Source, ICPartonline, Worldway, YIC, IC Components).
2. **Busca técnica dedicada** — descrição convergente: "2Gb DDR3L SDRAM 256Mx8 1.35V, 78-pin
   VFBGA".
3. **Wikimedia Commons** — nome de arquivo de uma foto real: `Kingston_ACR16D3LS1NGG-4G_-
   _Nanya_NT5CC256M8GN-DI-0021.jpg`, ou seja fotografia de um chip físico com essa marcação
   exata soldado num módulo Kingston real — evidência fotográfica, não só listagem de banco de
   dados. (O fetch direto da página do Wikimedia voltou vazio — provavelmente renderizada via
   JS — então usei o nome do arquivo como corroboração adicional, não como fonte primária
   isolada; as outras duas fontes já eram suficientes por si.)

As 3 fontes convergem sem conflito entre si (mesma organização, mesma tensão 1.35V = DDR3L).
Aritmética bate: `256M × 8bit = 2048Mbit = 2Gb`.

## 3. ⚠️ PN exato sem sufixo — ressalva de sufixo (repetida, confirmada em sandbox)

Não achei `NT5CC256M8GN` (sem sufixo) como entrada própria em nenhuma fonte. `normalize_pn`
remove só caracteres não-alfanuméricos (`-`), não reconcilia formas com/sem sufixo de letras:
`NT5CC256M8GN` (PN da bancada) normaliza diferente de `NT5CC256M8GNDI`. Confirmado em sandbox
(§4, passo 7): mesmo depois de aprovar os 4 known_parts, `classify("NT5CC256M8GN")` continua
`known_exact=False, profitable=INDETERMINADO`. **Resolve o chip físico SE a marcação tiver o
"-DI" (ou similar) legível** — mesma ressalva de todas as rodadas anteriores com sufixo.

## 4. known_parts submetidos (4) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CC256M8GN-DI | 2Gb | RENTÁVEL | Octopart + busca técnica + foto Wikimedia (3 fontes) |
| NT5CC256M8FN-DI | 2Gb | RENTÁVEL | Alldatasheet |
| NT5CC256M8IN-DI | 2Gb | RENTÁVEL | Alldatasheet |
| NT5CC256M8IN-EK | 2Gb | RENTÁVEL | Alldatasheet |

Passos rodados em sandbox isolado (SQLite descartável, `core.settings_test`):

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual (yaml com
   `NT6CL`/`NT5TU` já incluídos das rodadas anteriores), `catalog_version` sobe.
2. `classify("NT5CC256M8GN")` ANTES → `known_exact=False, chip_type='DDR3L', capacity=None,
   profitable='INDETERMINADO', pn_not_in_db=True` — reproduz o debug ao vivo exatamente.
3. `submit_known_parts` dry-run → portão valida: 4 NOVO, 0 COMPLEMENTO, 0 IGUAL, 0 erro.
4. `submit_known_parts --commit` → 4 gravados como `submitted`.
5. Aprovação simulada (`review_status="approved"` direto na tabela, equivalente ao admin).
6. `classify()` pós-aprovação, nos 4 PNs → todos `known_exact=True, chip_type=DDR3L,
   dram_density='2Gb por die [✓]', profitable=RENTÁVEL`.
7. `classify("NT5CC256M8GN")` DE NOVO (PN exato da bancada, sem sufixo) → **continua
   `known_exact=False, profitable=INDETERMINADO`** — confirma a ressalva do §3 na prática.

Script terminou sem exceções.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cc256m8.py
python manage.py submit_known_parts submissions/nanya_nt5cc_256m8_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_256m8_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cc256m8.py`:
```bash
cat > precheck_nt5cc256m8.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CC256M8GN-DI", "NT5CC256M8FN-DI", "NT5CC256M8IN-DI", "NT5CC256M8IN-EK"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 4 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cc256m8.py
```

## 6. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: decisão ainda pendente do dono, não decidida
  sozinho (mesma sinalização das rodadas 2 e 6).
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, e prefixos vistos de passagem
  (`NT6DM` Mobile DDR 1ª geração, `NT6AN`/`NT6AP`/`NT6TL` outras gerações LPDDR) — backlog,
  sem reabrir sem novo sinal.

## 7. Fontes

- https://octopart.com/search?q=NT5CC256M8GN-DI (ficha estruturada, aberta diretamente)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1132516/NANYA/NT5CC256M8FN-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145482/NANYA/NT5CC256M8IN-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145483/NANYA/NT5CC256M8IN-EK.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC256M8&sField=2 (80 resultados, sem die "G")
- Wikimedia Commons: arquivo `Kingston_ACR16D3LS1NGG-4G_-_Nanya_NT5CC256M8GN-DI-0021.jpg` (nome
  de arquivo como corroboração; fetch direto da página não retornou conteúdo utilizável)
