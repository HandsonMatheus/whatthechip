# PRECIFICACAO.md — Sistema de Preços do WhatTheChip (plano completo)

> **Status: F0 CONSTRUÍDA (2026-07-07) · F1 entregue pela fundação multi-tenant.**
> Design de ponta a ponta acordado no brainstorm de 2026-07-06 (dono + agente), a
> partir do `PROMPT_PRECOS.md` e da planilha `wuquanprices.xlsx` (comprador Wuquan).
> A fundação (`PLANO_MULTITENANT.md`, T1–T4) está construída e em produção — a
> precificação roda em cima dela. **Ver §12 (diário de execução)** para o que já
> existe e o runbook de validação de cada fase. **F2, F3 e F4 CONSTRUÍDAS
> (2026-07-07, suíte 271/271; import validado contra a planilha REAL: 314
> preços, zero conflitos)** — próxima fase: **F5** (preço no card de busca).
> Quando implementado, este arquivo vira a **bíblia técnica do sistema de preços**
> (mesmo papel do `RENTABILIDADE.md` para rentabilidade). A aba `Instructions` da
> planilha já aponta para este documento.
>
> Regras do jogo (herdadas do CLAUDE.md): o agente EDITA arquivos; o **dono roda**
> tudo que escreve no banco (`migrate`, imports `--commit`). Suíte verde +
> `characterize_baseline --diff` limpo a cada fase.

---

## 1. Visão e princípios invioláveis

**O que é:** dado um chip classificado (ou um lote inteiro), dizer **quanto o
comprador paga** — em USD, por unidade — implementando as regras da tabela do
comprador. O preço é um **lookup brand-agnostic sobre a saída normalizada do
`classify()`**, na mesma filososofia de fonte única do `assess_profitability`.

Princípios (decisões fechadas no brainstorm — não reabrir sem o dono):

1. **Fonte única: `price(result, buyer)`.** Nenhum outro lugar calcula preço.
2. **Nunca chuta.** Sem linha na tabela = sem preço + motivo explícito. Sem
   interpolação automática (capacidade fora da grade → o dono adiciona a linha).
3. **USD canônico, `DecimalField`.** RMB e câmbio existem só no import (conversão
   única, `ROUND_HALF_UP`, 2 casas). Float é proibido para dinheiro (erro binário
   acumula em lotes de milhares de linhas).
4. **Preço aproximado é dado, não código:** faixas viram `price_min`/`price_max`
   (exato ⇔ `min == max`); cenário (baixo/médio/alto) é parâmetro da consulta;
   `quote_date` velho além do limite exibe "≈ referência".
5. **Multi-comprador desde o dia 1 — e company-aware.** Todo preço pertence a um
   `Buyer`; todo `Buyer` pertence a uma `Company` (§3.0). Comprador A jamais
   vê preços do B. V1 opera só com Wuquan (comprador da eMiner), mas o modelo já
   nasce N×N (ver §10 + `PLANO_MULTITENANT.md`).
6. **Papéis de usuário nascem AGORA (admin / gerente / operador — por empresa).**
   Operador e gerente NÃO veem preço — seguem vendo RENTÁVEL/NÃO RENTÁVEL. Preço
   aparece para admin no card de busca (estoque fica para depois — F8) e para o
   próprio comprador no dashboard `/partner/`. Matriz completa de permissões:
   `PLANO_MULTITENANT.md` §5.
7. **Preço é on-read; congela no fechamento do lote.** Exibição sempre calcula da
   tabela viva (nada de snapshot de preço em entrada de estoque). Ao fechar/exportar
   um lote para venda, os preços daquele fechamento são gravados com data/versão da
   cotação (auditoria de "vendi com qual tabela").
8. **Rastreabilidade total via `pghistory`** (infra já instalada — migração 0016):
   quem mudou, quando, de que valor para qual. `updated_by`/`last_updated` em todo
   preço; **invisíveis no dashboard do comprador**, visíveis no admin.
9. **Rentabilidade separada do preço.** `assess_profitability` continua o portão da
   triagem (operador); `price()` é a camada de valor (dono/comprador). A ordem no
   lote é: classify → rentabilidade → preço (só faz sentido precificar aprovado —
   a própria tabela do comprador só lista faixas rentáveis).
10. **A planilha morre no import.** O `import_price_xlsx` é bootstrap único; depois
    dele os DOIS únicos canais de edição de preço são o admin (dono) e o dashboard
    `/partner/` (comprador). Nunca mais gerência de preço por planilha.
11. **Slugs e rotas públicas em INGLÊS** (`/partner/`, `/partner/generic/`…).

---

## 2. A chave de preço — como um chip classificado vira uma linha da tabela

A tabela do comprador cota por `(marca, tipo, subtipo, faixa de capacidade)`. Todos
esses campos já saem normalizados do `classify()` + `chips/chip_types.py`:

| `kind` (= `label_kind`) | `gen` (geração) | `tier` (capacidade) | unidade |
|---|---|---|---|
| `emmc` | — (vazio) | capacidade do pacote | GB |
| `ufs`  | — (vazio) | capacidade do pacote | GB |
| `emcp` / `umcp` | geração LPDDR (do `subtype`) | **NAND do pacote** | GB |
| `lpddr` | geração (do próprio `chip_type`) | capacidade do pacote | GB |
| `ddr`  | geração (`DDR3`, `DDR3L`, `DDR4`, `DDR5`) | densidade do die | **Gb** |
| `gddr` | geração (`GDDR5`, `GDDR6`…) | densidade do die | **Gb** |

- `kind` = `label_kind(canonical_chip_type(chip_type, subtype))` — fonte única já
  existente. `gen` = token canônico (`canonical_gen`/`canonical_chip_type`).
- **eMCP/uMCP: a RAM exata FICA FORA da chave** (regra do comprador: todo eMCP 64GB
  custa igual, +3 ou +4 de RAM). O que muda preço é a **faixa de NAND** e a
  **geração LPDDR** do subtype. ⚠ Por isso o `subtype` errado é bug de preço
  (LPDDR4 4GB ≠ LPDDR4X 4GB na tabela Samsung: ¥25 vs ¥17).
- Tipo genérico (`DDR`/`LPDDR` sem geração — famílias K3/SDEM) **não keia preço** →
  sai `NO_KEY` com motivo "geração indeterminada". Correto por design; resolve-se
  com a dívida de dados, não com chute.
- Tipos `dead`/não comerciais (NAND raw, NOR, ePoP…) nunca chegam ao preço (barrados
  na rentabilidade).
- DDR em bytes → ×8 (256MB = 2Gb) — já é a convenção do sistema (die em Gb).

---

## 3. Modelo de dados (app Django novo: `pricing/`)

App separado (não incha `chips/`; permissões e dashboard do comprador vivem nele).

### 3.0 `Company` + `Membership` — a fundação do multi-tenant (✅ ENTREGUE)

> Construída na sessão dedicada (`PLANO_MULTITENANT.md` T1–T4, em produção).
> Os modelos reais vivem em `tenancy/` — o esboço abaixo é o contrato que a
> precificação consome; detalhes de integração no §12.1.

```
Company:    name, slug, active, notes              (empresa #1 = eMiner)
Branch:     company FK · name                      (filial — NULLABLE em tudo no v1)
Membership: user → FK User · company → FK Company · branch FK opcional
            role → admin | manager | operator      (unique: user × company)
```

- Resolve DOIS problemas de uma vez: (a) os papéis **admin/gerente/operador** que
  faltam hoje — "preço no card só para admin" exige distingui-los; (b) o gancho do
  multi-tenancy (§10 + `PLANO_MULTITENANT.md`) sem construí-lo inteiro agora.
- **Redirect pós-login por papel:** conta com `Buyer.users` → `/partner/` ·
  operador/gerente → `/estoque/` · admin → `/estoque/`. **Django admin é só da
  PLATAFORMA** (`is_superuser` — o dono do WTC), acima das empresas.
- Conta de comprador NÃO tem `Membership` (é externa — o vínculo é `Buyer.users`).
  Operador NÃO acessa o admin Django (hoje acessa o que não devia — isto corrige).
- **Regra imediata:** toda tabela nova daqui em diante nasce com caminho para
  company (FK direta ou via pai) ou é declarada explicitamente GLOBAL no §10. O
  retrofit das tabelas velhas do estoque é o projeto T3+ do `PLANO_MULTITENANT.md`.

### 3.1 `Buyer` — o comprador

```
company → FK Company (de quem é este comprador; NULL = comprador
          compartilhado da plataforma — cobre marketplace futuro)
name, slug, active, notes
users   → M2M com User (as contas que logam no dashboard deste comprador)
```

### 3.2 `PriceList` — uma lista de preços por (comprador × marca)

```
buyer         → FK Buyer
brand         → FK chips.Brand (NULL = LISTA GENÉRICA do comprador)
inherits_from → FK self, opcional (herança explícita; ver §4)
active, notes
unique_together (buyer, brand)
```

- **FK para `chips.Brand`** — nunca nome em texto (mata a divergência
  "Toshiba Kioxia"/"Toshiba/Kioxia"/`Toshiba-Kioxia` de uma vez; a tradução do
  nome da aba acontece UMA vez, no import).
- A **lista genérica** (`brand=NULL`) é a "UMA PÁGINA" do comprador: preços para
  marca desconhecida/genérica (o papel da aba `Other Brands`).

### 3.3 `Price` — a linha de preço

```
price_list  → FK PriceList
kind        → choices: emmc|ufs|emcp|umcp|lpddr|ddr|gddr   (vocabulário §2)
gen         → token canônico ("", "LPDDR4X", "DDR3L", "GDDR6"…)
tier_value  → Decimal (64, 8, 1024…)   ·   tier_unit → GB|Gb
status      → quoted | no_buy | unquoted        (ver §3.5)
price_min   → Decimal USD (NULL se não-quoted)
price_max   → Decimal USD (exato ⇔ min == max)
quote_date  → date (da cotação do comprador)
source, notes
last_updated → auto (auto_now)   ·   updated_by → FK User (setado no save)
unique_together (price_list, kind, gen, tier_value, tier_unit)
CheckConstraints: min ≤ max; quoted ⇒ min/max NOT NULL; no_buy/unquoted ⇒ NULL
```

**Trackeado por `pghistory`** (como as 4 tabelas de catálogo): todo write vira
evento com contexto — o histórico de cotações de longo prazo sai daí, sem tabela
extra e sem complicar a consulta do preço vigente.

### 3.4 `PricingConfig` — singleton no admin (padrão `ProfitabilityConfig`)

```
staleness_days      → int, default 90   (cotação mais velha → exibe "≈ referência")
default_scenario    → low|mid|high, default mid   (faixas: qual valor usar por padrão)
```

### 3.5 Os TRÊS estados de "sem preço" (achado da planilha real)

A planilha distingue três situações — o modelo preserva as três:

| Na planilha | No modelo | Significado | `price()` devolve |
|---|---|---|---|
| `NO` (Samsung GDDR) | `status=no_buy` | comprador **não compra** este item | `NO_BUY` |
| célula vazia numa linha existente (SK `32+4`, Toshiba UFS 1TB) | `status=unquoted` | combo existe, **aguardando cotação** — são as "células amarelas" a preencher no dashboard | `UNQUOTED` |
| linha inexistente | (sem registro) | faixa fora da grade | `NO_ROW` |

---

## 4. Resolução de preço — herança como DADO (regras do comprador ≠ código)

O curinga "Nanya" e o "SK = Samsung" são manias do Wuquan, não leis do mercado —
comprador 2 terá outras. Logo: **cadeia de fallback configurável por dado**, nunca
hard-code.

**Ordem de resolução para (buyer, brand, chave):**

```
1. lista da marca (linha própria)
2. lista apontada por inherits_from da lista da marca      (1 salto)
3. lista GENÉRICA do buyer (linha própria)
4. lista apontada por inherits_from da genérica            (1 salto)
→ nada casou: NO_ROW (ou NO_LIST se a marca nem genérica existem)
```

- Primeira linha que casa vence; linha própria **sobrepõe** herdada (override).
- **Travas:** herança não pode formar ciclo (validação no `clean()`) e é limitada a
  1 nível por lista — a cadeia completa acima é o máximo (previsível e depurável).
- **Wuquan codificado como dado:** lista genérica (`Other Brands`) com
  `inherits_from → lista Nanya` — reproduz a regra 4 do prompt ("primeiro Other
  Brands, senão Nanya") sem uma linha de `if`. Quando o comprador preencher a
  página genérica com DRAM próprio, o curinga Nanya morre sozinho.
- **SK Hynix: importar como linhas PRÓPRIAS, não espelho.** Achado na leitura
  integral da planilha: a aba SK **diverge** da Samsung em cobertura (sem eMMC
  256GB; LPDDR5X em capacidades diferentes; várias linhas `unquoted` que na Samsung
  têm preço). "São iguais" era aproximação. O recurso de espelho fica disponível
  (via `inherits_from`) para quando fizer sentido de verdade.
- **Marcas genéricas** (Rayson, PieceMakers, GigaDevice…): ganham `PriceList`
  própria **sob demanda** (lazy), herdando tudo da genérica; um override (ex.:
  Rayson eMMC 8GB = $1.50, que existe na planilha) cria a linha própria.

**No dashboard do comprador:** valores herdados aparecem acinzentados com a origem
("herdado da lista genérica"); editar um herdado cria a linha própria (override).

---

## 5. `price(result, buyer)` — contrato da fonte única (`pricing/engine.py`)

Entrada: o dict do `classify()` (com os campos numéricos da Fase 0) + `Buyer`.

Saída: dataclass `PriceQuote`:

```
status       → PRICED | NO_BUY | UNQUOTED | NO_KEY | NO_ROW | NO_LIST
reason       → texto humano do sem-preço ("geração indeterminada",
               "faixa 24GB inexistente na tabela", "aguardando cotação"…)
price_min / price_max / price(scenario)  → Decimal USD
is_range     → bool (min ≠ max)
is_stale     → bool (quote_date > staleness_days)
quote_date   → date da cotação usada
provenance   → qual PriceList/linha respondeu + flag herdado/próprio
```

Regras: deriva a chave via §2 (usa `chip_types.py` + campos numéricos — **nunca
parseia string de exibição**); resolve via §4; **não inventa nada** — qualquer furo
vira status + motivo. Exibição de aproximado: `≈ $13.50–16.50` + cenário + data.

**Lote:** `price_lot(lot, buyer, scenario)` agrega: por linha → unitário × qtd; no
fim → total geral, **cobertura** (% de unidades e % de linhas com preço), lista do
sem-preço com motivo, totais nos 3 cenários quando houver faixa. O relatório de
cobertura é também o **dashboard da dívida de dados em dólares** (prioriza o
`PLANO_QUALIDADE_DADOS.md` por valor comercial).

---

## 6. Import da planilha — `import_price_xlsx <arquivo> --buyer wuquan`

Management command, **dry-run por padrão**, `--commit` grava (dono roda). Regras
extraídas da planilha REAL (todas já verificadas nas 10 abas):

1. **Marca:** nome da aba → FK `Brand` via mapa de normalização do próprio comando
   ("Toshiba Kioxia"/"Toshiba/Kioxia" → `Toshiba-Kioxia`; "SK Hynix" → `SK Hynix`;
   `Other Brands` → lista genérica). Coluna A vazia → herda a marca da aba (há
   linhas assim nas abas Samsung e Micron). Coluna A com marca ≠ aba (Rayson na
   `Other Brands`) → lista própria daquela marca (lazy) com a linha como override.
2. **Preço-fonte = coluna F (RMB):** número → `min=max`; faixa `90-110` →
   `min/max`; `NO` → `no_buy`; vazio → `unquoted`. **USD = RMB × câmbio da célula
   B2** (Decimal, `ROUND_HALF_UP`, 2 casas) — a coluna E (USD) da planilha é
   ignorada (derivada). Câmbio e data ficam gravados nas `notes` do import.
3. **eMCP/uMCP:** capacidade `64+4` → `tier=64GB`, `gen=subtipo LPDDR`; **combos de
   RAM da mesma faixa colapsam numa linha só** (16+1 e 16+2 → uma linha 16GB).
   Validação: se dois combos da mesma (faixa, gen) tiverem preços DIFERENTES, o
   import **aborta com relatório** (contradiz a regra "cota por faixa" — decisão é
   do dono, nunca do código).
4. **DDR/GDDR:** `2Gb` → `tier=2`, unit `Gb`. eMMC/UFS/LPDDR: `16GB`/`1TB` → GB.
5. **Relatório final:** linhas importadas por estado (quoted/no_buy/unquoted),
   puladas, conflitos, marcas criadas. Idempotente (re-rodar = upsert).
6. Pós-import a planilha **se aposenta como fonte**: a verdade passa a ser o banco
   (admin + dashboard), em USD. RMB nunca mais entra no sistema.

---

## 7. Superfícies e permissões

| Quem | Onde | Vê / faz |
|---|---|---|
| **Plataforma** (superuser) | Django admin | tudo: Company, Buyer, PriceList, Price (com `updated_by`/`last_updated` visíveis), PricingConfig, histórico pghistory |
| **Admin** (dono da empresa) | busca `/chips/` | card de decode ganha bloco de preço (gate por PAPEL, não por `is_staff` solto) |
| **Admin** | estoque | **AINDA SEM PREÇO** (decisão 2026-07-06). Quando entrar (F8): valoração on-read + fechamento congela (`LotPricing`) + export com cobertura — admin-only |
| **Comprador** | dashboard `/partner/` | SÓ as listas do Buyer dele (ver §7.1) |
| **Gerente** | busca + estoque | **NADA de preço** (decisão do dono; se abrir um dia, é flag por empresa) — abre/fecha/exporta lotes, revisa pendentes (`PLANO_MULTITENANT.md` §5) |
| **Operador** | busca + estoque | **NADA de preço** — só adiciona chips e vê RENTÁVEL/NÃO RENTÁVEL |

### 7.1 Dashboard do comprador (`/partner/`) — o substituto definitivo da planilha

**Rotas (inglês):**

```
/partner/                      → home: pendências (unquoted, as "células amarelas"),
                                 cotações velhas (staleness) e as listas do comprador
/partner/lists/                → todas as listas dele (por marca + a genérica)
/partner/lists/<brand_slug>/   → grid de edição da lista da marca
/partner/generic/              → a "UMA PÁGINA" (lista genérica p/ marcas sem lista)
```

- **Stack:** Django templates + HTMX + CSS puro — padrão do projeto, sem SPA/build.
  Grid espelha a planilha (kind/gen/tier nas linhas), salvamento inline por linha
  via HTMX, input único com toggle "faixa" (min–max), botão "não compro" (`no_buy`),
  filtro "só pendentes".
- **Fluxo de login:** mesma página `/login/`; o redirect pós-login por papel (§3.0)
  manda a conta do comprador para `/partner/`. Sem cadastro público (como hoje) —
  o dono cria a conta e vincula em `Buyer.users`.
- **Ao salvar:** `quote_date` auto = hoje (editável), `updated_by` = request.user
  (invisível pra ele), `last_updated` auto. Tudo em USD.
- **Segurança:** mixin `PartnerRequired`; TODO queryset filtrado pelo Buyer da conta
  logada (nunca "esconder o link"); todo POST valida que a linha pertence ao Buyer;
  zero acesso ao admin; valores herdados aparecem acinzentados com a origem e editar
  um herdado cria a linha própria (override, §4).
- A home é o que mata a planilha de vez: o comprador vê sozinho o que falta cotar e
  o que está velho — o ping-pong de xlsx por e-mail acaba.

---

## 8. Fase 0 — pré-requisito no engine (campos numéricos estruturados)

**Problema:** os campos do resultado são strings de exibição (`"eMMC 5.1 64GB"`,
`"8Gb = 1GB por die [~]"`, placeholders `"⚠ cap. não mapeada"`). Preço não pode
parsear texto de humano.

**Mudança (aditiva, um ponto só — ✅ construída, ver §12):** `classify()` virou um
wrapper público fino sobre `_classify_impl()` (o pipeline, intocado) que anexa o
bloco numérico via `_attach_numeric_specs(r)` — UM ponto cobre todos os caminhos
de retorno (db exato, norm, FBGA, gramática, desconhecido, PN inválido):

```
nand_gb          → float|None  (de emcp_nand)
ram_gb           → float|None  (de emcp_ram — informativo; NÃO entra na chave)
ram_gen          → str         (token LPDDR canônico do subtype, fallback no
                               emcp_ram; "" se ausente — nunca adivinha)
cap_gb           → float|None  (de capacity)
density_gbit_num → float|None  (de dram_density, via _extract_gbit case-sensitive)
```

— reusando os extratores existentes (`_extract_gib`, `_extract_gbit`,
`canonical_gen`). Placeholders/`"None"` → `None` (nunca 0).

**⚠ Duas armadilhas descobertas na implementação (respeite ao consumir):**
1. **O nome `density_gbit` estava OCUPADO:** o `characterize_baseline` captura
   `r.get("density_gbit")` (string do KnownPart, hoje sempre vazia no result) —
   criar a chave numérica com esse nome quebraria o contrato de diff=0. Por isso
   o campo numérico é **`density_gbit_num`**.
2. **Nunca aplicar `_extract_gib` ao `dram_density`:** o `_CAP_RE` é
   case-insensitive e leria `"8Gb"` (gigaBIT) como 8 GB. Densidade só via
   `_extract_gbit` (case-sensitive) — coberto por teste.

**Prova de que nada quebrou** (levantamento: 42 arquivos .py + 6 templates leem as
strings — nenhum tocado; strings byte a byte idênticas): `characterize_baseline
--diff` com **0 alterados** + suíte completa verde (239) + `NumericSpecsTests`/
`NumericSpecsWiringTests` (âncoras por tipo, placeholder→None, armadilha Gb≠GB).
Documentar no CLAUDE.md §4 na F7: "resultado do classify: strings para humano,
numéricos para máquina".

---

## 9. Fases de execução (cada uma termina com prova verde)

| Fase | Entrega | Prova |
|---|---|---|
| **F0 ✅** (2026-07-07) | `_attach_numeric_specs` no engine + testes (§8 e §12) | suíte 239 OK no agente; characterize diff + suíte no ambiente do dono = runbook §12 |
| **F1 (=T1)** | **ENTREGUE PELO PROJETO MULTI-TENANT** (sessão dedicada, `PLANO_MULTITENANT.md` T1/T2): `Company`+`Branch`+`Membership` (admin/gerente/operador), redirect por papel, numeração de lote atômica | checklist de handoff (§15 de lá) completo |
| **F2 ✅** (2026-07-07) | app `pricing/`: modelos §3 + migrations (0001 + 0002-RLS) + pghistory + admin básico (§12.3) | suíte 256 OK no agente; migrate + testes Postgres no dono = runbook §12.3 |
| **F3 ✅** (2026-07-07) | `pricing/engine.py`: `price()`/`price_lot()` + goldens com os números da planilha real (§12.4) | suíte 266 OK no agente; runbook §12.4 |
| **F4 ✅** (2026-07-07) | `import_price_xlsx` + testes + **dry-run E commit validados na planilha real** no sandbox (314 preços; §12.5) | dono roda dry-run + `--commit` no banco dele = runbook §12.5 |
| **F5** | preço no card de busca (gate por papel admin) | suíte verde · teste do gate por papel |
| **F6** | dashboard `/partner/` (§7.1: listas, herdados, unquoted, permissões) | teste de isolamento entre buyers |
| **F7** | docs: este arquivo atualizado p/ bíblia + seção no CLAUDE.md (§4 e §5: comandos) | — |
| **F8** *(futura, quando o dono pedir)* | preço no estoque: valoração on-read, `LotPricing` congela no fechamento, export com cobertura | suíte estoque verde |

O retrofit multi-tenant do **estoque** NÃO é fase daqui — é projeto próprio (§10).

Deploy: migrations aditivas (rodam no build do Render); import roda **localmente
apontando `DATABASE_URL` ao prod, pelo dono** (mesmo fluxo do `load_brands`);
`guard_catalog` intocado (preço não mexe em known_parts).

---

## 10. Multi-tenancy — o CONTRATO (execução: `PLANO_MULTITENANT.md`)

Contexto (dono, 2026-07-06): o alvo são **centenas de empresas-clientes**, cada uma
com acesso, lotes e envios próprios — mas nada multi-tenant existe ainda. Decisão:
**não** construir tenancy completo antes dos preços (atrasaria semanas sem cliente
usando), **nem** ignorá-lo (retrofit de FK depois de milhões de linhas dói). O
meio-termo: fixar AGORA o contrato + o esqueleto mínimo (§3.0), e os preços já
nascem no lugar certo.

**O mapa de tenancy (o que pertence a quem):**

| Domínio | Tenancy | Por quê |
|---|---|---|
| Catálogo (Brand/ChipFamily/DecodeMap/KnownPart), gramática, engine, fuzzy | **GLOBAL** | é o produto — o "Google dos chips" é um cérebro só, compartilhado por todos os clientes; melhorou pra um, melhorou pra todos |
| `ProfitabilityConfig` | global hoje; candidata a por-empresa no futuro | cada empresa pode vir a ter critério próprio de rentável |
| Estoque (Lot/InventoryEntry/PendingEntry/RejectedEntry) | **POR-EMPRESA — retrofit T3+** | lotes e envios são da empresa |
| `Buyer` / `PriceList` / `Price` / `LotPricing` | **POR-EMPRESA desde o nascimento** (`Buyer.company`) | cada empresa vende aos compradores DELA; `company=NULL` reservado p/ comprador de plataforma (marketplace futuro) |
| Usuários | `Membership(user, company, role)` | uma conta, papel por empresa |

**Execução completa — arquitetura, blindagem e fases — vive no
`PLANO_MULTITENANT.md`:** banco compartilhado + isolamento por linha (row-level),
blindagem em 2 camadas (manager auto-escopado por contextvar + RLS do Postgres com
`SET LOCAL`/`FORCE`), hierarquia Company→Branch→Membership, correções de
concorrência (numeração de lote atômica — race real confirmada no código),
domínio/rotas, alavancas de escala e fases T0–T6. Não duplicar aquele conteúdo aqui.

**Regra imediata (vale desde já, entra no CLAUDE.md na F7):** tabela nova sem
decisão explícita de tenancy não passa — ou tem caminho para company, ou está
declarada GLOBAL nesta tabela.

---

## 11. Decisões

**Fechadas (brainstorm 2026-07-06):** USD canônico + Decimal · faixas = min/max +
cenário na consulta · 3 estados de sem-preço · preço on-read, congela no fechamento
do lote (F8) · multi-comprador dia 1, company-aware · papéis de usuário AGORA (F1:
**admin/gerente/operador** por empresa; plataforma = superuser; parceiro externo) ·
gerente e operador NÃO veem preço · herança/fallback como dado por comprador (1
nível, sem ciclo) · SK Hynix importa linhas próprias (dado real ≠ espelho) · sem
interpolação (fora da grade → dono adiciona linha) · preço no estoque ADIADO (F8) —
v1 só no card de busca, admin · rotas públicas em inglês (`/partner/`) · app
`pricing/` · a planilha morre no import · auditoria via pghistory, oculta do
comprador · rentabilidade separada do preço · contrato de tenancy do §10 (catálogo
GLOBAL, comércio POR-EMPRESA; execução no `PLANO_MULTITENANT.md`) · nomenclatura
`Company`/`Branch` (não "Organization").

**Em aberto (decidir antes/durante as fases):**
- `staleness_days` default (proposta: 90) e cenário default (proposta: médio).
- Layout do bloco de preço no card de busca (F5).
- F8: `LotPricing` congela no export do `.xlsx` ou num botão "fechar lote" explícito.
- Negócio (quando o SaaS abrir): compradores por empresa, de plataforma, ou ambos —
  o schema já cobre os três (`Buyer.company` nullable); decidir com o 2º cliente.

**Riscos conhecidos (aceitos, com mitigação):**
- **Dívida de dados** (`PLANO_QUALIDADE_DADOS.md`): ~440 confirmados sem família não
  keiam preço → saem `NO_KEY`/`NO_ROW` e aparecem na cobertura em dólares (que
  prioriza a correção). Frentes 1–2 do plano de qualidade correm em paralelo.
- **`subtype` LPDDR4 vs 4X** muda preço (item aberto KMDD) — golden de F3 cobre.
- Famílias genéricas (K3/SDEM) sem preço até confirmação de geração — por design.

---

## 12. Diário de execução

### 12.1 Fundação recebida do multi-tenant (2026-07-07) — o que a precificação consome

Verificado no código após o deploy da fundação (T1–T4 + polimentos, suíte 231):

- **`tenancy.Company`/`Branch`/`Membership`** existem (eMiner = empresa #1 em
  prod, papéis reais atribuídos via `bootstrap_tenancy`). `Buyer.company` (F2)
  aponta para `tenancy.Company`.
- **`TenancyDeclarationTests` (estoque/tests.py) é o portão de tenancy:** ao criar
  o app `pricing/`, adicionar `'pricing'` em `APPS_DO_PROJETO` e cada modelo novo
  OU à lista `GLOBAL_DECLARADOS` OU escopado (campo `company` +
  `CompanyScopedManager` como manager padrão + `Meta.base_manager_name=
  'all_companies'`). Sem isso a suíte fica vermelha — por design.
  ⚠ `Buyer.company` é NULLABLE (comprador de plataforma): o manager escopado
  padrão filtra por igualdade — decidir na F2 como expor os de plataforma
  (provável: manager custom `Q(company=cid) | Q(company__isnull=True)` só-leitura).
- **RLS (Camada B):** seguir o padrão de `estoque/migrations/0014_t4_rls.py` para
  as tabelas do pricing na F2 — `ENABLE`+`FORCE`+policy lendo os GUCs
  `app.company_id`/`app.platform` (o `TenancyMiddleware` já os emite
  transaction-local). Policies também nas tabelas de EVENTO pghistory do pricing
  (preço é rastreado — histórico é tão sensível quanto o dado).
- **Gates de view:** usar `tenancy/access.py::role_required('admin')` /
  `RoleRequiredMixin` (F5: card de preço é admin-only; SEM bypass de superuser —
  decisão da fundação). Parceiro (F6) fica FORA do enum de papéis: gate próprio
  por vínculo `Buyer.users`.
- **Comandos:** `import_price_xlsx` (F4) roda fora de request → escopo explícito
  via `scope_command_to_company()` (auto-resolve com 1 empresa ativa; 2+ exige
  `--company <slug>`), como os comandos do estoque.
- **Redirect pós-login:** hoje `LOGIN_REDIRECT_URL='/painel/'`. Na F6, conta com
  `Buyer.users` desvia para `/partner/` (mexer na lançadeira, não criar 2º login).

### 12.2 F0 — construída em 2026-07-07 (suíte 239/239 no agente)

- **`chips/engine.py`:** `classify()` virou wrapper público
  (`_attach_numeric_specs(_classify_impl(pn_raw))`) — pipeline intocado, anexo em
  UM ponto, todos os caminhos de retorno cobertos. Import novo:
  `from .conventions import canonical_gen`. Contrato e armadilhas: §8.
- **`chips/tests.py`:** `NumericSpecsTests` (pura, 7 casos: eMCP completo,
  placeholder→None, decimal/MB/TB, lixo/'None', armadilha Gb≠GB, ram_gen
  normaliza+fallback+não-inventa, dict de erro) + `NumericSpecsWiringTests`
  (wrapper anexa o contrato no caminho desconhecido). 239 testes OK no sandbox
  do agente (3 skips Postgres-only, esperados).
- **Achados registrados no §8:** colisão de nome com o characterize
  (`density_gbit` → `density_gbit_num`) e a proibição de `_extract_gib` sobre
  `dram_density`.
- **Nota de ambiente (sem ação):** no sandbox do agente, o
  `GlobalMapGuardTests` não conseguia apagar o yaml temporário
  (`_guardtest.yaml` órfão fez o golden reclamar) — permissão de delete
  habilitada e arquivo limpo; no ambiente do dono isso não ocorre.

**Runbook do dono (F0):**

```bash
python manage.py test chips estoque tenancy --settings=core.settings_test   # 239 esperados
python manage.py characterize_baseline --diff baseline_t1t2.json            # "alterados: 0"
                                        # (PNs novos do catálogo aparecem como "adicionados" — ok)
git add chips/engine.py chips/tests.py PRECIFICACAO.md
git commit -m "pricing F0: specs numéricas no classify() — strings pra humano, números pra máquina"
git push origin main                    # deploy (só código; sem migration, sem passo em prod)
```

### 12.3 F2 — construída em 2026-07-07 (suíte 256/256 no agente)

**O que existe (app `pricing/`, tudo versionado; nada gravado em banco ainda):**

- **`pricing/models.py`:** `Buyer` (company nullable = plataforma), `PriceList`
  (brand NULL = genérica; `inherits_from` 1 nível intra-comprador, valida ciclo/
  cadeia no `clean()`), `Price` (chave kind/gen/tier + min/max Decimal + 3
  estados + auditoria `updated_by`/`last_updated`), `PricingConfig` (singleton
  global, staleness=90d, cenário=médio). O **vocabulário da chave**
  (KIND_*/UNIT_*/STATUS_* + regras kind×unidade e kind×gen) mora no topo do
  módulo — a F3 consome de lá (fonte única).
- **Tenancy:** company DENORMALIZADA em PriceList/Price (herdada no `save()`,
  mismatch rejeita — padrão `CompanyBoundByLot`); managers `objects` fail-closed
  + `all_companies`; `TenancyDeclarationTests` atualizado (`pricing` em
  APPS_DO_PROJETO; `PricingConfig` declarado GLOBAL).
- **Migrations:** `0001_initial` (modelos + eventos pghistory + constraints) e
  `0002_rls` (ENABLE+FORCE+policy nas 3 tabelas **e nas 3 de evento pghistory**;
  a M2M `buyer_users` fica fora com justificativa no cabeçalho — só pares de
  ids; o acesso do parceiro é decidido na view da F6).
- **Admin (plataforma):** `PlatformScopedAdmin` local (padrão estoque);
  `PriceAdmin` mostra `updated_by`/`last_updated` (readonly) e o `save_model`
  grava quem mudou — Feature 3 do prompt, invisível ao comprador.
- **Testes (17):** portão (kind×unidade, kind×gen, quoted⇔valor, faixa
  invertida, chave duplicada), herança (1 nível, intra-comprador, genérica
  única, auto-herança), escopo (fail-closed, A não vê B, NULL invisível),
  singleton, pghistory-evento e RLS-handshake do pricing (2 últimos
  Postgres-only, espelho do padrão estoque com probe-role anti-superuser).

**Decisões fechadas na F2 (registro):**
1. **`Buyer.company=NULL` fica INVISÍVEL ao manager escopado** (fail-closed até
   o marketplace existir; plataforma vê via `all_companies`/GUC `app.platform`).
2. **Unicidade é do BANCO, não do `full_clean`:** `validate_unique`/`validate_
   constraints` consultam o `_default_manager` — que é o escopado fail-closed e
   explodiria fora de request. O portão valida campos+regras (`clean()`); chave
   duplicada vira `IntegrityError` da UniqueConstraint. ⚠ Lição para modelos
   escopados futuros.
3. **Constraint com vocabulário usa `sorted()`** — frozenset cru muda a ordem
   por processo e o `makemigrations --check` acusa mudança fantasma.

**Runbook do dono (F2):**

```bash
python manage.py migrate                    # pricing/0001 + 0002 (liga o RLS) — LOCAL
python manage.py test chips estoque tenancy pricing --settings=core.settings_test   # 256 esperados
python manage.py test pricing               # settings DEFAULT (Postgres): roda os 2 Postgres-only
                                            # (evento pghistory + RLS handshake do pricing)
# smoke: /admin/ → seção "Preços" (Compradores, Listas, Preços, Configuração)
git add pricing/ core/settings.py estoque/tests.py PRECIFICACAO.md
git commit -m "pricing F2: Buyer/PriceList/Price/PricingConfig — portão no modelo, pghistory, RLS"
git push origin main                        # build roda o migrate em prod (0001+0002, aditivas)
python manage.py guard_catalog              # hábito pós-deploy (DATABASE_URL do prod)
```

### 12.4 F3 — construída em 2026-07-07 (suíte 266/266 no agente)

**O que existe (`pricing/engine.py` — sem migração, código puro):**

- **`derive_price_key(result)`:** a chave (kind, gen, tier, unidade) derivada da
  saída normalizada do classify — `label_kind(canonical_chip_type(...))` +
  `ram_gen`/`cap_gb`/`nand_gb`/`density_gbit_num` da F0. Genérico (`DDR`/`LPDDR`
  sem número), tipo fora do mercado, capacidade/geração ausente → `NO_KEY` com
  motivo. **eMCP/uMCP: RAM fora da chave** (regra do comprador, provada em golden).
- **`price(result, buyer) → PriceQuote`:** resolução em cadeia (marca → herança
  da marca → genérica → herança da genérica; linha própria vence), 1 query pros
  candidatos; statuses `PRICED/NO_BUY/UNQUOTED/NO_KEY/NO_ROW/NO_LIST` + motivo;
  `value(low|mid|high)` (mid = ponto médio, ROUND_HALF_UP em centavos);
  `is_stale` (sem `quote_date` ou > `staleness_days`); proveniência (`via` +
  `source_list`).
- **`price_lot(lot, buyer) → LotPricingReport`:** ON-READ (re-classifica cada PN
  — catálogo vivo, nunca o snapshot), totais nos 3 cenários, cobertura por
  linhas e por unidades, sem-preço com motivo. Nada persiste (congelamento = F8).
- **Goldens (10 testes novos, números REAIS da planilha):** eMMC 64GB Samsung =
  $6 · eMCP LPDDR4X 64GB = 13.50–16.50 com cenários e RAM 3vs4 no mesmo preço ·
  LPDDR4 $3.75 ≠ LPDDR4X $2.55 · DDR3L não cai em DDR3 (e override da genérica
  sobre a Nanya provado) · GDDR5 `NO_BUY` · UFS `UNQUOTED` · 24GB `NO_ROW` ·
  genérico/NAND/sem-capacidade `NO_KEY` · cadeia inteira (SK herda Samsung;
  Rayson própria; Rayson→genérica→Nanya; marca desconhecida→Nanya) · staleness
  por data · `NO_LIST` · relatório de lote (cobertura 10/15 unidades, total $60).

**Decisões/descobertas da F3 (registro):**
1. **Escopo:** `price()` consulta via `all_companies` FILTRADO pelo `buyer` — o
   buyer é o parâmetro de autorização (quem o obtém já passou por caminho
   escopado). `price_lot` exige escopo ativo (`lot.entries` é fail-closed).
2. **⚠ Para a F6 (dashboard `/partner/`):** conta de parceiro NÃO tem Membership
   → o middleware não emite GUC → **sob RLS, as queries do parceiro leriam 0
   linhas**. A F6 precisa emitir `app.company_id` da empresa do Buyer no fluxo
   do parceiro (extensão do middleware ou do gate `PartnerRequired`).
3. `Decimal.normalize()` sozinho imprime notação científica (`64.0`→`6.4E+1`) —
   mensagens usam `:f`.

**Runbook do dono (F3 — só código, sem migração):**

```bash
python manage.py test pricing --settings=core.settings_test      # 27 esperados
python manage.py test chips estoque tenancy pricing --settings=core.settings_test   # 266
git add pricing/ PRECIFICACAO.md
git commit -m "pricing F3: price()/price_lot() — chave, herança, cenários, staleness, goldens"
git push origin main
```

### 12.5 F4 — construída em 2026-07-07 (suíte 271/271; validada na planilha REAL)

**O que existe:** `pricing/management/commands/import_price_xlsx.py` — todas as
regras do §6 encodadas (normalização de marca com aliases Toshiba; câmbio da B2
por aba, RMB→USD Decimal ROUND_HALF_UP; faixa/`NO`/vazio → 3 estados; colapso
eMCP por faixa; coluna A vazia herda a aba, marca na coluna A ganha lista
própria; upsert idempotente pela chave; `Instructions`/`Sheet1` ignoradas;
linha malformada = pulada com motivo; conflito/câmbio-ausente/marca-sem-cadastro
= ABORTA sem gravar; escopo via `scope_command_to_company`). +5 testes com
fixture xlsx gerada em memória.

**Prova de fogo no sandbox (banco descartável):** dry-run e `--commit` contra a
`wuquanprices.xlsx` REAL → **314 preços** (227 cotadas · 6 não-compra · 81
aguardando · 31 combos eMCP colapsados · 9 listas · zero conflitos) e o ciclo
completo funcionando: `price()` devolveu eMMC Samsung 64GB = **$6.00**, eMCP SK
LPDDR4X 64GB = **13.50–16.50** (mid 15.00), DDR4 8Gb Nanya = **$1.50** — os
números exatos da planilha.

**Refino descoberto na planilha real:** a aba SK tem combos VAZIOS na mesma
faixa de combos cotados (64+4 cotado, 64+6 vazio). O colapso agora aplica
"informação vence ausência" (cotado > não-compra > vazio); **conflito de
verdade** = cotado×cotado divergente ou cotado×NO — esses continuam abortando.

**Runbook do dono (F4):**

```bash
# local:
python manage.py test pricing --settings=core.settings_test                  # 32 esperados
python manage.py test chips estoque tenancy pricing --settings=core.settings_test  # 271
python manage.py import_price_xlsx wuquanprices.xlsx --buyer wuquan          # DRY-RUN: revisar
python manage.py import_price_xlsx wuquanprices.xlsx --buyer wuquan --commit # grava LOCAL
# admin local: Listas de preços → configurar herança do Wuquan:
#   · lista GENÉRICA  → herda de → Nanya      (o "curinga" DRAM, agora dado)
#   (SK importou linhas próprias — espelho fica a critério futuro)
git add pricing/ PRECIFICACAO.md
git commit -m "pricing F4: import_price_xlsx — a planilha vira banco (e se aposenta)"
git push origin main
# produção (a noite do deploy): backup Render Export →
export DATABASE_URL="postgresql://…render.com…"
python manage.py import_price_xlsx wuquanprices.xlsx --buyer wuquan          # dry-run em prod
python manage.py import_price_xlsx wuquanprices.xlsx --buyer wuquan --commit
python manage.py guard_catalog
```

**Próxima fase: F5** — preço no card de busca `/chips/`, gate por papel ADMIN
(`tenancy.access`; gerente/operador seguem sem ver preço). Pequena: uma chamada
a `price()` na view + bloco no template.
