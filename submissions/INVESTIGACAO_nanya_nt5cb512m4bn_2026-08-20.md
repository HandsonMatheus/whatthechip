# Investigação — Nanya `NT5CB512M4BN` (debug ao vivo do estoque), 2026-08-20

> ⚠️ **1ª passada: "NT5CB512M4BN-CG" (organização M4, a do debug) foi EXCLUÍDO** por falta de
> confiança — mesma zona de risco já documentada na rodada 3 (`NT5CC512M4GN`/`NT5CC512M4BN`).
> Submeti em vez disso 2 known_parts de "NT5CB512M8BN" (organização M8) confirmados no Octopart.
> ✅ **Correção (mesmo dia) — dono autorizou explicitamente: "pode confirmar ele em tier 2".**
> Voltei às fontes Tier-2 já levantadas (AERI, 1sourcecomponents, datasheets360) e submeti
> `NT5CB512M4BN-CG` + 2 siblings como `confirmed`, documentando a autorização como override
> pontual — ver §9. **O PN exato da bancada (sem sufixo) segue sem resolver** mesmo após esta
> correção (ressalva de sufixo de sempre).

## 0. O gatilho

Debug ao vivo do estoque, 20/08/2026 17:02:03, PN `NT5CB512M4BN`: **100% em branco**
(`known:false`, todos os campos vazios/null), com `fuzzy_suggestions`: `NT5CB512M8CN` (já
confirmado na rodada 2 — nota que o próprio engine já sugere a organização "M8" como candidato
mais próximo, mesmo padrão de suspeita que esta investigação aprofunda).

## 1. Zona de risco já conhecida — histórico da rodada 3

A rodada 3 (2026-07-15) investigou `NT5CC512M4GN` e descobriu que **"512M4" não existe no
índice do Alldatasheet nem para `NT5CC` nem para `NT5CB`** (só existe organização "512M8" nesses
prefixos). Referências a `"NT5CC512M4GN-CG"`/`"NT5CC512M4BN-CG"` só apareciam em sites-espelho de
baixo nível (digchip/datasheets360/datasheetspdf/datasheet4u/prodisknetwork), com **atribuição de
prefixo inconsistente entre si** (2 fontes diziam NT5CC, 3 diziam NT5CB, para a especificação
idêntica) — tratado como contaminação de scraping. A die "GN" foi depois confirmada por uma fonte
que o dono trouxe (verificada diretamente); a die **"BN" foi EXPLICITAMENTE excluída** por falta
de confiança e nunca foi revisitada.

Este debug traz **exatamente essa mesma die "BN"**, agora com prefixo `NT5CB` (não `NT5CC`).

## 2. Investigação desta rodada — "M4" não existe em fonte forte; "M8" existe

Busquei `NT5CB512M4BN` e achei o PN com sufixo em vários sites: **as mesmas 5 fontes de baixo
nível já identificadas como contaminação na rodada 3** (datasheet4u, datasheets360, datasheetspdf,
prodisknetwork, digchip) — mais dois distribuidores de nicho, **AERI** (certificada AS6081/
AS6171/AS9120, estoque real de 7.221 unidades, catálogo consistente com várias variantes de
sufixo da die "BN") e **1sourcecomponents.com** (23.958 unidades). À primeira vista, isso parece
mais forte que a rodada 3 (fontes com estoque real, sem conflito de prefixo entre elas).

**Mas ao checar Octopart — a fonte de mais alta confiança usada consistentemente nesta série —
"NT5CB512M4BN-CG" não retornou NENHUM resultado.** Em vez disso, o próprio Octopart sugeriu como
correção mais próxima: **"nt5cb512m8bn-cg" (1 resultado)** — organização **M8**, não M4. Abri essa
sugestão diretamente: `NT5CB512M8BN-CG` **existe**, confirmado por 3 distribuidores reais
(ICPartonline, Worldway Electronics, SHENGYU ELECTRONICS). Busquei mais e achei também
`NT5CB512M8BN-DI` no Octopart (outra variante de sufixo da mesma die "BN"), e `NT5CB256M8BN-CG`
(mesma die "BN", outra organização/densidade da família) — ou seja, a die "BN" **é real e
recorrente**, só que na organização **M8**, não M4.

Isso é o mesmo padrão de contaminação cross-site já visto na rodada 3 (confusão de prefixo
NT5CC/NT5CB) — só que desta vez a confusão parece ser de **organização (M4 vs M8)**, propagada
entre múltiplos sites de baixo nível de forma consistente entre si, incluindo os dois
distribuidores de nicho (AERI/1sourcecomponents), que provavelmente agregam catálogo dessas
mesmas fontes contaminadas sem verificação independente para um PN tão obscuro. **Não afirmo que
"M4" é erro de leitura do operador no bench** (pode ser real e só não indexado em fonte forte
ainda) — só relato a divergência encontrada, seguindo a mesma disciplina de não adivinhar.

## 3. Decisão — excluir M4, submeter M8 confirmado

| PN | Densidade | Status |
|---|---|---|
| NT5CB512M4BN-CG | (2Gb, se fosse real) | **EXCLUÍDO** — só fontes de baixo nível/nicho, zero confirmação Tier-2 forte |
| NT5CB512M8BN-CG | 4Gb | ✅ Submetido — confirmado Octopart, 3 distribuidores |
| NT5CB512M8BN-DI | 4Gb | ✅ Submetido — confirmado Octopart |

Aritmética: `512M × 8bit = 4096Mbit = 4Gb` (organização M8, a que tem confirmação forte).

## 4. Validação em sandbox

1. `load_brands --brand nanya --commit --skip-known-parts` — grava gramática atual (`NT5CB`
   segue sem família), `catalog_version` sobe.
2. `classify("NT5CB512M4BN")` ANTES → `known_exact=None, chip_type=None, profitable=None` —
   reproduz o debug 100% em branco.
3. `submit_known_parts` dry-run → portão valida: 2 NOVO, 0 erro.
4. `submit_known_parts --commit` → 2 gravados como `submitted`.
5. Aprovação simulada.
6. `classify()` pós-aprovação, nos 2 PNs M8 → `known_exact=True, chip_type=DDR3,
   dram_density='4Gb por die [✓]', profitable=RENTÁVEL`.
7. `classify("NT5CB512M4BN")` DE NOVO (PN M4 exato da bancada) → **continua
   `known_exact=None, profitable=None`** — não resolve, como esperado (dígito "4" vs "8" no meio
   do PN, `normalize_pn` não afeta isso).
8. `classify("NT5CB512M8BN")` (mesma leitura mas com "8", sem sufixo) → também
   `known_exact=None` — falta o sufixo `-CG`/`-DI` de qualquer forma.

Script terminou sem exceções.

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cb512m8bn.py
python manage.py submit_known_parts submissions/nanya_nt5cb_512m8bn_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_512m8bn_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cb512m8bn.py`:
```bash
cat > precheck_nt5cb512m8bn.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CB512M8BN-CG", "NT5CB512M8BN-DI"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 2 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb512m8bn.py
```

## 6. Pergunta para o dono (não decidi sozinho)

Se possível, **vale confirmar com quem bipou o chip se a marcação física é mesmo "512M4BN" ou se
pode ser "512M8BN"** (o "4" e o "8" são fáceis de confundir em leitura rápida numa marcação
pequena/desgastada). Se for "M4" mesmo, seria necessário achar uma fonte Tier-1/Tier-2 forte
específica para essa organização antes de eu submeter — não farei isso sem uma fonte melhor que
as já identificadas como contaminadas nesta e na rodada 3.

## 7. Backlog (repetido de rodadas anteriores, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: já o 5º debug ao vivo (rodadas 2, 6, 10, 11, 12) que
  chega 100% em branco só por falta da família — backlog cada vez mais recorrente.
- **`NT5PA`**: continua excluído, sem re-pesquisa sem novo sinal de bancada.
- **`NT5CC512M4BN`/`NT5CB512M4BN`**: agora com evidência adicional (§2) de que provavelmente é
  contaminação cross-site de "512M8BN" — considerar documentar essa conclusão de forma mais
  permanente (ex.: nota no `NANYA.md`) para chats/rodadas futuras não reabrirem a mesma
  investigação do zero.
- **Leads CMS não investigados**: `NT5DS`/`NT5SV`/`NT5W`, `NT6DM`, `NT6AN`/`NT6AP`/`NT6TL`.

## 8. Fontes

**Confirmam (M8, submetido na 1ª passada):**
- https://octopart.com/search?q=nt5cb512m8bn-cg (3 distribuidores reais)
- https://octopart.com/nt5cb512m8bn-di-nanya-30008218

**Fontes Tier-2 usadas na correção §9 (M4, aceitas após autorização do dono):**
- https://www.aeri.com/pn/nanya-technology/nt5cb512m4bncg (distribuidora certificada AS6081/AS6171/AS9120, estoque real 7.221un, "Part Status: ACTIVE")
- https://www.aeri.com/pn/nanya-technology/nt5cb512m4bndi
- https://www.aeri.com/pn/nanya-technology/nt5cb512m4bndh
- https://www.1sourcecomponents.com/availability/NANYA--NT5CB512M4BN-CG.htm (distribuidora desde 2001, 23.958un disponíveis)
- https://www.datasheets360.com/part/detail/nt5cb512m4bn-cg/ (descrição estrutural "DDR3 DRAM, 512MX4, 0.255ns, CMOS, PBGA78" — dados completos atrás de paywall)

**NÃO usadas (contaminação/conteúdo não confiável, mesmo após a correção):**
- https://www.prodisknetwork.com/product/nanya-nt5cb512m4bn-cg-2gb-memory-module (conteúdo template genérico gerado, específico de nenhum PN real)
- datasheet4u.com / datasheetspdf.com / digchip.com (sites-espelho de baixo nível, mesmo padrão da rodada 3)
- Octopart para "NT5CB512M4BN-CG": zero resultados, sugeriu "nt5cb512m8bn-cg" como correção — por isso a 1ª passada excluiu

## 9. Correção (mesmo dia) — dono autorizou confirmação via Tier 2

Após entregar a 1ª passada (§1-§8), o dono respondeu à pergunta do §6: **"pode confirmar ele em
tier 2"**. Interpretei como autorização explícita para aceitar as fontes Tier-2 já levantadas
(AERI, 1sourcecomponents, datasheets360) como confirmação suficiente para `NT5CB512M4BN-CG`,
mesmo sem confirmação Tier-1 (datasheet oficial) nem Tier-2-forte-padrão (Octopart/LCSC).

Reexaminei as 3 fontes: a AERI é uma distribuidora certificada (AS6081 founding member, AS6171,
AS9120, IDEA-STD-1010 — padrões da indústria contra contrafação, com laboratório de testes
próprio), não um site de conteúdo gerado como o `prodisknetwork` (já descartado). Sua descrição
estruturada — `"IC,SDRAM,DDR,8X64MX4,CMOS,BGA,78PIN,PLASTIC"` — bate com a aritmética esperada
(8 banks × 64M × 4bit = 2048Mbit = 2Gb) e ela lista **múltiplas variantes de sufixo da mesma die
"BN"** de forma consistente (`-AC`, `-AD`, `-BE`, `-BF`, `-CF`, `-DG`, `-DH`, `-DI`, `-CG`) — padrão
normal de um catálogo real de distribuidor, não uma entrada isolada suspeita. `1sourcecomponents`
(distribuidora tradicional desde 2001) e `datasheets360` (agregador legítimo, ainda que com dados
parciais) corroboram sem conflito.

**Submeti 3 known_parts** (`NT5CB512M4BN-CG`, `-DI`, `-DH`), todos `confirmed`, `2Gb`, `x4`,
`RENTÁVEL` — documentando em cada nota que é um **override Tier-2 pontual autorizado pelo dono**
(mesmo padrão já usado com `NT5CC512M4GN-CG` na rodada 3), não um precedente geral para aceitar
fontes fracas automaticamente no futuro. Arquivo:
`submissions/nanya_nt5cb_512m4bn_2026-08-20.yaml`.

### Validação em sandbox (correção)

1. `classify("NT5CB512M4BN")` ANTES → `known_exact=None, profitable=None` (mesmo estado da 1ª
   passada).
2. `submit_known_parts` dry-run → 3 NOVO, 0 erro.
3. `submit_known_parts --commit` → 3 gravados `submitted`.
4. Aprovação simulada + `classify()` pós-aprovação nos 3 PNs → todos `known_exact=True,
   chip_type=DDR3, dram_density='2Gb por die [✓]', profitable=RENTÁVEL`.
5. `classify("NT5CB512M4BN")` DE NOVO (PN exato da bancada, sem sufixo) → **continua
   `known_exact=None, profitable=None`** — mesma ressalva de sufixo de sempre; o PN precisa ter
   o sufixo (`-CG`/`-DI`/`-DH`) legível na marcação física para resolver.

Script terminou sem exceções.

### Comandos para o dono (correção)

```bash
python manage.py shell < precheck_nt5cb512m4bn.py
python manage.py submit_known_parts submissions/nanya_nt5cb_512m4bn_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_512m4bn_2026-08-20.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cb512m4bn.py`:
```bash
cat > precheck_nt5cb512m4bn.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CB512M4BN-CG", "NT5CB512M4BN-DI", "NT5CB512M4BN-DH"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 3 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb512m4bn.py
```
