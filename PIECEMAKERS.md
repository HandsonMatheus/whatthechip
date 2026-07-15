> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da PieceMakers (famílias + decode maps)
> vive em **`chips/knowledge/piecemakers.yaml`** (via `load_brands`). Os **known_parts** (PNs
> confirmados = autoridade) **NÃO ficam no yaml** — vivem no **banco**, submetidos por
> `submit_known_parts` e **aprovados pelo dono** no admin (four-eyes). **Processo obrigatório
> completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados (decode key→valor, inventário de
> famílias, known_parts): esses vivem no **yaml** (gramática) e no **banco** (known_parts). Aqui
> ficam: **convenções, anatomia do PN, armadilhas, rentabilidade, fontes, o *porquê*** e ponteiros.

---

# PIECEMAKERS.md — Bíblia Técnica e de Negócio

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/piecemakers.yaml`). Regras gerais do WTC: `CLAUDE.md`.

**PieceMakers Technology** — Taiwan (Hsinchu), fabless DRAM design, fundada 2006 (fundador
Tah-Kang Joseph Ting, +40 anos de IC, +60 patentes). ISO 9001/14001. Linha: **standard DRAM**
(SDR, DDR, DDR2, DDR3, DDR3L, DDR4) + PSRAM/KGD/HBLL-RAM (nicho — sem PN visto na bancada ainda).
Fabricante **pequeno e pouco documentado** perto de Samsung/Hynix/Micron — aparece esporádico na
esteira, e é exatamente por isso que **dado escasso + IA que alucina specs** é o risco nº1 (§3). A
gramática vive em **8 famílias / 1 mapa** — inventário vivo em `piecemakers.yaml`. (Era 7 até
2026-07-13; `PMG6` — DDR4, prefixo novo — entrou nesta data, ver §5.)

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/piecemakers.yaml       ← GRAMÁTICA (7 famílias + mapa PMF_DDR3_CAP). SÓ isso (Opção 2).
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml)
AUTORIA.md / CLAUDE.md §5              ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → edita o yaml →
`load_brands --brand piecemakers` (dry-run = portão) → o **dono** roda `--commit`. **known_parts**
(autoridade) → `submit_known_parts` (dry-run) → o **dono** roda `--commit` + **aprova no admin**.
⚠ **Família nova → PN-âncora no golden é OBRIGATÓRIO** (`GoldenObrigatorioTests` falha sem — as 7
famílias atuais já são grandfathered/provadas: ver `LoadBrandsPiecemakersTests` + `_PMK_GOLDEN` em
`chips/tests.py`). **NÃO tocar sem revisão do dono:** `chips/engine.py`, `estoque/views.py`,
yamls/known_parts de outras marcas, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung). **Este
chat só edita `piecemakers.yaml` e arquivos de submissão** — `.py`, testes e infra ficam fora do
escopo (perguntar ao dono antes de cogitar mexer em código).

### 0.2 Regras de ouro — nunca violar

1. **Claude edita o yaml/submissão. O usuário roda os comandos.** Nunca `load_brands --commit` /
   `submit_known_parts --commit` / `migrate` sem confirmação do dono.
2. **`load_brands --brand piecemakers` (dry-run) é o portão** — valida a convenção, nada é
   gravado. Depois do `--commit`, o cache recarrega sozinho (`catalog_version`), sem restart.
3. **OPÇÃO 1: a GERAÇÃO vai no `chip_type`** para toda DDR discreta (`DDR1`/`DDR2`/`DDR3`/`DDR3L`/
   `DDR4`), espelhada no `subtype`. ❌ NUNCA `chip_type="RAM"`/`"DDR"` genérico. Fonte única:
   `chips/chip_types.py`.
4. **`subtype` = SÓ a geração** — aqui coincide 1:1 com o `chip_type` (a marca não tem qualificador
   tipo "Mobile"/"Multi-Channel" pra esconder).
5. **`interface` na GRAMÁTICA (yaml/família) fica `""`** — o barramento (x8/x16) existe no PN
   (`pn[7:9]`) mas a família **não decodifica isso estruturalmente** (sem mecanismo de
   `decode_interface`), só documenta no `tip`. **Em `known_part` individual, PREENCHA
   `interface="x8"`/`"x16"`** com o valor real confirmado — é o padrão já usado no known_part
   aprovado `PMF511816EBR` (`interface: "x16"`) e segue a convenção geral do projeto (§6 do
   CLAUDE.md: interface = bus width pra DDR/GDDR). Não confundir os dois níveis.
6. **`decode_density_type` e `decode_cap_map` são mutuamente exclusivos.** `PMF4`/`PMF5` usam
   `decode_cap_map: PMF_DDR3_CAP` — **nunca** `decode_density_type: "pc"` (armadilha real, §3).
7. **Nunca inverta `val_primary`/`val_secondary`** no mapa `PMF_DDR3_CAP` — `val_primary` é a
   capacidade legível (`"128MB"`); `val_secondary` fica vazio (o engine deriva o "por die" sozinho,
   não escreva isso na mão).
8. **Não confie em distribuidor/IA sem verificar.** Marca pequena e pouco documentada — cruze
   SEMPRE com `piecemakers.com.tw` ou pelo menos mais uma fonte independente antes de qualquer
   `known_part`.
9. **Ouro = identidade; specs derivadas sempre atestar Tier-1.** Um `confidence="manual"` prova que
   o PN existe e a fonte é rastreável — não dispensa checar capacidade/tensão contra o catálogo
   oficial ou uma fonte técnica cruzada (ex.: engenheiro documentando o chip em uso real).

### 0.3 Hierarquia de fontes (imutável)

```
1. piecemakers.com.tw (catálogo/datasheet oficial) → Tier 1, busca por PN/família
2. DigiKey / Mouser (quando listarem — raro nesta marca)
3. element14 community — engenheiros documentando hardware real (ex.: Arty S7-50 com PMF511816EBR)
4. glochip.com (tabela DDR3) → cross-check, nunca fonte única
5. Octopart → secundário, cruzar sempre
6. Distribuidor B2B rastreável → só apoio; nunca decide capacidade sozinho
7. IA externa → ÚLTIMO RECURSO; fabricante pequeno = maior taxa de alucinação do catálogo inteiro
```
Nunca fonte primária: fóruns genéricos, distribuidor não rastreável, catálogos agregadores sem
proveniência, eBay, IA sem verificação cruzada.

> ⚠ O endpoint do PDF oficial (`piecemakers.com.tw/api/v1/file/…`) voltou **vazio em 2026-06**.
> Alternativas: tentar a **Wayback Machine** (arquivo do PDF ou da página de produto — entra como
> `confidence="estimated"`, fica oculto até confirmação manual) ou pedir ao operador o download
> direto pela bancada.

---

## 1. Convenção canônica de campos

> Fonte única: `chips/chip_types.py`. Contexto geral: `CLAUDE.md §6`. Unidade inviolável: die em
> `Gb` (aqui só interessa o die — PieceMakers não empacota módulo/eMCP).

| Prefixo | `chip_type` | `subtype` | Decodifica capacidade? | `profit_family` |
|---|---|---|---|---|
| `PMF4` | `DDR3L` | `DDR3L` | ✅ via `PMF_DDR3_CAP` | `ddr` (depende de densidade) |
| `PMF5` | `DDR3` | `DDR3` | ✅ via `PMF_DDR3_CAP` | `ddr` (depende de densidade) |
| `PMF` (fallback) | `DDR3` | `DDR3` | ❌ routing puro | `ddr` |
| `PMA` | `DDR4` | `DDR4` | ❌ pendente (§2) | `ddr` (passa no gate de geração) |
| `PMG6` | `DDR4` | `DDR4` | ❌ pendente (1 PN só, §5) | `ddr` (passa no gate de geração) |
| `PMD` | `DDR1` | `DDR1` | ❌ não precisa (§3) | `ddr` (sempre morta) |
| `PME` | `DDR2` | `DDR2` | ❌ não precisa (§3) | `ddr` (sempre morta) |
| `PMS` | `SDRAM` | `SDRAM` | ❌ não precisa (§3) | `dead` (sempre morta) |

**Regras absolutas de campo:** `subtype` = só a geração (nunca densidade/tensão/"Mobile"/bus
width). `interface` = `""` na GRAMÁTICA (família no yaml, sem decode estruturado) mas
`"x8"`/`"x16"` explícito em cada `known_part` confirmado (§0.2.5 — não confundir os dois níveis).
`dram_density` é o campo DERIVADO que o engine calcula
a partir do `decode_cap_map` per-die (`"128MB"` → `"1Gb = 128MB por die [✓]"`) — não confundir com
`capacity`, que fica vazio nas famílias sem decode. Tudo que sobrar (tensão, package, revisão de
silício, drop-in compatível) vai no `tip`/`notes`.

---

## 2. Anatomia do PN — como LER um chip PieceMakers

**DDR3 / DDR3L (`PMF4…`/`PMF5…`)** — a única família com decode posicional de capacidade:

```
P  M  F  [V]  [DD]  [B]  [WW]  [R]  B  R  -[sufixo]
0  1  2   3    4-5   6    7-8   9   10 11
```

- `pn[3]` = **tensão/geração**: `5` = 1.5V → prefixo `PMF5` (**DDR3**) · `4` = 1.35V → prefixo
  `PMF4` (**DDR3L**). É o prefixo (4 chars) que já resolve isso no engine — `pn[3]` é redundante
  como confirmação visual pro operador.
- `pn[4:6]` = **densidade** (2 chars) → chave no mapa `PMF_DDR3_CAP` do yaml. Hoje só **3 chaves**
  mapeadas (`10`/`11`/`12` = 1Gb/2Gb/4Gb) — cobertura rala; PN com código fora dessas 3 exige
  pesquisa Tier-1 antes de adicionar chave nova (nunca extrapole por padrão numérico).
- `pn[6]` = filler fixo (não decodificado). `pn[7:9]` = **barramento**: `08`=x8 · `16`=x16 — a
  GRAMÁTICA só documenta isso no `tip` (não decodifica estruturalmente, §0.2.5), mas todo
  `known_part` confirmado deve preencher `interface="x8"`/`"x16"` com o valor real. `pn[9]` =
  revisão de silício (B/C/D/E/F/G, confirmado ao menos até G) — não altera specs: o catálogo
  oficial mostra a mesma densidade/org/tensão persistindo através de várias revisões em
  paralelo (ex.: 1Gb x16 com C/D/E todas MP simultaneamente).
- `BR` (posições 10-11) = package (96-FBGA para x16 · 78-FBGA para x8). Sufixo após hífen
  (`-KADN` etc.) = grade de velocidade/temperatura — **nunca** altera specs (§3).

**Routing puro por prefixo (as outras 5 famílias — sem decode de capacidade):** `PMA` = DDR4 ·
`PMD` = DDR1 · `PME` = DDR2 · `PMS` = SDRAM · `PMF` (sem dígito de tensão na 4ª posição) =
fallback DDR3 genérico.

**Ordem de match:** o engine ordena famílias por `priority` (menor primeiro) e, em empate, por
tamanho de prefixo (maior vence). `PMF4`/`PMF5` têm `priority=40`; o fallback `PMF` tem
`priority=70` — por isso qualquer PN que bata com `PMF4`/`PMF5` **nunca** cai no fallback
genérico.

> **`PMA` (DDR4) — decode de capacidade pendente.** Só 2 PNs com densidade confirmada em Tier-1
> hoje (`PMA212508ABR`/`PMA212816ABR`, ambos 4Gb — x8 e x16) — **insuficiente** pra inferir a
> posição do código de densidade no PN. Sem `decode_cap_map`, `classify()` tipa corretamente como
> DDR4 mas devolve capacidade vazia → `assess_profitability` cai em **INDETERMINADO** (DDR4 passa
> no gate de geração "morta", mas falta densidade pra aplicar o limiar) até um `known_part`
> confirmar a capacidade. **Não implemente decode posicional sem 2+ densidades DISTINTAS atestadas
> em Tier-1** — regra geral do projeto, vale em dobro aqui pela escassez de dado.

---

## 3. Armadilhas específicas (o durável)

- **`decode_density_type="pc"` NÃO serve pro PMF.** O engine hardcodeia `pn[3:5]` no modo `"pc"`
  (lookup em `DRAM_PC`) — mas a densidade do PieceMakers está em `pn[4:6]`. Use sempre
  `decode_cap_map="PMF_DDR3_CAP"` com `decode_cap_pos=4, decode_cap_len=2`. Confundir os dois modos
  lê a posição errada e devolve lixo silencioso (não dá erro).
- **`PMF5`/`PMF4` vs fallback `PMF`:** resolvido por `priority` (40 vence 70) — nunca amplie o
  fallback genérico pra "cobrir" um caso que na verdade merece família própria (perde o decode).
- **Sufixo nunca altera specs:** `PMF511816EBR-KADN` é o **mesmo chip** que `PMF511816EBR` (golden
  confirma specs idênticas). Se o operador digitar com sufixo, cadastre como PN adicional — não
  invente variação de capacidade/tensão só pelo sufixo.
- **DDR3L roda a 1.5V também:** `PMF4xx` é nominalmente 1.35V mas tolera 1.5V — não é motivo pra
  fundir com `PMF5xx` no mesmo `subtype`. O label depende dessa distinção (`DDR3L` vs `DDR3`).
- **`PMD`/`PME`/`PMS` (DDR1/DDR2/SDRAM) reprovam por GERAÇÃO, não por capacidade** — por isso não
  têm (e não precisam de) `decode_cap_map`. `assess_profitability` já corta pela geração (DDR1/DDR2
  ficam abaixo do mínimo aceito; SDRAM tem `profit_family="dead"` fixo) — o chip cai em **NÃO
  RENTÁVEL** mesmo sem nenhum `known_part`. **Nunca** crie um mapa de capacidade só pra "completar"
  essas 3 famílias — seria trabalho sem efeito comercial.
- **`PMA` é o padrão oposto:** DDR4 passa no gate de geração (não é "morta"), então SEM capacidade
  decodificada ele fica **INDETERMINADO** (não NÃO RENTÁVEL) — só um `known_part` com densidade
  confirmada resolve o veredito. Não confundir os dois padrões ao explicar pro operador por que um
  `PMA` fica pendente e um `PMD`/`PME`/`PMS` não.
- **Fabricante pequeno → dado escasso, IA alucina specs com frequência.** Exigir fonte cruzada
  (Tier 1 + pelo menos mais uma) antes de qualquer `known_part` — nunca confirmar com uma fonte só.

---

## 4. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` (código) + `ProfitabilityConfig` (admin, editável — muda com o
mercado). **Não cito limiares aqui** (dataria no dia seguinte). Padrões duráveis (a REGRA, não o
número):

- **SDRAM (`PMS`) e DDR1/DDR2 (`PMD`/`PME`) = geração morta → sempre NÃO RENTÁVEL**, independente
  de qualquer capacidade que venha a ser confirmada no futuro.
- **DDR3/DDR3L (`PMF4`/`PMF5`) dependem da densidade** — no golden atual, a chave `10` (1Gb)
  reprova e `11`/`12` (2Gb/4Gb) aprovam; é um retrato do `ProfitabilityConfig` de hoje, não uma
  constante — confira o admin se precisar do valor vigente.
- **DDR4 (`PMA`) passa no gate de geração** mas fica **INDETERMINADO** enquanto não houver
  capacidade decodificada (§2/§3) — não é "sempre rentável", é "ainda sem veredito".

---

## 5. Gaps e roadmap (o que falta pesquisar)

- **`PMG6` (DDR4) — família NOVA, adicionada em 2026-07-13, ainda PRECISA da âncora golden.** O
  catálogo oficial (piecemakers.com.tw/products/standard-dram) mostra `PMA212816C` (revisão C,
  além da `A` que já tínhamos) **e um prefixo totalmente novo `PMG6124D`** (4Gb, x8/x16 no mesmo
  PN, 1.2V, 78/96FBGA). Por pedido do dono, a família `PMG6` já entrou no yaml (routing-only,
  igual à `PMA`) e o PN `PMG6124D` + a revisão `PMA212816C` já estão na submissão
  `submissions/piecemakers_pmf5_pmf4_2026-07-13.yaml`. **Pendente (fora do escopo deste chat,
  é edição de `.py`):** `chips/tests.py` precisa de uma âncora `_PMK_GOLDEN` pra `PMG6124D` —
  `GoldenObrigatorioTests` vai falhar sem isso (prefixo novo, não é grandfathered). Sugestão de
  linha está no cabeçalho do arquivo de submissão. Também: só 1 PN de `PMG6` visto — achar mais
  antes de tentar decode posicional; confirmar `PMA212816C` em 2ª fonte.
- **`PMF4`/`PMF5`:** confirmado em DUAS fontes independentes (catálogo oficial + glochip.com) que
  a marca só vai até **4Gb** nessa linha — o tab "8Gb" existe no site oficial mas sem nenhum PN
  listado embaixo (provavelmente reservado/roadmap, não produto real). Não inventar PN 8Gb.
- **PSRAM/KGD/HBLL-RAM** — produtos de nicho citados no site oficial, sem família no yaml e sem PN
  visto na bancada até 2026-07. Se aparecer, é família nova (golden obrigatório — `AUTORIA.md
  §3.3`).
- **Known_parts:** rodada de 2026-07-13 pesquisou o cluster inteiro PMF5/PMF4 + expandiu ao pedido
  do dono ("colete mais, não só 1, precisamos do máximo possível de variações") — ver
  `submissions/piecemakers_pmf5_pmf4_2026-07-13.yaml` entregue ao dono: **70 known_parts** no
  arquivo após 3 adendos (`confidence=manual`, fontes: glochip.com estruturado + catálogo oficial
  + distribuidores + navegação individual de páginas do glochip). Cobre PMF5/PMF4 quase completo
  (1Gb/2Gb/4Gb × x8/x16 × revisões B–H), `PMA`/`PMG6` (DDR4), e DDR2(`PME`)/DDR1(`PMD`)/SDR(`PMS`)
  inteiros (sempre NÃO RENTÁVEL, mas incluídos por completude de identidade a pedido do dono).
- **Revisão de silício vai além de B–G — confirmado `H` em 2Gb/4Gb x16 (PMF5 e PMF4).** O glochip
  só lista `E`/`F` na tabela-resumo; a bancada trouxe `D` e `C` (2Gb x16, confirmados via
  distribuidor com estoque real — Ariat-Tech/Censtry pro `D`, Sierra IC/NetComponents pro `C`), e
  a navegação individual de páginas do glochip (não a tabela-resumo — cada PN pode ter página
  própria "anterior/próximo") revelou `H` em 2Gb E 4Gb x16, nas duas famílias. `G` foi TESTADO
  direto (URL do glochip) e não tem página própria — 404, confirmado excluído. **Também achei um
  gap na 1ª rodada:** revisão `E` em **1Gb** (x8 e x16, PMF5 e PMF4) estava na Tier-1 oficial
  desde o início mas eu não tinha cruzado direito — corrigido nesta expansão. Padrão a manter: se
  aparecer PN fora do que já documentei aqui, confirmar por página PRÓPRIA de distribuidor/glochip
  (não só "related parts"/tag solta) antes de adicionar.

---

## 6. Fontes de pesquisa

Tier 1: **piecemakers.com.tw/products/standard-dram** (catálogo oficial atual — URL mudou em
2026-07, sem `/en/`; é um SPA Nuxt, cada aba de densidade carrega via JS — sem navegador só se vê
a aba default). Tier 2: **glochip.com/ddr3/piecemakers.html** (tabela técnica estruturada com
TODAS as famílias — DDR4/DDR3/DDR3L/DDR2/DDR/SDR juntas na mesma página apesar do nome — Part
No./Den./Org./Vol./Speed/Package/Status; cruzado com o site oficial em 2026-07-13 e bateu 100% nas
linhas sobrepostas), **element14 community** (engenheiros documentando hardware real — ex.: uso do
`PMF511816EBR` na Digilent Arty S7-50). Tier 3 (nunca decide sozinho, só corrobora EXISTÊNCIA do
PN, não specs): distribuidores (Jotrin/Ariat-Tech/Censtry/LCSC — úteis pra confirmar que um PN
existe quando não está no glochip, ex.: `PMF511816DBR-KADN`, mas raramente trazem capacidade/org
confiável). Nunca fonte primária: fóruns, IA sem verificação cruzada. Hierarquia completa: §0.3.

---

> O inventário de famílias/chaves vive no **`piecemakers.yaml`** (gramática); os **known_parts**
> confirmados (com a proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2), submetidos via
> `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade, arquitetura,
> processo de autoria) está no **`CLAUDE.md`** / **`AUTORIA.md`** — leia-os antes de editar
> qualquer yaml ou submissão desta marca.
