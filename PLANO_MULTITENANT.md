# PLANO_MULTITENANT.md — WhatTheChip multi-empresa (documento de projeto)

> **Status: T1 + T2 + T3 + T4 CONSTRUÍDAS (2026-07-06, sessão dedicada).**
> T1–T3 validadas no local do dono (O3 no Postgres; migrate + backfill feitos;
> handshake Camada A verde). **T4 (RLS) construída em seguida** — suíte 231/231;
> falta o dono rodar `migrate` (0014 liga o RLS) + `RLSHandshakeTests` no
> Postgres, e o deploy em produção. Restam T5 (fila no app) e T6 (onboarding)
> antes do 2º cliente real logar — e a **T7 (subdomínio por cliente, §10)**,
> planejada em 2026-08-05 agora que o domínio próprio está no ar.
> **Revisão 2026-08-06 (dono), fechada em duas decisões no mesmo dia:**
> (1ª) a T7 é SÓ branding — o nome do cliente na URL, nada além (a arquitetura
> por-tenant pesada já foi descartada no §4: banco único row-level É a via
> escalável p/ dezenas/centenas de clientes); a revisão de código pré-T7 achou
> lacunas novas — **B5–B7** no §10.4 e **pré-condições** no §10.6.
> (2ª) **T5 DESCARTADA** — a fila PendingEntry segue no Django admin
> (plataforma revisa; reavaliar só se virar gargalo). Caminho fechado:
> **T6 → T7**, com roadmap executável completo no **§17** (E0 saneamento →
> E1/T6 onboarding → E2/T7 código → E3 deploy+DNS → E4 logo opcional).
> **Meta: os 2 clientes atuais de produção com subdomínio no ar.**
> **Ver §16 (diário de execução).**
>
> **▶ Sessão de 2026-08-05 — LER §10 INTEIRA ANTES DE TOCAR NA T7.** Três coisas
> mudaram de fora pra dentro: (a) `whatthechip.app` entrou em produção (§10.1);
> (b) a busca PÚBLICA acabou por decisão de negócio e os endpoints de consulta
> viraram plataforma-only — código já no disco, **suíte ainda não rodada**, com
> um teste do `pricing` que agora passa VACUAMENTE (§10.7); (c) o dono decidiu
> explicitamente que o subdomínio **não** precisa impedir ninguém de chegar ao
> apex — não gastar esforço nisso (§10, "NÃO-OBJETIVO").
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
- **O que é compartilhado (o produto):** o catálogo global de classificação. É o
  ativo central e o **efeito de rede**: toda busca de toda empresa-cliente
  exercita (e potencialmente alimenta) o mesmo cérebro. Melhorou para um,
  melhorou para todos.
  **⚠ Revisão de 2026-08-05 (dono): "não somos mais o Google dos chips".** A
  busca PÚBLICA acabou — visitante anônimo, comprador e usuário sem empresa não
  consultam PN nenhum (§10.7). O efeito de rede continua, mas roda **dentro** da
  plataforma: a vitrine aberta estava dando o ativo de graça, não gerando
  aquisição. Onde este documento ainda disser "Google dos chips" em outro
  parágrafo, vale esta revisão.
- **A fronteira comercial absoluta:** a empresa A JAMAIS vê lote, estoque, envio,
  comprador ou preço da empresa B. Recicladoras são concorrentes entre si — um
  vazamento de estoque/preço entre elas mata a confiança no produto.

**Fora do escopo deste projeto (non-goals explícitos):** cobrança/billing/planos
de assinatura; ~~subdomínio/branding por cliente~~ (**saiu dos non-goals em
2026-08-05: virou a T7, §10 — depois de T5/T6**); o sistema de
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

## 10. Rotas e domínio — e a T7 (subdomínio por cliente)

**Hoje (V1, no ar): SEM tenant na URL.** App 100% atrás de login → a SESSÃO
define a empresa (Membership). Zero DNS, zero middleware de host, zero risco
novo. **Subdomínio é branding, não isolamento — o RLS não depende dele.** Isto
continua verdade DEPOIS da T7: ela não move a fronteira de segurança, só põe um
nome bonito na frente dela.

**Para que serve a T7, então (dono, 2026-08-05):** o operador da empresa-cliente
trabalha o dia inteiro em `cliente.whatthechip.app` e **não é exposto à landing
comercial** do `whatthechip.app` — que é material de venda da plataforma, não do
cliente. É higiene comercial e branding. Nada além disso.

**⚠ NÃO-OBJETIVO, decidido explicitamente (dono, 2026-08-05), para evitar
sobre-engenharia:** *"não tem problema o operador apagar o nome do cliente e
chegar no site principal."* O subdomínio **não é** e **não deve tentar ser**
barreira de acesso ao apex. Quem digitar `whatthechip.app` chega — e está tudo
bem. O que protege o ativo é o portão de consulta (§10.7), **não** o hostname.
Qualquer esforço na T7 para "esconder" ou "bloquear" o apex é escopo indevido.

Slugs/rotas públicas **em inglês** (decisão do dono, já no `PRECIFICACAO.md`).

### 10.1 Pré-requisito CUMPRIDO: domínio próprio (2026-08-05)

`https://whatthechip.app` está em produção — apex canônico, `www` redireciona,
cert emitido. Registrado na Hostinger com a zona DNS lá, servido pelo serviço
`whatthechip` da Render. Era este o bloqueio real: `*.onrender.com` **nunca**
daria sub-subdomínio (`mundometal.whatthechip.onrender.com` não existe como
coisa configurável — a Render entrega um único rótulo e o DNS de `onrender.com`
não é seu). Registros e decisões de settings: memória `wtc-dominio-whatthechip-app`.

### 10.2 A regra inegociável: o host AFIRMA, o Membership CONCEDE

`request.company` **jamais** pode passar a sair do hostname. Hoje ela tem fonte
única (o Membership resolvido pelo `TenancyMiddleware`, §6.1); ler a empresa do
host criaria um SEGUNDO input para a mesma pergunta — e esse é digitável por
qualquer um na barra de endereço. O host entra só como AFIRMAÇÃO a conferir:

    host → empresa X  +  Membership do usuário = X   → segue
    host → empresa X  +  Membership do usuário = Y   → 403 (ou redirect pro
                                                        subdomínio de Y)
    host → nenhuma empresa                           → host canônico

Nunca "trocar de empresa" por causa do host. "Nenhuma empresa" inclui slug
inexistente, slug reservado (B3) **e empresa `active=False`** — todos caem no
canônico do mesmo jeito, sem revelar se a empresa existe. Este handshake vira
**teste permanente** na suíte (§12): host da empresa A + sessão de B = 403.

### 10.3 Configuração-alvo (Render + DNS) e custo

Cota Hobby = **2 domínios inclusos**, US$ 0,25/mês por extra. (O *workspace*
Hobby em si custa US$ 0 — os ~US$ 17/mês do `CLAUDE.md` são instância web +
Postgres. Domínio não mexe nessa conta.) A config final fecha exatamente em 2:

| # | Domínio na Render | Cobre |
|---|---|---|
| 1 | `whatthechip.app` | apex — site público + host canônico do app |
| 2 | `*.whatthechip.app` | `www`, `eminer`, `mundometal`, … todos |

A entrada avulsa do `www` **sai** quando a wildcard entrar — a wildcard absorve.
Wildcard exige 3 CNAMEs na zona: `*`, `_acme-challenge` (emissão/renovação do
certificado) e `_cf-custom-hostname` (validação do anti-DDoS). A Render exige
que o apex também aponte pra ela. **Custo adicional da T7: zero.**

⚠ **Não criar o `*` no DNS antes do middleware existir:** wildcard ativa sem
resolução de host faz QUALQUER subdomínio inventado servir o app inteiro.

### 10.4 Bloqueadores que a T7 tem que resolver (B1–B4: 2026-08-05 · B5–B7: revisão de código de 2026-08-06)

| # | Bloqueador | Por quê |
|---|---|---|
| **B1** | Site público (`/`, `/<slug>/`) não deve responder em host de tenant | **REDUZIDO em 2026-08-05:** a parte de sigilo foi resolvida na ORIGEM (§10.7 — os endpoints de consulta viraram plataforma-only), então B1 deixou de ser bloqueador de segurança. Sobra: conteúdo duplicado no Google e o cliente esbarrar na landing comercial. Fix: URLconf por host. ⚠ **Continua aberto:** as páginas `/fab-*/` (CMS público) — o `doc_url` do decode aponta pra elas e **ninguém auditou** quanta convenção de decode elas expõem. Auditar ANTES de decidir se ficam públicas |
| **B2** | `/partner/` fica no host canônico | Comprador não tem Membership (o vínculo é `Buyer.users`) e o comprador de PLATAFORMA é cross-empresa por desenho — não existe "subdomínio dele" |
| **B3** | Slugs reservados + validação | `Company.slug` é `SlugField` unique, mas **não** tem lista de reservados hoje: `www`, `admin`, `app`, `api`, `partner`, `static`, `media`, `mail` |
| **B4** | `Company.logo` em disco persistente ou S3 | FS da Render é efêmero. Se o subdomínio existe pra branding, o logo sumir no próximo deploy é falha visível pro cliente. **Ver B7: disco persistente sozinho NÃO resolve** |
| **B5** | Cookies de sessão/CSRF viram domain-wide: `SESSION_COOKIE_DOMAIN` e `CSRF_COOKIE_DOMAIN` = `.whatthechip.app` (+ `ALLOWED_HOSTS` com `.whatthechip.app` e `CSRF_TRUSTED_ORIGINS` com `https://*.whatthechip.app`) | **Achado 2026-08-06:** hoje não existe NENHUM `*_COOKIE_DOMAIN` no settings — o cookie é host-only, então o "login no apex → redirect pro subdomínio" (§10.6) chegaria **DESLOGADO**. Compartilhar a sessão entre os hosts é seguro AQUI porque o host só AFIRMA (§10.2): a empresa continua vindo do Membership, e host≠vínculo = 403. O teste do §12.6 ganha o caso "loga no apex → segue logado no subdomínio" |
| **B6** | Redirect `www`→apex troca de dono | Hoje quem redireciona é a **Render** (o `www` é domínio avulso na cota). Quando a wildcard absorver o `www` (§10.3), esse redirect **desaparece junto** — vira responsabilidade do `HostTenantMiddleware`: `www` entra nos slugs reservados (B3) com **301 pro apex**. Esquecer = `www.whatthechip.app` servindo o app como se fosse tenant |
| **B7** | `/media/` NÃO é servido em produção (agrava o B4) | O helper `static(settings.MEDIA_URL…)` do `core/urls.py` devolve lista **VAZIA** com `DEBUG=False` — mesmo com disco persistente o logo não seria entregue por URL nenhuma. Logo em prod = storage backend de verdade (S3/`django-storages` ou equivalente servindo a URL), não só disco |

### 10.5 Por que NÃO o path `/t/<company-slug>/`

Era a alternativa "sem DNS" do plano original. Neste código ela é **mais** cara,
não menos: varredura em 2026-08-05 achou **zero** acoplamento a host no projeto
— nenhum `request.get_host()`, `build_absolute_uri`, `django.contrib.sites`, e
nenhum e-mail/PDF com link absoluto. (Re-varrido em 2026-08-06 incluindo
`SITE_ID` e `*_COOKIE_DOMAIN`: segue zero.) Host é, portanto, aditivo puro. Path, ao
contrário, toca todo `urls.py`, todo `{% url %}` e todo redirect. **Descartada.**

### 10.6 Custo de construção e ORDEM

O `Company.slug` já existe (nasceu na T1 com `help_text` "para rotas/domínio
futuros"). Com B1–B4 fechados, a T7 em si é ~meio dia: `HostTenantMiddleware`,
`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` com wildcard, login no apex que
redireciona pro subdomínio do usuário, e o teste de handshake host×Membership.

**A T7 vem DEPOIS da T6, não antes** (T5 foi DESCARTADA em 2026-08-06 — §11).
A T6 constrói o fluxo de criar empresa; a T7 acrescenta um passo a esse mesmo
fluxo (escolher/validar o slug que vira hostname público e quase permanente).
Inverter a ordem = construir o onboarding duas vezes. **Roteiro executável
completo: §17.**

**Pré-condições de ABERTURA da T7 (registradas 2026-08-06):** (a) as pendências
1–2 do §10.7 fechadas — suíte rodada de verdade pós fim-da-busca-pública e o
teste vácuo do `pricing` re-especificado (o aceite da T7 é suíte verde; não se
abre fase partindo de suíte em estado desconhecido); (b) escopo com **B1–B7**
na conta: o "~meio dia" acima é só o miolo (middleware + settings + handshake)
— com os bloqueadores, planejar **1–2 sessões dedicadas** (fases E2+E3 do §17).

### 10.7 Estado em 2026-08-05 — fim da busca pública (HANDOFF)

Sessão de 2026-08-05, na esteira do domínio próprio. Ler isto antes de tocar na
T7: parte do que a T7 ia resolver **já foi resolvido em outro lugar**.

**Decisão de negócio (dono):** acabou a busca pública. *"Não somos mais o Google
dos chips. Pessoas anônimas, usuários públicos, sem acesso a uma empresa e sem
cadastro no site não devem ser capazes de pesquisar nada."*

**O achado que motivou:** `/chips/search/` e `/chips/decode/` **não tinham gate
nenhum** — nem `login_required`. Devolviam o `classify()` inteiro (subtype,
densidade, capacidade, fonte, confiança e o veredito RENTÁVEL) para a internet
aberta. Provado ao vivo em produção:
`GET https://whatthechip.app/chips/search/?pn=K4B4G16E` → classificação
completa, sem login. Era o furo lateral da própria máscara v3.1.

**FEITO (código no disco do dono, `chips/views.py`, 306 linhas):** decorator
`platform_only(as_json=...)` nos dois endpoints, critério
`tenancy.access.is_unmasked` — a MESMA fonte única de bancada/tabela/export/OV.
Anônimo, comprador, operador, gerente e admin de empresa → **403**. Superuser
inalterado. `search_api` responde JSON 403; `decode_html` responde 403 com um
`<span>` curto (HTMX não faz swap em 4xx → o alvo fica intacto em vez de exibir
card meio-vazio parecendo bug).

> **⚠ Por que `is_unmasked` e não `role_required('operator')` — não afrouxar:**
> gate de PAPEL barraria só o anônimo; o operador da empresa-CLIENTE passaria e
> receberia por URL exatamente o que a v3.1 esconde da tela dele. Se um dia
> alguém "abrir pro operador poder consultar", é **regressão da F12**.
> Ninguém que trabalha perde nada: a bancada usa `estoque:preview`
> (`preview_chip`), que já mascara. Os dois endpoints eram órfãos da home antiga
> — as únicas refs a `/chips/` em template são `/chips/submit/` e `/chips/report/`.

**NÃO FEITO — pendências herdadas por quem pegar isto:**

1. **Suíte não rodou** (a ponte com a máquina do dono caiu na hora). Rodar
   `test chips estoque tenancy pricing vendas --settings=core.settings_test`.
2. **`pricing/tests.py::test_decode_card_nao_carrega_preco_nem_para_admin` fica
   VERDE MENTINDO** — é a pendência mais perigosa. Ele itera
   admin/manager/operator/None batendo em `/chips/decode/`; os quatro agora
   recebem 403 e o `assertNotIn(preço)` passa **vacuamente**. O teste continua
   verde e para de testar o que foi escrito para testar. **Re-especificar, não
   "consertar".**
3. `chips/tests_i18n.py:148` bate anônimo em `/chips/decode/` → fica vermelho
   (falha honesta). Logar superuser.
4. `scripts/test_ui.py` usa `RequestFactory` (request sem `.user` → 403). É
   script de dev, não entra na suíte.
5. `chips/management/commands/sync_index_page.py:61` tem copy de CMS afirmando
   que a home usa a API `/chips/search/` — texto obsoleto no site.
6. **Teste novo pronto para colar** em `chips/tests.py`: `ConsultaEhPlataformaTests`
   (auto-contido, sem fixture do projeto) — cobre 403 para anônimo, 403 para
   logado-não-plataforma, corpo do 403 sem vazar veredito/specs/marca, e
   plataforma continuando a consultar. Foi entregue ao dono no chat da sessão.
7. **Consequência de produto:** a finder bar da home no redesenho de frontend
   (fatia 1, ainda local, não deployada) perde o backend anônimo — tem que
   virar prompt de login antes de ir pro ar.

**Deixados abertos DE PROPÓSITO:** `/chips/stats/` (só contagens agregadas — é
número de marketing, não decode), `/chips/submit/` (é ENTRADA: visitante manda
PN não catalogado + foto, não devolve nada — funil, não vazamento) e
`/chips/report/` (só grava `CorrectionRequest`; o link vive dentro do
decode_card, que agora é plataforma-only).

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
| **T5** | ~~UI de gerente no app: fila PendingEntry (aprovar/reprovar) no app — esvazia o Django admin de operação de empresa~~ | — | **DESCARTADA (dono, 2026-08-06):** a fila segue no Django admin e a PLATAFORMA revisa a fila de todos os clientes (abrir/fechar/exportar lote já está no app desde a T1). Reavaliar só se virar gargalo com mais clientes |
| **T6** | Onboarding: tela/fluxo de plataforma "criar empresa + primeiro admin (+ filiais)"; roteiro documentado. **Absorve o B3** (validador DNS do slug + reservados) | O5: empresa de teste criada em < 5 min sem tocar código | **PRÓXIMA — fase E1 do §17** |
| **T7** | Subdomínio por cliente (§10): bloqueadores B1–B7 + `HostTenantMiddleware` (**host afirma / Membership concede**) + wildcard `*.whatthechip.app` na Render e no DNS + login no apex com redirect (exige B5) | handshake NOVO na suíte: host da empresa A + sessão de B → 403; host desconhecido → canônico; login no apex segue logado no subdomínio (B5); nenhum lugar lê o host como FONTE de empresa; suíte verde | **depois da T6** — fases E2+E3 do §17 |

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
6. **Handshake de HOST (T7 — §10.2):** com o subdomínio ligado, provar que o
   host é AFIRMAÇÃO e não CONCESSÃO. Usuário com Membership na empresa B
   acessando o host da empresa A recebe **403** (nunca 200 com dados de A, nunca
   200 com dados de B "trocando de empresa"); host desconhecido cai no canônico;
   e nenhuma view lê a empresa do hostname. Com o B5, entra junto o caso "loga
   no apex → segue LOGADO no subdomínio" (cookie em `.whatthechip.app`) e o
   301 do `www` (B6). No Django, `Client` fala com
   `testserver` por padrão — estes casos precisam de `HTTP_HOST=` explícito +
   `override_settings(ALLOWED_HOSTS=...)`. Sem este teste a T7 não entra.

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
- **Armadilha §6.2.1 CONFIRMADA na prática (2026-07-06):** o dev local conecta
  como role **SUPERUSER** (usuário da máquina) → RLS é bypassado por completo,
  até com FORCE — o 1º run do handshake achou 2 linhas sem GUC. O
  `RLSHandshakeTests` agora detecta `rolsuper` e troca para um role de
  sondagem sem-super (membro do role original) durante as asserções, então a
  prova vale mesmo no dev. Consequências: em DEV a proteção efetiva é a
  Camada A (manager fail-closed) — o RLS local só "morde" se você criar um
  role não-super para a app; em PROD (Render) o role da app NÃO é superuser
  e o RLS vale integralmente. A regra do plano segue: a app nunca deve
  conectar como super.

### Correção pós-produção (2026-07-09): default manager NÃO pode ser fail-closed

Bug real em prod (`/admin/pricing/buyer/add/` → `CompanyScopeMissing`): o
Django 5 valida `UniqueConstraint` de formulário via **`_default_manager`** —
que era o `CompanyScopedManager`. Plataforma sem Membership (ou editando dado
de outra empresa) explodia em QUALQUER admin de modelo tenant-scoped.
**Convenção corrigida (é o padrão da doc do Django: default manager não
filtra):** `objects` = escopado fail-closed (o caminho EXPLÍCITO das views),
`Meta.default_manager_name = 'all_companies'` (validação/admin/dumpdata), e
os `get_object_or_404` passam o manager explícito (`Lot.objects`). O
`TenancyDeclarationTests` agora EXIGE o trio completo em modelo novo; 
`PlatformAdminFormTests` é a regressão (Lot e Buyer via admin sem escopo).

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

### E0 — Saneamento (2026-08-06/07; parte do agente FEITA — roadmap §17.1)

**Suíte reproduzida no sandbox** (repo espelhado, py3.11 + requirements-render;
run local do dono continua sendo a fonte da verdade). Estado ANTES: 433 testes,
**4 FAIL + 1 ERROR**. O que cada um era e o que foi feito:

1. **`check_translations` ERROR** — «Consulta restrita.» (as 2 marcações do
   `platform_only`, chips/views.py:72/77) faltava nos 3 catálogos. Adicionada e
   traduzida (es «Consulta restringida.» · en «Restricted query.» · zh-hans
   «查询受限。»), `.mo` recompilados (554 entradas cada) — portão verde.
2. **`tests_i18n::test_decode_card_renderiza_em_zh`** (§10.7.3) — anônimo agora
   leva 403; o smoke passou a logar SUPERUSER (única conta que renderiza o card).
3. **`pricing::test_decode_card_nao_carrega_preco_nem_para_admin`** (§10.7.2) —
   o redesenho (e47f496) esperava 200 e falhava 403≠200. RE-ESPECIFICADO nas
   duas pernas: superuser 200 SEM preço/comprador no parcial (o ponto original
   segue vivo) + papéis de empresa/anônimo 403 sem vazamento no corpo.
4. **`pricing::test_search_api_json_so_tem_prices_para_admin`** — idem:
   /chips/search/ é plataforma-only; todo papel de empresa e o anônimo → 403,
   sem chave `prices`, sem valor/spec vazando. O caminho feliz (superuser COM
   prices + 2 moedas F10) já vivia no teste vizinho
   `test_superuser_plataforma_ve_prices_no_json`.
5. **`GoldenObrigatorioTests`** — o par x8 da ESMT (`M15T2G8256A`,
   `M15T4G8512A`, 2ª rodada de 2026-08-05) estava no yaml SEM âncora. Goldens
   adicionados conforme ESMT.md §3.2 (família magra → DDR3L sem densidade →
   INDETERMINADO). ⚠ Não era do escopo §10.7 — pendência herdada do chat ESMT.

Mais o **`ConsultaEhPlataformaTests`** (o cadeado permanente do §10.7.6) colado
em `chips/tests.py`: 403 p/ anônimo E p/ todo papel de empresa nos 2 endpoints,
corpo do 403 sem vazar spec/veredito/marca, plataforma seguindo com 200.

**Estado DEPOIS: 437 testes, OK (6 skips Postgres-only).** No disco do dono:
`chips/tests.py` · `chips/tests_i18n.py` · `pricing/tests.py` ·
`locale/{es,en,zh_Hans}/LC_MESSAGES/django.{po,mo}`.

**⚠ ACHADO CRÍTICO (2026-08-07 ~00h30 Caracas):** o portão **NÃO está em
produção** — `GET https://whatthechip.app/chips/search/?pn=K4B4G16E` ainda
devolve o `classify()` inteiro (chip_type, dram_density, `profitable`
= RENTÁVEL…) pra internet aberta. O código de 2026-08-05 ficou só no disco.
**O furo lateral da máscara v3.1 segue aberto até o próximo push.**

**Runbook do DONO (fecha a E0; o push é o que FECHA O FURO):**

```bash
git status   # conferir o que está pendente (deve incluir chips/views.py da sessão 2026-08-05!)
python manage.py test chips estoque tenancy pricing vendas --settings=core.settings_test   # fonte da verdade
python manage.py characterize_baseline --out baseline_pre_t6.json   # baseline das fases E (guardar; NÃO commitar)
git add chips/views.py chips/tests.py chips/tests_i18n.py pricing/tests.py locale PLANO_MULTITENANT.md
git commit -m "E0: consulta plataforma-only (fecha o furo em prod) + testes re-especificados + i18n + golden ESMT x8"
git push origin main   # deploy automático na Render
# pós-deploy:
#   navegador: whatthechip.app/chips/search/?pn=K4B4G16E → deve dar 403 «Consulta restrita.»
python manage.py guard_catalog   # com DATABASE_URL do Render (tripwire, como sempre)
```

Aceite da E0 = suíte local verde + baseline gerado + **403 confirmado em prod**
+ guard_catalog estável. Aí a E1 (T6, onboarding) pode abrir.

**✅ E0 FECHADA em 2026-08-07 (~01h Caracas).** Dono rodou o runbook: suíte
LOCAL **437 OK** (fonte da verdade, bateu com o sandbox) + `baseline_pre_t6.json`
gravado (**7.843 PNs**; guardar, não commitar) + commit cirúrgico + push. O
agente verificou em produção PÓS-deploy: `/chips/search/` e `/chips/decode/`
→ **403** (o furo está FECHADO) e a home segue no ar, intacta. Observação
registrada FORA do escopo E (trilha de qualidade de dados): avisos
pré-existentes «JSON inválido em ChipFamily.reasoning» no test run e no
characterize (M15T*, SDIN, SDAD, SDINB, SD5DH, H9DP, PMG6, 08/16EMCP…) — o
campo é texto livre do yaml e algum leitor tenta `json.loads`; não bloqueia
nada (suíte verde, baseline gravado), investigar em sessão própria.
**→ PRÓXIMA SESSÃO: E1 (T6 — onboarding, §17.2).** Levar fechada a decisão
§17.5.1 (slugs dos 2 clientes).

### E1 — T6, onboarding de empresa (2026-08-07; código PRONTO — §17.2)

**Decisão §17.5.1 fechada pelo dono na abertura:** slugs **`eminer` +
`erecyclo`** (a 2ª empresa está em prod com o nome errado "Mundo Metal" →
renomear para **eRecyclo**). Grep no repo: único hardcode é fixture de teste
(`pricing/tests.py`, 'Mundo Metal T'/'mm-t' — não muda); `PRECIFICACAO.md`
menciona o caso (atualizar quando aquele doc for revisado).

**O que foi construído (suíte 449 OK no sandbox — 437 + 12 novos):**

- **B3 no MODELO** (`tenancy/models.py`): `validate_company_slug` (rótulo DNS
  RFC 1123 — ⚠ o SlugField aceitava `_`/maiúscula, hostname não) +
  `RESERVED_COMPANY_SLUGS` congelada em CÓDIGO (infra/DNS + superfícies do
  produto, ~30 nomes) + portão no `Company.save()` (cobre shell/ORM; migração
  de dados usa modelo histórico → backfills antigos intactos). Migração
  **tenancy/0005** (AlterField state-only, zero mudança de dado).
- **`platform_required`** (`tenancy/access.py`): gate de plataforma (só
  superuser; anônimo → login, resto → 403) — irmão do `role_required` para
  superfícies que não pertencem a empresa nenhuma.
- **Fluxo `/company/new/`** (`tenancy/forms.py` + `views.py` + `urls.py`
  montado em `company/` — rota inglês, §14.5 — + template
  `tenancy/company_new.html` no shell do app): empresa + slug + filial
  opcional + 1º admin (senha provisória ≥8) numa TRANSAÇÃO; empresa nasce com
  contador 0 → 1º lote **#001**; confirmação mostra o endereço futuro
  `<slug>.whatthechip.app`; sem PRG de propósito (F5 re-post morre nos
  uniques, nada duplica); unicidade `iexact` em nome/slug/usuário (evita
  gêmeos por caixa: "ERecyclo" × "erecyclo").
- **i18n na MESMA entrega** (MULTILANGUAGE §7): 25 msgids novos marcados E
  traduzidos (es/en/zh-hans) → catálogos com 579 entradas,
  `check_translations` verde.
- **12 testes novos** (`tenancy/tests.py`): validador (formato × reservados ×
  a própria lista reservada é DNS-válida × portão no save × os slugs REAIS da
  §17.5.1), gate (anônimo→login; admin de EMPRESA→403), e2e O5 (cria tudo num
  POST e o admin novo já navega o /painel/), opcionais, duplicatas e senha
  curta não criam NADA.

**Runbook do DONO (fecha a E1):**

```bash
python manage.py migrate tenancy      # 0005 — validador no slug (state-only)
python manage.py test chips estoque tenancy pricing vendas --settings=core.settings_test
python manage.py characterize_baseline --diff baseline_pre_t6.json   # esperado: diff 0
# RENAME da 2ª empresa em PROD (admin → Tenancy → Empresas → "Mundo Metal"):
#   nome → eRecyclo · slug → erecyclo   (pghistory audita a mudança)
# SMOKE O5 (runserver local): logar superuser → /company/new/ → criar empresa
#   de teste em < 5 min → abrir lote e conferir #001 → desativar no admin
git add tenancy core/urls.py locale PLANO_MULTITENANT.md
git commit -m "E1/T6: onboarding de empresa (plataforma) + B3 validador DNS de slug + i18n"
git push origin main
python manage.py guard_catalog        # DATABASE_URL do Render, como sempre
```

Aceite = suíte local verde + diff 0 + O5 provado + rename feito + guard OK.
Depois disso: **E2 (T7 — código do subdomínio, §17.3)**.
**✅ Runbook cumprido pelo dono em 2026-08-07 ("tudo já tá em produção") —
E1 FECHADA; commit 63c58cd em prod.** (No meio: incidente da ponte gravando
página de erro HTML nos 16 arquivos — restaurados e verificados por md5;
lição registrada na memória `wtc-verificar-commit-checksum`.)

### E2 — T7, o código do subdomínio (2026-08-07; código PRONTO — §17.3)

**Construído (suíte 462 OK = 449 + 13 do HostHandshake; ZERO string nova de
usuário → sem rodada i18n nesta fase):**

- **Settings B5 env-driven** (`core/settings.py`): `WTC_TENANT_DOMAIN` liga o
  modo multi-host — `.domínio` no ALLOWED_HOSTS, `https://*.domínio` no
  CSRF_TRUSTED_ORIGINS, cookies de sessão/CSRF domain-wide (só fora de
  DEBUG). **Sem a env var o deploy é INERTE.** Smoke local:
  `WTC_TENANT_DOMAIN=localhost` no `.env` (Chrome resolve `eminer.localhost`
  → 127.0.0.1 sozinho).
- **`HostTenantMiddleware`** (tenancy/middleware.py, DEPOIS do Tenancy): o
  host AFIRMA, o Membership CONCEDE (§10.2). `www` → **301** apex (B6);
  slug desconhecido/reservado/empresa inativa/rótulo com ponto → **302**
  canônico INDISTINTO (não revela se a empresa existe); host de tenant
  válido → `request.urlconf = core.urls_tenant` + `request.tenant_host_company`
  (afirmação p/ branding — NUNCA escopo); vínculo ≠ host → **403**; anônimo
  segue (cai no login DO host — bookmark do operador); superuser passa
  (§17.5.3) com o escopo do PRÓPRIO vínculo intacto.
- **`core/urls_tenant.py`** (B1/B2): só o APP — chips/estoque/painel/vendas/
  login/logout/i18n, nomes idênticos ao core/urls (levantei os nomes que os
  templates do shell resolvem; reverse() usa a URLconf da request). `/` →
  painel; fallback `.*` → 302 canônico. Site público/CMS, `/partner/`,
  `/admin/` e `/company/` só no canônico.
- **`TenantAwareLoginView`** (item 4 do §17.3): login no APEX → redirect pro
  subdomínio do vínculo. ⚠ o Membership é resolvido DENTRO da view
  (pós-login) — o TenancyMiddleware rodou com o usuário ainda anônimo. Login
  no host do tenant fica no host (redirect relativo); `next` mantém a
  validação padrão do Django.
- **`HostHandshakeTests`** (13 casos — o teste permanente do §12.6): B no
  host de A → 403 (painel E estoque); avulso logado → 403; anônimo → login
  do host; superuser passa SEM trocar escopo (asserção `request.company` =
  vínculo, `tenant_host_company` = afirmação); host nunca é fonte; www 301
  preservando caminho+query; desconhecido/reservado/inativo/sub-sub → 302
  indistinto; raiz de tenant → painel; CMS//partner//admin//company em
  tenant → 302 canônico; canônico e testserver intactos; middleware INERTE
  sem env var; login no apex → 302 pro subdomínio E segue LOGADO.

**Auditoria `/fab-*/` (pendência do B1) — resultado no §17.5.2.** Decisões
§17.5.3 e §17.5.5 aplicadas conforme recomendação (dono pode vetar antes da
E3 — mudar é 1 linha no middleware/urls_tenant).

**Runbook do dono = a PRÓPRIA E3 (§17.4, já atualizado com o passo da env
var).** O push desta fase pode ir a qualquer momento: sem `WTC_TENANT_DOMAIN`
na Render, produção não muda NADA.

---

## 17. Roadmap de execução — da fundação ao subdomínio dos 2 clientes (dossiê 2026-08-06)

> Pedido do dono: *"plano para fazermos este trabalho completo, desde a
> fundação até eu ter o subdomínio de cada cliente atual de produção — que são
> só 2."* T5 DESCARTADA na mesma decisão. Cada fase termina com **prova verde**
> antes da próxima (convenção de testes do projeto). Regra de ouro #1 vale em
> todas: o agente **edita arquivos**; o **DONO roda** migrate/`--commit`/
> deploy/DNS. Backup fresco (Render Export) antes de toda operação de prod.

### 17.0 Premissas e estado de partida

- **T1–T4 no ar em produção** (RLS ativo — confirmado na prática pelo
  incidente RunPython de 2026-08-01). **2 empresas reais** em prod; slugs a
  confirmar na E1 (viram hostname quase-permanente — decisão §17.5.1).
- **T5 descartada (dono, 2026-08-06):** fila PendingEntry continua no Django
  admin — a plataforma revisa a fila de TODOS os clientes. Consequência aceita
  conscientemente; reavaliar se virar gargalo. Abrir/fechar/exportar lote já
  está no app com gate de papel (T1).
- **T7 = branding puro** (§10): hostname NUNCA decide segurança (§10.2); o
  apex continua alcançável (NÃO-OBJETIVO do §10 — zero esforço em "esconder").
- **Logo (B4+B7) FORA do caminho crítico** — vira E4 opcional: o header já
  mostra o NOME da empresa; subdomínio funciona sem logo.
- **Redesenho de frontend** (fatia 1 local, memórias
  `wtc-frontend-redesign-render`/`wtc-platform-redesign-phases`) é trilha
  SEPARADA — não misturar nas fases E.

### 17.1 E0 — Saneamento (sessão curta; pré-condição de tudo)

Fecha o §10.7 e confere a fundação antes de qualquer código novo:

1. Rodar a suíte COMPLETA: `python manage.py test chips estoque tenancy
   pricing vendas --settings=core.settings_test` — o código do
   fim-da-busca-pública está no disco **sem prova** desde 2026-08-05.
2. Colar `ConsultaEhPlataformaTests` (§10.7.6 — já entregue no chat daquela
   sessão); **re-especificar** o teste vácuo do pricing (§10.7.2); corrigir
   `chips/tests_i18n.py:148` (§10.7.3 — logar superuser).
3. `characterize_baseline --out baseline_pre_t6.json` — baseline ANTES das
   fases (nenhuma fase E toca o engine; diff esperado = **0 sempre**).
4. Conferir prod: `migrate` em dia + `guard_catalog` estável.

**Aceite:** suíte verde DE VERDADE + baseline gerado. Sem isso, nenhuma fase abre.

> **Status: ✅ E0 FECHADA em 2026-08-07 (§16-E0): suíte local 437 OK, baseline
> 7.843 PNs, push feito, 403 verificado ao vivo em prod — furo fechado.
> Próxima: E1 (§17.2).**

### 17.2 E1 — T6, o onboarding (1 sessão) — absorve o B3

Fluxo de PLATAFORMA no app (não no Django admin cru): **criar empresa +
primeiro admin em < 5 min sem tocar código** (O5).

- Tela/fluxo de plataforma (gate `is_superuser`): nome da empresa, **slug**,
  primeiro usuário admin (username/e-mail/senha provisória), filial opcional.
- **B3 entra AQUI (não na T7):** validador de slug com **formato DNS label**
  — `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$` — ⚠ o `SlugField` do Django
  **aceita `_`, hostname NÃO**; minúsculas, sem ponto. Mais a **lista de
  reservados congelada em código**: `www`, `admin`, `api`, `app`, `mail`,
  `static`, `media`, `partner`, `ftp`, `smtp`, `imap`, `ns1`, `ns2`,
  `status`, `dev`, `staging`, `test`. E **checagem dos slugs das empresas
  EXISTENTES** (ajustar agora, antes de virarem hostname).
- UI avisa: slug é quase-permanente (vira o endereço público do cliente).
- Roteiro de onboarding documentado (runbook: criar empresa → papéis →
  primeiro login → troca de senha).
- **Testes:** validador (formato + reservados + colisão), 403 p/
  não-plataforma, fluxo e2e (Company + Membership admin + contador de lote
  zerado), `TenancyDeclarationTests` segue verde.

**Aceite:** O5 provado com empresa de teste (criada e depois desativada);
suíte verde; `characterize --diff` = 0.

> **Status: código PRONTO (2026-08-07, §16-E1) — suíte 449 OK no sandbox
> (437 + 12 novos). Falta o runbook do dono: migrate 0005 + rename eRecyclo +
> smoke O5 + push + guard.**

### 17.3 E2 — T7, o código (1–2 sessões) — B1/B2/B5/B6 + middleware + testes

1. **Settings (B5):** `ALLOWED_HOSTS = ['.whatthechip.app', …]` (o ponto
   cobre apex + subdomínios) · `CSRF_TRUSTED_ORIGINS` += `https://*.whatthechip.app`
   · `SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = '.whatthechip.app'`
   **só em prod** (env-driven — em dev/localhost cookie domain quebraria o
   login local) · `.onrender.com` preservado como rota de fuga.
2. **`HostTenantMiddleware`** (depois do `TenancyMiddleware`): extrai o label
   do host. Canônico, `.onrender.com`, `localhost` → comportamento de hoje.
   `www` → **301 pro apex** (B6). Slug desconhecido, reservado ou empresa
   `active=False` → redirect pro canônico (sem revelar qual caso é — §10.2).
   Host de tenant: **AFIRMA** — bate com `request.company` (do Membership) →
   segue; não bate → **403**; anônimo → tela de login na própria URL do
   tenant (bookmark do operador funciona).
3. **URLconf por host (B1/B2):** host de tenant serve SÓ o app (login,
   painel, estoque, vendas, i18n, endpoints internos); site público/CMS
   (`/`, `/<slug>/`, `/fab-*/`) e `/partner/` SÓ no canônico — em host de
   tenant, redirect pro canônico (decisão §17.5.5). **Auditar `/fab-*/`**
   (pendência do B1) nesta mesma sessão.
4. **Login no apex → redirect pro subdomínio** do vínculo (conveniência
   pós-login; navegar logado no apex continua OK — NÃO-OBJETIVO §10).
5. **Plataforma em host de cliente:** implementar conforme §17.5.3.
6. **Testes (§12.6):** matriz com `HTTP_HOST=` + `override_settings` —
   A×B → 403 · anônimo em tenant → login · `www` → 301 · desconhecido →
   canônico · login no apex → segue LOGADO no subdomínio (B5) · nenhuma view
   lê o host como fonte de empresa · suíte inteira + `characterize --diff`=0.
7. Dev local: `.localhost` no `ALLOWED_HOSTS` de DEBUG (Chrome resolve
   `eminer.localhost` → 127.0.0.1) pro smoke manual sem mexer em /etc/hosts.

**Aceite:** suíte verde com o handshake de host; **deploy desta fase é
INERTE** — nada muda pra quem usa o canônico até o DNS da E3 entrar.

> **Status: código PRONTO (2026-08-07, §16-E2) — suíte 462 OK (449 + 13 do
> HostHandshake). A chave da fase é a env var `WTC_TENANT_DOMAIN`: sem ela,
> prod não muda NADA. Falta só a E3 (§17.4, atualizado com o passo da env).**

### 17.4 E3 — Deploy + DNS (operação do DONO, ordem estrita; ~1h)

> As duas armadilhas (memória `wtc-dominio-whatthechip-app`): **settings
> primeiro, DNS depois** (senão 400 DisallowedHost que parece DNS quebrado); e
> **NUNCA criar o `*` antes do middleware estar no ar** (§10.3).

1. **Backup fresco** (Render Export) — §2.1b.
2. Push em `main` → deploy (migrate no build). **Smoke no canônico:** nada
   mudou pro usuário atual (a E2 é INERTE sem a env var).
3. **Ligar o modo multi-host:** Render → Environment → adicionar
   **`WTC_TENANT_DOMAIN=whatthechip.app`** (o serviço reinicia). Smoke de
   novo no canônico: tudo igual — só os cookies viram domain-wide (B5;
   quem estava logado pode precisar relogar). Este é o "settings ANTES do
   DNS" da T7.
4. **Slugs congelam AQUI:** `eminer` + `erecyclo` (§17.5.1; rename da E1
   feito em prod).
5. Render (serviço `whatthechip`): adicionar **`*.whatthechip.app`**.
   Cota Hobby = 2: pra zero-downtime no `www`, adicionar a wildcard ANTES de
   remover o `www` avulso (3º domínio custa US$ 0,25/mês pro-rata por uns
   minutos) → cert emitido → **remover o domínio `www`**. Alternativa: remover
   o `www` primeiro e aceitar `www` fora do ar por minutos (é só redirect).
6. Hostinger: **remover o CNAME `www`** (a wildcard cobre) → criar os 3
   CNAMEs que a Render indicar (`*`, `_acme-challenge`,
   `_cf-custom-hostname`) → aguardar Verified + Certificate Issued.
   ⚠ zero `AAAA`, como sempre.
7. **Checklist de verificação manual:** `https://eminer.whatthechip.app` e
   `https://erecyclo.whatthechip.app` abrem no login · logar usuário do
   cliente 1 e visitar o host do cliente 2 → **403** · subdomínio inventado →
   volta pro canônico · `www` → 301 apex · apex intacto (site + `/partner/`)
   · login no apex → cai LOGADO no subdomínio do vínculo. ⚠ usuários logados
   no momento da virada podem precisar relogar (cookie antigo era host-only).
8. `guard_catalog` (tripwire pós-deploy, como sempre).
9. `.onrender.com` fica no `ALLOWED_HOSTS` (rota de fuga) por dias; remover é
   opcional e adiável.

**Aceite = a META DO PEDIDO:** os 2 clientes atuais de produção acessando
pelos próprios subdomínios, checklist do item 6 todo verde.

### 17.5 Decisões em aberto (fechar com o dono ANTES da fase correspondente)

1. **Slugs dos 2 clientes — ✅ FECHADA (dono, 2026-08-07):** `eminer` +
   `erecyclo`. ⚠ A 2ª empresa está em prod com o NOME ERRADO ("Mundo Metal")
   — o certo é **eRecyclo**: renomear no admin (nome + slug `erecyclo`;
   pghistory audita). Runbook no §16-E1; congelam de vez na E3.
2. **`/fab-*/` públicas?** (B1 — DECISÃO AINDA ABERTA). **Auditoria E2
   (2026-08-07):** `fab-samsung.html` (88KB) expõe decode PESADO — 60 menções
   a "decode", posições `pn[3]`/`pn[4]`, tabelas de capacidade (=1/2/4GB,
   =8Gb…); `fab-hynix` moderado; `fab-micron` e demais leves. Recomendação
   REFORÇADA: plataforma-only (coerente com o fim da busca pública §10.7 — a
   vitrine morreu, as páginas ensinam a convenção de graça). A duplicação em
   subdomínio já está resolvida de qualquer forma (urls_tenant). Fica pro
   dono decidir; dá pra fechar em sessão curta depois da E3.
3. **Plataforma (superuser) em host de cliente** — ✅ IMPLEMENTADA na E2
   conforme recomendação: PASSA (espelha o `app.platform` do RLS) e o ESCOPO
   continua o do vínculo dele (o host não vira fonte nem pra super — o
   HostHandshake prende com asserção em `request.company`).
4. **Logo agora ou depois** (E4): recomendação = DEPOIS (fora do caminho
   crítico; exige S3/storage — B4+B7).
5. **Tenant pedindo conteúdo canônico** — ✅ IMPLEMENTADA na E2 conforme
   recomendação: redirect 302 pro canônico (fallback da urls_tenant — nunca
   404).

### 17.6 E4 — OPCIONAL, pós-T7: logo/branding por cliente (B4+B7)

`django-storages` + S3/R2 (ou disco persistente + view de media — pior),
`Company.logo` exibida no header do host do tenant. Sem prazo; não bloqueia
nada do caminho crítico.

---

**Esforço total estimado:** E0 (curta) + E1 (1 sessão) + E2 (1–2 sessões) +
E3 (~1h de operação com o dono) → **~3–4 sessões dedicadas** até a meta.
