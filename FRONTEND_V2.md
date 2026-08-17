# FRONTEND_V2.md — contrato técnico do redesign com canary por cliente

> **Pra quem é este doc:** o agente (sessão de IA) que vai CONSTRUIR o novo
> frontend das telas logadas. A infraestrutura de rollout já existe e está em
> produção-ready (commit `ef802cf`, suíte 503 OK) — o seu trabalho é SÓ
> escrever os templates v2 dentro do contrato abaixo. Não reconstrua nada da
> mecânica. Fonte da decisão: `PLANO_MULTITENANT.md` §17.7 e §16-E5.

---

## 0. TL;DR

1. **Nunca edite os templates atuais.** Cada tela nova é uma CÓPIA em
   `v2/` (ex.: `estoque/templates/estoque/v2/painel.html`).
2. A seleção v2×atual **já está feita nas views** (`tenancy/ui.py` +
   `Company.ui_v2`). Um arquivo v2 passa a valer automaticamente — e SÓ pra
   empresa com o flag ligado. Tela sem arquivo v2 cai na atual (fallback
   por tela; entrega parcial é segura).
3. Dentro dos arquivos v2, `{% extends %}`/`{% include %}` apontam
   **explicitamente** pros caminhos v2.
4. Respeite os 4 contratos: i18n (4 idiomas), máscara/sigilo server-side,
   endpoints+contexto das views (não mude .py), CSS namespaced.
5. Entrega = suíte completa verde:
   `python manage.py test chips estoque tenancy pricing vendas --settings=core.settings_test`

---

## 1. Como o canary funciona (mecânica PRONTA — não mexer)

Deploy de código é global (1 serviço Render, 1 banco). O rollout por cliente
vem do flag **`Company.ui_v2`** (checkbox "Frontend v2 (canary)" no admin de
Empresas) + do helper **`tenancy/ui.py`**:

```python
ui(request, 'estoque/painel.html')
# flag OFF → 'estoque/painel.html'
# flag ON  → ['estoque/v2/painel.html', 'estoque/painel.html']
```

O `render()` do Django aceita lista e usa o **primeiro template que existe**
(`select_template`). Semântica do flag: segue o VÍNCULO (`request.company`);
anônimo em host de tenant segue `request.tenant_host_company`; anônimo no
canônico = sempre o atual. Rollout/rollback = marcar/desmarcar o checkbox —
nunca deploy. Testes de referência: `tenancy/tests.py::UiV2CanaryTests`.

**Proibido:** condicionar v2 DENTRO de template (`{% if %}` no flag), ler o
flag do host, criar 2º serviço Render, alterar a semântica de
`tenancy/ui.py`.

## 2. Convenção de caminhos

Regra: o `v2/` entra **depois do 1º segmento do NOME do template**
(`v2_name()` em `tenancy/ui.py`). No filesystem:

| Tela / peça | Template ATUAL (não tocar) | Cópia V2 (você cria) |
|---|---|---|
| Shell (header/nav) | `estoque/templates/estoque/base_estoque.html` | `estoque/templates/estoque/v2/base_estoque.html` |
| Painel (home logada) | `estoque/templates/estoque/painel.html` | `estoque/templates/estoque/v2/painel.html` |
| Ledger de lotes | `estoque/templates/estoque/lotes.html` | `estoque/templates/estoque/v2/lotes.html` |
| Bancada (triagem) | `estoque/templates/estoque/estoque.html` | `estoque/templates/estoque/v2/estoque.html` |
| Partials da bancada | `estoque/templates/estoque/partials/*.html` | `estoque/templates/estoque/v2/partials/*.html` |
| Vendas (4 telas) | `vendas/templates/vendas/{so_list,so_detail,invoice_detail,settlement_form}.html` | `vendas/templates/vendas/v2/…` |

Partials existentes (todos já wired nas views): `table_body`, `fx_badge`,
`lot_value_card`, `lot_valuation`, `confirm_card`, `confirm_card_masked`,
`rejected_feedback`, `unknown_feedback`, `pending_feedback`.

**Você não precisa criar todos os v2** — só os das telas que redesenhar.
O resto cai no atual sozinho.

## 3. extends / includes / blocks

- Conteúdo v2 estende o shell v2: `{% extends "estoque/v2/base_estoque.html" %}`.
  Nunca cruzar mundos (v2 estendendo shell v1 ou vice-versa).
- Blocks do shell atual: `title`, `nav_painel`, `nav_estoque`, `nav_vendas`,
  `main`, `extra_head`, `extra_js`. **Mantenha os mesmos nomes no shell v2**
  — portar uma tela vira mecânico.
- ⚠ **Partial com include estático E endpoint HTMX** (caso real:
  `fx_badge` — incluído no shell E refrescado por `hx-get` a cada 60s;
  `table_body` e `lot_valuation` — incluídos em `estoque.html` E trocados
  por HTMX): se você criar o v2 desse partial, o include estático no SEU v2
  tem que apontar pro MESMO v2 — senão o 1º paint sai v1 e o refresh HTMX
  troca pra v2 (os endpoints já são wired e servem o v2 quando existe).
  Consistência é sua responsabilidade dentro dos arquivos v2.
- O shell atual carrega o logo do cliente (E4). Reproduza no shell v2:

```django
{% if wtc_company.logo_mime %}
  <img src="{% url 'company_logo' slug=wtc_company.slug %}?v={{ wtc_company.logo_updated_at|date:'U' }}" alt="{{ wtc_company.name }}">
{% else %}
  {# iniciais: {{ wtc_company.name|slice:':2' }} #}
{% endif %}
```

## 4. O que já está wired (e o que NÃO está)

**Wired (19 `render()` — as views já chamam `ui()`; NÃO toque nelas):**
`estoque/views.py` (15): painel, lotes, estoque, fx_badge, lot_value_card,
lot_valuation, confirm_card, confirm_card_masked, rejected_feedback (×2),
unknown_feedback, pending_feedback, table_body (×3).
`vendas/views.py` (4): so_list, so_detail, settlement_form, invoice_detail.

**Fora do canary (por ora):** site público (`base.html`, `_content/*`,
pages), tela de login (`registration/login.html` — os LoginView usam o
template padrão) e o Django admin. Se o redesign PRECISAR de login v2 por
empresa, não improvise: é uma edição pequena de view
(`get_template_names` com `ui()`), peça pro dono encomendar.

**Se você criar uma view nova** que renderiza template de tela logada:
`return render(request, ui(request, 'app/tela.html'), ctx)` — import
`from tenancy.ui import ui`. (Mudança de .py é exceção — proponha antes,
padrão do projeto.)

## 5. Contratos que o v2 TEM que respeitar

### 5.1 i18n — 4 idiomas (bíblia: `I18N.md`)

Todo texto visível passa por `{% trans %}`/`{% blocktrans %}`. Reuse msgids
existentes sempre que possível (o texto atual das telas já está nos
catálogos). String NOVA = na MESMA entrega: adicionar aos 3
`locale/{es,en,zh_Hans}/LC_MESSAGES/django.po` + recompilar `.mo`
(`scripts/i18n_compile.py`, usa polib) + portão
`python manage.py check_translations` verde. A suíte tem teste que quebra
com catálogo incompleto. Strings dentro de JS inline: cuidado com
apóstrofos em literais `'...'` (lição registrada do redesign da home).

### 5.2 Sigilo / máscara — SERVER-SIDE (F12; não afrouxar no template)

- O contexto `access` está em todo template: `access.is_unmasked`,
  `access.can_see_price`, `access.can_sales`, `access.can_debug`,
  `access.role_tag`. Menu Vendas gated por `{% if access.can_sales %}`.
- `confirm_card_masked.html` é WHITELIST: papel mascarado vê SÓ
  PN + código de caixa C-### + quantidade (+ preço quando o papel permite).
  **Zero** specs/marca/veredito/debug. O v2 dele mantém a whitelist — na
  dúvida, copie os campos do atual, mude só o visual.
- Vendas: o NOME real do comprador nunca aparece (contraparte =
  "WhatTheChip"); gerente não vê ¥/US$/taxa (a view já omite do contexto —
  não reintroduza por outro caminho).
- Regra geral: máscara no template é cosmética; a garantia é a view. Não
  adicione ao template dado que a view não mandou.

### 5.3 Endpoints, contexto e hooks HTMX

As views não mudam → o CONTRATO de dados é o atual: mesmas variáveis de
contexto (leia a view correspondente antes de cada tela), mesmos endpoints
HTMX (`preview_chip` → `#confirm-area`, refresh do `fx_badge` 60s,
paginação/filtros da `table_body`, close/reopen/export de lote, delete+toast,
modal de fechar lote, `est-lot-data`, hidden fields do submit). O JS pode
ser SEU (vive no `extra_js` do seu v2), mas o que ele chama é isso. Se
reaproveitar o JS atual, preserve os ids/classes que ele usa
(`#pn-input`, `#confirm-area`, `est-*`, `data-*`…).

### 5.4 CSS — armadilhas JÁ pagas (não pagar de novo)

- Toda tela logada carrega `style.css` global → **nunca** classes genéricas
  (`.btn`, `.card`, `.hero`, `.steps`, `.active`…). Namespace próprio por
  tela/peça (padrão da casa: `.uib`, `.pnl-*`, `.ivd-*`, `.sod-*`, `.lg-*`).
  Confira colisão com `style.css` antes de batizar.
- **Nunca escreva `*/` dentro de comentário CSS** (nem `.x*/`) — fecha o
  comentário no meio e descarta o resto do bloco (bug real de 2026-07-22).
- Comentário Django `{# #}` é de UMA linha; multilinha = `{% comment %}`
  (vaza como texto se quebrar — teste da suíte pega).
- CSS inline no template (padrão das telas logadas) = reflete no reload,
  sem collectstatic. `design.css` é só do site público — não misturar.

### 5.5 Git / entrega

- Commits cirúrgicos: só os arquivos v2 novos (+ .po/.mo se houver string
  nova). Nunca commitar `_to_delete/`, nunca arrastar WIP alheio.
- Nada de migração/DB neste trabalho (se "precisar", o desenho está errado —
  pare e pergunte).
- Suíte completa verde antes de entregar (comando no §0). Template-only não
  exige characterize_baseline (não toca o engine).

## 6. Como testar localmente

```bash
# ligar o canary pra eMiner no banco LOCAL (ou: admin → Empresas → checkbox)
python manage.py shell -c "from tenancy.models import Company; Company.objects.filter(slug='eminer').update(ui_v2=True)"
python manage.py runserver   # logar com usuário da eMiner → vê v2
# desligar: update(ui_v2=False) — rollback instantâneo
```

Usuário de outra empresa (ex.: `erecyclo`) na MESMA instância continua vendo
o atual — é o teste de honestidade do canary. Em teste automatizado, siga o
padrão de `UiV2CanaryTests` (flag na empresa + `assertContains`); com
arquivos v2 reais no repo não precisa do truque de `override_settings`.

## 7. Rollout (do DONO, depois do seu trabalho)

Push → admin de PROD → marcar `ui_v2` na eMiner → validar → depois eRecyclo.
Quando 100% migrar, o v2 vira padrão e os templates antigos morrem — isso é
uma fase FUTURA registrada no PLANO §17.7 (não faça essa limpeza agora).

## 8. Referências

- `PLANO_MULTITENANT.md` §17.7 (design/decisões do canary) e §16-E4/E5
  (diário: logo no banco, esqueleto).
- `tenancy/ui.py` (o helper — docstring é normativa),
  `tenancy/tests.py::UiV2CanaryTests`.
- `I18N.md` (rotina de tradução), `CLAUDE.md` (regras gerais da casa).
- Protótipos visuais: kit `design_handoff_whatthechip` (screens/*.html) —
  reproduzir ESTRUTURA dos protótipos, não re-skin do layout antigo (lição
  registrada do pivô de 2026-07-21).
