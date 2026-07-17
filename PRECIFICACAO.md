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
- F11.4 acerto + fatura + pagamentos (+ F11.2b PDF da OV… entregue no
  F11.2c; resta o PDF do romaneio do estoque, fora do F11).

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
