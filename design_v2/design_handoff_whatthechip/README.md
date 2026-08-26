# Handoff: WhatTheChip — Redesenho completo (F10–F12, plataforma multiempresa com sigilo)

## Overview
WhatTheChip (**什么芯片**) virou **plataforma multiempresa com sigilo de conhecimento**: o que um
chip **é** (marca, tipo, specs, rentabilidade) é o ativo do WhatTheChip. A empresa-**cliente** opera
às cegas com **códigos de caixa opacos (C-###)**; só a **plataforma** vê o decode real. A fonte única
da regra é `tenancy.access.is_unmasked` — **nunca** invente lógica de exibição por página.

Codebase real: **Django 5.2 + HTMX**, Postgres, deploy no **Render**. Este pacote são **referências de
design em HTML/CSS/JS puro** (protótipos de alta fidelidade), **não** código de produção. A tarefa é
**recriar estas telas no Django existente**, ligando a exibição ao `tenancy.access`.

## ⚠️ Regra central — a matriz de papéis (aplicar em TODA superfície)
Todo o comportamento deriva de um único objeto de acesso. No protótipo isso está em
`screens/access.js` (`window.WTCAccess.access()`), que espelha o que o Django deve fornecer no contexto
do template. Derivados a partir do papel:

| Papel | `is_unmasked` | `can_see_price` | `can_sales` | `can_debug` |
|---|---|---|---|---|
| **Operador** (cliente) | ❌ | ❌ | ❌ | ❌ |
| **Gerente** (cliente) | ❌ | ❌ | ❌ | ❌ |
| **Admin da empresa** | ❌ | ✅ | ✅ | ❌ |
| **Plataforma / superuser** (`empresa.is_platform`) | ✅ | ✅ | ❌ | ✅ |

O que cada flag controla:
- **`is_unmasked`** — ver o decode real (tipo eMMC/eMCP…, marca, capacidade, specs, e as palavras
  "rentável / não rentável / indeterminado" e a barra de rentabilidade). Só plataforma.
  Cliente (operador/gerente/**admin**) **NUNCA** vê nada disso — só o **destino** (C-###, CONFERÊNCIA, DESCARTE).
- **`can_see_price`** — bloco de preço `¥ 90 · US$ 12.60`, valoração de lote em US$, coluna Valoração. Admin+.
- **`can_sales`** — menu **Vendas** e os smart buttons (Lote↔OV↔Fatura). Só admin da empresa
  (a plataforma é a contraparte, não compra de si mesma).
- **`can_debug`** — botão `📋 Debug`. **Só superuser** (nem o admin de empresa).

**No Django:** exponha `access` no contexto e gate por ela (`{% if access.is_unmasked %}`,
`{% if access.can_see_price %}`…). NÃO use `request.user.is_staff` espalhado; centralize em
`tenancy.access`. O switcher flutuante "PROTÓTIPO · ver como" existe só nos protótipos (troca o papel
via localStorage) — **não** portar para produção.

## Fidelity
**Alta (hifi).** Cores, tipografia, espaçamentos, interações e a lógica de mascaramento são finais.

## Screens (em `ui_kits/whatthechip/`)
Cada tela é standalone e carrega `access.js`. Todas usam o shell interno e a folha `wtc-carbon.css`.

> **As cópias legado deste diretório (`screens/`) foram removidas.** Elas ainda cravavam os tokens do
> sistema anterior (raios 8/12/16, sombras `sh-*`, Helvetica Neue) e tinham divergido das telas vivas.
> A fonte única é `ui_kits/whatthechip/` — 16 telas, dos dois lados do balcão (vendedor e comprador).
> Mapear no Django para a home pública + `templates/base.html` e `templates/registration/login.html`.

### `painel.html` — Painel (pós-login)
- Saudação + missão 1→2→3, hero "Continue de onde parou" (`LOT/042/07/26`), lote secundário, pulso do dia, atalhos.
- **Mascarado (operador/gerente):** hero sem barra de rentabilidade → "Conteúdo do lote · N categorias · M un.";
  foot Unidades/**Categorias**; pulso "**Categorias hoje**". **Admin:** + célula "Valor hoje" (US$).
  **Plataforma:** barra de rentabilidade, "Tipos", org vira WhatTheChip.

### `estoque.html` — Estoque (lista de lotes, `/estoque` → `lot_list`)
- "Em triagem agora" (lotes abertos) + **ledger** (tabela) com busca, filtros de status e período/ordenação, criar sob demanda.
- **Mascarado:** lotes em `LOT/###/MM/YY`; **sem** coluna Rentabilidade → coluna neutra **Categorias**; sem filtro de tipo.
  **Admin:** + coluna **Valoração** (US$). **Plataforma:** coluna Rentabilidade (barra verdict).
- Export (gerente+): colunas **Part Number / Category / Qty. / Last Added**.

### `triagem.html` — Bancada / detalhe do lote (`lote/<id>/`)
- Console de scan fixo à esquerda + conteúdo do lote à direita. É a tela onde o sigilo mais aparece.
- **Mascarado:** digita o código e recebe **só o destino** — cartão verde gigante **C-153**,
  `C-000 · Geral (avaliação)`, âmbar **CONFERÊNCIA** ou vermelho **DESCARTE**. NUNCA tipo/marca/specs/verdict/debug.
  Tabela do lote com badge C-### no lugar do tipo, sem sub-linha marca/capacidade; resumo neutro
  (Unidades/Categorias/Conferência/Descarte). **Admin:** + bloco de preço `¥ · US$`. **Plataforma:** card
  completo (specs, verdict) + `📋 Debug`.
- **Fechar lote:** modal (digitar o código completo `LOT/042/07/26` para confirmar) → redireciona à **OV**.
- Smart buttons Odoo (Lote↔OV↔Fatura) só admin.

### `vendas.html` — Vendas (admin-only)
- OV `SO/001/07/26` → contraparte **sempre "WhatTheChip"** (o nome do comprador real **nunca** aparece
  fora do Django admin). Stepper Rascunho→Confirmada→Faturada→Paga; smart buttons Lote↔OV↔Fatura.
- Linhas por **C-###** + Qtd. + **¥ unitário** + subtotal ¥ (total ¥ + US$ derivado). Acerto (câmbio).
  Fatura `INV/001/07/26` (US$). **Pagamentos só em US$**, com saldo.
- Papel sem `can_sales` → tela "Acesso restrito" (e o item Vendas some da nav).

## Padrões fixos (não redesenhar contra)
- **Códigos canônicos**, NUNCA traduzidos, sempre **IBM Plex Mono**: `LOT/040/07/26` · `SO/001/07/26`
  · `INV/001/07/26` · `C-###`. Formato `TIPO/sequencial(3)/MM/YY`.
- **Dinheiro:** `¥` canônico, **US$ derivado**, ponto decimal sempre; **pagamentos só em US$**.
- **Fechar lote:** modal Carbon com resumo + digitar o código completo do lote → ao fechar, redireciona à OV.
- **Smart buttons** estilo Odoo no topo direito (lote ↔ OV ↔ fatura).
- **Fuzzy "VOCÊ QUIS DIZER?":** parte digitada normal, parte faltante em **VERDE com "+"** (só caracteres
  do PN — vale também no card mascarado; o PN em si não é segredo, o que ele significa é).
- **i18n 4 idiomas** (pt-BR, en, es, zh-hans): toda string nova nasce com `{% trans %}` e é traduzida na
  mesma entrega. **Valores canônicos jamais traduzem** (C-###, LOT/SO/INV, chaves de lógica, verdict keys).
  *Nos protótipos as strings estão em pt-BR (canônicos intactos) — o wiring de 4 idiomas é trabalho de
  template Django, não representável no HTML estático.*

## Design tokens
Ver `../styles.css` + `../tokens/` no design system. Resumo:
- **Azul primário** `#0f62fe` (hover `#0353e9`). Neutros "ink" (Carbon). Verdict: verde `#24a148`,
  âmbar `#f1c21b`, vermelho `#da1e28`. Shell interno escuro `#101317`.
- **Tipografia:** Manrope (UI) · IBM Plex Mono (todos os códigos/PN/valores) · Noto Sans SC (什么芯片).
- **IBM Carbon:** cantos **quadrados** (0px em tudo — tags, barras, cartões, campos, botões; só ponto de
  status e avatar são redondos), **sem sombra** em lugar nenhum (a separação é fio de 1px `--line` e as
  chapas rebaixadas `--ink-05`/`--ink-10`), alturas de controle 36/48/56/76, linha de tabela 56,
  barra de navegação 52. Foco = `outline:2px solid var(--blue-60)` com `outline-offset:-2px`.
- Motion 120/240ms `cubic-bezier(.2,0,.2,1)`.

## Assets (em `assets/`)
- `whatthechip-lightmode.svg` / `whatthechip-darkmode.svg` — lockup (badge + wordmark + 什么芯片), trocado por tema.
- `favicon.svg`. Ícones = SVG inline stroke 24×24, `currentColor`, estilo Lucide.

## Como aplicar (sugestão de ordem)
1. `tenancy.access` no contexto (is_unmasked/can_see_price/can_sales/can_debug) + `base_estoque.html` (shell).
2. `decode_card` / bancada (`triagem.html`) — o gate mais crítico. Garanta que o backend **não envie**
   specs/marca/verdict para roles mascarados (mascare no servidor, não só no template).
3. `/estoque` ledger + painel.
4. Módulo **Vendas** (novo): OV/acerto/fatura/pagamentos.
5. Site público + login. 6. i18n `{% trans %}` nas strings novas.

**Segurança:** mascarar no template não basta — o endpoint HTMX (`/chips/search/`) deve **omitir** os
campos sigilosos do JSON/HTML quando `not access.is_unmasked`. O protótipo mascara no cliente só para demo.
