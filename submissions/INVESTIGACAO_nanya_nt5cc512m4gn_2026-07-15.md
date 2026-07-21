# Investigação — Nanya `NT5CC512M4GN` (debug ao vivo do estoque) + cluster `NT5CC`, 2026-07-15

> ✅ **ATUALIZADO — resultado final: 5 known_parts `NT5CC` submetidos, todos `confirmed`.** A 1ª passada
> (§1) não achou fonte confiável pro PN exato do caso e não submeteu nada pra ele — Alldatasheet/Octopart
> não tinham "512M×4" no índice, só sites-espelho de baixo nível com atribuição de prefixo inconsistente
> (`NT5CB` vs `NT5CC`) pra mesma especificação. **O dono então indicou a fonte certa**
> (`datasheets360.com/part/detail/nt5cc512m4gn-cg/...`) — abri e verifiquei diretamente (não só o link, o
> CONTEÚDO da página): é uma ficha técnica estruturada dedicada (não resumo de busca), confirma
> Manufacturer=NANYA, Description="DDR3L DRAM, 512MX4 ... PBGA78", die "GN" (bate com o debug). **Adicionei
> ao mesmo submit**: `NT5CC512M4GN-CG`, 2Gb, x4, RENTÁVEL (validado em sandbox, ver §5). ⚠️ **Nuance
> importante**: o PN exato escaneado na bancada é `NT5CC512M4GN` (sem "-CG") — `normalize_pn` remove `-`
> mas não remove `CG`, então esse known_part NÃO dá match automático no PN sem o sufixo (confirmado em
> sandbox, §5 passo 8). Resolve o PN **se** a marcação física tiver o "-CG" (ou equivalente); senão seria
> necessário um known_part separado pra forma sem sufixo — sem fonte própria pra isso ainda, não inventei.
> Também identificado: **drift de ambiente** — o debug ao vivo mostra `Tipo: DDR3`, mas a gramática atual
> (yaml + `chips/tests.py`, "corrigido jul/2026") define `NT5CC` como **DDR3L**. Ver §4.

## 0. O gatilho

Debug do estoque, PN `NT5CC512M4GN`: reconhecido como Nanya via gramática (`known=true`,
`in_review_queue=false`), mas `capacity=null`, `dram_density=null`, `profitable=INDETERMINADO` — a
família `NT5CC` não decodifica capacidade (nenhuma das 3 famílias Nanya decodifica, ver `NANYA.md` §1),
então sem `known_part` exato o PN fica sem capacidade nenhuma. Instrução do dono: "mesmo trabalho" (mesma
tarefa da rodada `NT5CB` — identificar o PN do caso em Tier-1 + coletar todas as variantes da família).

## 1. `NT5CC512M4GN` — investigação exaustiva, resultado NEGATIVO

### 1.1 O que a busca inicial sugeriu

Um `WebSearch` inicial por `"NT5CC512M4GN" OR "NT5CC512M4GN-CG"` retornou um link para
`digchip.com/datasheets/parts/datasheet/3929/NT5CC512M4GN-CG.php` — um resumo gerado por IA descreveu
como "2Gb x4 DDR3 DRAM memory chip". Abri a página diretamente: **bloqueada por cookie-wall**, sem
conteúdo técnico real acessível (só o banner de cookies do site). Não é uma fonte que pude verificar.

Uma segunda busca encontrou `NT5CC512M4BN-CG` (die "BN", não "GN") no Datasheets360.com, Datasheetspdf.com
e Datasheet4u.com. **Mas outras duas dessas mesmas fontes** (`datasheets.com` e `prodisknetwork.com`)
atribuem a **especificação idêntica** (512M×4, PBGA78, 0.255ns, DDR3-1333, die B) ao prefixo **`NT5CB`**,
não `NT5CC`:

- "NT5CB512M4BN-CG - Nanya DDR3-1333MHz 512Mx4 (2GB) DRAM" (prodisknetwork.com)
- "Datasheets" → `nt5cb512m4bn-cg-nanya-technology` (datasheets.com)
- "NT5CB512M4BN DDR3 SDRAM B-Die Datasheet" (datasheet4u.com)

Duas fontes dizem `NT5CC`, três dizem `NT5CB`, para a mesma especificação exata. Isso é o padrão clássico
de contaminação entre sites-espelho de baixo nível (fácil confundir `NT5CB`↔`NT5CC` visualmente — o mesmo
risco que o `NANYA.md` §3 já documenta para humanos).

### 1.2 O que o índice PRIMÁRIO (Alldatasheet) mostra — decisivo

Busquei o prefixo `NT5CC` inteiro no Alldatasheet (o mesmo índice que mapeou o cluster `NT5CB` na rodada
anterior, historicamente confiável e completo neste projeto). Resultado: **610 resultados totais**,
quebrados em exatamente 4 sub-prefixos:

| Sub-prefixo | Resultados | Organização | Densidade |
|---|---|---|---|
| `NT5CC6*` | 100 | 64M×16 | 1Gb |
| `NT5CC1*` (=`NT5CC12*`) | 182 | 128M×16 | 2Gb |
| `NT5CC2*` | 204 | 256M×16 / 256M×8 | 4Gb |
| `NT5CC5*` (=`NT5CC51*`) | 124 | 512M×8 | 4Gb |
| **Soma** | **610** | — | — |

**100+182+204+124 = 610 — bate exato com o total, zero resultado sobrando.** Isso significa que o índice
do Alldatasheet **não tem NENHUM resultado** fora desses 4 buckets — se `NT5CC512M4*` existisse como PN
catalogado, apareceria como um 5º bucket e a soma não fecharia. Abri também o bucket `NT5CC512M4`
diretamente (`Searchword=NT5CC512M4`): retornou **"No Data"** em Match e Start-with — só
`NT5CC512M8*(124)` aparece como sugestão.

**Conferi o mesmo raciocínio no `NT5CB`** (cluster da rodada anterior, 679 resultados = 108+194+220+133+24,
também bate exato — ver `INVESTIGACAO_nanya_nt5cb64m16fp_2026-07-15.md` §2). Também sem sobra para
"512M4".

Busca direta no Octopart por `NT5CC512M4GN` também não achou o PN — caiu num "Did you mean: nt5ccb512" e
devolveu resultados de `NT5CC128M*`, não `NT5CC512M4`.

### 1.3 Conclusão

**Não submeti `NT5CC512M4GN` nem nenhuma variante "512M4" de `NT5CC`.** As duas fontes que eu trato como
mais confiáveis neste projeto (Alldatasheet — índice completo e reconciliado; Octopart — busca própria)
não têm nenhum registro dessa organização para `NT5CC` (nem para `NT5CB`). As referências que existem
vêm só de sites-espelho de terceiro nível, com atribuição de prefixo **inconsistente entre si** — não é
"não achei ainda", é "achei sinal contraditório o suficiente pra não confiar". Sigo a regra de sempre:
**excluir, não adivinhar** (ver `wtc-excluir-nao-adivinhar-known-part`). Hipóteses possíveis, sem forma de
decidir sozinho:

1. O PN real é `NT5CB512M4BN-CG` (não `NT5CC`) e a maioria das fontes-espelho erraram o prefixo — mas
   mesmo assim nenhuma fonte primária (Alldatasheet/Octopart) confirma isso para `NT5CB` também.
2. É um PN genuinamente raro/antigo (die "B", revisão inicial — plausível ser anterior à cobertura do
   Alldatasheet) que só sites-espelho menores indexaram, com erro de prefixo na transcrição.
3. A marcação física do chip na bancada foi lida/transcrita como "M4" mas é outra coisa (não é pra mim
   especular sobre isso — só sinalizo a possibilidade de conferir a peça física de novo, se o dono achar
   útil).

## 1.4 Correção — dono indicou a fonte certa, verificada e adicionada

O dono apontou `https://www.datasheets360.com/part/detail/nt5cc512m4gn-cg/-804841350957475624/`. Abri a
página diretamente (não só a URL — o conteúdo) e é uma **ficha técnica estruturada dedicada** (campos
Manufacturer/Part Category/Description/Status/specs, não um resumo de busca genérico):

```
Manufacturer:  NANYA TECHNOLOGY CORP
Part Category: DRAMs
Description:   DDR3L DRAM, 512MX4, 0.255ns, CMOS, PBGA78
Status:        Discontinued
Clock Frequency-Max (MHz): 667.00000
Access Mode:   MULTI BANK PAGE BURST
```

Isso confirma o die **"GN"** especificamente (o mesmo do debug ao vivo — diferente do die "BN" visto nas
fontes de baixo nível do §1.1, que continuam sem confirmação própria e **não** foram submetidas). Explica
também por que não apareceu no índice Alldatasheet usado no §1.2: `Status=Discontinued` — peça descontinuada,
plausivelmente fora do crawl mais recente daquele índice (que mostrou principalmente peças "Commercial,
Industrial and Automotive", um catálogo mais atual). **Adicionado ao mesmo arquivo de submissão** como PN
#5 — ver §2 e §5.

⚠️ **PN exato da bancada vs. PN confirmado — não são a mesma string.** O debug mostrou `NT5CC512M4GN` (sem
sufixo); a fonte confirma `NT5CC512M4GN-CG` (com sufixo de grade/velocidade). `normalize_pn` (código do
projeto) remove `-` mas não remove os caracteres "CG" — as formas normalizadas são `NT5CC512M4GN` vs.
`NT5CC512M4GNCG`, **strings diferentes**. Testei em sandbox (§5, passo 8): mesmo depois de aprovar o
known_part `NT5CC512M4GN-CG`, `classify("NT5CC512M4GN")` (a string exata do debug) continua
`known_exact=False`. Ou seja: **esta submissão resolve o chip na bancada SE a marcação física tiver o
"-CG" (ou equivalente) legível** — comum em códigos de grade que não vão no laser do encapsulamento, mas
não é algo que eu possa confirmar à distância. Se o dono conferir a peça física e o sufixo realmente não
estiver lá, seria necessário um known_part separado pra forma sem sufixo — não inventei essa entrada
paralela por falta de fonte própria para ela.

## 2. Cluster `NT5CC` — o que HÁ de sólido, coletado

Do mapeamento do §1.2, duas densidades **não tinham known_part real no catálogo local** (que só tinha
`128M16`/`256M16`/`256M8`, per rodada de onboarding): `64M16` (1Gb) e `512M8` (4Gb) — mesmo padrão exato
da rodada `NT5CB` anterior (lá também as densidades novas foram 1Gb e 4Gb). Submeti 2 PNs de cada:

| PN | Densidade | Interface | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|---|
| NT5CC64M16FN-DHA | 1Gb | x16 | **NÃO RENTÁVEL** | Alldatasheet |
| NT5CC64M16FP-DHA | 1Gb | x16 | NÃO RENTÁVEL | Alldatasheet |
| NT5CC512M8CN-DI | 4Gb | x8 | **RENTÁVEL** | Alldatasheet |
| NT5CC512M8CN-DIA | 4Gb | x8 | RENTÁVEL | Alldatasheet |
| **NT5CC512M4GN-CG** (die do PN do caso) | 2Gb | x4 | **RENTÁVEL** | Datasheets360 (§1.4, indicado pelo dono e verificado direto) |

Aritmética: `64M×16bit = 1024Mbit = 1Gb`; `512M×8bit = 4096Mbit = 4Gb` — mesma fórmula profundidade×largura
já validada nas 2 rodadas anteriores (`NT5AD`/`NT5CB`), agora também em `NT5CC`.

**Não há variante 1024M/8Gb** — nenhum sub-prefixo `NT5CC10*` aparece nos 610 resultados; o cluster
`NT5CC` vai de 1Gb a 4Gb, igual ao `NT5CB`.

## 3. ⚠️ Drift de ambiente encontrado: `DDR3` (debug ao vivo) vs. `DDR3L` (gramática atual)

**O debug ao vivo do usuário mostrou `Tipo: DDR3` para `NT5CC512M4GN`.** Mas a gramática atual
(`chips/knowledge/nanya.yaml`, linha do `NT5CC`) define `chip_type: DDR3L`, e `chips/tests.py` tem um
comentário explícito: *"NT5CC=DDR3L (1.35V), não DDR3 (corrigido jul/2026...)"* — ou seja, o valor `DDR3`
era o ANTIGO (errado), já corrigido no yaml/testes.

Reproduzi isso na sandbox: rodei `load_brands --brand nanya --commit` com o yaml ATUAL e chamei
`classify("NT5CC512M4GN")` — saída: **`chip_type='DDR3L'`** (não `DDR3`). Ou seja, o yaml certo já existe
no repositório, mas **o banco que serviu o debug ao vivo ainda não recebeu esse `load_brands --commit`** —
está desatualizado nesse ponto específico.

Corroboração externa: Datasheets360 categoriza o `NT5CC512M4BN-CG` (mesmo achado do §1.1) como **"DDR3L
DRAM"**, e o próprio Alldatasheet descreve TODA a família `NT5CC` como "Commercial, Industrial and
Automotive **DDR3(L)**" — reforça que `DDR3L` é o rótulo tecnicamente correto pro prefixo `NT5CC`.

**Não é um bug de código — é um passo de publicação pendente.** Rodar
`python manage.py load_brands --brand nanya --commit` no banco que serve esse debug deve corrigir o rótulo
imediatamente (reflete na hora, sem restart — regra de ouro #3 do `CLAUDE.md`). Sinalizando pro dono
decidir quando rodar; não é algo que eu (chat de marca) rodo.

## 4. Validação em sandbox (mesma metodologia das rodadas anteriores)

1. `load_brands --brand nanya --commit --skip-known-parts` (yaml atual) → aviso já conhecido (3 famílias
   sem fonte de densidade).
2. `classify("NT5CC512M4GN")` — reproduz o debate do §3: `known_exact=False, chip_type='DDR3L',
   capacity=None, profitable='INDETERMINADO', pn_not_in_db=True`. Mesma "forma" do debug ao vivo (sem
   capacidade/rentabilidade), confirmando `chip_type` = `DDR3L` na gramática atual (≠ `DDR3` do debug).
3. `submit_known_parts` dry-run → portão aceitou os 5 (incluindo `NT5CC512M4GN-CG` adicionado no §1.4).
4. `--commit` → gravou como `submitted` (oculto), `density_gbit` certo (1Gb/4Gb/2Gb), `chip_type=DDR3L`.
5. Aprovação simulada + `classify()` de novo → os 5 saem `known_exact=True`, `dram_density` certo,
   rentabilidade conforme a tabela do §2 (`NT5CC512M4GN-CG` → **RENTÁVEL**).
6. `classify("NT5CC512M4GN")` DE NOVO (PN exato do debug, SEM o sufixo "-CG", após aprovar os 5) →
   **continua sem mudança**: `known_exact=False, capacity=None, profitable='INDETERMINADO'`. Confirma na
   prática a nuance do §1.4: `normalize_pn` não equipara `NT5CC512M4GN` a `NT5CC512M4GNCG` — o known_part
   novo só resolve o chip na bancada se a marcação física incluir o sufixo "-CG" (ou o operador conseguir
   confirmar visualmente). Não é pra esconder essa limitação.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cc.py   # ver abaixo
python manage.py submit_known_parts submissions/nanya_nt5cc_2026-07-15.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_2026-07-15.yaml --commit
# aprovar em /admin/chips/knownpart/ (filtro review_status → Submetido)
python manage.py guard_catalog
```

`precheck_nt5cc.py`:
```bash
cat > precheck_nt5cc.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = [
    "NT5CC64M16FN-DHA", "NT5CC64M16FP-DHA",
    "NT5CC512M8CN-DI", "NT5CC512M8CN-DIA", "NT5CC512M4GN-CG",
]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 5 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cc.py
```

**Separadamente, se o dono quiser corrigir o drift do §3** (fora desta submissão, é a gramática que já
está versionada — só falta publicar):
```bash
export DATABASE_URL="<url do banco que serve o debug>"
python manage.py load_brands --brand nanya --commit
```

## 6. Backlog / próxima rodada

- **`NT5CC2*`** (256M, 204 resultados) não foi sub-dividido em 256M16 vs 256M8 nesta rodada — o catálogo
  local já parece ter ambos (per rodada de onboarding), então não priorizei; conferir com precheck antes
  de uma rodada futura caso o dono queira mais variantes de sufixo dessa densidade.
- **PN exato do caso sem sufixo (`NT5CC512M4GN`, sem "-CG") continua sem known_part dedicado** — o
  known_part novo (`NT5CC512M4GN-CG`) só resolve a bancada se a marcação física tiver o sufixo. Se o dono
  confirmar visualmente que a peça NÃO tem "-CG" legível, sinalizar de volta — aí sim consideraria (com
  fonte própria) um known_part separado pra forma sem sufixo.
- **Die "BN" (`NT5CB512M4BN-CG`/`NT5CC512M4BN-CG`, §1.1)** continua não submetido — só as fontes de baixo
  nível com atribuição de prefixo inconsistente, sem confirmação própria como a que veio pro die "GN".
- **Drift DDR3→DDR3L (§3)**: publicar `load_brands --brand nanya --commit` no banco que serve o debug ao
  vivo resolve o rótulo (não afeta rentabilidade, só o label `Tipo`).

## 7. Fontes completas

- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC&sField=2 (índice completo, 610 resultados,
  usado pra mapear a família inteira por sub-prefixo e provar a ausência de "512M4")
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC512M4&sField=2 ("No Data" — confirma ausência)
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CC6&sField=2 (bucket 64M, 100 resultados)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145618/NANYA/NT5CC64M16FN-DHA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145622/NANYA/NT5CC64M16FP-DHA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145491/NANYA/NT5CC512M8CN-DI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145573/NANYA/NT5CC512M8CN-DIA.html
- https://octopart.com/search?q=NT5CC512M4GN (sem match direto — "did you mean nt5ccb512")
- https://www.datasheets360.com/part/detail/nt5cc512m4gn-cg/-804841350957475624/ — **usada**, indicada
  pelo dono e verificada diretamente (§1.4): confirma `NT5CC512M4GN-CG`, DDR3L, 512M×4, PBGA78, die "GN"
- Fontes NÃO usadas para submissão (baixa confiança, atribuição inconsistente CB×CC, die "BN" diferente
  do "GN" confirmado): digchip.com (bloqueado por cookie-wall), datasheetspdf.com, datasheet4u.com,
  prodisknetwork.com, datasheets.com (versão "NT5CB")
