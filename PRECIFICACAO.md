# PRECIFICACAO.md — Sistema de Preços do WhatTheChip (plano completo)

> **Status: F0 CONSTRUÍDA (2026-07-07) · F1 entregue pela fundação multi-tenant.**
> Design de ponta a ponta acordado no brainstorm de 2026-07-06 (dono + agente), a
> partir do `PROMPT_PRECOS.md` e da planilha `wuquanprices.xlsx` (comprador Wuquan).
> A fundação (`PLANO_MULTITENANT.md`, T1–T4) está construída e em produção — a
> precificação roda em cima dela. **Ver §12 (diário de execução)** para o que já
> existe e o runbook de validação de cada fase. **F2–F6 + F8 CONSTRUÍDAS
> (2026-07-07, suíte 283/283). Import REAL gravado: 314 preços, planilha
> APOSENTADA. Preço vivo na home, na bancada e no lote; dashboard do comprador
> em `/partner/` no ar.** Resta: **F7** (dobrar docs no CLAUDE.md e promover
> este arquivo a bíblia).
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
| **F5 ✅** (2026-07-07) | preço no card de busca, gate por papel admin (§12.6) | suíte 273 OK · `PriceCardGateTests` (admin vê; gerente/operador/anônimo não) |
| **F6 ✅** (2026-07-07) | dashboard `/partner/` (§7.1 e §12.8: home com pendências/staleness, grid com herdados, save com portão, GUC do parceiro, lançadeira) | suíte 283 OK · `PartnerDashboardTests` (gate, isolamento entre buyers, auditoria invisível) |
| **F7** | docs: este arquivo atualizado p/ bíblia + seção no CLAUDE.md (§4 e §5: comandos) | — |
| **F8 ✅** (2026-07-07, antecipada a pedido do dono) | preço na bancada do lote (admin) + valoração on-read no lote + `LotPricing` congela no fechamento (§12.7). Export com preço: fora por ora (vazaria ao gerente) | suíte 277 OK · `BenchAndLotPricingTests` |

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
# ⚠ --company OBRIGATÓRIO quando há 2+ empresas ativas (local tem a "Brasil
#   Reciclagem" de teste — o fail-closed exige o slug explícito):
python manage.py import_price_xlsx wuquanprices.xlsx --buyer wuquan --company eminer          # DRY-RUN
python manage.py import_price_xlsx wuquanprices.xlsx --buyer wuquan --company eminer --commit # grava LOCAL
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

### 12.6 F5 — construída em 2026-07-07 (suíte 273/273; import REAL já gravado no local)

**Contexto:** o dono rodou o `import_price_xlsx --commit` no banco local — 314
preços vivos, comprador Wuquan criado, planilha oficialmente aposentada.

**O que existe:**

- **`chips/views.py::_price_quotes_for_admin(request, result)`:** gate por
  PAPEL antes de qualquer query — `request.company_role != 'admin'` → lista
  vazia (operador/gerente/anônimo nem disparam a resolução). Admin → um
  `PriceQuote` por comprador ativo da empresa (v1: o Wuquan; multi-comprador já
  funciona de graça). Import lazy (chips não depende de pricing no load).
- **Bloco no `decode_card.html`** (após o cabeçalho): PRICED → `US$ 6,00` ou
  `≈ US$ 13,50–16,50` + méd. + data da cotação (ou "referência (sem data)") +
  proveniência (`marca`/`herança…`); NO_BUY → "não compra este item"; UNQUOTED →
  "aguardando cotação"; NO_KEY/NO_ROW → "sem preço — motivo". O `≈` marca
  faixa/staleness (princípio #4).
- **`PriceQuote.mid`** (property sem argumentos) para uso em template.
- **`PriceCardGateTests`:** admin vê o bloco; gerente, operador E anônimo
  recebem o card sem `dc2-price-block` (gate provado na view, não no template).
  ⚠ Nota de l10n: `LANGUAGE_CODE=pt-br` formata Decimal com vírgula ("6,00") —
  asserções de preço em teste não devem fixar o separador decimal.

**Runbook do dono (F5 — só código):**

```bash
python manage.py test chips estoque tenancy pricing --settings=core.settings_test   # 273
python manage.py runserver     # smoke: logar como ADMIN → buscar KLMAG2GE4A-A001
                               # (ou outro PN classificável) → bloco 💰 no card;
                               # logar como operador → card SEM preço
git add chips/views.py chips/templates/chips/partials/decode_card.html pricing/ PRECIFICACAO.md
git commit -m "pricing F5: preço no card de busca — admin-only, com cenários/staleness/proveniência"
git push origin main
```

**Produção (quando quiser ligar os preços lá):** o código sobe no push; os
DADOS entram com o mesmo import rodado contra o prod (backup antes, como
sempre): `export DATABASE_URL=<prod>` → dry-run → `--commit` → `guard_catalog`.

### 12.7 F5-bis + F8 — construídas em 2026-07-07 (suíte 277/277)

**F5-bis — o card da home é JS, não o partial (achado do smoke do dono):** a
home renderiza o resultado client-side a partir do JSON de `/chips/search/`
(o `decode_card.html` da F5 só atende o partial HTMX de `/chips/decode/`).
Correções: `search_api` agora anexa `result["prices"]` — **só para papel
admin** (o gate é do servidor; para os demais a chave nem existe no JSON;
Decimal serializado como STRING) — e o `renderResult` do `_content/index.html`
ganhou o bloco 💰. ⚠ A home é uma Page do CMS: depois de editar o
`_content/index.html`, rodar **`python manage.py sync_index_page`** (senão o
banco segue servindo o JS antigo).

**F8 — preço na bancada + valoração + congelamento (antecipada a pedido):**

- **Fonte única do gate:** `pricing.engine.quotes_for_admin(request, result)`
  (chips/views delega; estoque/views consome). Markup na fonte única
  `pricing/templates/pricing/price_block.html`, incluído pelo `decode_card.html`
  E pelo `confirm_card.html` (bancada — só em `aprovado`/`fila`; preço de
  sucata não orienta triagem).
- **Valoração do lote (admin-only, `estoque.html`):** lote ABERTO = estimativa
  on-read da tabela viva (re-classifica cada PN); lote FECHADO = painel do
  **congelado**.
- **`LotPricing` (modelo novo, migrações 0003+0004-RLS):** no fechamento do
  lote (`lot_close`), um snapshot por comprador ativo — totais nos 3 cenários,
  cobertura, linhas em JSON (auditoria "vendi com qual tabela"). Reabrir+fechar
  = outro registro (append). Falha de preço **nunca trava o fechamento** (log e
  segue). Gerente fecha mas não vê valores; admin vê painel + registro no
  Django admin (read-only). Export `.xlsx` segue SEM preço (deliberado:
  exportar é permissão de gerente — colunas de preço vazariam; um "export
  valorizado" admin-only fica como melhoria futura).

**Lições de implementação (registro):**
1. ⚠ **`{# … #}` do Django NÃO é multilinha** — comentário longo em template
   vira TEXTO RENDERIZADO (vazou "Valoração do lote" pra todo papel até o
   teste pegar). Comentário longo = `{% comment %}…{% endcomment %}`, sempre.
2. Em teste, mock de `classify` com `return_value` compartilhado + view que
   MUTA o result (`search_api` anexa `prices`) vaza estado entre chamadas —
   usar `side_effect=lambda pn: dict_novo()`.

**Runbook do dono (F5-bis + F8):**

```bash
python manage.py migrate                    # pricing/0003 (LotPricing) + 0004 (RLS)
python manage.py sync_index_page            # publica o JS novo da home (CMS Page)
python manage.py test chips estoque tenancy pricing --settings=core.settings_test   # 277
python manage.py test pricing               # Postgres-only (RLS + pghistory)
python manage.py runserver                  # smoke como ADMIN:
                                            #  · home: buscar H5TQ4G63AFR → 💰 US$ 0,60
                                            #  · lote: preview do mesmo PN → 💰 no card
                                            #  · lote: painel "Valoração do lote" no topo
                                            #  · fechar lote → painel vira "congelada"
                                            # e como OPERADOR: nada de preço em lugar nenhum
git add pricing/ chips/ estoque/ _content/index.html PRECIFICACAO.md
git commit -m "pricing F5-bis+F8: preço na home (JSON/JS), bancada do lote e LotPricing congelado"
git push origin main
# prod (quando for ligar): build migra; rodar com DATABASE_URL do prod:
#   sync_index_page (home nova) → import_price_xlsx (se ainda não rodou) → guard_catalog
```

### 12.8 F6 — construída em 2026-07-07 (suíte 283/283)

**O dashboard do comprador está no ar — a planilha morreu de vez (§1.10).**

- **`pricing/views.py` + `pricing/urls.py` em `/partner/`:** `partner_home`
  (KPIs: aguardando cotação + cotações velhas; tabela de listas com pendências),
  `partner_list` (grid espelhando a planilha: linhas próprias editáveis,
  **herdadas acinzentadas** com a origem — salvar numa herdada cria a linha
  própria/override, §4) e `partner_save` (semântica da planilha: USD preenchido
  → cotado com `quote_date`=hoje; "não compro" → NO; vazio → aguardando;
  `updated_by` GRAVADO mas jamais exibido — §7). Sem HTMX de propósito:
  formulários simples + PRG.
- **`partner_required` resolve o GUC do parceiro (a descoberta do §12.4):**
  conta de comprador não tem Membership → o middleware não emite
  `app.company_id` → sob RLS leria 0 linhas. O decorator roda a view inteira
  dentro de `company_scope(buyer.company)` (contextvar + GUC com restauração).
  Autorização em 3 camadas: vínculo `Buyer.users` (gate) + posse por queryset
  (lista alheia = 404) + RLS.
- **Lançadeira:** `tenancy/access.py::role_required` agora, no caso
  "sem Membership", verifica o vínculo de comprador e redireciona para
  `/partner/` (em vez de 403) — parceiro que cai em `/painel/` ou qualquer rota
  de estoque é levado pro lugar dele. Import lazy (tenancy ≠ dependente de
  pricing no load).
- **Templates standalone** (`partner_base/home/list.html`): o parceiro não vê o
  chrome da empresa. ⚠ Lição de HTML: `<form>` dentro de `<tr>` envolvendo
  `<td>` é inválido (o browser ejeta o form) — o padrão certo é o `<form>` no
  último `<td>` + inputs com atributo `form="fN"`. E inputs `type=number`
  precisam de `{% localize off %}` (l10n pt-br poria vírgula no value).
- **`PartnerDashboardTests` (6):** gate (anônimo→login, membro→403,
  parceiro→200), lançadeira, herdado+override, os 3 estados no save com data e
  `updated_by`, erro do portão não grava, e **isolamento entre compradores**
  (lista alheia 404 no GET e no POST).

**Runbook do dono (F6 — só código, sem migração):**

```bash
python manage.py test chips estoque tenancy pricing --settings=core.settings_test   # 283
python manage.py runserver
# smoke do parceiro:
#   1. admin Django → Compradores → Wuquan → vincular uma conta de teste em "users"
#      (conta SEM Membership — ex.: criar usuária "wuquan_teste")
#   2. logar como wuquan_teste → /login/ → cai em /partner/ (lançadeira)
#   3. home: KPI "Aguardando sua cotação" (os 81 unquoted do import)
#   4. abrir a lista SK Hynix → linhas próprias + (se configurar herança) herdadas cinzas
#   5. preencher um USD → Salvar → tag "cotado <hoje>"; conferir no admin que
#      updated_by/last_updated foram gravados (e que o parceiro NÃO os vê)
#   6. logar como operador → /partner/ → 403
git add pricing/ tenancy/access.py core/urls.py PRECIFICACAO.md
git commit -m "pricing F6: dashboard /partner/ — a UMA PÁGINA do comprador (GUC, herança, portão)"
git push origin main
```

### 12.9-bis DECISÃO: PREÇO FIXO — faixa desativada (dono, 2026-07-07; suíte 283/283)

O dono revisou o v1: **um preço só, sem variação** ("para deixar o sistema mais
simples"). A faixa min/max existia porque a planilha REAL do Wuquan tinha
faixas ("90-110" RMB) e o prompt original mandava encodá-las (regra 3) — mas a
simplicidade venceu. Implementação REVERSÍVEL:

- **Schema fica** (`price_min`/`price_max` como representação interna) — o que
  muda é a TRAVA: migração `0005_fixed_price` **achata as faixas existentes no
  ponto médio** (ROUND_HALF_UP, centavos) e adiciona a CheckConstraint
  `price_fixed_only` (cotado ⇒ min = max); o `clean()` dá a mensagem amigável.
  **Reativar faixa = remover trava + regra do clean()** (sem migração de dados).
- **Import:** faixa da planilha → ponto médio (ex.: "90-110" RMB → ¥100 →
  US$ 15.00). Conflito eMCP continua sendo detectado (mids diferentes ≠).
- **UI/displays:** partner grid com UM campo "Preço US$"; card da busca, JS da
  home e valoração do lote sem "min–max/méd." — só o valor. `value()`/cenários
  do engine seguem existindo mas colapsam (min = max); `LotPricing` mantém as 3
  colunas (iguais) por compatibilidade.
- **Nota (Q2 do dono, registrada):** eMCP/uMCP precificar por NAND+geração
  (RAM fora da chave) é REGRA DO COMPRADOR (Instructions da planilha + regra 2
  do prompt), confirmada nos dados: 31 combos colapsaram sem nenhum conflito.

⚠ Rodar `sync_index_page` de novo (o JS da home mudou).

### 12.13 `add_price_row` — faixa nova revelada por chip real (2026-07-08)

Caso real: H9HCNNN8KUMLHRNLE (SK Hynix **LPDDR4X 1GB**) saiu "fora da grade" —
a planilha nunca teve LPDDR4X 1GB. É o fluxo previsto ("sem preço → dono
adiciona a linha", §2/§11), agora com ferramenta própria:

- **`add_price_row --buyer wuquan --kind lpddr --gen LPDDR4X --tier 1 --unit GB
  --made-by "Samsung,SK Hynix,Micron,Nanya"`** — a faixa nasce em TODAS as
  listas do grid unificado: `--made-by` + Outras marcas → **não cotado** (o
  comprador cota no /partner/, com revisão); demais marcas → **não fabricado**.
  Valida kind×gen×unidade no portão; idempotente; dry-run por padrão.
- Quem fabrica LPDDR (matriz da aba Instructions): Samsung, SK Hynix, Micron,
  Nanya. Kingston/Toshiba-Kioxia/SanDisk entram como não fabricado.

### 12.20 F12 — MÁSCARA DE INFORMAÇÃO (código C-###; dono 2026-07-17; **ENTREGUE local** — suíte 380/380, i18n verde)

**Tese (dono):** o conhecimento "PN → o que é → quanto vale" é o ativo do
negócio — empresa-CLIENTE não pode aprendê-lo usando a plataforma. O
operador vê o DESTINO, não o porquê.

**Decisões fechadas (brainstorm 2026-07-17):** código **GLOBAL e estável**
(sem variação por cliente — auditabilidade/confiança > embaralhamento);
formato **`C-###`** (canônico, nunca traduz); **1 código por CHAVE DE PREÇO**
(kind/gen/tier — F11.1/OV); numeração inicial **SORTEADA** (ordem natural da
grade vazaria estrutura), depois sequencial automático; baldes fixos
**C-000 · Geral** (aprovado sem chave), **CONFERÊNCIA** (fila) e
**DESCARTE** (reprovado — a palavra "NÃO RENTÁVEL" some da bancada);
gerente exporta com código, sem specs; **eMiner fora da máscara**
(`Company.is_platform`); **site público = fase 2** (ocultar a busca — hoje
ele ainda entrega decode completo a anônimo; furo CONHECIDO e aceito até lá).

**Implementação:** `pricing.CategoryCode` (GLOBAL — declarado no
TenancyDeclarationTests; dicionário só no Django admin, read-only;
`label_for_key` cria o próximo sequencial na 1ª aparição) + comando
**`seed_category_codes`** (chaves do grid + do estoque, sorteio, idempotente,
dry-run) + `tenancy.Company.is_platform` + **fonte única da política**
`tenancy.access.is_unmasked(request)` (superuser OU empresa is_platform).
Superfícies mascaradas p/ empresa-cliente: **bancada** (template WHITELIST
`confirm_card_masked.html`: PN + Caixa C-### gigante/baldes + typo-popup
só-PNs + qtd + preço p/ admin — **sem specs, sem veredito nominal, sem
`data-debug`**, hidden inputs só pn/has_cap — o add re-classifica no
servidor); **tabela do lote** (badge C-### no lugar do tipo; sub-linha sem
marca/capacidade; filtro por tipo oculto); **export .xlsx** (colunas
PN/Category/Qty/Last Added + preço p/ admin); **vendas** (OV/acerto/fatura/
PDF com `display_label` = C-### p/ cliente, rótulo real p/ plataforma).
Fixtures "eMiner" dos testes viraram `is_platform=True` (semanticamente
correto); máscara testada com empresa-cliente própria (`MaskingTests` +
`SeedCategoryCodesTests`). 5 msgids novos es/en/zh. Migrações: tenancy
(is_platform) + pricing (CategoryCode), aditivas.

**Runbook local/prod (F12):** `migrate` → `seed_category_codes` (dry →
`--commit`) → marcar a eMiner como plataforma (admin → Empresas →
is_platform) → smoke com usuário de empresa-CLIENTE (bancada = "Caixa
C-###"; nada de eMMC/specs no HTML; export com Category; OV com C-###).

**Refinos do teste do dono (2026-07-20/21; suíte 388/388):**
- **Debug 📋 (copiar diagnóstico) = SÓ superuser** — nem admin de empresa
  (`confirm_card.html`, gate `user.is_superuser`; `DebugButtonGateTests`).
- **Card mascarado recuperou o diff verde do fuzzy** (parte digitada vs
  faltante — só caracteres do PN; `MaskedFuzzyDiffTests`).
- **Caixa SÓ para categoria VENDÁVEL (v2):** o seed v1 varria as chaves do
  ESTOQUE e cunhou DDR1/DDR2 (descarte). Agora `seed_category_codes` lê **só
  o grid** (lista ativa + comprador ativo, status cotado/não-cotado — no_buy
  e not_made ficam fora) e `CategoryCode.label_for_key` só CRIA código de
  chave vendável (`key_is_sellable`); fora do grid → **C-000 Geral**. Código
  já atribuído sempre vale (caixa é física). `--reset` ressemeia (SÓ
  pré-deploy). Sob RLS, requisição de cliente nunca cria código (a cunhagem
  é do seed/plataforma).
- **Fold de geração na categoria comercial** (`pricing.models.fold_gen`,
  fonte única): **DDR3L/DDR3U→DDR3** (já valia no derive desde 12.16) e
  agora **LPDDR4X→LPDDR4 / LPDDR5X→LPDDR5 no LPDDR AVULSO** — "mesma coisa,
  uma só caixa" (dono 2026-07-21), mantendo a separação por capacidade.
  **eMCP/uMCP mantêm a geração da RAM** na chave ("manter o formato" — a
  caixa divide pelo NAND, a RAM fica fora do tier desde a F11.1) e **GDDR
  nunca dobra** (GDDR5X é outro mercado). O fold aplica em: derive (escrita),
  `price_from_key` (LEITURA — chave materializada pré-fold resolve na
  linha-base sem resnapshot), agregação da OV (4 e 4X fundem na mesma linha),
  `label_for_key`/máscara, e o **grid se canoniza no save** (`Price.save`
  dobra o gen; variante com linha-base já presente → ValidationError amigável
  — o merge de ¥ é decisão do dono; `import_price_xlsx`/`add_price_row`/
  `enable_price_row` dobram na entrada). Goldens invertidos registrados:
  `test_lpddr4x_dobra_para_lpddr4_na_chave` (antes 4X tinha ¥ próprio) e
  `test_ddr3l_dobra_para_ddr3_na_chave` (linha DDR3L do grid agora é
  alcançável como DDR3 da marca). `FoldGenTests` cobre o contrato.
- **CONVENÇÃO UNIVERSAL v3 (dono 2026-07-23 — CONGELADA; fonte:
  `pricing/convention.py`):** os códigos viraram **`LETRA-##`** — letra FIXA
  por tipo (A=eMCP, B=eMMC, C=uMCP, D=UFS, E=DDR, F=LPDDR — anti-mnemônica
  de propósito), número CONGELADO pela **TABELA FUNDADORA** (55 categorias,
  embaralhada UMA vez na autoria — número nunca é ranking; append-only;
  nunca reordena/reusa). Baldes especiais: **H-00 HOLD** (fila de
  conferência — não embarca; também exibido p/ aprovado raro sem categoria
  derivável) e **R-00 REFINO** (reprovado); `00` reservado em toda letra;
  letras H/R reservadas (tipo novo pega G, I, J…). **O conceito
  "Geral/C-000" foi DESFEITO** (dono: "todos os chips devem ter categoria —
  preço até pode ficar sem, categoria não"): a categoria deriva do CHIP
  (decoder), nunca do grid — `key_is_sellable` removido; cunhagem de
  categoria inédita acontece na APROVAÇÃO da bancada (`label_for_key`,
  próximo número livre da letra, sem depender de preço); **leitura nunca
  cunha** (tabela do lote/OV usam `create=False` → '—' p/ legado sem
  código — é o que impede DDR1/DDR2 ressuscitarem: categoria morta nunca é
  aprovada). Fold do X estendido aos COMBOS (eMCP/uMCP LPDDR4X→LPDDR4,
  5X→5 — "LPDDR e LPDDRx devem ser unidos"). Roteamento da triagem
  INALTERADO (confirmado pelo dono: não confirmado → H-00, salvo gramática
  denunciando morte → R-00; confirmado + rentável → estoque). Seed v3 é
  DETERMINÍSTICO (carrega a fundadora; divergência banco×convenção = erro
  alto; `--reset` pré-deploy). Migração pricing/0015 (número por letra).
  ⚠ Transição do grid: linhas eMCP grafadas `LPDDR4X` ficam inalcançáveis
  até canonizar (re-save dobra sozinho; GÊMEA com a linha-base →
  ValidationError, dono funde no admin decidindo o ¥) — comando de
  canonização no runbook.
- **v3.1 — COMBOS SÓ PELO NAND (dono 2026-07-24, planilha `WuQuan_price_
  sheet_EN_v9.xlsx` "unified by cap"):** eMCP/uMCP perderam a geração de RAM
  na CHAVE (grid + caixa + OV): `fold_gen(emcp|umcp, *) = ''`,
  `_GEN_RULE` = vazio, derive keia só NAND — a geração segue nas specs e no
  rótulo real da plataforma. Fundação renumerada PRÉ-deploy: **A = 6 caixas**
  (eMCP 8/16/32/64/128/256GB — 256 entrou da v9) e **C = 4** (uMCP
  64/128/256/512GB); **E anexou E-12 DDR4 2Gb e E-13 DDR4 1Gb** (v9;
  rentáveis ≥1Gb). **DDR3 1Gb da v9 ficou FORA de propósito** (morto por
  densidade — mínimo DDR3 = 2Gb → nunca aprovado → R-00). Tabela = 53.
  Cruzamento planilha×convenção: UFS/eMMC/LPDDR/DDR restante = 1:1.
  `canonize_price_grid` virou GRUPO-a-grupo (várias gerações de combo → uma
  linha por NAND; vencedor = status mais informativo; divergência de ¥ →
  relatório). ⚠ `import_price_xlsx` lê o formato ANTIGO multi-aba — a v9 é
  aba única; leitor novo só se o dono pedir.
- **REPACTUAÇÃO — parte ESTRUTURAL (dono 2026-07-27, cobrança em prod: "a
  convenção mudou de FORMATO"):** eMCP/uMCP/LPDDR viraram preço ÚNICO
  brand-agnostic DE VERDADE — **a linha vive SÓ na lista GENÉRICA**
  (`UNIFIED_KINDS` em pricing/models; portão no save rejeita em lista de
  marca; a resolução de qualquer marca cai na genérica). **`unify_price_rows`**
  colapsa o legado (apaga linhas de marca — incl. not_made, que bloquearia o
  fallback; genérica sem ¥ herda o MAIS ALTO cotado; dry/backup/revert).
  **/partner/**: aba de marca só mostra eMMC/UFS/DDR; genérica ganha a seção
  "PREÇO UNIFICADO — vale para todas as marcas" no topo; eMCP/uMCP com DOIS
  campos (mín–máx) e `PriceChangeRequest.new_price_max` (migração 0018) —
  a moderação/approve aplica a faixa. `add_price_row` p/ kind unificado cria
  SÓ a genérica; `enable_price_row` recusa kind unificado; **import_price_xlsx
  (formato multi-aba velho) APOSENTADO/apagado** — o v2 grava unificados só
  na genérica. Fixtures da suíte migradas pra estrutura nova.
- **/partner/ POR TIPO (dono 2026-07-27: "menu lateral com cada marca ficou
  confuso… no menu lateral fica cada tipo de chip… RMB não tem casas
  decimais"):** sidebar/​home viram navegação por TIPO (`partner_kind`, rota
  `tipo/<kind>/`; SSD fora — é linear, sem grid). **eMCP/uMCP/LPDDR** =
  página de COLUNA ÚNICA (linhas da genérica; faixa mín–máx nos combos);
  **eMMC/UFS/DDR** = MATRIZ linha=geração+faixa × coluna=marca (+Outras=
  genérica; not_made vira "—" sem form) — cada célula posta no
  `partner_save` da lista DELA (moderação intacta; `from_kind` devolve à
  página do tipo). **¥ INTEIRO em todo o painel** (inputs `step=1`; valores
  formatados NA VIEW via `normalize():f` — floatformat ignora localize-off;
  notificações idem, com faixa "¥ a–b"); hiddens de `tier_value` sob
  `{% localize off %}` (vírgula pt-br quebrava o Decimal do save). Rotas
  antigas `lists/<pk>/` seguem no ar (legado/testes). `PartnerKindNavTests`
  (6); 9 msgids novos traduzidos es/en/zh no mesmo commit.
- **MATRIZ v2 (dono, mesma data: "muita informação… seletor confuso… seta
  sem ideia… compacta e responsiva"):** célula da matriz vira **UM campo
  estilo planilha** — número = ¥ · `x` = não compro · vazio = sem cotação
  (a MESMA convenção da planilha que o comprador já usa; `partner_save`
  ganha `mode=cell` que DERIVA o estado do campo — seletor extinto). Botão
  ↑ extinto: **OK aparece só na célula editada** (JS de 4 linhas, sem
  strings) e Enter também envia. Coluna Geração REMOVIDA (eMMC/UFS não têm;
  **DDR agrupa por linhas de seção** `ptn-matrix__gen`). Selo verde "Todos
  os preços em ¥ (RMB)" no topo de toda página de tipo. Responsivo: 1ª
  coluna **sticky** + rolagem horizontal das marcas (padrão mobile), célula
  58px, fundo amarelo/vermelho por estado, input 16px no celular (iOS não
  zooma). Legenda única embaixo. 3 msgids (es/en/zh; zh manteve "Enter"
  literal — glossário). Testes: 8 em `PartnerKindNavTests` (célula x/vazio/
  número vira pedido certo).
- **v3 (dono, mesma data: "bota um botão no final pra enviar… gostei da
  abordagem minimalista, faz o mesmo nos outros tipos… o dropdown vira
  bullet de informação"):** a página do tipo é **UM formulário** — rodapé
  FIXO (sticky bottom) com o botão **"Enviar para revisão"** + legenda
  única; o endpoint novo **`partner_kind_save`** (`tipo/<kind>/enviar/`,
  POST) faz o **DIFF no servidor**: só linha ALTERADA vira
  `PriceChangeRequest` (mesma moderação; "nada mudou" não gera pedido
  fantasma; not_made ignorada mesmo forjada no POST; erros por linha —
  ilegível/faixa invertida — voltam como messages sem travar o resto).
  Páginas UNIFICADAS (eMCP/uMCP/LPDDR) ganharam a MESMA linguagem da
  matriz: célula estilo planilha (x/vazio/número; par p<pk>/pmax<pk> nos
  combos), **LPDDR agrupa por geração** em linha de seção, e o dropdown de
  estado virou **SELO informativo** (Cotado/Não cotado/Não compro/Não
  fabricado — tags coloridas). O `mode=cell` do save unitário (v2) foi
  REMOVIDO — superado pelo batch; `partner_save` segue intacto p/ a rota
  legada `lists/<pk>/`. OK-por-célula e JS extintos. 7 msgids (es/en/zh).
  `PartnerKindNavTests` = 10 (batch x/vazio/número, diff só-do-que-mudou,
  faixa+ilegível, selo sem dropdown).
- **HOME + CATÁLOGO PDF na convenção (dono, mesma data):** `catalog_data`
  REESCRITO — devolve SEÇÕES na ordem do painel (`_SECTION_KINDS`), cada
  uma com as PRÓPRIAS colunas: unificada (eMCP/uMCP/LPDDR) SEM coluna de
  marca (tabela capacidade → preço único, título "— preço único para todas
  as marcas"; **faixa '90–100'** nos combos, en-dash WinAnsi); por marca
  (eMMC/UFS/DDR) em matriz ENXUTA (só marcas com linha do tipo + Outras);
  **SSD entra como linha "por GB"** quando o contrato tem `ssd_rmb_per_gb`
  (não há grid de SSD). ¥ inteiro/sem zeros; USD derivado 2 casas (faixa
  nas duas moedas). `render_catalog_pdf` perdeu o param `columns` (cada
  seção traz o seu). Home: rodapé explica a convenção (unificado × por
  marca × coluna «Outras») e o card do PDF fala "tabela completa" (era
  "todas as tabelas", jargão da era por-marca). 4 msgids es/en/zh.
- **BUG do lote 042 (2026-07-31) — chip aprovado SEM categoria (H-00 na
  máscara):** H5AN8G8NCJR(-VKC) entrou no estoque com `price_kind='ddr'`
  mas motivo "densidade (Gb) indisponível" → sem chave → sem caixa. Causa:
  cap_map per-die com die ≥ 1GB ('8G'→'1GB') — o derive de densidade
  (2026-07-11) aceitava só 'NNNMB'/Gbit pelado; a guarda anti-GB era larga
  demais DENTRO de kind-DDR (lá capacity é per-die por convenção §6; o
  próprio tip do yaml valida 4G=512MB=4Gb · 8G=1GB=8Gb · AG=2GB=16Gb).
  Fix de LEITURA em 3 pontos com fonte única: `RX_DIE_GB` em convention.py
  + branch GB×8 no engine (família) e no `_gbit_from_capacity` (known sem
  família). Escrita intacta (regra 4 segue recusando 'GB').
  `PerDieGbDensityTests` (3 caminhos); goldens H5AN/H5CG atualizados com a
  conta; guard antigo do `DdrDensityFallbackTests` revisado ('2GB'→16Gb,
  minúsculo continua fora). Prod: deploy + `resnapshot_lote` re-keia (o
  `validate_convention` dava 0 porque cobria só a forma Gbit — dado não
  precisa migrar, a densidade é derivada na leitura). PENDENTES do lote:
  JW/JZ eMCP identity-only (spec Tier-1), GDDR físico → R-00, decisão do
  portão "aprovado sem chave → fila".
- **REPACTUAÇÃO 2026-07-27 (planilha final do comprador — aba única):**
  **eMCP/uMCP em FAIXA** (os ÚNICOS: `price_fixed_only` liberou min≤max só
  p/ esses kinds + `price_range_ordered`; migração pricing/0017; portão
  clean() idem) — **vendas usam o PONTO MÉDIO** (`value_rmb()`/`value()` em
  draft/confirm; fixo = próprio valor, zero mudança; acerto ajusta ao real);
  card mostra "US$ mín–máx". **`import_price_sheet_v2`**: unified em faixa
  nos combos gravado em TODAS as listas não-not_made + genérica; LPDDR
  unified fixo (limpa sujeira "3,"/"8;"); eMMC/UFS/DDR por marca + coluna
  **Other = genérica**; "x" = no_buy; "—"/vazio não mexe; dry-run com diff
  célula a célula (NOVO/SUBIU/CAIU); backup + --revert; idempotente;
  quote_date = hoje. DEFERIDO: edição de faixa no /partner/ (parceiro
  editando uma faixa hoje colapsa em valor único — pendência). Panorama da
  repactuação: LPDDR −40…−80%, combos convergem (Samsung/SK ↓, Micron/
  Kingston ↑), UFS/eMMC/DDR praticamente estáveis + preenchimentos novos.
- **SSD ENTROU NO NEGÓCIO (dono 2026-07-24 — WeChat do comprador: "SSD
  chips are priced per GB… 512GB×0.1=51rmb / 128GB×0.1=13rmb"):** tipo
  canônico **`SSD`** no vocabulário (chips/chip_types.py; aliases bga/nvme) —
  os MTFD da Micron são **BGA SSD**, não eMMC (59 registros contaminados no
  catálogo, curadoria via shell do dono). Rentabilidade: cap conhecida →
  RENTÁVEL (¥ escala com GB); sem cap → INDETERMINADO. Pricing: kind `ssd`
  **LINEAR** — SEM linhas de grid: ¥ = GB × **`Buyer.ssd_rmb_per_gb`**
  (contratual, migração pricing/0016; NULL = sem preço com motivo), ¥ INTEIRO
  HALF_UP (512→¥51, 128→¥13 conferidos), US$ derivado, is_stale=False,
  via='por GB'; hook em price() e price_from_key ANTES da cadeia de listas.
  Convenção: **letra G = ssd** (deixa de ser livre; próximo tipo pega I);
  fundadoras G-01=440GB, G-02=220GB (capacidades reais do estoque; novas
  anexam na aprovação). Caixa unmasked: "SSD440GB". `SsdLinearPricingTests`.
- **GDDR FORA DO NEGÓCIO (dono 2026-07-23):** sempre **NÃO RENTÁVEL** (morto
  POR TIPO no `assess_profitability` — o bloco fica na posição, interceptando
  o substring "DDR"; `is_dead_by_generation`=True → descarte mesmo sem
  confirmação) e **extinto do pricing**: kind `gddr` fora de
  `KIND_CHOICES`/`KINDS`/`KIND_UNIT`/`_GEN_RULE` → `derive_price_key` devolve
  NO_KEY "tipo fora do mercado"; `import_price_xlsx` PULA linha GDDR da
  planilha; `gddr_min_gen`/`gddr_min_gbit` removidos (migração chips/0023);
  8 goldens GDDR flipados p/ NÃO RENTÁVEL (H5GQ, K4G, K4J, K4W, K4Z). O
  vocabulário GDDR/GDDR5X segue no CLASSIFICADOR (chip é identificado; o
  veredito é fixo). **Runbook:** apagar as linhas `kind='gddr'` do grid
  (local agora; prod no deploy) + reseed dos códigos (os C-### de GDDR somem
  — pré-deploy, renumeração livre). Bíblia atualizada: RENTABILIDADE.md §3.9
  e §9.1.

### 12.19 F11 — VENDAS (plano fechado 2026-07-16; **EXECUÇÃO INICIADA no local** — dono deu o "vai" 2026-07-16; publicação em prod só com runbook próprio)

**Motivação:** o incidente dos lotes 41/42 (valoração on-read = classify × PN
× comprador × ACESSO; 28s por página mesmo otimizada) + empresa crescendo
(clientes novos diários, multi-tenant no ar). O on-read do §1.7 foi decisão
nossa p/ 1 empresa e lotes pequenos — não é convenção de mercado; a convenção
(Odoo) é a que o dono pediu: **valor mora em documento comercial; estoque é
quantidade**.

**Decisões FECHADAS pelo dono (brainstorm 2026-07-16):**
- **Um comprador só, sempre** (Wu Quan) — sem multi-cotação/comparação; todos
  os lotes de TODOS os clientes da plataforma desaguam nele. Quando o 2º
  cliente chegar, Wu Quan vira **comprador de PLATAFORMA** (`company=NULL`,
  reservado no §3.1).
- **Sigilo total do comprador:** nome/slug/qualquer identificação = segredo
  de PLATAFORMA (é o segredo comercial da eMiner como broker). Empresa-cliente
  e usuário final NUNCA veem — telas/exports/PDFs internos usam rótulo neutro
  ou codinome; nome real só no Django admin. ⚠ Leaks atuais a corrigir na
  F11: card "💰 Wuquan" e header do export "Preço unit. — Wuquan (USD)" (ok
  enquanto o único cliente é a própria eMiner; OBRIGATÓRIO antes do 2º).
- **Lote aberto SEMPRE valorado** (admin) — via join barato (chave
  materializada), preço segue VIVO.
- **Lote fechado é imutável** (só admin); reabrir CANCELA cotação draft; com
  OV confirmada a reabertura é BLOQUEADA até cancelar a ordem (padrão Odoo).
- **OV em ¥ canônico com toggle US$** (visualizar em ambas — padrão F10).
- **Linhas da OV = resumo por CATEGORIA** (a chave de preço: "eMMC 4GB",
  "DDR3 2Gb", "eMCP LPDDR4X 64GB" — geração incluída: DDR3 2Gb ≠ DDR4 2Gb);
  o detalhado por PN fica só no inventário.
- **Resultado do comprador NUNCA edita a OV** (padrão Odoo: fatura pelo
  aceito + nota de crédito): entra como **ACERTO** vinculado — ajustes por
  categoria (mortos, repreciação) → valor final. Bônus: histórico de acerto
  por comprador vira dado de negociação.
- **Pagamentos sempre em US$** (parciais, contra a fatura; saldo em aberto
  nas duas moedas pela taxa congelada).
- **Retroativos:** lotes já fechados ganham OVs geradas dos `LotPricing`
  (migração de dados); o LotPricing é absorvido/aposentado.

**Arquitetura (3 camadas):**
1. **Escrita:** a bancada já classifica no lançamento → grava na entrada a
   **CHAVE de preço** (kind/gen/tier — estável; quem muda é o preço). Custo
   zero; defasagem de chave = mesma classe do snapshot (cura: resnapshot
   estendido, que também faz o backfill dos lotes existentes).
2. **Leitura (lote aberto):** valoração = chaves gravadas × `Price` vivo via
   `BuyerPricingContext` (construído no incidente 2026-07-16) — SEM classify;
   ~4-6 queries por página, qualquer tamanho/nº de compradores.
3. **Comercial (app `vendas/`):** fechamento → **Cotação draft** (valores
   VIVOS, re-join) → **confirmar congela** linha a linha (¥ unit + taxa
   contratual + US$ — auditoria cambial "vendi a 0.14") → **Acerto**
   (resultado) → **Fatura** (valor final) → **Pagamentos US$**. Link forte
   lote ↔ OV (botão nos dois sentidos). Menu Vendas admin-only (regra
   "gerente não vê valor" mantida). Tenancy por-empresa padrão T3/T4 + RLS +
   pghistory + numeração `(company, number)`.

**Assumidos salvo veto do dono:** app ÚNICO `vendas/` no v1 (OV+Acerto+
Fatura+Pagamento; separar `faturamento/` quando crescer).

**Nomenclatura (dono, 2026-07-16): UNIVERSAL, inglês, NUNCA traduz** — o
código é valor CANÔNICO (regra i18n: banco guarda canônico, rótulo em volta
traduz). Formato `PREFIX/NUM/MM/YY`: **`LOT/041/07/26`** (estoque; NUM = a
sequência perpétua por empresa que já existe — "lote 41" continua "lote 41",
MM/YY informativo do mês de abertura) · **`SO/012/07/26`** (ordem de venda) ·
**`INV/005/08/26`** (fatura — INV **confirmado pelo dono** 2026-07-16; BILL
descartado: no Odoo é conta de FORNECEDOR). **NUM perpétuo, NUNCA reinicia**
(confirmado); zero-padded 3 dígitos; sequência por empresa, `unique (company,
number)`.

**Anotado para o ESTOQUE (fora do escopo F11):** romaneio de FECHAMENTO
imprimível por categoria SEM valores (conferência física); a versão com
valores é o PDF da OV — nenhum expõe o comprador.

**Fases (cada uma com testes + tenancy declarado + i18n §7):**
- **F11.0 ✅ ENTREGUE 2026-07-16 (local; suíte 358/358):**
  (a) `price_lot_multi(lot, buyers)` — classify **1× por PN distinto**,
  compartilhado entre compradores (era 1× por PN × buyer: ~900 no lote 42);
  `_lot_valuations`/`_freeze_lot_pricing`/`_export_price_maps` migrados;
  `price_lot(lot, buyer)` mantido como caso-de-1.
  (b) **Paginação** do "Estoque do lote": 100 linhas/página (`?p=`), botões
  no padrão HTMX dos filtros; filtro/busca/add/remove resetam pra pág. 1
  (ordem -last_updated → recém-lançado sempre visível); valoração e export
  seguem cobrindo o lote INTEIRO. 3 msgids novos traduzidos es/en/zh.
  Testes: `test_multi_comprador_classifica_cada_pn_uma_vez` (10 classifies
  p/ 10 PNs × 2 buyers) + `LotPaginationTests`.
- **F11.1 ✅ ENTREGUE 2026-07-16 (local; suíte 362/362):** InventoryEntry
  ganhou a CHAVE DE PREÇO (`price_kind/gen/tier_value/tier_unit` +
  `price_key_reason` p/ NO_KEY — migração **0015**, aditiva); o intake grava
  via `_price_key_fields(server_result)` (o classify já rodou — custo zero);
  `BuyerPricingContext.price_from_key()` + `price_lot_multi` leem a chave
  gravada — **classify SAIU do caminho de leitura** (fica só no fallback de
  entrada LEGADA: pré-F11.1, aprovação de pendência, restores);
  `resnapshot_lote` faz o backfill/refresh da chave (filtro pega defasada
  **OU sem chave** — mesmo com carimbo em dia). ⚠ Pós-migrate, rodar
  `resnapshot_lote --all --commit` uma vez (backfill do estoque atual);
  freshness da chave = mesma régua do snapshot (§ resnapshot).
- **F11.2 ✅ ENTREGUE 2026-07-16 (local; suíte 369/369, i18n verde):** app
  **`vendas/`** — `DocSequence` (NUM perpétuo por empresa, atômico via
  select_for_update), `SalesOrder` (código canônico `SO/NUM/MM/YY`; estados
  draft→confirmed→cancelled; `one_active_so_per_lot`; congela
  `fx_usd_rate`/`total_rmb`/`total_usd` na confirmação — CheckConstraint
  `so_confirmed_is_frozen`) e `SalesOrderLine` (**categoria POR MARCA** — a
  chave de preço + brand: o comprador cota por marca, "eMMC 16GB" Samsung ≠
  SanDisk; detalhado por PN fica no inventário). **Fluxo:** fechar lote →
  cotação draft (agregada das chaves F11.1; `unkeyed_units` transparente);
  draft é VIVO (re-join via `price_from_key`); **confirmar exige todas as
  linhas cotadas** (erro lista as pendências — força completar o grid) e
  congela ¥+taxa+US$ linha a linha; reabrir cancela draft e é **BLOQUEADO**
  com OV confirmada; re-fechar cria OUTRA ordem (número novo). Telas
  `/vendas/` admin-only (nav "Vendas" no shell gated por `wtc_role`; barreira
  real = `@role_required('admin')`); dual ¥·US$ com `{% localize off %}`;
  nome do comprador NÃO aparece nas telas (sigilo; admin Django é o único
  lugar). Migrações **0001+0002-RLS** (padrão pricing); pghistory; tenancy
  declarado (`APPS_DO_PROJETO` += vendas). **Bônus:** o shell do estoque não
  renderizava `django.contrib.messages` — corrigido no `base_estoque.html`
  (o aviso de reabertura bloqueada era invisível). 28 msgids es/en/zh.
  Testes: `vendas/tests.py` (fluxo completo, congelamento vs grid vivo,
  bloqueio de confirmação com linha sem preço, numeração, hooks de
  fechar/reabrir, gates de papel). **Fica pra F11.2b:** PDF da OV.
  **Revisão do dono (2026-07-16, mesma entrega):** (a) `total_usd` da OV =
  **SOMA das linhas congeladas** (estilo fatura — quem confere linha a linha
  chega no total), não `total_rmb × taxa` (divergia por arredondamento por
  linha: caso ¥2.10 → 0.28 vs 0.294); (b) **type-to-confirm no fechamento**:
  digitar o código COMPLETO do lote (barreira na VIEW via `confirm_code`;
  prompt é UX); (c) **nomenclatura `LOT/NUM/MM/YY` aplicada** (`Lot.code`,
  exibida em painel/lotes/lote/vendas — a fala "lote 41" segue); (d) tabela
  do /vendas/ alinhada ao Carbon (hover/zebra); (e) **falso-bug de preço
  investigado**: prod lote 39 US$ 25k (congelado PRÉ-F10, Σ¥×0.15) vs local
  US$ 3,4k — o banco LOCAL nunca rodou o `migrate_prices_to_rmb` (só o prod
  rodou na virada): os USD antigos (13.50) eram lidos como ¥ → ~6,7× menor.
  Cura: rodar a migração de dados no local também. ⚠ Lição de ambiente: a
  migração de DADOS da F10 é POR BANCO — todo ambiente (local, staging,
  prod) precisa rodá-la uma vez.
  **⚠ INCIDENTE 2 (2026-07-16, local): a migração ¥ rodou DUAS vezes** (o
  comando não tinha trava e a instrução foi repetida em mensagens
  diferentes) → ¥90 virou ¥600 e TODA valoração inflou 6,7× (lote 39:
  151.403 = 3.395×(1/0.15)²; o aviso de "¥ não-redondo" não pega a 2ª
  rodada — ¥600 é redondo). Cura: `--revert` do json da última rodada.
  **Trava permanente:** `Buyer.prices_in_rmb` (migração pricing/0013) — o
  commit liga a trava; re-rodar (até dry-run) é RECUSADO com erro;
  `--mark-migrated` liga a trava sem tocar valores (ambiente que já está em
  ¥ — ex.: prod no deploy da F11, e o local do dono pós-revert); `--revert`
  desliga e manda conferir. Testado em MigratePricesToRmbTests.
  **Resolução (2026-07-16):** o revert.json da rodada extra não foi
  encontrado no local → reversão pela MATEMÁTICA: `--rate-used 6.6667`
  (=×0.15) desfez exatamente uma divisão; dry-run provou (todos os ¥
  redondos: 33.33→5, 266.67→40…; 13 não-redondos = USD pós-launch no
  ¥-equivalente, mesma família dos 41 do prod). Commit ok, trava religada.
  ⚠ Lição operacional: comandos pro dono AGORA vão UM POR VEZ e sem
  placeholders em bloco (blocos colados inteiros executaram placeholder
  `/CAMINHO/COMPLETO` e um `--mark-migrated` indevido).
  **⚠ INCIDENTE 3 (2026-07-16): `{# #}` multiline vazando como TEXTO** nas
  páginas (3ª ocorrência do erro da casa — 7 pontos: header/messages do
  shell, smart button, form/modal de fechamento, fx do parceiro, moeda do
  catálogo). Corrigidos para `{% comment %}` e agora há PORTÃO:
  `TemplateMultilineCommentTests` (estoque/tests.py) varre TODOS os
  templates e deixa a suíte vermelha se alguém escrever `{# #}` com quebra
  de linha. Suíte 373/373.
  **2ª revisão do dono (F11.2c, 2026-07-16):** (a) fechamento com **modal da
  casa** (est-modal Carbon: resumo código+total, type-to-confirm digitando o
  código; modal DENTRO do gate de gerente — operador não vê nem o HTML;
  barreira segue na view); (b) admin fecha → **redirect direto pra OV**
  (gerente segue no lote — não vê /vendas/); (c) **smart buttons padrão
  Odoo** nos dois sentidos: lote→"Ordem de venda SO/…" (ctx só p/ admin) e
  venda→"Lote LOT/…"; (d) **Baixar PDF da OV** (`vendas/pdf.py`, simples sem
  timbre, reusa helpers CJK do pricing/pdf; draft = valores vivos,
  confirmada = congelados; filename `SO-001-07-26.pdf`). Suíte 371/371.
- **F11.3 ✅ ENTREGUE 2026-07-16 (local; suíte 372/372):** (a) **sigilo do
  comprador — SEM codinome** (dono corrigiu na revisão: "o cliente final nem
  precisa saber que existe um comprador; o trato é direto com o
  WhatTheChip"): toda superfície de EMPRESA mostra o rótulo fixo
  **`WhatTheChip`** como contraparte — card (`price_block`), JSON da home
  (`serialize_quote`, cobre os 4 JS do CMS), painel de valoração do lote e
  headers do export .xlsx ("Preço unit. — WhatTheChip (USD)"). Comprador
  (nome/slug/existência) visível SÓ no Django admin (plataforma — que já é
  restrito a superuser via bootstrap_tenancy) e no /partner/ dele mesmo. A
  1ª versão com `Buyer.codename` foi REVERTIDA antes de qualquer migrate
  (campo+migração 0013 removidos; `makemigrations --check` limpo). (b)
  **`backfill_sales_orders`** — lotes FECHADOS sem OV ganham OV retroativa
  **CONFIRMADA** do congelado F8: `total_usd` = total_mid fiel; `total_rmb`
  = ÷ `--rate-used` (0.15 pré-virada); `fx_usd_rate` = taxa da ÉPOCA;
  `confirmed_at` = data do congelamento; linhas por (marca, chave) só com
  QUANTIDADES (unitário vazio — congelado F8 é por PN/total; notas da OV
  explicam); dry-run/commit, idempotente; lote fechado SEM congelado é
  pulado com aviso. Rodar por empresa após o resnapshot (as linhas dependem
  das chaves F11.1).
- **F11.4 ✅ ENTREGUE 2026-07-16 (local; suíte 375/375, i18n verde — 27
  msgids):** **Acerto → Fatura → Pagamentos** (migração vendas/0003 +
  0004-RLS). `Settlement`/`SettlementLine` = o RESULTADO do comprador
  (mortos por categoria + repreço ¥); **a OV confirmada NUNCA muda** (padrão
  Odoo fatura-pelo-aceito): `settle_and_invoice()` cria acerto + **Fatura
  `INV/NUM/MM/YY`** num ato atômico — total final = Σ linhas ajustadas
  ((qty−rejeitadas) × (novo ¥ ou o congelado)), USD somado POR LINHA (F10),
  taxa herdada da OV. UMA fatura ativa por OV; re-acerto = cancelar fatura
  (SÓ sem pagamentos) e reemitir (número novo). `Payment` sempre **US$**
  (decisão do dono), parciais, acima-do-saldo barrado; saldo zero → PAGA.
  Telas: CTA "Registrar resultado e faturar" na OV confirmada → form de
  ajustes → fatura com Total/Recebido/Saldo, ajustes do acerto, pagamentos e
  form de registro; **smart buttons** OV↔Fatura (o "fatura relacionada" do
  Odoo) e Fatura→Lote. Admin-only. Histórico de acerto por comprador fica
  registrado (dado de negociação). Testes:
  `SettlementInvoicePaymentTests` (fluxo + OV intacta + travas) e telas.
  **F11 COMPLETA** (resta só o romaneio do estoque, fora do escopo).

**Ajuste pós-F11 (dono, 2026-07-17):** o gate do preço no card
(`quotes_for_admin`) passou a aceitar também o **admin do SISTEMA**
(superuser sem Membership → manager cru, enxerga todos os compradores) —
única exceção documentada ao "plataforma navega com Membership real";
admin de empresa segue no manager escopado; operador/gerente/anônimo seguem
sem a chave `prices` no JSON. Teste:
`test_superuser_plataforma_ve_prices_no_json`. E o bug do topnav da home
("Entrar" fixo com sessão iniciada) foi corrigido no shell público
(`templates/base.html` + `pages/tests.py::TopnavSessionTests`); de quebra, o
`PriceCardGateTests` foi adaptado ao redesenho `e47f496` (sessão paralela),
que removeu o price_block server-side do card HTMX da busca — o preço da
busca é client-side via JSON do search_api; fonte server-side = bancada.

**F11.5 — PDF DE CONFERÊNCIA DO LOTE (documento do GERENTE; dono,
2026-08-18; local, suíte 555/555 + i18n verde):** o gerente deixou de baixar
"o PDF do admin com os números tampados de `***`" e passou a baixar **outro
documento**. `vendas/pdf.py::render_so_manager_pdf` + `services.
manager_document()`; a view `so_pdf` ramifica no `can_see_price` (fonte
única) e o **PDF comercial do admin fica INTOCADO** (decisão do dono: *"por
enquanto só gerente, dps fazemos deles"*).

O que o documento traz, item por item do pedido:

1. **Zero coluna de preço** — não existe célula de dinheiro para mascarar. A
   barreira virou ESTRUTURAL: nenhum caminho de código põe ¥/US$ no PDF do
   gerente, então não há bug de template capaz de vazar valor. (O parâmetro
   `masked=` do `render_so_pdf` continua funcionando, mas a app não usa mais.)
2. **Quantidade por categoria WTC** — com as **MARCAS FUNDIDAS**. A linha da
   OV é por (marca, chave) porque o comprador cota por marca, então o mesmo
   código de caixa aparecia REPETIDO no PDF mascarado (Samsung e SanDisk eMMC
   16GB = duas linhas "B-06"). Para quem confere caixa isso era ruído — e a
   marca nem chega ao gerente. `wtc_summary()` soma as repetições.
3. **Quantidade por TIPO × CAPACIDADE reais** (eMMC 64GB · 640) —
   `spec_summary()`. **⚠ AFROUXAMENTO CONSCIENTE DA F12**, perguntado e
   aprovado pelo dono nesta data: as duas tabelas lado a lado entregam ao
   gerente o de-para `B-06 = eMMC 16GB` das categorias DAQUELE lote. A
   máscara segue valendo em todo o resto (bancada, tabela, export, tela da
   OV, PDF comercial). **Ponto único de reversão:** tirar `spec_summary` do
   `manager_document` — nada mais depende dele; o teste que cai primeiro é
   `PdfConferenciaGerenteTests.test_resumo_por_tipo_e_capacidade`.
4. **SO e LOTE com o MESMO peso** — cabeçalho de duas colunas, mesmo
   `fontSize` nos dois códigos (*"nenhum é mais importante que o outro"*).
   Coberto por `test_so_e_lote_tem_o_mesmo_tamanho`, que lê o operador `Tf`
   vigente no momento em que cada código é desenhado — asserção estrutural,
   não visual.
5. **Cabeçalho de auditoria** — empresa, **emitida em** (data da ORDEM:
   `confirmed_at` na confirmada, `created_at` na cotação — congela no
   documento; a data do download fica só no rodapé), **lote fechado em**,
   **fechado por** e o **câmbio travado no fechamento** (`Lot.fx_rate`). A
   taxa sobrevive ao gate de valor porque é **mid-market público** por
   decisão do PLANO_FX — o que a máscara esconde é a taxa de CONTRATO e o
   dinheiro, não a cotação do dia (mesma regra do badge de câmbio do shell).

**Migração `estoque/0019_lot_closed_by` (aditiva, sem RunPython):** o `Lot`
não tinha "quem fechou" — só `closed_at`. Campo novo `Lot.closed_by`
(SET_NULL) gravado no `lot_close` e limpo no `lot_reopen`. **Sem backfill de
propósito**: RunPython em tabela com RLS exige o GUC de plataforma no migrate
do Render (armadilha que quebrou o 1º push de 2026-08-01) — em vez disso, o
`Lot.closed_by_user` cai no **`LotPricing.closed_by`** para lote fechado
ANTES desta data (o snapshot de valoração nasce no mesmo ato do fechamento).
Sem nenhum dos dois (congelar valor nunca trava o fechamento — padrão F8) o
documento sai com travessão, não com exceção.

**2ª rodada (dono, 2026-08-18, mesma sessão) — o documento virou também o
PAPEL QUE VIAJA COM O PACOTE (DHL).** Suíte 561/561 + i18n verde.

1. **SEMPRE EM INGLÊS**, qualquer que seja o idioma da sessão —
   `translation.override('en')` no `render_so_manager_pdf`. Idioma de
   documento de embarque é do TRANSPORTE, não de quem clicou (precedente da
   casa: o Django admin é fixo em pt-br pela razão simétrica). As strings
   continuam MARCADAS e traduzidas nos 4 catálogos: tirar o override devolve
   o documento ao idioma da sessão, e é o único ponto a mexer.
2. **Subtítulo perdeu "documento sem valores" e "valores congelados"** (pedido
   literal). Ficou `Lot check · confirmed`. Isso trocou o msgid: entrou
   `Conferência de lote` e a entrada antiga saiu dos 3 catálogos. Os status
   curtos (`cotação`/`confirmada`/`cancelada`) já existiam — o PDF COMERCIAL
   segue com os longos, intocado.
3. **Dois logos:** WhatTheChip (asset commitado em `vendas/assets/wtc-logo.png`)
   à esquerda e o da empresa-cliente (blob de `CompanyLogo`, E4) à direita.
   O logo do WTC só existia em SVG e o reportlab não desenha SVG — em vez de
   pôr `svglib` em produção por causa de um logo, o PNG é gerado uma vez do
   `static/img/wtc-logo-light.svg` e commitado (mesma escolha da fonte CJK em
   `pricing/fonts/`); a receita está no `vendas/assets/README.md`. Achatado em
   RGB de propósito: PNG com alfa vira DOIS objetos no PDF (imagem + /SMask).
   Logo ilegível nunca derruba o documento (`_img` devolve None e segue).
4. **Bloco `SHIP TO 收貨人`** — rótulo bilíngue CANÔNICO (nunca traduz: é a
   convenção da transportadora). Os dados vêm de campos NOVOS do comprador
   (`pricing/0024_buyer_ship_to`, aditiva): `ship_to_name`, `ship_to_address`,
   `ship_to_email`, `ship_to_phone`. **Endereço é TEXTO LIVRE de propósito** —
   cada país tem uma estrutura (Macau não tem estado) e a transportadora quer
   o bloco exatamente como o destinatário o escreve; campo estruturado só
   criaria tradução errada. Preenchimento pelo ADMIN (nada de backfill: RLS).
   Comprador sem endereço = bloco simplesmente ausente — **nunca inventa
   destino** (melhor a DHL reclamar do que despachar errado).
   ⚠ **Exceção pontual à F11.3:** aqui a contraparte tem NOME. O sigilo do
   comprador continua em toda superfície de empresa-cliente; o que aparece
   neste bloco é o DESTINATÁRIO do frete, não o nome do comprador — e quem
   embarca precisa saber para onde.
5. **Fonte CJK forçada:** `_cjk_font(force=True)` (parâmetro novo em
   `pricing/pdf.py`). O "收貨人" e um endereço chinês são CONTEÚDO, não
   tradução — sem a TTF embutida o reportlab desenha quadradinhos mesmo com o
   documento em inglês.

**3ª rodada (dono, 2026-08-18) — UM documento só, bilíngue, com SHIP FROM.**
Suíte 568/568 + i18n verde.

1. **Rótulo bilíngue EN + 繁體中文** em cada título, legenda e cabeçalho de
   coluna: `Category (類別)`, `Qty. (數量)`, `Issued on (簽發日期)`… Fonte única
   é o dicionário `_L` em `vendas/pdf.py` (`_t('chave')` monta o par). **Saiu
   do gettext:** o documento é de idioma FIXO, então os rótulos são
   CANÔNICOS, como `LETRA-##` e `SO/NUM/MM/YY` — um `{% trans %}` aqui faria
   o papel mudar de língua conforme quem apertou o botão. Os 8 msgids que a
   2ª rodada tinha criado saíram dos 3 catálogos (598 entradas agora).
   ⚠ **繁體 (Macau/HK/Taiwan), não o zh-hans da interface** — não reuse um
   catálogo pelo outro; o teste crava `類別`/`數量`/`晶片類型彙總`.
2. **Um documento só, duas versões** (`with_prices`): sem preço para
   gerente/operador, com `Unit ¥ / Total ¥ / Total US$` para o admin da
   empresa — *"a única diferença é que tem preços"*. O `so_pdf` deixou de
   ramificar entre DOIS documentos; o `render_so_pdf` comercial saiu do
   caminho da tela (segue no módulo até o dono validar o novo).
   ⚠ **Unitário só sai quando é o MESMO em todas as marcas fundidas** naquele
   código de caixa — o comprador cota POR MARCA, então "B-06" pode ter dois
   preços e mostrar um deles seria mentira. Ambíguo → `—`, e só o TOTAL (que
   continua exato) aparece. Idem para linha sem preço, que ainda soma em
   `unpriced_units`.
3. **SHIP FROM (寄件人) ao lado do SHIP TO**, na mesma caixa dividida ao meio
   (é o par que a transportadora procura junto). O comprador recebe lote de
   VÁRIAS empresas e precisa saber de qual veio — por isso o **nome da
   empresa sai sempre**, com ou sem endereço. Endereço novo em
   `Company.address` (`tenancy/0008_company_address`, aditiva), texto livre,
   preenchido no admin.
4. **Layout reorganizado:** logos → identificação (SO/LOTE) → endereços →
   faixa de auditoria → tabelas. A grade pesada das tabelas virou linha fina
   com filete só no cabeçalho e no total; a empresa saiu da faixa de meta
   (virou o nome do SHIP FROM) e a faixa caiu de 5 para 4 colunas, que é o
   que o rótulo bilíngue precisa para não quebrar.

**⚠ BUG REAL que o teste de glifos pegou:** célula de tabela com ideograma
**tem que ser `Paragraph`**. String crua é desenhada na fonte BASE da tabela
(Helvetica, WinAnsi) e o CJK sai como lixo — `無類別` estava imprimindo `nnn`
no papel. O teste `test_todo_rotulo_tem_o_chines_tradicional_ao_lado` varre
cada ideograma dos rótulos e exige que ele apareça no CMap da TTF embutida;
é ele que pega glifo faltando (que sairia como quadradinho sem ninguém notar)
e a regressão do Paragraph. Terceira armadilha de leitura do PDF na mesma
sessão: o CMap da fonte também entra nos streams sem `/Filter`, e um `(`
solto nele casava com o `) Tj` do stream seguinte — por isso `_streams_do_pdf`
exige `Tj` DENTRO do stream e o regex de texto roda por stream, nunca no
conjunto concatenado.

**Duas armadilhas de teste que os logos revelaram** (estão comentadas em
`vendas/tests.py`): (a) asserção `assertNotIn(b'US$')` sobre o PDF CRU passou
a falhar por coincidência de bytes dentro do blob ASCII85 do logo — as
asserções agora leem só os streams de CONTEÚDO (`_conteudo_do_pdf` pula quem
tem `/Filter`); (b) o regex de stream com `\n` obrigatório antes de
`endstream` ENGOLIA o PDF inteiro num casamento só, porque o stream de imagem
termina em `~>endstream` — o conteúdo voltava vazio e as asserções passavam
vacuamente.

**Testes:** `PdfConferenciaGerenteTests` (17 casos) + o
`VendasGateTests.test_gerente_entra_mas_sem_nenhum_valor` **RE-ESPECIFICADO**
— a asserção `assertIn(b'(***)')` morreu junto com as células mascaradas; no
lugar entrou "nenhum texto desenhado tem cara de dinheiro" (regex de 2 casas
decimais sobre os operadores `(…) Tj`, que não confunde valor com coordenada
do stream). i18n: 8 msgids novos nos 3 catálogos + `.mo` recompilado.

### F11.6 — O RESULTADO NA MÃO DO COMPRADOR (plano fechado 2026-08-18)

O acerto do F11.4 existe inteiro (`Settlement`/`SettlementLine`/`Invoice` +
`settle_and_invoice`) — o que muda é **a mão que opera**: sai do admin e vai
para o COMPRADOR, numa superfície nova em `/partner/`. Não é modelo novo, é
tela nova sobre modelo existente.

**Decisões do dono (2026-08-18, todas perguntadas):**

1. **O ¥ congela no FECHAMENTO do lote**, automático — a OV nasce confirmada.
   Motivo que fechou a decisão: o PDF que viaja com a caixa imprime preço, e
   com a OV em rascunho esse preço é VIVO — o papel podia não bater com a
   fatura. ⚠ `confirm()` é tudo-ou-nada (exige TODAS as linhas cotadas), então
   **lote com categoria sem preço no grid fecha do mesmo jeito e a OV fica em
   RASCUNHO**, com aviso na tela dizendo quantas faltam. Quem resolve é o
   COMPRADOR, na tela de compras dele: o grid incompleto é problema dele, e o
   laço fecha na mão certa. **Nunca** bloquear o fechamento do lote por preço:
   o gerente não controla a tabela do comprador.
2. **Linha do resultado = linha da OV**: agrupa por MARCA, e dentro dela por
   capacidade (Samsung → eMMC 32GB, 64GB…; depois SanDisk → …). Fundir por
   capacidade seria mais bonito mas cria dedução AMBÍGUA em lote PCB, onde o
   preço é por marca ("recusei 10 de eMMC 64GB" não diz de qual marca sai o
   desconto). Separação sempre visualmente clara quando não são fundidas.
3. **Isolamento: laço por empresa.** O Wu Quan é comprador de PLATAFORMA
   (`company IS NULL`) e lê OVs de VÁRIAS empresas — caso que o
   `partner_required` nunca cobriu (ele roda sob `company_scope(buyer.company)`,
   que para plataforma é escopo NENHUM → RLS devolve zero linhas em silêncio).
   A tela roda **uma consulta por empresa dentro do `company_scope` dela** e
   junta. Mais lento, mas **o Postgres continua sendo a barreira**: um
   `filter(buyer=...)` esquecido não vaza nada. Trocar por GUC `app.buyer_id`
   quando N de empresas crescer — nunca por `platform_scope`, que desliga o
   filtro do banco e deixa a proteção só no Python.
4. **Reabrir lote é afordância de TESTE, não produto** (dono: "NÃO DEVE SER
   POSSÍVEL REABRIR UM LOTE, só é possível agora porque estamos em fase de
   testes"). Logo: a regra atual (OV confirmada BLOQUEIA a reabertura) fica
   como está — não vale investir em suavizar o que vai sumir.
5. **Escopo do MVP:** lista + resultado + **despacho** (transportadora, datas,
   rastreio) + **pagamentos visíveis** ao comprador + **observação/motivo da
   recusa**.

⚠ **Máscara:** `is_unmasked` é `user.is_superuser`, e o comprador NÃO é
superuser — qualquer helper mascarado reusado aqui entrega `C-014` no lugar de
`eMMC 32GB`. A superfície do comprador usa rótulo REAL (ele compra chip; o grid
de preço dele já é por tipo e capacidade). Não reusar `annotate_labels(...,
unmasked=False)` nesta superfície.

**Fases (1–3 = o MVP ponta a ponta; 4–5 = os extras pedidos):**

- **F1 — congelamento no fechamento.** `lot_close` tenta `confirm()` logo após
  criar a OV; `ValidationError` de pendência deixa a OV em rascunho e avisa na
  tela (mesmo portão de silêncio do incidente do K9). Pequena, e torna o preço
  do PDF confiável.
- **F2 ✅ ENTREGUE — `/partner/compras/`**: lista das OVs de todos os clientes
  (laço por empresa), com lote, cliente, chips, ¥, US$ e estágio.
- **F3 ✅ ENTREGUE — tela do resultado**: cabeçalho + tabela marca→capacidade
  com input de RECUSADOS por linha, observação, e "Fechar resultado" chamando
  `settle_and_invoice()`. Depois de faturada a tela vira LEITURA e mostra o
  saldo a pagar (o F5 saiu junto — era só leitura).

**Arquitetura entregue (F2+F3+F5):** `vendas/views_partner.py` +
`vendas/urls_partner.py` (namespace `compras`, montado em `/partner/compras/`
ANTES do include do `pricing`), templates em `vendas/templates/vendas/`, e as
funções de dados em `vendas/services.py` — `orders_for_buyer`, `buyer_order`
(context manager que abre a OV JÁ dentro do `company_scope` da dona),
`order_stage` e `result_rows`. O `partner_base.html` ganhou o item **Compras**
na nav e um `{% block sidebar %}` (a sidebar de preços não faz sentido aqui).

⚠ **`buyer_order` é context manager de propósito:** ler linhas, calcular e
acertar têm que acontecer todos sob o MESMO `company_scope`. Fora dele o RLS
devolve zero linhas em silêncio, e o bug apareceria como "OV sem linhas" em
vez de erro — a mesma classe de armadilha do incidente do K9.

✅ **RESOLVIDO em 2026-08-18 — `Company.code` no identificador.** O código
colidia entre clientes porque a numeração é POR EMPRESA (o comprador via dois
`LOT/001/08/26` na lista dele). Agora: `LOT/EMI/041/08/26` · `SO/EMI/012/08/26`
· `INV/EMI/003/08/26`, com `Company.code` de 2-4 letras MAIÚSCULAS (só letras:
o código é DIGITADO no type-to-confirm do fechamento e impresso — dígito
convida a confundir 0/O e 1/I). Único entre os preenchidos; vazio se repete,
porque é o legado.

⚠ **Código de PAÍS (PY/VE) foi avaliado e RECUSADO:** duas recicladoras do
mesmo país voltariam a colidir — e é exatamente esse o caminho de crescimento.
País é metadado de EMBARQUE e já viaja no endereço do SHIP FROM; não pertence
ao identificador.

⚠ **Formato novo só em documento NOVO** (decisão do dono): papel já impresso
não pode divergir da tela. Por isso o código deixou de ser propriedade
calculada e virou campo CONGELADO na criação (`code_str` em Lot, SalesOrder e
Invoice; helper único em `tenancy/doc_code.py`). Documento sem `code_str` cai
no formato antigo. De quebra o identificador virou IMUTÁVEL — renomear o
código da empresa não reescreve o passado, que é como número de documento deve
se comportar (há teste cravando).

Migrações `tenancy/0009`, `estoque/0020` e `vendas/0006` — aditivas, **sem
backfill de propósito**. Preencher o `code` de cada empresa no admin.

**RUNBOOK DO DEPLOY F11 EM PROD (o dono roda; comandos UM POR VEZ):**

0. **Pré (bloqueantes):** (a) senha do Postgres ROTACIONADA confirmada; (b)
   **Render Export fresco** (regra §2.1b: backup antes de deploy com
   migrations); (c) Render → serviço web → Settings → Start Command: se
   preenchido, tem que ser IGUAL ao Procfile (`--timeout 120 --workers 2`).
1. `git push origin main` → build roda `migrate` (estoque/0015 aditiva +
   pricing/0013 aditiva + vendas/0001–0004, RLS incluso) + collectstatic.
   Esperar **Live**. Sem janela de dado (prod já está em ¥; F11 é aditiva).
2. **IMEDIATAMENTE pós-Live** (com `DATABASE_URL` do prod exportada; slug
   prod = **wu-quan**): `migrate_prices_to_rmb --buyer wu-quan --mark-migrated`
   — o prod JÁ está em ¥ e a trava nasce desligada; ligar é o 1º ato
   (proteção contra o incidente da dupla-migração).
3. `resnapshot_lote --all --commit --company eminer` — backfill das CHAVES
   de preço (F11.1) em todo o estoque. ⚠ classifica cada PN: com ~20k
   entradas leva VÁRIOS minutos; idempotente, re-executável. Até rodar, a
   valoração usa o fallback (funciona, só mais lenta). O SafeWriteCommand
   pede digitar o nome do banco — conferir que o BANCO-ALVO é o do Render.
4. `backfill_sales_orders --company eminer` (dry-run: revisar lote a lote
   US$ congelado → ¥ ÷0.15) → re-rodar com `--commit`. Depende do passo 3.
5. `guard_catalog` (tripwire padrão pós-deploy).
6. **Smoke read-only:** /vendas/ com o histórico (retroativas confirmadas);
   card de PN cotado = "💰 WhatTheChip ¥ … · US$ …" (sem Wu Quan!); página
   do lote 39 rápida (LOT/039/…); abrir uma OV retroativa + PDF; export
   .xlsx com header "WhatTheChip (USD)"; /partner/ intacto (nome real ok
   lá). NÃO fechar/reabrir lote real como teste em prod.
7. Vendas novas a partir daqui: fechar lote (modal type-to-confirm) → OV →
   acerto → fatura → pagamentos, tudo em prod.

### 12.18 F10 — RMB CANÔNICO (**LIVE** — virada executada 2026-07-16: deploy `2b75916` + `migrate_prices_to_rmb --buyer wu-quan --rate-used 0.15 --commit` = 256 registros → ¥; 41 valores ¥ não-redondos aceitos como estão — digitados em USD pós-launch, ÷0.15 é a leitura fiel da época; arredondar seria mudar preço do parceiro sem consentimento (ajuste, se quiser, via moderação/admin). `guard_catalog` ✓ 7729. Reversão: `migrate_prices_to_rmb_revert.json` guardado FORA do git. Suíte 354/354 + `check_translations` verde.)

**F10.1 entregue 2026-07-11 (INERTE até a virada):** `Buyer.fx_usd_rate`
(default 0.14, pghistory audita; migração de schema aditiva — deploy seguro a
qualquer hora) + comando `migrate_prices_to_rmb --rate-used 0.15` (dry-run/
revert; golden 13.50→¥90; reporta ¥ não-redondo). ⚠ **O comando de DADOS só
roda junto com o deploy da F10 completa** — antes disso o banco falaria ¥ e a
tela US$.

**F10.2–F10.7 entregues 2026-07-16 (sessão de pricing):**

- **Engine (F10.2) — decisão de desenho central:** o USD é derivado **NA
  CONSTRUÇÃO do `PriceQuote`** (`price()`: `price_min/max` = ¥ × taxa,
  quantizado a centavo), e o ¥ armazenado sai em campos novos
  `rmb_min/rmb_max` + `value_rmb()/mid_rmb/rmb/rmb_display`. Assim
  `value()`/`mid`/`price_min` continuam USD e **NENHUM consumidor do estoque
  mudou** (valoração on-read, congelamento F8 — inclusive as `lines` de
  auditoria — e export .xlsx seguem USD, agora derivado).
  `serialize_quote` ganhou `rmb` (display, '90') e `mid_rmb` ('90.00').
- **Parceiro (F10.3):** grid/inputs/moderação/notificações em ¥; header troca
  a cotação viva (script er-api/frankfurter REMOVIDO) pela **taxa contratual**
  "1 ¥ = US$ 0.14 · taxa do contrato" (server-side, `fx_usd_rate_display`);
  página "Como funciona" reescrita em ¥ + FAQ nova ("E se a taxa mudar?").
- **Admin (F10.4):** `Price` com verbose_names em ¥ (migração **0012**, só
  metadados) + coluna **US$ (derivado)** calculada; `fx_usd_rate` no
  BuyerAdmin (list + form); delta da moderação em ¥.
- **Card/bancada (F10.5):** dual **"¥ 90 · US$ 12.60"** no `price_block.html`
  (com `{% localize off %}` — dinheiro sempre com ponto) e no JS da home
  (4 arquivos `_content/index*.html`; a home lê `_content/` do disco → o push
  já publica).
- **PDF (F10.6):** `?currency=rmb|usd` (default **usd** — é o documento que
  circula pros clientes dele); seletor de moeda ao lado do de idioma na home;
  título "(US$ / ¥ RMB)", legenda e células na moeda; filename com a moeda.
  ¥ existe em WinAnsi (Helvetica) — sem mexer na fonte CJK.
- **`import_price_xlsx` corrigido (guarda-costas do canônico):** gravava
  RMB × B2 (foi assim que os USD "nasceram a 0.15") — agora grava o **¥
  DIRETO** (B2 continua obrigatória só como validação de estrutura). Re-rodar
  o import nunca mais corrompe o banco ¥.
- **i18n (F10.7):** 16 msgids novos/mudados traduzidos es/en/zh na MESMA
  entrega (append no bloco "F10 RMB canônico" dos `.po`; `.mo` compilados;
  portão `check_translations` verde, 337 entradas/idioma).
- **Testes:** 354/354 (`chips estoque tenancy pricing`, era 352). Goldens
  refeitos com os **¥ da planilha** (¥40/¥90/¥25…) e USD derivado @0.14
  (¥90→12.60); novos: `test_taxa_nova_muda_usd_e_preserva_o_yuan`,
  `test_header_mostra_taxa_contratual`, PDF nas 2 moedas, `rmb`/`mid_rmb` no
  JSON, linhas do congelado F8 em USD ('5.60', nunca ¥), export .xlsx
  ¥15→US$ 2.10. Fixture do estoque (`ExportPriceColumnsTests`) migrado p/ ¥.
- **Pegadinha nova documentada:** `floatformat` **ignora** `{% localize off %}`
  (sempre localiza → '0,1400' em pt-br). Taxa/dinheiro formatado em property
  Python (`Buyer.fx_usd_rate_display`, `PriceQuote.rmb_display`) com
  `f'{d.normalize():f}'` (o `:f` evita o 9E+1 — §12).

**⚠ INCIDENTE pós-virada (2026-07-16, ~20:10 UTC) — site fora por worker em
loop; resolvido no mesmo dia:** `/estoque/lote/42/` (lote grande) levava ~30s
→ `WORKER TIMEOUT` do gunicorn (default 30s) matava o worker ÚNICO no meio da
escrita → browser re-tentava → worker novo nascia FRIO (recarrega o catálogo)
→ loop; o site inteiro parecia fora, mas banco/senha/dados-¥ estavam OK
(preview e estáticos respondiam 200). **Causa raiz (pré-existente, exposta
pelo lote grande + caches frios do deploy):** a valoração on-read fazia ~3
queries POR PN (cadeia de listas + linha de preço + `PricingConfig.
get_or_create`) × comprador, contra o Postgres remoto. **Fix em 2 camadas:**
(a) `Procfile` → `--timeout 120 --workers 2` (cinto de segurança + sem fila
atrás de página lenta; se o Start Command do dashboard estiver preenchido,
ele VENCE o Procfile — manter iguais); (b) **`BuyerPricingContext`**
(pricing/engine.py): `price_lot` passa a fazer **4 queries TOTAIS** (entries
+ config + listas + todas as linhas do buyer) qualquer que seja o tamanho do
lote — o `price()` do card segue com a consulta estreita; a cauda
(`_quote_from_candidates`) é fonte única dos dois caminhos. Regressão
travada por `test_valoracao_faz_queries_constantes` (assertNumQueries=4;
suíte 355/355). Nota solta do log: `JSON inválido em ChipFamily.reasoning`
(SDINB/SDAD/SDIN/PMG6/H9DP/EMCP…) é dado sujo no campo `reasoning` dessas
famílias — inofensivo; corrigir nos yamls das marcas.

**RUNBOOK DA VIRADA (o dono roda; deploy + dados JUNTOS, nesta ordem):**

0. **Pré-requisitos bloqueantes:** (a) senha do Postgres **ROTACIONADA**
   (vazou 2× em chat); (b) **backup fresco** (Render Export); (c) horário de
   baixo uso — entre o deploy ficar live e o passo 4 há uma janela de minutos
   em que o card mostra USD errado-BAIXO (¥ antigo × 0.14 ≈ US$ 1.89) — por
   isso dados vêm IMEDIATAMENTE após o deploy (errado-baixo é o lado seguro;
   rodar dados ANTES mostraria errado-ALTO, US$ 90).
1. **Local:** suíte (354) + `check_translations` + revisar `git status` (há
   arquivos alheios à F10 no working tree — FORESEE.md/BRIEFING_* — não
   commitá-los junto sem querer; `submissions/` nunca vai pro git).
2. `git push origin main` → build do Render roda a migração **0012**
   (metadados, segura) + collectstatic.
3. Esperar o deploy **LIVE** no dashboard.
4. **Dados (IMEDIATAMENTE):** com `DATABASE_URL` do prod (a URL NOVA
   pós-rotação; conferir o **slug real do buyer** no /admin/pricing/buyer/):
   `python manage.py migrate_prices_to_rmb --buyer <slug> --rate-used 0.15`
   (DRY-RUN: os ¥ têm que sair REDONDOS — 13.50→¥90 é a prova; ¥ não-redondo
   = digitado em USD pós-launch, revisar caso a caso) → re-rodar com
   `--commit` → **guardar o `migrate_prices_to_rmb_revert.json`** (é a
   reversão: `--revert <arquivo>`).
5. **Smoke:** card de PN cotado (admin) = "¥ 90 · US$ 12.60"; /partner/ em ¥
   com header "1 ¥ = US$ 0.14"; PDF nas 2 moedas; valoração/export de lote em
   USD ~6,7% menor que antes (**intencional** — contrato 0.14 vigente; lotes
   FECHADOS congelados não mudam).
6. `python manage.py guard_catalog` (tripwire padrão pós-deploy).
7. Avisar o Wu Quan que o painel dele agora é em ¥ (a tela que ele pediu).

O comprador trata preço em RMB (convenção do mercado dele). Decisões fechadas
com o dono (AskUserQuestion, 2026-07-11): **RMB armazenado** (o ¥ digitado
nunca muda; USD é DERIVADO na leitura) · **taxa contratual gerida pelo dono**
(sem API viva; editável com histórico pghistory) · **exibição dual ¥+US$** no
card/bancada (valoração de lote e export .xlsx seguem SÓ USD) · **taxa vigente
= 0.14**.

⚠ **A sutileza da migração:** os valores atuais foram convertidos a **0.15**
(import da planilha + WeChat). Logo: migrar dividindo por **0.15** (recupera
os ¥ redondos originais — ¥90, ¥110, ¥80) e configurar a taxa vigente **0.14**
para a derivação. Efeito intencional: USD derivado cai ~6,7% (¥90 → US$ 12.60,
era 13.50) — é o contrato atual refletindo na valoração. O dry-run mostra
tudo; ¥ não-redondo na saída = valor que o parceiro digitou em USD depois do
launch (revisar caso a caso).

**Fases:**
- **F10.1 Modelo:** `Buyer.fx_usd_rate` (Decimal 4 casas, default 0.14,
  auditado); `Price.price_min/max` e `PriceChangeRequest.new/old_price` passam
  a SEMÂNTICA RMB (sem rename — docstrings/verbose_name '¥'); comando
  `migrate_prices_to_rmb --rate-used 0.15` (dry-run/revert, reporta ¥ não-
  redondos). `LotPricing` congelados ficam como estão (snapshots históricos
  em USD, documentar).
- **F10.2 Engine:** `PriceQuote` ganha `.rmb`/`mid_rmb` (armazenado) e
  `value()/mid` passam a DERIVAR USD (¥ × taxa do buyer) — consumidores de
  estoque não mudam. `serialize_quote` com os dois.
- **F10.3 Parceiro:** grid/inputs/moderação/notificações em ¥; header troca a
  API viva pela **taxa contratual vigente** ("1 ¥ = US$ 0.14 · contrato");
  página "Como funciona" reescrita (msgids de USD mudam → rodada i18n
  completa es/en/zh).
- **F10.4 Admin:** PriceAdmin em ¥ + coluna US$ calculada; `fx_usd_rate`
  editável no BuyerAdmin (mudar a taxa NÃO toca os ¥ — só o USD lido).
- **F10.5 Card/bancada:** dual "¥ 90 · US$ 12.60" (partial + JS da home);
  valoração/export inalterados (USD derivado).
- **F10.6 Catálogo PDF:** seletor de MOEDA além do idioma (`?currency=rmb|usd`)
  — título/legenda/células na moeda escolhida.
- **F10.7:** i18n (portão verde) + testes (migração golden 13.50→¥90; USD
  derivado a 0.14; ¥ do parceiro gravado cru; PDF nas duas moedas; taxa nova
  muda USD e preserva ¥) + diário + runbook.

### 12.17 Fase 2 do lote 40 — habilitações no grid (dono, 2026-07-11; suíte 338/338)

Chips REAIS do lote 40 revelaram combos marcados "não fabricado" (o seed usou
a planilha original como censo de fabricação) e uma faixa fora da grade:

- **`enable_price_row` (comando novo):** flip **não fabricado → não cotado**
  para marca que fabrica de fato, garantindo a linha da GENÉRICA junto.
  Só essa transição: cotado/não-compro são intocáveis (rebaixar é decisão de
  admin); faixa inexistente aponta o `add_price_row`. Dry-run por padrão;
  idempotente; pghistory audita. Testes: `EnablePriceRowTests`.
- **Habilitações desta fase** (evidência = chips físicos no lote): SK Hynix
  emcp/LPDDR3/8GB · Micron emcp/LPDDR3/64GB e emcp/LPDDR4/64GB · Samsung
  umcp/LPDDR4X/256GB.
- **Faixa nova eMCP LPDDR4 128GB** via `add_price_row`, made-by Samsung +
  SK Hynix + Micron (decisão do dono). Conferência nas DEMAIS marcas pelo
  próprio catálogo: Kingston eMCP para em 64GB (prefixos 04–64EMCP), Toshiba
  só tem eMCP legado LPDDR2 4–8GB (TYC), SanDisk não tem família eMCP, Nanya
  é DRAM-only → seguem "não fabricado" (habilitar depois se aparecer chip —
  precedente H9HCN).

### 12.16 BUG lote 40 — DDR "sem preço" com linha cotada (2026-07-11; suíte 332/332)

Export do lote 40 mostrava DDR3/DDR4 de **SK Hynix e Nanya** como "sem preço"
apesar do grid ter a linha cotada (ex.: DDR3 2Gb US$ 0.45). Reproduzido em
banco-sonda com os PNs reais; a chave morria em `NO_KEY "densidade (Gb)
indisponível"` por DUAS vias, ambas fora do `dram_density` (única fonte do
`density_gbit_num` da F0):

- **Gramática** dessas famílias decodifica a densidade como **bytes por die
  no `capacity`** (`'256MB'` = 2Gb) e nunca preenche `dram_density`;
- **Confirmados via `bless_base`** carregam a convenção da caixa no
  `capacity` (`'2G'` = 2 **Gbit**) com `density_gbit` vazio.

(Samsung tem decode de densidade próprio e Micron preenche via FBGA — por
isso só parte do lote falhava.)

**Fix (pricing, sem tocar o engine de classificação — zero characterize):**
`derive_price_key` ganhou `_gbit_from_capacity` — fallback SÓ para ddr/gddr:
`'2G'/'2Gb'` → 2.0 · `'256MB'` → ×8÷1024 → 2.0 · `'2GB'` NUNCA (byte de
pacote; Gb≠GB). F0 continua com prioridade. Teste:
`DdrDensityFallbackTests`.

**Decisões do dono na sequência (2026-07-11):**
- **DDR3L = DDR3 no preço** ("são a mesma coisa em termos de preço"): variante
  de TENSÃO (sufixo L/U) dobra para a geração-base na chave — golden
  `test_ddr3l_dobra_para_ddr3_na_chave` ATUALIZADO (afirmava o oposto até
  10/07). GDDR5X NÃO dobra (outro mercado, não é tensão).
- **Raiz tratada em camadas (pacote completo aprovado)** — o fallback acima é
  o leitor-tolerante; a ESCRITA foi curada: regra 4 do `apply_kp_convention`
  (density_gbit auto-preenche no save, todo caminho — cura o bless_base),
  `_known_dram_density` no chips/engine (caminhos known-SEM-família também
  exibem densidade), `validate_convention` reporta + `normalize_convention`
  backfilla o legado (reversível), `load_brands` avisa família DDR-kind sem
  `decode_density_type`. Ver CLAUDE.md §7 (armadilha nova). Characterize:
  diff esperado = SÓ chips com density_gbit preenchido ganhando
  `dram_density` (intencional).

**Sobras do lote 40 (fase 2, decisão do dono — DADO, não código):**
- **"não fabricado" para chips que existem** (SK eMCP 8+1GB etc., Samsung
  uMCP 256+8): estado do grid a corrigir no painel/admin.
- **eMCP/uMCP com NAND 128GB+** e "⚠ cap. não mapeada": faixas fora da grade
  (`add_price_row`) e lacunas de gramática, respectivamente.
- ~~Reforma das famílias DDR~~ **RESOLVIDA no engine (2026-07-11, dono
  delegou):** `_result_from_family` deriva `dram_density` de cap_map per-die
  (MB×8÷1024) para TODAS as marcas — sem cirurgia de yaml (posições variam
  por marca). GDDR5X entrou no vocabulário (fim do fold pra genérico). 14
  goldens atualizados; aviso do `load_brands` agora só p/ família sem
  NENHUMA fonte de densidade (K4J/K4N/K4Z/H5RS — GDDR legadas).

### 12.15 F9 — Catálogo de preços em PDF (dono, 2026-07-10; suíte 331/331)

O comprador baixa da home do /partner/ um PDF com TODAS as tabelas — é o
documento que ele repassa aos clientes dele (decisões do dono: os 4 estados
entram; **seletor de idioma próprio** ao lado do botão; rodapé discreto
"Gerado por WhatTheChip").

- **Layout = a MATRIZ da planilha original** (compacidade máxima): seção por
  tipo (ordem de KIND_CHOICES), marcas nas colunas (ordem da sidebar, genérica
  por último), capacidades nas linhas. Célula: preço · `×` não compro (verm.) ·
  `—` não fabricado (cinza) · vazio = sem cotação. Legenda no topo; ~83 combos
  cabem em 2 páginas A4 retrato (cabeçalho repete na quebra).
- **Código:** `pricing/pdf.py` — `catalog_data(buyer)` (ORM, 1 query) separado
  de `render_catalog_pdf(...)` (reportlab puro, sem banco — testável/amostras).
  View `partner_catalog_pdf` (`/partner/catalog.pdf?lang=…`), gate
  `partner_required`; botão+seletor na `partner_home.html`. **reportlab>=4.5
  nos DOIS requirements.**
- **⚠ 3 pegadinhas descobertas (2026-07-10), todas documentadas no código:**
  1. `_()` dentro de f-string é INVISÍVEL ao extractor/portão no Python 3.11
     (f-string = um token). Os `_()` do pdf.py ficam fora de f-strings.
  2. A CID `STSong-Light` NÃO é embutida — chinês some em leitor sem a fonte
     (WeChat/celular, o destino do catálogo). Solução: TTF embutida com
     subset (`pricing/fonts/DroidSansFallbackFull.ttf`, Apache-2.0, LICENSE
     ao lado; PDF zh fica ~14KB).
  3. A DroidSansFallback é SÓ CJK (cmap sem latino/dígitos/`×`/`—`) — nunca é
     fonte-base: Helvetica sempre cobre latino/números; a CJK entra por RUN
     (`_rich`/`_draw_mixed`) só nos trechos chineses.
- **i18n:** 9 msgids novos traduzidos na mesma entrega (es/en/zh); specs e
  nomes de marca canônicos nunca traduzem; "Outras marcas"→其他品牌 reusa o
  msgid existente via `catalog_data`.
- **Teste:** `test_catalogo_pdf` (matriz + HTTP 200/pdf/attachment + ?lang=zh
  + 403 p/ operador). Sem migração, sem mudança de banco.
- **Revisão do dono (2026-07-10, mesma entrega):** (a) célula cotada mostra
  **`US$ <preço>`** (o catálogo circula solto — tem que gritar que é dólar);
  (b) comentário `{# #}` multiline VAZOU na home do parceiro — 2ª ocorrência
  do erro (CLAUDE.md §7) — trocado por `{% comment %}`; (c) **caso Rayson**:
  lista criada à mão no admin de prod "pra herdar" poluiu sidebar+PDF —
  marca SEM lista **já herda da genérica automaticamente** (cadeia do
  `price()` filtra `active=True`); conserto = desativar a lista no admin, e o
  `PriceListAdmin` ganhou aviso anti-footgun no formulário.

### 12.14 Página "Como funciona" no /partner/ (dono, 2026-07-09; suíte 324/324)

Guia de apresentação do painel para o comprador — comunicação **curta e
direta** (decisão do dono: "esses caras não gostam muito de ler"), nascida
**já nos 4 idiomas** (contrato MULTILANGUAGE.md §7):

- **Rota/UI:** `/partner/how/` (`partner_how` em `pricing/views.py` +
  `pricing/urls.py`), link "Como funciona" no header do `partner_base.html`.
  Template `partner_how.html`: proposta em 1 frase, **4 passos** em cards,
  os **4 estados** com as mesmas tags do grid, "Bom saber" (Outras marcas /
  câmbio-referência / preço unitário) e **FAQ de 7 perguntas** em
  `<details>` dobrável (sem JS). Gate `partner_required` (operador → 403).
- **i18n:** 30 msgids novos, todos `{% trans %}`, traduzidos para es/en/
  zh-hans na MESMA entrega (append-only nos `.po`, termos consagrados
  reusados: Otras marcas/Other brands/其他品牌, Inicio/Home/首页, en
  revisión/under review/审核中…). `check_translations` verde (311
  entradas/idioma); zh usa 使用说明 ("instruções de uso") para o título.
- **Teste:** `test_como_funciona` (PartnerDashboardTests) — parceiro 200 +
  conteúdo; operador 403.
- ⚠ O PT é a versão de revisão do dono — ajustes de texto mudam o msgid e
  exigem re-rodar a rotina §7.2 (extract → traduzir → compile → portão).

### 12.12 🔔 Notificações do parceiro (dono, 2026-07-07; suíte 286/286)

Fechando o ciclo da moderação: o comprador fica sabendo da decisão.

- **Sem modelo novo:** o feed são os próprios `PriceChangeRequest` decididos
  (aprovado/rejeitado) + o campo `seen_by_partner` (migração 0009). Um usuário
  do comprador abrir a página = o comprador viu (v1).
- **Botão 🔔 Notificações** no header do /partner/ (toda página), com bolha
  vermelha de não-lidas — a contagem é anexada pelo `partner_required`
  (`request.partner_unseen`, calculada dentro do `company_scope`).
- **`/partner/notifications/`**: as últimas 50 decisões (✔ Aprovado / ✘
  Rejeitado, chip, mudança pedida, quando) — abrir a página zera o badge. Sem
  nome de revisor (a decisão é "do WhatTheChip"; auditoria interna segue só no
  admin).

**Runbook:** `migrate` (0009) → suíte (286) → smoke: aprovar/rejeitar no admin
→ badge aparece pro parceiro → abrir 🔔 zera.

### 12.11 MODERAÇÃO das mudanças do comprador (dono, 2026-07-07; suíte 286/286)

**Feature-chave de alinhamento: NADA que o comprador edita vale na hora.**
Todo save no /partner/ vira um **`PriceChangeRequest` pendente**; o dono
aprova/rejeita no Django admin; **só a aprovação aplica no `Price`** (e aí
reflete em card/bancada/valoração). Mesmo padrão four-eyes do catálogo
(KnownPart.review_status).

- **Modelo `PriceChangeRequest`** (migrações 0007 + 0008-RLS, pghistory): o
  pedido (`new_status`/`new_price`) + snapshot do antes (`old_*`) + quem pediu
  e quem revisou. **Um pendente por linha** (constraint `one_pending_per_price`)
  — editar de novo ATUALIZA o pedido, não empilha. No-op não gera pedido.
- **`approve(reviewer)`** aplica via portão do modelo: `quote_date` = dia da
  APROVAÇÃO; `updated_by` = quem PEDIU (o parceiro — auditoria fiel).
  `reject()` deixa o preço exatamente como estava.
- **Django admin → "Mudanças de preço (revisão)"**: fila com pendentes
  primeiro, delta legível ("US$ 6.00 → US$ 5.50"), filtros, e actions em massa
  **✔ Aprovar / ✘ Rejeitar**. Pedido é read-only (nasce só no /partner/).
- **UX do parceiro:** popup de confirmação no envio ("será enviada para
  REVISÃO…"), botão "Enviar p/ revisão", badge azul **⏳ em revisão** na linha
  (mostrando o valor pedido) enquanto o vigente continua exibido.
- **Cosméticos do mesmo pedido:** linha não-cotado = amarelo clarinho; não
  compro = vermelho claro; preço DESABILITADO quando "Não fabricado" (JS
  sincroniza ao trocar o select); coluna "Data" → **"Última atualização"**.

**Runbook do dono:** `python manage.py migrate` (0007+0008) → suíte (286) →
smoke: como parceiro, editar um preço → popup → badge "em revisão"; como
dono, `/admin/` → Mudanças de preço → selecionar → ✔ Aprovar → o card/grid
refletem. Commit/push como sempre.

### 12.10 Rework do grid do parceiro (dono, 2026-07-07; suíte 286/286)

Revisão do dono após uso real. Sete mudanças:

1. **Sem lista-fantasma:** a coluna A da planilha é DECORATIVA no import — na
   "Other Brands" TUDO vira linha da genérica (a linha "Rayson eMMC 8GB" agora é
   preço de "Outras marcas"; a lista Rayson morre). Fold no banco local via
   shell (runbook abaixo).
2. **Estado novo `not_made` ("Não fabricado")** — migração `0006`. Combos que a
   marca não produz (ex.: Kingston eMMC 256GB) deixam de aparecer como
   "herdado" e viram negativa explícita. **No engine é AUTORITATIVA**: linha
   not_made responde `NOT_MADE` e bloqueia fallback (de propósito).
3. **"Sobrescrever" morreu** junto com a exibição de herança na UI do parceiro:
   com o grid unificado, cada lista mostra SÓ as próprias linhas. A herança
   segue existindo NO ENGINE (Outras marcas cobrindo marcas sem lista;
   `inherits_from` configurável pelo dono no admin).
4. **GRID UNIFICADO** — comando novo `seed_price_grid --buyer wuquan`
   (dry-run/commit): toda lista ganha a grade-mestra (união de todos os
   combos); faltantes entram como não-fabricado (marca) / não-cotado (Outras
   marcas). Idempotente; roda após todo import.
5. **Filtros por tipo e estado** acima do grid (GET, selects com auto-submit;
   preservados no salvar).
6. **Estado e Data separados** em duas colunas; o estado é um SELECT explícito
   (Cotado exige preço; os demais limpam o USD).
7. **Vocabulário de estados** = Cotado / Não cotado / Não fabricado /
   **Não compro** — o 4º mantido com aval na conversa: "não compro" (Samsung
   FABRICA GDDR, o Wuquan não quer) ≠ "não fabricado" (Kingston não faz eMMC
   256GB); os dois existiam na planilha ('NO' vs. linha ausente).

**Runbook do dono (rework):**

```bash
python manage.py migrate                    # pricing/0006 (estado not_made)
# fold da Rayson (uma vez, banco local — pghistory registra):
python manage.py shell -c "
from datetime import date
from decimal import Decimal
from tenancy.models import Company
from tenancy.scope import company_scope
from pricing.models import PriceList, Price, STATUS_QUOTED
with company_scope(Company.objects.get(slug='eminer')):
    PriceList.objects.filter(brand__name='Rayson').delete()
    p = Price.objects.get(price_list__brand__isnull=True, kind='emmc',
                          tier_value=8, tier_unit='GB')
    p.status = STATUS_QUOTED
    p.price_min = p.price_max = Decimal('1.50')
    p.quote_date = date(2026, 7, 5)
    p.save()
    print('Rayson fundida em Outras marcas: eMMC 8GB = US$ 1.50')"
python manage.py seed_price_grid --buyer wuquan --company eminer            # dry-run
python manage.py seed_price_grid --buyer wuquan --company eminer --commit  # grid unificado
python manage.py sync_index_page            # JS da home ganhou o estado not_made
python manage.py test chips estoque tenancy pricing --settings=core.settings_test   # 286
python manage.py runserver                  # smoke: filtros, select de estado, coluna Data
git add pricing/ _content/index.html PRECIFICACAO.md
git commit -m "pricing: grid unificado do parceiro — not_made, filtros, estado+data separados, sem lista-fantasma"
git push origin main
```

### 12.9 Polimento do /partner/ (2026-07-07, pedido do dono; suíte 283/283)

- **Header = padrão do painel interno:** o `partner_base.html` replica o Carbon
  UI shell escuro do `base_estoque.html` (mesmas classes/tokens `.wtc-header__*`,
  logo, zonas com borda, crachá "Comprador", Sair vermelho). Copy revisada pelo
  dono (2026-07-07): **só PT** (sem 中文); nav do topo e sidebar = "Início".
- **Câmbio RMB→USD de REFERÊNCIA no topo:** exibe `1 ¥ ≈ US$ 0.xxx` (a API
  devolve USD→CNY; mostramos o INVERSO — é como o comprador pensa). Client-side
  (open.er-api.com, fallback frankfurter.app; sem chave; cache 1h; em falha a
  zona não aparece). ⚠ Exibição apenas — **nenhum cálculo usa esse número**
  (USD é a moeda canônica, princípio #3).
- **Sidebar "Seus preços por marca" em todas as páginas:**
  `_lists_with_stats(buyer)` alimenta a navegação (Início + cada marca +
  "Outras marcas" — o nome partner-facing da lista genérica — com badge de
  pendências e item ativo). A home = "Bem-vindo, {comprador}": 3 KPIs
  ("Chips sem cotação" / "Cotações com mais de N dias" / "Chips cotados") +
  a tabela-panorama de todas as marcas.
- **Datas das cotações do import:** o dono pediu todas as cotadas em
  05/07/2026 — comando (dono roda; `.update()` em massa ainda dispara o
  pghistory, que é gatilho de banco):

```bash
python manage.py shell -c "
from datetime import date
from tenancy.models import Company
from tenancy.scope import company_scope
from pricing.models import Price, STATUS_QUOTED
with company_scope(Company.objects.get(slug='eminer')):
    n = Price.objects.filter(status=STATUS_QUOTED).update(quote_date=date(2026, 7, 5))
    print('cotações datadas em 05/07/2026:', n)"
```

**Próxima e ÚLTIMA fase: F7** — dobrar o durável no `CLAUDE.md` (§4: app
pricing/fonte única do preço; §5: comandos `import_price_xlsx`; §6: convenção
"preço = admin + parceiro") e promover este arquivo de plano a **bíblia
técnica** do sistema de preços.

### §12.21 — Comprador de PLATAFORMA (2026-08-03, REVISA a F2)

Caso real que decidiu: **Mundo Metal** (2ª empresa, viva em prod) abriu lote e
não via valoração — o comprador/grid eram da eMiner (comércio POR-ORG, F2). O
dono fechou a doutrina nova: **"o comprador serve pra todo o sistema, não por
empresa"** — a tabela do Wu Quan precifica o lote de QUALQUER empresa (cliente
vê a tabela CHEIA; a receita da eMiner é **comissão sobre o total**); nenhum
cliente acessa a ENTIDADE comprador (rótulo fixo 'WhatTheChip', F11.3, já
existia). Implementação (suíte 429 OK):

- **Camada A:** `tenancy.scope.PlatformSharedManager` (escopado + `company IS
  NULL`; fail-closed preservado) — vira o `Buyer.objects`. Todos os callsites
  (valoração, export, bancada, vendas, comandos por slug) herdam de graça.
- **Camada B:** `pricing/0021` troca a `tenant_isolation` por par
  leitura/escrita — leitura AMPLA (empresa OU plataforma OU NULL) em
  buyer/pricelist/price/pcr; eventos pghistory continuam estritos; ESCRITA =
  empresa dona OU plataforma OU usuário-parceiro (`app.user_id` ∈
  `pricing_buyer_users` — o /partner/ grava em linha NULL sem GUC de empresa).
  Residual documentado no arquivo da migração (multi-comprador futuro).
- **Dados:** 0021 flipa todo Buyer + filhas denormalizadas para
  `company=NULL` (RunPython com `SET LOCAL app.platform` — lição 2026-08-01).
  Eventos históricos intactos; reverse de dados é manual por decisão.
- `0022`: espelho pghistory do help_text. Teste-chave:
  `CompradorPlataformaTests` (empresa SEM comprador próprio valora pelo da
  plataforma; PriceList NULL propaga) + flip do antigo
  `test_comprador_de_plataforma_null_fica_invisivel`.
- **Fora do escopo (abertos):** cálculo/registro da COMISSÃO da plataforma
  sobre vendas de clientes; painel do parceiro segue 1 comprador; apertar a
  policy de escrita por-tabela se um dia houver 2+ compradores com parceiros
  distintos.

### §12.22 — K9: NAND cru TSOP, tipo PLANO a ¥ fixo por unidade (dono 2026-08-14, HANDOFF_K9; suíte 493/493, characterize diff=0)

**O que é:** K9 = NAND cru (não gerenciado) em encapsulamento **TSOP** — o
ÚNICO chip não-BGA da operação (retangular, perninhas gullwing "de aranha").
O prefixo Samsung (K9F/K9G/K9K) virou nome genérico da categoria no mercado
(tipo "band-aid"). Commodity: o valor **não varia** por marca nem capacidade
→ ler spec seria atrito sem ganho — **deliberadamente omitido**.

**Decisões fechadas (dono, 2026-08-14 — não reabrir sem ele):**

1. **Tipo de primeira classe PLANO** no registro (`chips/chip_types.py`):
   `"K9"` = `nand_raw` / `label_kind='k9'` / `profit_family='k9'` /
   `commercial=True`. SEMPRE RENTÁVEL (o tipo é o veredito — sem limiar).
2. **Caixa K-01** na convenção universal: letra **K** — DESVIO CONSCIENTE da
   regra "próxima letra livre" (seria I; K é mnemônica do nome de mercado e
   aqui não há decode a proteger — a triagem é por formato). Número **01**
   porque "00 é reservado em TODA letra" (o K-00 sugerido no handoff violaria
   a regra fundadora). Fundadora anexada: `('k9','','1','',1)` — tier = "1
   unidade", `tier_unit=''` (GB/Gb não se aplicam). I e J seguem livres.
3. **Preço em `Buyer.k9_rmb_each`** (padrão SSD: SEM linhas de grid; kind
   `k9` existe p/ chave/caixa). Nasce **NULL** → K9 "sem preço" com motivo
   ("K9 sem preço ¥/unidade — defina no comprador (admin)"); **o ¥1 só entra
   no admin após o OK do Wu Quan** (§7.2 do handoff). Engine: `_k9_quote` em
   `price()` E `price_from_key()` (chave materializada F11.1 resolve igual).
   Chave PLANA: `derive_price_key` → `('k9','',1,'')`. Valor do lote =
   `qtd × ¥ × taxa` — câmbio SEM exceção (mesmo feed/travamento de todos).
4. **"NAND Flash" INTOCADO** (caminhos PARALELOS): PN de NAND cru digitado
   (K9F…, GD5F…, W29N…) segue `dead` → NÃO RENTÁVEL → refino R-00. K9 é
   triado por FORMATO, nunca por PN ("zero leitura de spec") — treinar o
   operador: chip de perninha NÃO se digita, joga na caixa K9 e lança "K9".
   Prova: characterize diff=0 (596 PNs, 12 marcas).
5. **Bancada por pseudo-código:** o operador digita **"K9"** no campo de PN
   (exceção ao mínimo de 4 chars — `_pn_too_short`/`_TYPE_PSEUDO_PNS` no
   server + `pnTooShort`/`PN_PSEUDO` no JS do estoque.html). O classify
   curto-circuita ANTES de família/banco/fuzzy (`_classify_impl`, passo 0):
   resultado sintético `known_exact` + `confidence='manual'` (elegível ao
   estoque), sem marca/capacidade, `fuzzy_suggestions=[]` (jamais sugerir
   K9F…). Card completo E mascarado funcionam (mascarado mostra K-01).

**Premissa registrada (§7.3 do handoff):** SEM subdivisão futura por
capacidade/marca. Se o negócio mudar, K9 vira tipo com capacidade como os
NAND gerenciados (remodelagem, não gambiarra na chave).

**Fora do escopo (consciente):** busca da HOME/site segue exigindo 4+ chars —
"K9" digitado lá não decodifica (a bancada é o fluxo do K9; abrir a exceção
na home = mexer no `_content/index.html`/CMS — decisão futura se fizer falta).

**Arquivos:** `chips/chip_types.py` · `chips/engine.py` (passo 0 do classify
+ família k9 no assess) · `pricing/models.py` (KIND_K9 + campo; migr.
`pricing/0023_buyer_k9_rate` com espelho pghistory + constraint
`price_kind_vocab`) · `pricing/engine.py` (`_k9_quote`) ·
`pricing/convention.py` (letra K + fundadora) · `pricing/admin.py` ·
`estoque/views.py` (`_pn_too_short` + caixa `('K9','k9')`) ·
`estoque/templates/estoque/estoque.html` (JS) · testes: `K9PseudoPnTests`,
`K9FixedPricingTests`, `K9BenchTests` + convenção.

**Runbook (prod):**
1. `python manage.py migrate pricing` (0023).
2. `python manage.py seed_category_codes --commit` (cunha SÓ o K-01 novo —
   idempotente; conferir "a criar: 1").
3. Admin → Compradores → Wu Quan → **K9 — ¥ por unidade = 1** (SÓ após o OK
   dele; até lá o card mostra "sem preço" com motivo — comportamento certo).
4. Caixa física "K9" na bancada; smoke: digitar `K9` → card "K9 · Rentável"
   → lançar 3 un. → linha própria "K9" no lote (masked: K-01) → valoração
   `3 × ¥1` com o ¥ definido.
