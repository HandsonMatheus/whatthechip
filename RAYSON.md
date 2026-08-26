> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da Rayson (famílias + mapas) vive em
> **`chips/knowledge/rayson.yaml`** (via `load_brands`). Os **known_parts** (PNs confirmados = autoridade)
> **NÃO ficam no yaml** — vivem no **banco**, submetidos por `submit_known_parts` e **aprovados pelo dono**
> no admin (four-eyes). **Processo obrigatório completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados (decode key→valor, inventário de known_parts):
> esses vivem no **yaml** (gramática) e no **banco** (known_parts). Aqui ficam: **convenções, anatomia do
> PN, armadilhas, rentabilidade (princípio), fontes, o *porquê*** e ponteiros.

---

# RAYSON.md — Bíblia Técnica e de Negócio

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/rayson.yaml`). Regras gerais do WTC: `CLAUDE.md`.

**Rayson HI-TECH (SZ) Co., Ltd.** — Shenzhen, China, fundada em 2016; também comercializada como
**晶存科技**. Brand code WTC: **`RAY`**. Prefixo de PN: **`RS`**.

É uma **fabricante de módulo/pacote de baixo custo**, não uma fab: projeta controlador e firmware próprios
e encapsula die de terceiros. Linha oficial atual (fonte Tier-1, §6): **LPDDR4/4X** (200-ball, até
4266 Mbps), **LPDDR5/5X**, **DDR3/4**, **eMMC** (4GB–256GB, JEDEC 5.1, HS400), **UFS** (2.2/3.1/4.1, até
512GB), **MCP** (NAND + LPDDR4/4X), **eMCP** e **ePoP**.

⚠ **A gramática cobre uma fração disso** — hoje só LPDDR3, LPDDR4 e eMMC. O resto da linha não tem família
nenhuma (§5). Não confunda "a Rayson fabrica" com "o WTC classifica".

> ⚠ **Destino comercial:** produto Rayson **não é aceito como substituto** de Samsung/SK Hynix/Micron no
> B2B premium → a intenção é **lote segregado Rayson/budget**. ⚠ **Isso é regra de NEGÓCIO declarada, NÃO
> implementada** — não existe segregação por marca em `estoque/` nem em `pricing/` (censo 2026-08-20).
> Hoje só sobrevive como texto em `tip`/`notes`. Ver §5.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/rayson.yaml           ← GRAMÁTICA (famílias + mapas). SÓ isso (Opção 2).
banco (submit_known_parts→aprovação)  ← known_parts confirmados = autoridade (não no yaml)
chips/tests.py :: _RAY_GOLDEN         ← os PN-âncora que PROVAM o decode (§2)
AUTORIA.md / CLAUDE.md §5             ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** → edita o yaml → `load_brands --brand rayson`
(dry-run = portão) → o **dono** roda `--commit`. **known_parts** (autoridade) → `submit_known_parts <arq>`
(dry-run = portão) → o **dono** roda `--commit` + **aprova no admin**. ⚠ **Família nova → PN-âncora no
`_RAY_GOLDEN` é OBRIGATÓRIO** (`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:**
`chips/engine.py`, `estoque/views.py`, yamls/known_parts de outras marcas, mapas globais
(`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca `load_brands --commit`/`migrate` sem confirmação.
2. **`load_brands --brand rayson` (dry-run) é o portão** da gramática — valida a convenção, nada gravado.
   Depois `--commit` (recarrega o cache sozinho, sem restart).
3. **known_part NUNCA entra pelo yaml.** É `submit_known_parts` → `--commit` do dono → **aprovação no
   admin**. Escrever o banco direto (shell/ORM/admin ad-hoc) é **PROIBIDO** — só o `submit` passa pelo
   portão. (Esta bíblia mandava o contrário até 2026-08-20 — ver §7.)
4. **A GERAÇÃO vai no `chip_type`** para DRAM discreta (`LPDDR3`, `LPDDR4`, `LPDDR4X`, `LPDDR5`, `DDR3`…),
   espelhada no `subtype`. ❌ NUNCA `chip_type="RAM"`/`"DDR"`/`"LPDDR"` genérico. Fonte única:
   `chips/chip_types.py`.
5. **`subtype` = SÓ a geração/célula** (1–3 palavras). ❌ densidade, bus width, tensão, `"Mobile"`,
   `"x32"`, `"4266Mbps"` — isso vai em `tip`/`notes`.
6. **A gramática não distingue 4X de 4.** Toda família LPDDR4 da Rayson resolve `chip_type="LPDDR4"`; o
   portão reduz `"LPDDR4/4X"` → `"LPDDR4"` (verificado em `canonical_chip_type`). **`LPDDR4X` num chip
   específico só existe via known_part confirmado.** Se a fonte Tier-1 atesta 4X, submeta o known_part —
   não tente ensinar 4X à gramática pelo prefixo.
7. **eMMC Rayson: `capacity` em GB, `subtype` vazio.** Não force `emcp_ram`/`emcp_nand` — esses são de
   eMCP/MCP (que ainda não têm família, §5).
8. **Não confie em distribuidor/IA sem verificar** (confundem Gb/GB, alucinam capacidade). Mesmo num
   `confidence=confirmed`, o que está atestado é a **identidade** — `capacity` é derivado e pode estar
   errado; atestar sempre em Tier-1.
9. **Não invente chave de decode por "padrão matemático"** sem PN-âncora + fonte Tier-1. A Rayson já tem um
   código que foge do padrão numérico (§3) — extrapolar aqui é como errar.

### 0.3 Hierarquia de fontes (imutável)

```
1. szrayson.com — datasheet/página de produto oficial Rayson .................. Tier 1
2. Octopart/Nexar (categorização própria), LCSC, Alldatasheet ................. Tier 2, rastreável
3. Glochip / chip.com.cn (tabelas técnicas estruturadas do meio chinês) ....... Tier 2/3, apoio
4. Distribuidor B2B genérico (Jotrin, Win Source, Ariat…) ..................... Tier 3, só apoio
5. Wayback Machine ........................................................... PN descontinuado
6. IA externa ................................................................ ÚLTIMO RECURSO, verificar SEMPRE
```
⚠ **`rayson-tech.com` NÃO é a Rayson.** É a *Rayson Technologies, LLC*, consultoria de dados no Alabama —
nada com memória. Esta bíblia apontou pra lá até 2026-08-20 (§7). O domínio certo é **`szrayson.com`**.

Nunca fonte primária: AliExpress, fórum, catálogo genérico sem rastreio, IA sem verificação.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **Fonte única: `chips/chip_types.py`.** Contexto geral: `CLAUDE.md §6`.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| LPDDR3 / LPDDR4 (famílias na gramática hoje) | a geração | espelha | `""` | `capacity` = pacote em **GB** |
| LPDDR4X (só via known_part — §0.2#6) | `LPDDR4X` | espelha | `""` | `capacity` (GB) |
| eMMC (famílias na gramática hoje) | `eMMC` | `""` | `""` ou versão | `capacity` = **GB** |
| LPDDR5/5X, DDR3/4, UFS, eMCP, MCP, ePoP | ver §5 — **sem família**, pesquisar antes de criar | | | |

**Regras absolutas:** `subtype` = só a geração. `capacity` = pacote em bytes (`"4GB"`), **nunca Gbit**.
`tip`/`notes` = velocidade (4266Mbps), ball count (200ball), tensão, temperatura, **fonte Tier-1**.

**Label da caixa:** LPDDR `{chip_type}+{cap}GB` (ex.: `LPDDR4+4GB`) · eMMC `EMMC{cap}GB` (ex.: `EMMC16GB`).

---

## 2. Anatomia do PN — como LER um chip Rayson

> **O item de maior valor desta bíblia.** É o que permite ler um PN que **não** está na tabela do yaml.
> Os valores/mapas completos vivem no yaml; aqui fica o padrão.

### LPDDR — a fórmula JEDEC (igual à Micron)

```
RS  256M   32   L   D3   D1   LMZ
│   │      │    │   │    │    └── sufixo: pacote/temperatura/revisão (não decodificado)
│   │      │    │   │    └────── dies/canais no encapsulamento — NÃO multiplica a densidade
│   │      │    │   └─────────── geração: D3 = LPDDR3 · o dígito 4 solto = LPDDR4/4X
│   │      │    └─────────────── L = LPDDR
│   │      └──────────────────── LARGURA do barramento em bits (32)
│   └─────────────────────────── PROFUNDIDADE (256M, 512M, 1G, 2G)
└─────────────────────────────── prefixo Rayson
```

**`profundidade × largura ÷ 8 = capacidade do pacote em GB`** — a mesma fórmula da Micron
(`MICRON.md §2`). Confere nos quatro casos vivos:

| PN | conta | capacidade |
|---|---|---|
| `RS256M32L…` | 256M × 32 ÷ 8 | 1GB |
| `RS512M32L…` | 512M × 32 ÷ 8 | 2GB |
| `RS1G32L…`   | 1G × 32 ÷ 8   | 4GB |
| `RS2G32L…`   | 2G × 32 ÷ 8   | 8GB |

⚠ **O `D{N}` (D1/D2/D4) é dies/canais — NÃO multiplica.** `profundidade × largura` já é o dispositivo
inteiro. Multiplicar por dies é o **bug de dies** que inflou a Micron ×N em jun/2026 (`MICRON.md §2`); a
Rayson tem exatamente a mesma armadilha esperando.

⚠ **A letra entre `L` e a geração varia e NÃO é capacidade** (`F`, `O`, `V`, `M`, `Z` aparecem nos
âncoras). Não a use pra decodificar nada sem fonte.

### eMMC — capacidade no prefixo

```
RS70B   16G   4S15G
│       │     └── sufixo: firmware/revisão/pacote (não decodificado)
│       └──────── CAPACIDADE (código de 3 chars)
└──────────────── RS70B = família eMMC Rayson
```

O código de capacidade é **majoritariamente numérico + `G`**, mas **tem exceção** (§3). As chaves vivem no
yaml — não as copie pra cá.

### Onde está a prova

**`chips/tests.py :: _RAY_GOLDEN`** — **20 PN-âncora** cobrindo LPDDR3, LPDDR4 (1GB a 8GB) e eMMC (8GB a
128GB), cada um com tipo, capacidade e **veredito de rentabilidade** esperados. Dois estão marcados
`# KnownPart em prod`. **Toda família nova precisa de âncora ali** — e é o primeiro lugar pra olhar quando
alguém disser "a Rayson decodifica errado". Os 12 prefixos `RS*` atuais estão em
`_FAMILIES_GRANDFATHERED` (existiam antes da regra do golden obrigatório).

---

## 3. Armadilhas e Decisões Arquiteturais

- ⚠ **`T7G` = 128GB — o único código de capacidade não-numérico.** Todos os outros seguem `08G`/`16G`/
  `32G`/`64G`; esse é código interno da Rayson. **Consequência:** qualquer heurística "extrai o número
  antes do G" quebra nele. Se aparecer capacidade nova (256GB, que o catálogo oficial já anuncia), **não
  presuma** o código — confirme em Tier-1.
- ⚠ **`RS70B` é família FALLBACK de prioridade 70** (as específicas são 50). Ela existe pra o PN não sumir,
  mas **engole em silêncio** qualquer eMMC de código de capacidade desconhecido: o chip sai classificado
  como eMMC **sem capacidade** → INDETERMINADO → fila, em vez de erro. Se um eMMC Rayson chega sem
  capacidade, suspeite de código novo antes de suspeitar de bug.
- ⚠ **4 vs 4X é invisível pra gramática** (§0.2#6). Duas peças fisicamente incompatíveis em tensão de I/O
  (LPDDR4 1.1V × LPDDR4X 0.6V) saem com o mesmo `chip_type`. Só known_part separa. Mesma classe do
  `MT53B` ≠ `MT53E` da Micron (`MICRON.md §4`) — lá o erro **danifica hardware**.
- ⚠ **`ePoP` é sempre NÃO RENTÁVEL, independente de capacidade** (decisão de negócio 2026-06-20, no bloco
  de tipos no topo de `assess_profitability`). A Rayson **vende ePoP** — quando a família existir, ela já
  nasce reprovada. Não tente "salvar" com capacidade.
- ⚠ **O prefixo de um LPDDR4 é o COMEÇO de um LPDDR3 — e o que separa é a ordem de match.** `RS256M32L`
  (LPDDR4) é literalmente o começo de `RS256M32LD3` (LPDDR3); idem `RS512M32L` × `RS512M32LD3`. O engine
  ordena por **`("priority", "-prefix_len")`** — **menor priority casa PRIMEIRO** (contraintuitivo) e, em
  empate, **prefixo mais LONGO ganha**. Hoje o LPDDR3 está em 50 e o LPDDR4 em 55.
  **Testado por mutação (2026-08-20):** igualar os dois em 50 **continua passando** (o desempate por
  comprimento segura); mas pôr o LPDDR4 **abaixo** do LPDDR3 (55→40) **quebra** — `RS256M32LD3D1LMZ` muda
  de identificação e vira LPDDR4. Ou seja: **o `-prefix_len` é a rede de proteção real; a priority só não
  pode INVERTER a ordem.** Mesma mecânica protege `RS70B08G`… (50) do fallback `RS70B` (70).
  **Mexeu em priority → rode `RaysonLoadBrandsTests`.**
- ⚠ **Zero known_parts Rayson no seed** (censo 2026-08-20). A marca inteira depende **só** de gramática,
  logo **nada Rayson é autoritativo** hoje: um dado de distribuidor errado não tem `confirmed` pra vencê-lo.
- ⚠ **Não crie `PriceList` "só pra herdar"** (caso Rayson 2026-07-10 — §7). Marca sem lista já usa
  "Outras marcas" automaticamente; criar lista vazia **polui a sidebar do parceiro e o catálogo PDF**.

---

## 4. Rentabilidade — princípio (os valores NÃO ficam aqui)

Fonte única: **`assess_profitability`** + **`ProfitabilityConfig`** (singleton no admin, market-variable).
Nunca reimplemente regra de rentabilidade aqui nem no yaml. Contrato completo: **`RENTABILIDADE.md`**.

O padrão durável que o `_RAY_GOLDEN` já demonstra: **a geração decide antes da capacidade.**
`RS256M32LD3…` (1GB **LPDDR3**) resolve **NÃO RENTÁVEL**, enquanto `RS256M32LZ4` (1GB **LPDDR4**) resolve
**RENTÁVEL** — mesma capacidade, veredito oposto. eMMC Rayson de 8GB pra cima sai RENTÁVEL nos âncoras.

⚠ **Rentabilidade ≠ destino.** "RENTÁVEL" é o veredito do funil; **"lote segregado Rayson/budget" é regra
de DESTINO** e não está implementada (§5). Um chip Rayson RENTÁVEL hoje vai pra mesma caixa de um Samsung
equivalente. Não descreva a segregação como se o sistema a fizesse.

---

## 5. Gaps e Roadmap (o durável — o resto está no yaml)

**Linha oficial SEM família na gramática** (fonte Tier-1, §6) — cada uma é uma rodada de pesquisa própria:

| Linha | Situação | Nota |
|---|---|---|
| **LPDDR5 / 5X** | sem família | a Rayson anuncia; nenhum prefixo mapeado |
| **DDR3 / DDR4 discreto** | sem família | anunciado (DDR3-1866, DDR4-3200); precisa de `density_gbit`, não `capacity` |
| **UFS** (2.2/3.1/4.1, até 512GB) | sem família | |
| **eMCP / MCP** (NAND + LPDDR4/4X) | sem família | exige `emcp_nand` + `emcp_ram`, não `capacity` |
| **ePoP** | sem família | já nasce NÃO RENTÁVEL (§3) |
| **eMMC 256GB** | fora do mapa | o catálogo oficial vai a 256GB; a gramática para em 128GB (`T7G`) |

**Dívidas conhecidas:**

1. **Nenhum known_part Rayson** — a marca é 100% gramática. Primeira rodada de `submit_known_parts` é o
   maior ganho isolado disponível: é o que permite 4X, corrige capacidade e dá autoridade.
2. **Segregação Rayson/budget não existe em código.** Ou vira regra implementada (campo/rota no gateway ou
   no pricing), ou fica explicitamente registrada como intenção — o meio-termo atual (texto manual em
   `tip`/`notes`) não escala e dá falsa sensação de que o sistema separa.
3. **Sem histórico de bug de decode** — o `_RAY_GOLDEN` está verde, mas nenhuma família Rayson passou por
   correção documentada. Quando passar, registre em §7.

---

## 6. Fontes de pesquisa

**Tier-1 — Rayson oficial (`szrayson.com`):**

- Consumer-grade embedded storage: `szrayson.com/product_62/`
- Industrial/automotive embedded storage: `szrayson.com/product_103/`
- Soluções (aplicação por segmento): `szrayson.com/en/solution/`
- Datasheets em PDF: publicados sob `szrayson.com/static/upload/file/...` (ex.: o datasheet **eMMC 5.1**)

**Tier-2/3 (apoio, sempre cruzar):** Octopart/Nexar · LCSC (página de marca) · Glochip / chip.com.cn
(tabelas do meio chinês, úteis pra matriz densidade×organização) · Alldatasheet.

⚠ **Nunca `rayson-tech.com`** — outra empresa (§0.3).

---

## 7. Histórico (o *porquê* — durável)

- **2026-07-10 — `PriceList` criada "só pra herdar" (caso Rayson).** Uma lista de preço vazia foi criada
  para a Rayson só para herdar da genérica. Efeito: a marca passou a **aparecer na sidebar do parceiro e no
  catálogo PDF** sem ter preço próprio. Lição: **a ausência de lista já herda** — lista só se a marca terá
  preços PRÓPRIOS. Virou anti-footgun escrito no `PriceListAdmin` (`pricing/admin.py`).
- **2026-08-20 — esta bíblia estava desatualizada e, em três pontos, errada.** Auditoria contra o código,
  o yaml e a fonte oficial encontrou: **(a)** a única fonte Tier-1 apontava pra `rayson-tech.com`, que é
  outra empresa (consultoria de dados no Alabama) — um chat de marca seguia o ponteiro, não achava nada e
  concluía "sem fonte", **falhando em silêncio**; **(b)** o cabeçalho era pré-Opção 2, dizendo que os PNs
  confirmados viviam no yaml; **(c)** o "Como popular" mandava adicionar `known_parts` no yaml — a
  violação exata da trava de escrita. Faltavam ainda anatomia do PN, armadilhas, rentabilidade, gaps e
  histórico; o arquivo tinha 32 linhas contra uma mediana de ~200 nas outras bíblias. Lição:
  **bíblia de marca sem §Armadilhas e sem §Fontes verificadas envelhece pra errada, não pra incompleta** —
  um ponteiro quebrado é pior que ponteiro nenhum, porque produz silêncio em vez de erro.

> Inventário de famílias/chaves de decode: **`rayson.yaml`**. Known_parts: **no banco** (Opção 2).
> Comandos (com flags), convenção completa, rentabilidade, contrato de autoria: **`CLAUDE.md`** /
> **`AUTORIA.md`** / **`RENTABILIDADE.md`**.
