# PLANO_MULTITENANT.md — WhatTheChip multi-empresa (documento de projeto)

> **Status: T1 + T2 + T3 + T4 CONSTRUÍDAS (2026-07-06, sessão dedicada).**
> T1–T3 validadas no local do dono (O3 no Postgres; migrate + backfill feitos;
> handshake Camada A verde). **T4 (RLS) construída em seguida** — suíte 231/231;
> falta o dono rodar `migrate` (0014 liga o RLS) + `RLSHandshakeTests` no
> Postgres, e o deploy em produção. Restam T5 (fila no app) e T6 (onboarding)
> antes do 2º cliente real logar. **Ver §16 (diário de execução).**
> **Este é o documento-guia de uma SESSÃO DEDICADA de implementação.** Quando o
> projeto terminar, a precificação (`PRECIFICACAO.md`) começa em cima da fundação
> construída aqui (a F1 de lá **é** a T1 daqui).
>
> **Sessão nova: leia NESTA ordem, antes de tocar em qualquer coisa:**
> 1. `CLAUDE.md` inteiro (regras de ouro — especialmente §2.1: o agente EDITA
>    arquivos, o DONO roda tudo que escreve no banco; prod é a fonte da verdade
>    do catálogo vivo, 6.500+ known_parts, NUNCA se reconstrói).
> 2. Este arquivo inteiro.
> 3. `PRECIFICACAO.md` §3.0 e §10 (o contrato de tenancy que este projeto executa).
>
> **Como trabalhar:** brainstorm curto para fechar as decisões em aberto (§14) →
> execução fase a fase (§11), cada fase termina com a prova verde antes da próxima.
> Suíte: `python manage.py test chips estoque --settings=core.settings_test` +
> `characterize_baseline --diff` (zero diff esperado — este projeto NÃO toca o
> engine de classificação).

---

## 1. Negócio: de ferramenta interna a SaaS

**Hoje** o WhatTheChip opera para UMA empresa (eMiner, Paraguai): operadores de
bancada classificam chips recuperados, o gateway decide RENTÁVEL/NÃO RENTÁVEL, os
lotes acumulam estoque e são exportados para venda. Login único, sem papéis, sem
noção de "empresa" no banco.

**A visão** é abrir a plataforma para **centenas de empresas recicladoras**, cada
uma operando como a eMiner opera hoje:

- **O que cada empresa-cliente recebe:** acesso próprio (usuários com papéis
  admin/gerente/operador), lotes e envios próprios, fila de conferência própria,
  exports próprios — e, do projeto irmão, compradores e tabelas de preço próprios.
- **O que é compartilhado (o produto):** o catálogo global de classificação — o
  "Google dos chips". É o ativo central e o **efeito de rede**: toda busca de toda
  empresa exercita (e potencialmente alimenta) o mesmo cérebro. Melhorou para um,
  melhorou para todos.
- **A fronteira comercial absoluta:** a empresa A JAMAIS vê lote, estoque, envio,
  comprador ou preço da empresa B. Recicladoras são concorrentes entre si — um
  vazamento de estoque/preço entre elas mata a confiança no produto.

**Fora do escopo deste projeto (non-goals explícitos):** cobrança/billing/planos
de assinatura; subdomínio/branding por cliente (§10 explica o porquê); o sistema de
preços em si (projeto irmão); SSO/convite self-service sofisticado; i18n.

---

## 2. Objetivos mensuráveis (o "pronto" do projeto)

| # | Objetivo | Como se prova |
|---|---|---|
| **O1** | Papéis funcionando: operador SÓ adiciona chips; gerente abre/fecha/exporta/revisa; admin controla a empresa | testes de view por papel (403 nas ações proibidas) + teste de redirect pós-login |
| **O2** | Operação da eMiner INTACTA: zero regressão de classificação, zero mudança no fluxo do operador atual | suíte completa verde + `characterize_baseline --diff` = 0 + smoke manual do dono na bancada |
| **O3** | Corrida da numeração de lote eliminada (bug real de hoje, §7) | teste de concorrência (N threads abrindo lote → números sequenciais, zero IntegrityError) |
| **O4** | Isolamento entre empresas PROVADO nas duas camadas | "handshake de tenancy" na suíte (§12): A não lê/escreve dado de B via ORM **e** via SQL cru (RLS) |
| **O5** | Onboarding: criar empresa nova + primeiro admin em < 5 min, sem tocar código | roteiro T6 executado com uma empresa de teste |
| **O6** | Fundação pronta para a precificação: `Company`/`Branch`/`Membership` exatamente como o `PRECIFICACAO.md` §3.0 espera | checklist de handoff (§15) |

---

## 3. Estado atual do sistema (verificado no código, 2026-07-06)

- **Single-tenant total:** nenhum modelo tem noção de empresa. `estoque/` é
  `@login_required` simples; qualquer usuário logado faz tudo; operadores enxergam
  mais do que deviam (inclusive caminhos de admin).
- **Sem papéis:** não existe operador/gerente/admin — só `is_staff`/`is_superuser`
  do Django, usados de forma binária.
- **Concorrência:** `estoque/models.py::Lot.next_number()` usa `Max('number')+1`
  → **race condition real** (dois gerentes abrindo lote juntos = um leva
  `IntegrityError`; o `number` é `unique=True`, então não corrompe, mas quebra na
  cara). Já o incremento de quantidade **está correto**: `.update(quantity=
  F('quantity') + qty)` + constraints `unique_lot_pn`/`unique_pending_lot_pn` —
  atômico no banco, **não mexer**.
- **Infra pronta que este projeto reaproveita:** `pghistory` (migração 0016) para
  auditoria; `catalog_version` para cache do engine (não é tocado); Postgres no
  Render (plano pago), PgBouncer disponível mas não ativo.
- **Stack:** Django 5.2 LTS / Python 3.11 / HTMX + templates + CSS puro (sem SPA)
  / Render com auto-deploy no push em `main`.

---

## 4. Decisão de arquitetura: banco compartilhado + isolamento por LINHA

**Uma coluna `company_id` nas tabelas de comércio/estoque; um Postgres só.**

| Alternativa | Veredito | Por quê |
|---|---|---|
| **Row-level (escolhida)** | ✅ | é o padrão dos SaaS de grande escala; migrations rodam 1×; conexões não multiplicam; backup/restore único; centenas de empresas × milhões de linhas é confortável com índices liderados por `company_id` |
| Schema-por-tenant | ❌ | migrations × N tenants (deploy vira loteria), `search_path` frágil, ferramentas Django lidam mal |
| Banco-por-tenant | ❌ | conexões multiplicam (o limite real do Render é CONEXÃO), custo por tenant, agregação cross-tenant impossível |

- **Saída híbrida preservada:** se um cliente gigante exigir isolamento físico,
  faz-se "peel-off" só dele para um banco dedicado (mesmo schema, mesma app
  apontando outro `DATABASE_URL`) — a arquitetura row-level não fecha essa porta.
- **Alavancas de escala, na ordem do mais barato:** índices compostos
  `(company_id, …)` → PgBouncer (pooling) → réplicas de leitura (o catálogo global
  é read-heavy e cacheado por `catalog_version`) → particionamento do
  `InventoryEntry` (por company ou por data) → sharding (futuro distante).
  **Não otimizar no escuro:** cada alavanca só entra com sinal real de gargalo.

**Dois mundos no mesmo produto** (contrato do `PRECIFICACAO.md` §10):

| Domínio | Tenancy |
|---|---|
| Catálogo (Brand/ChipFamily/DecodeMap/KnownPart), gramática, engine, fuzzy, páginas de doc | **GLOBAL — sem `company_id`, sem RLS** |
| Estoque (Lot/InventoryEntry/PendingEntry/RejectedEntry), exports | **POR-EMPRESA** |
| Buyer/PriceList/Price/LotPricing (projeto irmão) | **POR-EMPRESA** (via `Buyer.company`) |
| `ProfitabilityConfig`, `SearchLog`, `UnknownChip` | global hoje — decisões em aberto (§14) |

---

## 5. Modelo de dados (app novo: `tenancy/`)

### 5.1 Os três modelos da fundação (T1)

```python
class Company(models.Model):
    name       = CharField(unique=True)          # "eMiner"
    slug       = SlugField(unique=True)          # "eminer" (rotas/domínio futuros)
    active     = BooleanField(default=True)      # desativar ≠ deletar (histórico)
    last_lot_number = PositiveIntegerField(default=0)  # contador atômico (§7)
    created_at = DateTimeField(auto_now_add=True)
    notes      = TextField(blank=True)

class Branch(models.Model):                      # filial/planta — NÃO é tenant
    company    = ForeignKey(Company, PROTECT, related_name="branches")
    name       = CharField()                     # "Matriz", "Bancada CDE"
    active     = BooleanField(default=True)
    # unique_together (company, name)

class Membership(models.Model):
    user       = ForeignKey(User, CASCADE, related_name="memberships")
    company    = ForeignKey(Company, PROTECT)
    branch     = ForeignKey(Branch, PROTECT, null=True, blank=True)  # opcional no v1
    role       = CharField(choices=["admin", "manager", "operator"])
    active     = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    # unique_together (user, company)  · índice (company, role)
```

- **`Company` é a fronteira do isolamento** (a chave do RLS). `Branch` é
  sub-unidade organizacional — dashboards agregam por empresa OU por filial, mas
  segurança é sempre por empresa.
- **Branch é nullable em TUDO no v1** — empresa pequena (1 bancada) não deve ser
  obrigada a criar filial. Vira obrigatório por empresa via flag futura se preciso.
- **`PROTECT`, não `CASCADE`, em company/branch:** apagar empresa por acidente não
  pode levar lotes junto. Desativação é `active=False`.
- Empresa #1 = eMiner (criada no backfill da T1, com os usuários atuais recebendo
  Membership com papel definido pelo dono).
- **pghistory** nos três modelos (mudança de papel é evento de segurança).

### 5.2 Retrofit do estoque (T3)

```
Lot            + company FK (denormalizado, chave do RLS) + branch FK nullable
InventoryEntry + company FK (denormalizado — NÃO navegar lot.company p/ filtrar)
PendingEntry   + company FK      RejectedEntry + company FK
```

- **Denormalizar `company_id` em TODAS as tabelas tenant-scoped** (mesmo tendo FK
  pro pai): o RLS precisa da coluna na própria tabela, e os índices compostos
  `(company_id, …)` também. Consistência pai-filho garantida no `save()`.
- **Numeração de lote muda de global para por-empresa:** `unique (company,
  number)` substitui `number unique=True`. eMiner herda a sequência atual
  (`last_lot_number` = max atual no backfill); cada empresa nova começa no
  "Lote #001" dela.
- **Migração em 3 passos (padrão seguro em banco vivo):** (1) adicionar colunas
  NULLABLE (aditivo, deploy sem downtime) → (2) backfill `company=eMiner`
  (comando com dry-run/`--commit`, **backup Render Export antes** — CLAUDE.md
  §2.1b.c) → (3) travar: NOT NULL + constraints + índices. Cada passo é uma
  migration separada e reversível.
- **Índices:** `(company, -number)` no Lot; `(company, lot)` e `(company,
  part_number)` no InventoryEntry — toda consulta do app começa por company.

---

## 6. Blindagem em DUAS camadas (o risco do row-level é vazar dado)

### 6.1 Camada A — aplicação (ergonomia: impossível esquecer o filtro)

```python
# tenancy/scope.py
_current_company: ContextVar[int | None] = ContextVar("company", default=None)

# Middleware (após AuthenticationMiddleware):
#   resolve o Membership ativo do request.user → seta o contextvar
#   → e emite SET LOCAL (§6.2) dentro da transação do request

class CompanyScopedManager(models.Manager):
    def get_queryset(self):
        cid = _current_company.get()
        if cid is None:
            raise CompanyScopeMissing(...)   # FAIL-CLOSED: sem escopo → ERRO,
        return super().get_queryset().filter(company_id=cid)   # nunca "todos"

class Lot(models.Model):
    objects       = CompanyScopedManager()   # o caminho padrão JÁ vem filtrado
    all_companies = models.Manager()         # escape EXPLÍCITO e gritante
```

- **Fail-closed é a decisão-chave:** código rodando sem escopo (bug, comando
  esquecido) EXPLODE em vez de vazar. `all_companies` só em código de plataforma,
  fácil de auditar por grep.
- **Management commands e jobs rodam fora de request** → escopo SEMPRE explícito:
  `with company_scope(company):` ou flag `--company <slug>` obrigatória. Comando
  tenant-scoped sem escopo declarado não passa em review.
- **Views:** mixins `RoleRequired(role="manager")` etc. decidem o PAPEL; o manager
  decide a EMPRESA. Camadas independentes.
- `ATOMIC_REQUESTS = True` entra junto (pré-requisito do `SET LOCAL` e boa prática
  geral — cada request é uma transação).

### 6.2 Camada B — banco (garantia: nem query bugada cruza empresa) — T4

```sql
-- por tabela tenant-scoped (via migration RunSQL, com reverse):
ALTER TABLE estoque_lot ENABLE ROW LEVEL SECURITY;
ALTER TABLE estoque_lot FORCE  ROW LEVEL SECURITY;   -- ⚠ SEM ISTO O RLS NÃO VALE:
                                                     -- o DONO da tabela bypassa
                                                     -- policies, e a app do Render
                                                     -- conecta como dono
CREATE POLICY tenant_isolation ON estoque_lot
    USING (company_id = current_setting('app.company_id', true)::int);
```

- O middleware emite **`SET LOCAL app.company_id = <id>`** na transação do request.
  **`SET LOCAL` por TRANSAÇÃO, nunca `SET` por sessão:** é o único modo seguro com
  PgBouncer em transaction mode (a conexão é reciclada entre transações — variável
  de sessão VAZARIA entre empresas).
- ⚠ **Correção (revisão 2026-07-06): `ATOMIC_REQUESTS` NÃO basta para o SET LOCAL.**
  Ele abre a transação só em volta da VIEW (dentro do `_get_response`); middleware
  roda FORA dela — um `SET LOCAL` emitido ali seria no-op. Na T4, o próprio
  `TenancyMiddleware` abre o `transaction.atomic()` EXTERNO em volta do
  `get_response` e emite o `SET LOCAL` logo após entrar (o middleware já existe
  desde a T1 e tem o comentário marcando o ponto).
- `current_setting(..., true)` retorna NULL se a variável não foi setada → policy
  avalia falso → **zero linhas (fail-closed também no banco)**.
- **Armadilhas mapeadas:**
  1. Postgres superuser bypassa RLS — a app nunca conecta como super.
  2. **Migrations/comandos de dados sob RLS:** rodam como dono (que com FORCE
     também é filtrado) → data-migration precisa setar a GUC ou usar role com
     `BYPASSRLS` (decisão operacional da T4; DDL não é afetado).
  3. **Tabelas de evento do pghistory** copiam as colunas → também carregam
     `company_id` → recebem policy igual (histórico é tão sensível quanto o dado).
  4. Policies vivem em **migrations versionadas** (RunSQL com reverse), como tudo.
- A camada A funciona sozinha entre T3 e T4 (o app já sai isolado); a T4 é o
  cinto-e-suspensório que remove a confiança no código.

---

## 7. Concorrência (T2) — validado contra o código real

| Alegação (chat de arquitetura) | Verificação no código (2026-07-06) | Ação |
|---|---|---|
| "Número de lote `Max+1` é race" | **CONFIRMADO** — `Lot.next_number()` agrega `Max('number')+1`; `unique=True` evita corrupção mas dá `IntegrityError` num dos lados | Corrigir na T2 (abaixo) |
| "Incremento de quantidade é ler-modificar-escrever" | **FALSO** — já é `.update(F('quantity') + qty)` + constraints únicas; atômico | **Nada a fazer** |
| "`SET LOCAL` por transação sob PgBouncer" | PgBouncer ainda não ativo | Regra escrita em §6.2 para quando ativar |

**Correção recomendada (contador por empresa, à prova de corrida):**

```python
with transaction.atomic():
    c = Company.objects.select_for_update().get(pk=company_id)  # lock da linha
    c.last_lot_number += 1
    c.save(update_fields=["last_lot_number"])
    lot = Lot.objects.create(company=c, number=c.last_lot_number, ...)
```

Lock de UMA linha por empresa, segura o número sem window de corrida, e já nasce
por-empresa (casa com `unique (company, number)` da T3). Prova: teste com N
threads abrindo lotes simultâneos → números sequenciais sem buraco, zero
`IntegrityError`. **A T2 protege a operação DE HOJE** (multi-operador já existe na
eMiner) — por isso vem cedo, independente do 2º cliente.

Notas de execução (revisão 2026-07-06):
- **Seed do contador já resolvido na T1:** o `bootstrap_tenancy` grava
  `last_lot_number = max(Lot.number)` no backfill — a T2 só troca o
  `next_number()` pelo contador com lock.
- ⚠ **O teste de corrida (O3) exige Postgres:** `select_for_update` é NO-OP no
  SQLite e threads + banco em memória travam — sob `settings_test` a prova
  passaria sem provar nada. O teste multi-thread deve rodar contra Postgres
  local e receber `skipUnless(vendor == 'postgresql')`.

---

## 8. Papéis — OPERADOR / GERENTE / ADMIN (por empresa) + plataforma acima

`Membership.role`; decisão do dono (2026-07-06):

| Ação | OPERADOR | GERENTE | ADMIN (dono da empresa) |
|---|---|---|---|
| Buscar/classificar chips, ver RENTÁVEL/NÃO | ✔ | ✔ | ✔ |
| Adicionar chips a lote ABERTO | ✔ | ✔ | ✔ |
| Abrir / fechar lotes | — | ✔ | ✔ |
| Revisar fila de conferência (PendingEntry) | — | ✔ | ✔ |
| Exportar lote (.xlsx) | — | ✔ | ✔ |
| Ver PREÇO (projeto irmão: card de busca; estoque na F8) | — | — | ✔ |
| Gerenciar compradores/listas de preço da empresa | — | — | ✔ |
| Gerenciar usuários/filiais da empresa | — | — | ✔ |
| Django admin | — | — | — (**só plataforma**) |

- **Plataforma** = `is_superuser` (o dono do WTC): acima das empresas, único no
  Django admin, opera o catálogo global e cria empresas. NÃO é role de Membership.
- **Parceiro (comprador)** = fora do enum: conta externa via `Buyer.users`, vive
  em `/partner/` (projeto irmão). Sem Membership.
- Preço para GERENTE fica **desligado** (se abrir um dia: flag por empresa, não
  mudança de arquitetura).
- **Enforcement em 3 pontos:** mixin de view (403), template (esconder botão) e —
  para o que importa — o próprio fluxo (ex.: fechar lote é POST só em view de
  gerente+). Esconder botão NUNCA é a única barreira.
- **Consequência estrutural:** operações de empresa que hoje moram no Django admin
  (aprovar PendingEntry, gerenciar lotes) migram para telas do app com gate por
  papel (T5). Django admin vira ferramenta exclusiva de plataforma.
- **Redirect pós-login:** conta com `Buyer.users` → `/partner/` · demais → 
  `/estoque/` (a navegação interna é que muda por papel). Sem cadastro público.

---

## 9. Login, navegação e UX por papel

- Login único em `/login/` (como hoje). Após T1: middleware resolve o Membership;
  usuário com múltiplas empresas (raro; ex.: consultor) ganha seletor de empresa —
  v1 pode simplesmente pegar a primeira ativa e deixar o seletor pra depois.
- Navegação renderizada por papel (template tags `{% if role >= "manager" %}`):
  operador vê busca + "adicionar ao lote aberto"; gerente vê lotes/fila/export;
  admin vê tudo + gestão da empresa.
- Filial: se a empresa tem branches e o operador tem `branch` no Membership, os
  lançamentos dele carregam a filial automaticamente; dashboards filtram por
  filial opcionalmente.

---

## 10. Rotas e domínio

- **V1: SEM tenant na URL.** App 100% atrás de login → a SESSÃO define a empresa
  (Membership). Zero DNS, zero middleware de host, zero risco novo. Subdomínio é
  branding, não isolamento — o RLS não depende dele.
- **Depois (branding/marketing):** wildcard `*.whatthechip.com` →
  `eminer.whatthechip.com` (requer domínio próprio; `*.onrender.com` não dá
  sub-subdomínio; o plano pago tem 2 custom domains — wildcard conta como 1).
  Alternativa sem DNS: path `/t/<company-slug>/`.
- Slugs/rotas públicas **em inglês** (decisão do dono, já no `PRECIFICACAO.md`).

---

## 11. Fases (T) — entregas, critérios de aceite e provas

> Regra de ouro #1 em todas: o agente edita arquivos e escreve migrations; o
> **dono roda** `migrate`/backfills/`--commit`. Antes de backfill em banco vivo:
> **backup fresco (Render Export)**. Depois de todo deploy: `guard_catalog`
> (intocado por este projeto, mas o tripwire continua obrigatório).

| Fase | Entrega | Aceite / prova | Quando |
|---|---|---|---|
| **T0** | Contrato (PRECIFICACAO §10) + este plano | — | ✅ feito |
| **T1** | app `tenancy/`: `Company`+`Branch`+`Membership` (§5.1) + middleware/contextvar + mixins de papel + navegação por papel + redirect + **backfill eMiner** (empresa #1, usuários atuais → papéis definidos pelo dono) + pghistory | O1 e O2 provados: testes de permissão por papel (403), redirect, suíte verde, characterize diff=0; operador real da eMiner não nota diferença (exceto o que deixou de ver indevidamente) | ✅ **construída 2026-07-06** (§16) — falta o dono rodar migrate+backfill |
| **T2** | Numeração de lote atômica (§7): contador `select_for_update` + teste de corrida (o `unique (company, number)` completo fica pra T3; na T2, com 1 empresa, o contador já elimina a corrida) | O3: teste multi-thread verde; zero mudança de comportamento visível | ✅ **construída 2026-07-06** (§16) — prova da corrida roda no Postgres do dono |
| **T3** | Retrofit do estoque (§5.2): colunas nullable → backfill → NOT NULL + `unique (company, number)` + índices; managers `CompanyScopedManager` em Lot/Entry/Pending/Rejected; comandos de estoque ganham `--company` | handshake de tenancy via ORM (§12); export/telas todos escopados; suíte estoque verde | ✅ **construída 2026-07-06** (§16) — gatilho antecipado: 2ª empresa de teste criada pelo dono |
| **T4** | RLS (§6.2): policies + FORCE + `SET LOCAL` no middleware + policies nas tabelas pghistory + decisão BYPASSRLS p/ comandos | handshake via **SQL cru**: conexão da app sem GUC → 0 linhas; com GUC da empresa A → só linhas de A | ✅ **construída 2026-07-06** (§16) — prova no Postgres do dono |
| **T5** | UI de gerente no app: fila PendingEntry (aprovar/reprovar), abrir/fechar lote, export — esvazia o Django admin de operação de empresa | testes de view por papel; Django admin sem uso operacional por não-plataforma | com T3/T4 |
| **T6** | Onboarding: tela/fluxo de plataforma "criar empresa + primeiro admin (+ filiais)"; roteiro documentado | O5: empresa de teste criada em < 5 min sem tocar código | antes do 2º cliente logar |

**Relação com a precificação:** T1 (e idealmente T2) prontos → volta ao
`PRECIFICACAO.md` e executa F0→F7 de lá. T3+ NÃO bloqueia os preços (Buyer já
nasce com `company` FK; o retrofit do estoque corre depois, em paralelo ou não).

---

## 12. Testes obrigatórios (a rede de segurança do projeto)

1. **Handshake de tenancy** (novo, permanente na suíte — no espírito do
   golden/handshake de rentabilidade): para cada modelo tenant-scoped, o teste
   cria empresas A e B com dados e prova que A não lê/edita/deleta nada de B —
   via manager padrão (T3) **e** via SQL cru com GUC (T4). Para cada modelo NOVO
   do sistema, o teste exige: ou está na lista GLOBAL declarada
   (`PRECIFICACAO.md` §10), ou tem manager escopado + policy + caso no handshake.
   **Tabela sem decisão de tenancy = suíte vermelha.**
2. **Permissão por papel:** cada view sensível × cada papel → 200/403 esperado
   (matriz do §8 vira parametrização de teste).
3. **Corrida de lote:** N threads simultâneas (§7).
4. **Regressão de classificação:** `characterize_baseline --diff` = 0 em TODAS as
   fases (este projeto não toca o engine — qualquer diff é bug).
5. **Suíte completa** verde a cada fase: `python manage.py test chips estoque
   --settings=core.settings_test` (+ o novo app `tenancy`).

---

## 13. Riscos e armadilhas (além dos §6/§7)

- **Vazamento por relatório/export:** export `.xlsx` e agregações são os lugares
  onde vazamento passa despercebido — TODOS passam pelo manager escopado (e o
  handshake cobre um export).
- **Backfill em banco vivo:** é operação destrutiva por natureza → backup fresco +
  dry-run + revisão do dono + reversível (CLAUDE.md §2.1b.c). O catálogo
  (known_parts) NÃO é tocado por este projeto — `guard_catalog` deve continuar
  estável como testemunha.
- **`is_superuser` usado no dia a dia:** plataforma logada como super em telas de
  empresa fura o modelo mental (contextvar sem Membership). Definir na T1: super
  navegando o app assume uma empresa explicitamente (seletor de plataforma) ou só
  usa o Django admin.
- **Sessões ativas na virada de papéis (T1):** usuários logados no deploy do
  backfill — forçar re-login (invalidar sessões) para o middleware nascer limpo.
- **Django `permission` nativo vs role próprio:** decisão consciente por role
  simples no Membership (3 papéis fixos, matriz clara) — o sistema de permissions
  granular do Django fica como evolução se um dia precisar de permissão por-ação.

---

## 14. Decisões em aberto — **FECHADAS no brainstorm de 2026-07-06 (dono)**

1. **`SearchLog`/`UnknownChip`: ✅ FECHADA** — `company` nullable, mas os modelos
   **permanecem GLOBAIS** (sem manager escopado, sem RLS; declarados na lista
   global do handshake). A empresa é ANOTAÇÃO de análise (SET_NULL); dedup do
   UnknownChip continua mundial (1ª empresa a reportar fica anotada). Implementado
   na T1 (`chips/0022`; engine anota via contextvar em `_log_search`/`_log_unknown`).
2. **`ProfitabilityConfig`: ✅ FECHADA** — global até um cliente pedir;
   `get_config()` centraliza o ponto de mudança. (Nada a implementar agora.)
3. **Papéis dos usuários atuais da eMiner:** lista nominal do dono — informada na
   hora de rodar `bootstrap_tenancy` (argumentos `--admin/--manager/--operator`).
   Não bloqueou o código.
4. **Superuser navegando o app: ✅ FECHADA** — o dono ganha **Membership admin
   normal na eMiner** (zero código extra); superuser SEM vínculo fica restrito ao
   Django admin (o fail-closed cuida do resto). Sem seletor de plataforma no v1.
5. **Nomes: ✅ FECHADA** — app `tenancy/`; rotas de gestão em inglês
   (`/company/users/`…) quando existirem (T5/T6).
6. **Gatilho da T3: ✅ FECHADA** — espera o 2º cliente assinando (T1+T2 primeiro;
   preços correm em paralelo).
7. **Multi-empresa por usuário: ✅ FECHADA** — v1 usa a primeira empresa ativa
   (`order_by pk` no middleware, testado); seletor fica para quando houver caso real.

---

## 15. Checklist de handoff — de volta à precificação

Ao fim da sessão dedicada (mínimo T1, ideal T1+T2):

- [ ] `Company`/`Branch`/`Membership` no banco, com eMiner + usuários reais e
      papéis atribuídos (migrations aditivas aplicadas pelo dono).
- [ ] Middleware + contextvar + `CompanyScopedManager` disponíveis (mesmo que só
      os modelos novos usem até a T3).
- [ ] Mixins de papel funcionando; operador sem acesso a abrir/fechar/exportar;
      redirect por papel ativo; Django admin restrito à plataforma.
- [ ] Numeração de lote atômica (T2) com teste de corrida verde.
- [ ] Suíte completa verde + `characterize_baseline --diff` = 0 + `guard_catalog`
      estável pós-deploy.
- [ ] Este arquivo atualizado com o que foi construído (vira bíblia técnica do
      tenancy); regra de tenancy nova dobrada no `CLAUDE.md` (§ de convenções).
- [ ] → **Abrir a sessão de implementação da precificação** com `PRECIFICACAO.md`
      (F0 em diante), que assume esta fundação pronta.

---

## 16. Diário de execução

### T1 — construída em 2026-07-06 (suíte 216/216 verde)

**O que existe (tudo versionado; nada gravado em banco ainda):**

- **`tenancy/`** — `models.py` (Company/Branch/Membership, PROTECT, pghistory nos
  três, `membership_role_vocab` CheckConstraint, portão filial×empresa no
  `save()`); `scope.py` (contextvar + `company_scope()` + `require_company_id()`
  fail-closed + `CompanyScopedManager` pronto para a T3 — com a nota do
  `base_manager_name='all_companies'`); `middleware.py` (resolve Membership →
  `request.company/membership/company_role` + contextvar, reset no finally; ponto
  do SET LOCAL da T4 comentado); `access.py` (`role_required(min_role)` decorator
  + `RoleRequiredMixin`; SEM bypass de superuser — decisão §14.4);
  `context_processors.py` (`wtc_is_manager` etc.); `admin.py` (plataforma);
  `management/commands/bootstrap_tenancy.py` (backfill dry-run/--commit).
- **Migrations aditivas:** `tenancy/0001_initial` (3 modelos + eventos pghistory)
  e `chips/0022` (SearchLog.company + UnknownChip.company, nullable SET_NULL).
  Zero migration no estoque (schema intacto na T1).
- **Gates aplicados (`estoque/views.py`):** operador = lista/detalhe/preview/
  adicionar/remover-de-lote-aberto; gerente+ = criar/fechar/reabrir/exportar e
  remover de lote fechado. Templates escondem ações por papel (`wtc_is_manager`);
  header mostra `usuário · empresa · papel`.
- **Anotação §14.1:** `chips/engine.py::_log_search/_log_unknown` gravam
  `company_id` do contextvar (helpers de log — a CLASSIFICAÇÃO não muda).
- **Testes novos:** `tenancy/tests.py` (scope fail-closed, manager escopado,
  middleware, redirect, anotação §14.1, bootstrap) +
  `estoque/tests.py::RoleMatrixTests` (matriz §8 parametrizada, O1).

**⚠ Mudança de comportamento intencional (aprovada pela matriz §8):** o lote
virou **ativo da EMPRESA** — caiu o filtro `operator=request.user` (`_get_lot`/
`lot_list`): todos os papéis VEEM todos os lotes; operador ADICIONA em lote
aberto (por qualquer gerente); só gerente+ abre/fecha/exporta. O campo
`Lot.operator` agora significa "quem abriu". Sem isso a matriz seria impossível
(operador não pode criar lote, logo precisa trabalhar em lote de outro).

**Runbook do dono (nesta ordem, no ambiente local primeiro):**

```bash
python manage.py migrate                      # ✅ FEITO 2026-07-06 (tenancy/0001 + chips/0022)
python manage.py test chips estoque tenancy --settings=core.settings_test   # ✅ 220 OK
python manage.py test estoque.tests.LotNumberRaceTests   # ✅ FEITO — OK no Postgres local
                                              # (settings DEFAULT; no SQLite se auto-pula)
python manage.py characterize_baseline --out baseline_t1t2.json   # ✅ FEITO — 6.568 PNs
                                              # ⚠ sintaxe correta: --out gera o snapshot; o --diff
                                              # EXIGE um arquivo (gere o baseline ANTES de cada fase
                                              # futura e rode --diff <arquivo> DEPOIS; T1/T2 não
                                              # tocam o engine)
python manage.py bootstrap_tenancy --company eMiner \
    --admin <dono> --manager <..> --operator <..> --operator <..>   # DRY-RUN: revisa
python manage.py bootstrap_tenancy --company eMiner ... --commit    # ✅ FEITO no LOCAL
                                              # (--admin admin; eMiner criada, contador → 40)
python manage.py runserver                    # smoke: operador não vê Fechar/Exportar/Novo Lote
```

> ⚠ **O `--commit` do bootstrap PRECISA da lista nominal de papéis.** Os gates não
> têm bypass de superuser (decisão §14.4): sem `--admin <seu-usuário>`, NINGUÉM —
> nem você — acessa o estoque depois (403 até ganhar vínculo via admin).

Produção (após validar local): backup fresco (Render Export) → push em `main`
(deploy roda `migrate` no build) → rodar `bootstrap_tenancy --commit` localmente
com `DATABASE_URL` do Render → `guard_catalog` (tripwire, como sempre). Todos
relogam (sessões invalidadas de propósito, §13).

### T2 — construída em 2026-07-06 (mesma sessão; suíte 220/220 verde)

- **`Lot.open_for_company(company, operator, description)`** (`estoque/models.py`)
  substitui o `next_number()` (removido — era o `Max+1` da corrida): lock na linha
  da Company (`select_for_update`) → incrementa `last_lot_number` → cria o Lot,
  tudo numa transação. Criações simultâneas serializam no lock: números
  consecutivos, zero `IntegrityError`. `lot_create` usa (`request.company` vem do
  middleware; o gate garante o vínculo).
- **Guard de drift:** `max(contador, Max(Lot.number)) + 1` — auto-cura contador
  atrasado (lote criado antes do bootstrap, restore etc.) enquanto o `number` é
  unique GLOBAL; na T3 o `Max` passa a filtrar por company.
- **Empresa nova começa no Lote #001** (contador 0 → 1); eMiner herda a sequência
  (seed no bootstrap, com o mesmo guard).
- **Testes:** `LotNumberSequenceTests` (série: primeira numeração, seed, drift —
  qualquer banco) + `LotNumberRaceTests` (O3: 8 threads com `Barrier` →
  sequencial sem buraco, zero erro; `TransactionTestCase`, **skipUnless
  Postgres** — no SQLite `select_for_update` é no-op e a prova seria falsa; cada
  thread fecha a própria conexão).

**Pendências deixadas de propósito:** fila PendingEntry continua no Django admin
até a T5 (quem revisa é a plataforma/dono); managers escopados entram nos modelos
do estoque na T3 (com `base_manager_name` — ver §6.1); RLS na T4.

### T3 — construída em 2026-07-06 (mesma sessão; suíte 230/230 verde)

**Gatilho antecipado:** o dono criou a 2ª empresa de teste ("Brasil Reciclagem")
e viu todos os lotes compartilhados — exatamente a fronteira que a T1/T2 não
cobria (documentado nos comentários do código). A T3 fecha o isolamento.

**O que existe:**

- **Modelos (`estoque/models.py`):** `Lot.company` (PROTECT) + `Lot.branch`
  (nullable, v1) + base abstrata `CompanyBoundByLot` nos 3 filhos (company
  DENORMALIZADO — o RLS da T4 exige coluna local; `save()` herda do lote e
  rejeita mismatch). Managers: `objects = CompanyScopedManager()` (fail-closed),
  `all_companies` (plataforma), `Meta.base_manager_name='all_companies'` (senão
  travessias internas do Django explodiriam — correção anotada na revisão).
- **Numeração POR EMPRESA:** caiu o `unique` global do `number`; entrou
  `unique (company, number)`; `open_for_company` conta por empresa (Brasil
  Reciclagem começa no **Lote #001**; a eMiner segue a sequência dela).
  Índices: `(company, -number)` no Lot; `(company, part_number)` e
  `(company, lot)` no InventoryEntry.
- **Migrações em 3 passos** (padrão §5.2): `0011` nullable (aditiva) → `0012`
  backfill (data migration: lote herda a empresa do Membership de quem o abriu,
  fallback empresa #1; **se produção não tiver NENHUMA Company, a 0012 CRIA a
  eMiner** — slug `eminer`, mesmo nome do bootstrap — para o build não quebrar;
  filhos herdam do lote via Subquery) → `0013` NOT NULL + constraint + índices
  (à mão: o makemigrations pergunta interativo no null→NOT NULL).
  **Ensaio de produção EXECUTADO no sandbox:** banco legado (lotes, zero
  empresas) → `migrate` → eMiner auto-criada, tudo backfillado, travas ok.
- **Views:** nada mudou de propósito — o manager escopado faz o trabalho sob o
  escopo da request. Lote de outra empresa = **404** (nem existe). `lot_create`
  grava company + a filial do gerente (se houver).
- **Django admin = plataforma:** `PlatformScopedAdmin` (get_queryset via
  `all_companies`, dropdown de lote idem); colunas/filtros por empresa;
  `aprovar` da fila usa `all_companies` (a entrada herda a empresa do lote).
  ⚠ Filtro `list_filter` por FK `lot` foi trocado por `company` (o filtro de FK
  usa o default manager fail-closed).
- **Comandos com escopo explícito (§6.1):** os 8 comandos tenant-scoped
  (`bless_base`, `clean_lote`, `fix_pns`, `list_unconfirmed`,
  `reconcile_lote_039`, `refresh_lote`, `resnapshot_lote`,
  `audit_estoque_drift`) ganharam `--company <slug>` +
  `scope_command_to_company()` (tenancy/scope.py): com UMA empresa ativa,
  auto-resolve (ergonomia de hoje preservada); com 2+, **exige** o slug
  (fail-closed). `bootstrap_tenancy` seeda o contador POR empresa.
- **Testes novos (O4):** `TenancyHandshakeTests` — A não lê/edita/deleta/exporta
  NADA de B (ORM escopado, 0 linhas em update/delete cross-company; views 404;
  lista/painel só mostram a própria) + fail-closed sem escopo + numeração por
  empresa. `TenancyDeclarationTests` — **tabela sem decisão de tenancy = suíte
  vermelha** (lista GLOBAL declarada vs. company+manager escopado; eventos
  pghistory isentos até a T4).

**Runbook do dono (local):** backup lógico se quiser (é o banco local) →
`python manage.py migrate` (0011→0012→0013 + tenancy/0002 da logo, se pendente)
→ `python manage.py test chips estoque tenancy --settings=core.settings_test` →
smoke: logar com o operador da Brasil Reciclagem e conferir que o lote da eMiner
SUMIU (e vice-versa). **Produção:** backup fresco (Render Export, obrigatório —
§2.1b.c) → push em `main` (o build roda o migrate; a 0012 cria a eMiner e
backfilla) → `bootstrap_tenancy --company eMiner ... --commit` (papéis reais;
nome EXATO "eMiner") → `guard_catalog`.

**Próximo:** T4 (RLS — Camada B: policies + FORCE + SET LOCAL no middleware,
lembrando a correção do §6.2: o atomic externo é do TenancyMiddleware) e
T5/T6 (fila no app + onboarding) antes do 2º cliente REAL logar.

### T4 — construída em 2026-07-06 (mesma sessão; suíte 231/231 verde)

**Camada B: nem query bugada cruza empresa — o Postgres filtra sozinho.**

- **Migração `estoque/0014_t4_rls`** (RunPython Postgres-only, reversível):
  `ENABLE` + **`FORCE`** ROW LEVEL SECURITY + policy `tenant_isolation` nas 4
  tabelas. Policy: `company_id = NULLIF(current_setting('app.company_id',
  true), '')::int OR current_setting('app.platform', true) = '1'`. GUC ausente
  → NULL → **zero linhas** (fail-closed no banco). `app.platform='1'` é o
  caminho da PLATAFORMA (superuser/Django admin enxerga tudo — §8); resolve a
  armadilha "FORCE também filtra o dono da tabela".
- **`TenancyMiddleware`** agora abre o **`transaction.atomic()` externo** da
  request (a correção §6.2 — `ATOMIC_REQUESTS` não serviria) e emite os GUCs
  **transaction-local** (`set_config(..., local=True)` ≡ `SET LOCAL`,
  PgBouncer-safe): `app.company_id` do vínculo + `app.platform` p/ superuser.
  Anônimo → nenhum GUC → RLS devolve zero linhas de estoque. No SQLite dos
  testes: sem atomic, sem GUC (não há RLS lá; a Camada A cobre).
- **`company_scope()` e `scope_command_to_company()`** também setam o GUC
  (sessão, com restauração) — comandos, shell e testes sob Postgres continuam
  funcionando; o `bootstrap_tenancy` (seed) e o teste de corrida foram
  escopados. ⚠ Consequência desejada: **`manage.py shell` ad-hoc em tabela de
  estoque devolve 0 linhas** até você entrar num `company_scope(...)` — é o
  fail-closed da Camada B funcionando, não um bug.
- **`RLSHandshakeTests`** (Postgres-only; skip no SQLite): por **SQL cru** —
  sem GUC → 0 linhas; GUC da A → só linhas da A (WHERE pela B devolve 0);
  INSERT cross-company viola o WITH CHECK; GUC de plataforma → vê as duas.
- **Pendência declarada:** tabelas de EVENTO pghistory de estoque não existem
  (estoque não é rastreado) — se um dia forem rastreadas, as policies entram
  junto (armadilha §6.2.3 continua mapeada). BYPASSRLS não foi necessário:
  data-migration futura usa `app.platform` ou `company_scope`.

**Runbook do dono (T4):** local → `python manage.py migrate` (0014 liga o RLS)
→ `python manage.py test estoque.tests.RLSHandshakeTests` (prova Camada B) →
re-rodar `estoque.tests.LotNumberRaceTests` (corrida sob RLS) → smoke com as
duas empresas + Django admin (superuser vê tudo). Produção: mesma coisa via
push (build migra); backup antes, `guard_catalog` depois.

### T1.1 — polimentos pós-validação (2026-07-06, suíte 224/224 verde)

- **`/painel/` — home pós-login (lançadeira, decisão de UX):** responde "o que
  eu faço agora?" sem virar dashboard-enfeite. Hero = o lote ABERTO com CTA único
  "Continuar triagem →" (1 clique até a bancada); sem lote aberto, empty-state por
  papel (gerente: "Abrir um lote"; operador: "peça ao gerente"); linha de missão
  (ler chip → digitar PN → lançar no lote); stats do dia discretos (lotes abertos,
  tipos lançados hoje, fila, reprovados hoje); atalhos secundários.
  `LOGIN_REDIRECT_URL='/painel/'`; link "Painel" no header. `estoque/views.py::painel`
  + `estoque/templates/estoque/painel.html` + `PainelTests`.
- **Logout consertado (bug pré-existente):** Django 5 removeu o GET do
  `LogoutView` — o link "Sair" devolvia 405/página em branco. Virou form POST;
  redireciona ao `/` (LOGOUT_REDIRECT_URL).
- **Admin — filial filtrada pela empresa:** widget `BranchSelect` (option com
  `data-company`) + `tenancy/static/tenancy/membership_branch_filter.js` no
  MembershipAdmin. UX apenas — a barreira é o `clean()` do modelo.
- **`Company.logo`** (ImageField `company_logos/`, migração `tenancy/0002`, prévia
  no admin) para o branding futuro (§10). ⚠ Filesystem do Render é efêmero:
  logo em prod exige disco persistente/S3.
- **URL por empresa:** mantida a decisão §10 — v1 SEM tenant na URL (a sessão
  define a empresa; slug/subdomínio é branding futuro, não isolamento).
