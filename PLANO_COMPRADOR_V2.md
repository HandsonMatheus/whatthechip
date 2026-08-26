# Plano v2 do painel do COMPRADOR — comparação com o que roda hoje

**Data:** 2026-08-26 · **Escopo:** só a superfície do comprador (`/partner/`). Nada da área do cliente/admin.

## 0. Fontes

| O quê | Onde |
|---|---|
| Spec v2 (o *o quê*) | `design_v2/design_handoff_whatthechip/BACKEND-PAINEL-COMPRADOR.md` |
| Guia (o *porquê*) | `design_v2/design_handoff_whatthechip/GUIA-PAINEL-COMPRADOR.md` |
| Histórico das etapas | `design_v2/design_handoff_whatthechip/PLANO-V2-ETAPAS.md` |
| Protótipos vivos | `design_v2/ui_kits/whatthechip/parceiro-*.html/js` + `wtc-parceiro.css` |
| CSS/tokens do DS | `design_v2/dist/whatthechip-ds/` |

⚠ **A spec foi escrita SEM o repo na mão.** `PERGUNTAS-ABERTAS.md` §1 ("Conectar o repo Django?") nunca foi
respondida. Por isso ela inventa nomes de model, de campo e de rota. A própria spec avisa: *"Nomes são
sugestões; a **forma** não é."* Toda divergência de NOME abaixo é tradução, não conflito. Só está em §3 o
que diverge em **comportamento**.

---

## 1. Veredito

O backend de hoje **já implementa a maior parte das invariantes duras da v2** — e em vários pontos está
*à frente* dela (os quatro estados de célula com CheckConstraint, o resultado gravado por `line.pk` em vez
de índice posicional, o MIME do comprovante sniffado dos bytes). O que falta é quase todo **superfície**:
lista com filtro/ordenação/CSV, aba de observações, badge, catálogo parametrizado, e a fila de cotação
travada.

Três blocos, em ordem de esforço crescente:

| Bloco | Já existe | Falta |
|---|---|---|
| **Preços** | ~85% | SSD/K9 na tela, piso do SSD, `BlockedQuote`, catálogo parametrizado |
| **Ficha do lote** | ~70% | aba Observações, CSV por aba, idempotência do pagamento, carteira, celular |
| **Lista de compras** | ~25% | busca, filtros, período, ordenação, paginação, CSV, badge |

---

## 2. O que a v2 pede e JÁ EXISTE — não refazer

| Spec | Onde já está | Nota |
|---|---|---|
| §3.3 quatro estados de célula | `pricing/models.py:126-135` + CheckConstraints `:510-527` | **Melhor que a spec.** Ela pedia enum de 3 + flag `manufactured`; o repo tem enum de 4 (`quoted/unquoted/not_made/no_buy`) e o banco proíbe `0` fazendo papel de `x` |
| §3.2 faixa `[mín,máx]` só em emcp/umcp | `price_min`/`price_max` + CheckConstraint `price_fixed_only` `:510-514` | idêntico |
| §3.4 `PriceReview` (preço antigo vale até aprovar) | `PriceChangeRequest` `:750-885`, `one_pending_per_price` `:816` | idêntico, com snapshot do antes |
| §5.1 diff no servidor, só o alterado | `partner_kind_save` (`pricing/views.py:420`) | idêntico |
| §3.2 eMMC = duas grades | `Price.origin` phone/pcb + CheckConstraint `:482-486` | idêntico |
| §3.2 ordem canônica dos tipos | `_NAV_KINDS` (`pricing/views.py:121`) | **mesma ordem** nos 6 que existem |
| §4.4 trilho de **cinco** células | `services.order_steps` `:1213-1214` — `fechado·enviado·recebido·resultado·pagamento` | **match exato** |
| §4.5 estado derivado, nunca decorativo | `order_stage`/`order_steps` derivam de timestamps + `Invoice.status` | o repo já segue o princípio da spec |
| §6.4 digita-se o **recusado**, vazio = zero | `rej_<pk>` (`views_partner.py:190`) | idêntico |
| §6.4 agrupar por MARCA | `services.result_rows` `:1068-1149` | idêntico |
| §3.8 gravar resultado por chave de linha | `SettlementLine` por `line.pk` | **a spec pede isso como dívida a evitar; o repo já evita** |
| §2.3 taxa travada por lote | `Lot.fx_rate`/`fx_locked_at` (`estoque/models.py:77-85`) → `SalesOrder.fx_usd_rate` → `Invoice.fx_usd_rate` | idêntico, com CheckConstraint `so_confirmed_is_frozen` |
| §3.9 pagamento nativo em US$, `by`/`kind` no servidor | `Payment.amount_usd` (`vendas/models.py:590`) | idêntico |
| §6.8 comprovante obrigatório | `views_partner.py:250-254` + `attach_receipt` | **melhor que a spec**: MIME sniffado dos bytes, SVG recusado |
| §7.1 folha sem nome do comprador, sem pagamentos, sem fatura | `services.result_document` `:565-632` (comentário explícito `:612-613`) | idêntico |
| §9 vocabulário canônico não traduz | regra da casa, 3 catálogos (`en`/`es`/`zh_Hans`) + pt-br fonte | idêntico |
| §5.2 catálogo em PDF | `partner_catalog_pdf` (`pricing/views.py:350`) | existe com `lang` + `currency` |

---

## 3. CONFLITOS — precisam de decisão do dono

### C1. Vocabulário de estado: 6 derivados (repo) × 4 armazenados (spec) 🔴 BLOQUEIA TUDO

A spec §4 desenha `st ∈ transit|received|settled|paid` como **campo**. O repo **não guarda estado**: deriva
`stage` de timestamps + `Invoice.status`, com seis nomes: `sem_preco · a_congelar · a_conferir · faturado ·
parcial · pago`.

A própria spec §4.5 manda derivar (*"Se você guardar um campo `stage` e desenhar a partir dele, os dois
divergem no primeiro caso de borda"*) — e §12.3 **pergunta exatamente isto**: *"Oito estados onde o briefing
nomeia seis... Se o app tem exatamente seis, diga quais pares fundem."*

**Recomendação:** manter derivado, e responder o §12.3 com o mapa abaixo. Zero migração.

| spec | repo hoje |
|---|---|
| `transit` | `a_conferir` sem `received_at` |
| `received` | `a_conferir` com `received_at` |
| `settled` | `faturado` |
| `settled` + pago parcial | `parcial` |
| `paid` | `pago` |
| — (não existe na spec) | `sem_preco`, `a_congelar` |

> Os dois últimos são o nó do **C2**.

### C2. Quem entra na lista de compras 🔴

Spec §4.1: *"Só entra lote que o vendedor fechou **E** despachou. Não existe lote 'em aberto' no painel do
comprador."* Hoje a lista mostra também `sem_preco` e `a_congelar` — ou seja, **rascunhos**, com o selo
"falta preço seu".

A v2 não perde esse trabalho: ela o **move** para o lado dos preços, como `BlockedQuote` (§3.5) — *"o estado
`falta preço` do cliente visto do lado de quem pode resolver"*, com `orders`, `units` e `since`.

**Recomendação:** aceitar. A lista de compras vira só caixa despachada; a fila de cotação travada vira card
no resumo de preços. Mas é mudança de rotina diária do parceiro — **confirmar antes**.

⚠ Efeito colateral: o selo "Congelar" da lista (`partner_compras.html:87`) hoje aparece sem rota nem botão —
morre junto.

### C3. SSD e K9 nas telas de preço 🟠

Spec §3.2 lista **oito** tipos e dá regra fechada para os dois que faltam:
- **SSD**: `form: linear` — `preço(cap) = max(round(¥_por_GB × GB), piso_por_peça)`, capacidades derivadas
  `[128,256,512,1024]`, célula em âmbar quando o piso vence.
- **K9**: **uma** linha, **um** campo — *"Não crie grade por densidade 'para ficar consistente'."*

Repo: `Buyer.ssd_rmb_per_gb` e `Buyer.k9_rmb_each` existem, mas **só no Django admin**. Nenhum dos dois está
em `_NAV_KINDS` nem no catálogo PDF. E **o piso por peça não existe** — nem campo, nem lógica.

**Decisão necessária:** (a) expor os dois ao comprador? (b) criar o campo de piso do SSD?

### C4. Aba Observações — hoje é um textarea de mão única 🟠

Spec §6.9: lista de notas com autor + data, removível pelo autor, `⌘/Ctrl+Enter` registra, **tudo impresso no
PDF**, e a observação do diálogo de fechamento cai **nesta mesma lista** (*"não num campo próprio, que criaria
dois lugares onde procurar"*).

Repo: só `Settlement.notes` — um textarea no modal de fechar resultado, sem autor, sem data, uma nota só,
sem como acrescentar depois.

Muda o PDF: §7.1 manda a autoria virar **"Conferência"** no documento (o cliente não pode saber quem comprou).

**Recomendação:** model novo `LotNote`/`OrderNote` (FK na OV, `author`, `created_at`, `text`), e
`Settlement.notes` passa a nascer como a primeira nota. Migração de dados: 1 linha por acerto existente.

### C5. Limite e tipos do comprovante 🟢

Spec §6.8: PDF/PNG/JPG até **10 MB**. Repo: até **5 MB**, aceita também WebP, recusa SVG de propósito.

**Recomendação:** manter os 5 MB e o sniff (é mais seguro), e ajustar o texto da tela. Confirmar.

### C6. URL da ficha: `pk` × código do lote 🟢

Spec §5.4: `/parceiro/lote/<code>/`. Repo: `/partner/compras/<pk>/`. Trocar quebra link guardado (já houve um
redirect legado por isso em `urls_partner.py:23`).

**Recomendação:** manter `pk`. As rotas em português da spec (`/parceiro/...`) também não valem — a decisão do
dono é rota em inglês (`core/urls.py`), e há teste cravando `/partner/how/`.

### C7. Rotas órfãs 🟢

`/partner/lists/<pk>/` (`partner_list`) e `/partner/save/<pk>/` (`partner_save`) funcionam mas **nenhum link
aponta pra elas** — a sidebar só linka `partner_home` e `partner_kind`. A v2 não as tem.

**Recomendação:** remover na v2 (com teste de 404/redirect), ou decidir mantê-las. Não deixar meio-caminho.

---

## 3-bis. DECISÕES DO DONO — 2026-08-26

| # | Decisão | Consequência |
|---|---|---|
| **C1** | **Manter o estado DERIVADO**, só mapear pro vocabulário da spec | Zero migração. A resposta ao §12.3 da spec é a tabela de C1. `order_stage`/`order_steps` ficam como estão |
| **C2** | **Aceitar §4.1**: só lote despachado entra na lista + criar `BlockedQuote` | A lista de compras perde `sem_preco`/`a_congelar`. A fila de cotação travada vira card no resumo de preços. O selo "Congelar" morre |
| **C3** | **Expor SSD e K9 ao comprador + criar o piso por peça do SSD** | Migração nova em `pricing` (⚠ blast radius: `pricing/models.py` é compartilhado com a bancada). SSD `form:linear` com capacidades derivadas e âmbar no piso; K9 uma linha, um campo |
| **C4** | **Model `OrderNote` novo + migrar as notas de acerto existentes** | O textarea do modal passa a criar a primeira nota. PDF imprime a lista com autoria **"Conferência"**. 1 linha de migração por `Settlement` com nota |
| **C5** | Comprovante: manter **5 MB + MIME sniffado** (contra os 10 MB da spec) | Ajustar só o texto da tela |
| **C6** | Manter `/partner/compras/<pk>/` (não trocar por código do lote) e as rotas em **inglês** | Não quebra link guardado; preserva o teste que crava `/partner/how/` |
| **C7** | Remover `/partner/lists/<pk>/` e `/partner/save/<pk>/` (órfãs) na v2 | Com teste cravando o 404/redirect |

---

## 4. NOVO — o que não existe e precisa ser construído

### 4.1 Lista de compras (`/partner/`) — o maior bloco

Hoje o template diz, com todas as letras: *"MVP de propósito: sem filtro nem paginação"*. Ordenação fixa por
`created_at` desc. A v2 §5.3 pede:

- **Busca** num único `haystack` minúsculo: código do lote, código da ordem, cliente, país, cidade,
  transportadora, rastreio.
- **Status** com a contagem embutida na opção (`"A conferir (2)"`), e a contagem vem do **conjunto completo**,
  nunca do filtrado.
- **Período** filtrando pela data de **despacho** (`ship`) — mesma convenção de Estoque e Vendas.
- **Ordenação** por `n|seller|so|units|val|usd|due`, default `n` desc. Lotes sem resultado ordenam por `-1` e
  afundam — proposital.
- **Paginação** 10/25/50; trocar filtro/busca/por-página volta pra página 1.
- **Coluna Resultado dupla**: valor + sub-linha `falta US$ N` (âmbar) ou `quitado` (verde). Antes do
  fechamento, `—` — **não zero**.
- **Vazio** com frase: *"Nenhum lote encontrado / Ajuste a busca ou os filtros acima."*
- **CSV** do mesmo recorte filtrado: 14 colunas, `;`, BOM UTF-8, `compras-<comprador>.csv`. Colunas de
  resultado saem **vazias** para lote não fechado.

### 4.2 Badge do nav

```
badge = (lotes a conferir) + (lotes com saldo em aberto)
```
Não conta `transit` nem quitado. **Zero ⇒ string vazia, não `0`.** Um único context processor; toda tela do
painel recalcula no load. Hoje só existe o ponto do sino de notificações, sem número.

### 4.3 `BlockedQuote` — a fila de cotação travada

Derivado, não armazenado: agregação dos lotes em `sem_preco` por (tipo, linha), com `orders`, `units` e
`since` (data do lote travado mais antigo). A matéria-prima já existe em `services.draft_pendencias`
(`vendas/services.py:1381`) — falta agregar e expor no resumo de preços.

Spec §3.5 crava a distinção que importa: **lacuna** (`miss`, célula vazia que ninguém está vendendo, pode
esperar) × **travado** (lote já fechado que a plataforma não consegue precificar, **fila de trabalho**).

### 4.4 Catálogo parametrizado

Hoje: `?lang=` + `?currency=`. A v2 §5.2 pede formulário com:
- **seleção por exclusão** (mapa de *excluídos*, para tipo novo entrar sozinho no catálogo);
- busca por nome/descrição e filtro de cobertura (`all`/`full`/`gap`);
- `valid_until`, `cover_note`;
- `gaps: hide|dash`;
- **carimbo de taxa no rodapé de cada página**;
- 中文 simplificado como **primeira** opção de idioma;
- sob câmbio `none`, `¥ + US$ ≈` **não pode** gerar coluna de dólar;
- zero tipos ⇒ geração desabilitada.

### 4.5 Carteira de destino (§3.12)

Model `Wallet` do **WhatTheChip** (não do vendedor): `owner`, `net` (USDT · TRC-20), `addr`, `memo`. Some na
aba Pagamentos e dentro do modal, copiável, com o aviso literal: *"Você paga o WhatTheChip, nunca o vendedor
direto. Confira os seis primeiros e os seis últimos caracteres antes de enviar: transferência em blockchain
não volta."*

Regra de corte: **identificador longo em célula estreita corta no MEIO, nunca no fim** (`TQ9fH4mVx…z8gXqN`) —
a cauda é o que se confere. Vale pra carteira, rastreio e hash. Valor inteiro no `title`.

### 4.6 Rastreio clicável (§3.13)

`carrier` e `track` já são campos separados. Falta a lista de transportadoras com página conhecida — **DHL,
FedEx, UPS, SF Express, EMS, Correios** — virando link. Fora da lista, texto puro copiável: *melhor sem link
do que com link quebrado*.

### 4.7 CSV por aba da ficha (§6.10)

Exporta **a aba aberta**. `;`, BOM UTF-8, `<CODIGO>-<aba>.csv`. Quatro conjuntos de colunas (Resultado /
Chips / Pagamentos / Observações). Não existe nenhum CSV na superfície do comprador hoje.

### 4.8 Modal de pagamento completo (§6.8)

Repo tem valor + data + comprovante. Falta:
- resumo com **SO** (é a referência do memo), resultado `¥ = US$`, já pago, **restante** destacado;
- atalhos **25% / 50% / Restante** (o terceiro traz o valor exato do saldo);
- conversão viva `= ¥ N` pela taxa travada, **sem `≈`** (com taxa travada a conversão é exata);
- acima do saldo: campo vermelho + `"acima do saldo · máx US$ N"` — não trunca, não aceita;
- rótulo do botão muda: **"Registrar quitação"** × **"Registrar pagamento parcial"**.

### 4.9 A ficha no telefone (≤600px) (§6.4)

A planilha vira cartão na ordem do trabalho de bancada: tipo/capacidade/caixa → `enviados N` → **o campo**
(48px, rótulo próprio) → `aprovados` + `¥ resultado`. Preço unitário e esperado **saem**. Barra viva grudada
no rodapé com resultado final e diferença, porque no telefone os heróis já rolaram pra fora.

### 4.10 Aba desabilitada continua visível (§6.3)

Aba indisponível fica **desabilitada e listada**, contador `—`, `title="disponível quando o resultado fechar"`.
*"Não desaparece: o comprador precisa saber que existe."*

---

## 5. Bugs e riscos achados no caminho

| # | O quê | Onde | Gravidade |
|---|---|---|---|
| B1 | **Pagamento sem chave de idempotência.** Spec §5.4: *"O comprador está em rede instável e vai clicar duas vezes. Um pagamento duplicado é dinheiro perdido."* `mark_received` é idempotente e `settle_and_invoice` se protege pela fatura ativa — `compra_pagar` **não tem nada** | `vendas/views_partner.py:218` | 🔴 |
| B2 | **A tela mente sobre o câmbio.** O header diz "taxa do contrato" mesmo quando `is_market=True` — o comentário e o `title` ficaram do tempo em que a API tinha morrido | `pricing/templates/pricing/partner_base.html:177-179` | 🟠 |
| B3 | Estado `none` do câmbio é **inalcançável**: `Buyer.fx_usd_rate` tem default `0.14`, então nunca cai em "sem taxa do dia" — cai em bootstrap calado. Spec §2.7: *"nenhuma tela inventa número"* | `pricing/models.py:215` | 🟠 |
| B4 | Selo "Congelar" na lista sem rota nem botão que o resolva | `vendas/templates/vendas/partner_compras.html:87` | 🟢 |
| B5 | `_MATRIX_KINDS` definido e nunca referenciado — código morto | `pricing/views.py:122` | 🟢 |

---

## 6. Ordem de execução proposta

Cada etapa fecha sozinha, com teste, e não deixa a tela pela metade.

| # | Etapa | Depende de |
|---|---|---|
| **0** | Responder C1–C7 | — |
| **1** | B1 (idempotência do pagamento) + B2/B3 (verdade do câmbio) | — |
| **2** | Lista de compras: busca, status com contagem, período por despacho, ordenação, paginação | C2 |
| **3** | CSV da lista + badge do nav | 2 |
| **4** | `LotNote` + aba Observações + PDF com autoria "Conferência" | C4 |
| **5** | CSV por aba + modal de pagamento completo + carteira + rastreio clicável | 4 |
| **6** | `BlockedQuote` no resumo de preços | C2 |
| **7** | SSD + K9 nas telas de preço, piso do SSD | C3 |
| **8** | Catálogo parametrizado | 7 |
| **9** | Aplicar o design v2 em todos os templates do comprador | 1–8 |
| **10** | Celular (≤600px) + 4 idiomas das strings novas | 9 |

---

## 7. Fronteira — o que NÃO tocar

**Exclusivo do comprador (livre):** `vendas/urls_partner.py`, `vendas/views_partner.py`,
`vendas/templates/vendas/partner_compra*.html`, `pricing/urls.py`, **todo** o `pricing/views.py` (as 8 views
são `partner_*`), `pricing/templates/pricing/partner_*.html`, `static/wtc/` inteiro.

**Compartilhado — mexer é perigoso:**

| Arquivo | Quem mais depende |
|---|---|
| `pricing/models.py` | estoque, chips, tenancy, vendas, pages, 5+ management commands. Mudar `Price`/`STATUS_*`/`KIND_CHOICES`/constraint bate na **bancada**, no card de decode, na valoração de lote e na OV |
| `pricing/engine.py` | precificação do sistema inteiro |
| `pricing/pdf.py` | `_cjk_font`/`_draw_mixed`/`_rich` são importados por `vendas/pdf.py` (documentos do cliente) |
| `pricing/convention.py` | caixas físicas — número nunca reordena nem se reusa |
| `vendas/services.py` | `settle_and_invoice`/`register_payment`/`payment_history`/`confirm`/`cancel` também rodam pelo `vendas/views.py` (admin) |
| `vendas/pdf.py` | `render_result_pdf` divide o dicionário `_L`/`_t` com `render_so_pdf` (cliente) |
| `estoque/models.py` (`Lot`) | trava de câmbio, `closed_at`, `code` |
| `tenancy/scope.py`, `tenancy/access.py` | `company_scope`, RLS, `role_required` |
| `templates/partials/lang_select.html` | os dois mundos |
| `pricing/templates/pricing/price_block.html` | **NÃO é do comprador** — é da bancada do cliente (`confirm_card*.html`) |
| `core/urls.py` | a ordem dos dois includes em `/partner/` (há teste cravando `/partner/how/`) |

⚠ `partner_required` (o gate da superfície inteira) mora em `pricing/views.py:61-84`, **não** em
`tenancy/access.py`. Qualquer mexida nele é mexida em segurança.

---

## 8. Andaimes do protótipo que NÃO vão para produção (§10 da spec)

`demobar` · overrides em `localStorage` (`wtc_buys`) · `pns()` com gerador semeado · `fakeRef()` ·
`TODAY = "01/08"` · widget de câmbio clicável · máscara no cliente (`[data-wtc-needs]` — em produção o
endpoint **omite** o campo) · fixtures `parceiro-compras.js`/`parceiro-data.js`/`wtc-categorias.js`.

⚠ **As letras de categoria do protótipo (`E M U L F D K S`) são inventadas.** As reais estão em
`pricing/convention.py` (`KIND_LETTER`).

---

## 9. Estado da execução

### ✅ Etapa 1 — os três bugs (2026-08-26)

**B1 · Idempotência do pagamento** (spec §5.4)

| Arquivo | O quê |
|---|---|
| `vendas/models.py` | `Payment.idempotency_key` + `UniqueConstraint` **parcial** `payment_idempotency_per_invoice` (exclui `''`, senão o 2º pagamento manual de qualquer fatura seria recusado) |
| `vendas/migrations/0014_payment_idempotency.py` | gerada pelo Django (traz o churn de triggers do pghistory). Campo com `default=''`, **sem backfill** — roda em prod sem janela |
| `vendas/services.py` | `register_payment(..., idempotency_key='')`; **não** captura o `IntegrityError` — quem abriu o `atomic()` é que sabe até onde desfazer |
| `vendas/views_partner.py` | chave no contexto da ficha (uma por página servida) + duas guardas: checagem rápida antes de gravar e `except IntegrityError` para a corrida |
| `vendas/templates/vendas/partner_compra.html` | `<input type="hidden" name="idem">` no modal |

Duas guardas porque cada uma pega um caso: o 2º POST que chega **depois** do 1º commitar (a view responde "já registrado" sem tocar no arquivo) e os dois POSTs **simultâneos**, que só o banco separa.

**B2 · O `title` do cabeçalho mentia.** Dizia "taxa do contrato" mesmo com mid-market vivo — texto do tempo em que a API tinha morrido, que sobreviveu à volta dela. Agora o título tem três formas, uma por estado, e o subtexto e o título deixaram de se contradizer.

**B3 · Estado do câmbio nomeado.** `fx_display()` passou a devolver `state` ∈ `market · fallback · bootstrap` (`none` = retorno `None`). O template não re-deriva mais de dois booleanos — `fallback` lido como "mercado" fazia a taxa de ontem passar por taxa de hoje, calada. **Sem mudança de comportamento para o cliente**: a chave é aditiva, `is_market`/`is_fallback` seguem iguais (a bancada usa `price_block.html`).

**Testes escritos** (não rodados aqui — ver abaixo):
- `vendas/tests.py::CompradorPagamentoTests` — 6 testes novos: duplo-clique registra uma vez · comprovante do repetido não fica órfão · página recarregada é intenção nova · pagamento sem chave continua repetível · a trava é do banco, não da view · a ficha serve a chave e ela muda a cada carga.
- `pricing/tests.py::FxEstadoNomeadoTests` + `CabecalhoDoParceiroNaoMenteSobreATaxaTests` — 6 testes: os três estados + o `fallback` que não se disfarça de `market` + a regressão do `title` nos três casos.

**i18n:** 6 msgids novos, traduzidos nos 3 catálogos (`en`/`es`/`zh_Hans`), `.mo` recompilados. O `title` antigo virou **obsoleto** (convenção gettext), não foi apagado. Zero strings sem tradução.

### ✅ Etapa 2 — o recorte da lista de compras (2026-08-26)

O `MVP de propósito: sem filtro nem paginação` acabou.

| Onde | O quê |
|---|---|
| `vendas/services.py` | `purchase_haystack` · `purchase_counts` · `filter_purchases` · `sort_purchases` + `PURCHASE_SORTS`/`PURCHASE_PERIODS` |
| `vendas/views_partner.py` | `_recorte()` (uma leitura só para a tela e para o CSV) · `compras_list` com paginação · `compras_csv` |
| `vendas/urls_partner.py` | `/partner/compras/export.csv` — **antes** do `compras/<pk>/`, senão o resolvedor tenta `export.csv` como pk |
| `vendas/templates/.../partner_compras.html` | `.tbar` de recorte, cabeçalhos ordenáveis, coluna Resultado dupla, `.pgn` no rodapé, dois vazios diferentes |
| `static/wtc/patterns/parceiro.css` | `.tfoot__sum` — o `.tfoot` do pacote é `space-between` com UMA ponta; aqui a esquerda tem duas frases |

**Tudo em Python, e não é preguiça:** `orders_for_buyer` percorre uma empresa por vez dentro do
`company_scope` dela (é assim que o RLS deixa o comprador ler várias). Não existe queryset único onde
caiba um `.filter()` que valha para todas — a lista já nasce materializada. É também o que faz a
contagem de status sair correta de graça.

Quatro regras que parecem detalhe e não são:

1. **A contagem da opção vem do conjunto COMPLETO.** Sobre o recorte, toda opção não-selecionada
   mostraria `(0)` e o comprador concluiria que perdeu dado.
2. **Período filtra por DESPACHO**, não por criação. Ordem sem `shipped_at` (a confirmada legada) sai
   de qualquer recorte com período — não foi despachada em janela nenhuma, e fingir uma data seria
   inventar dado.
3. **O formulário não carrega `page`.** Trocar busca, filtro ou por-página volta à página 1 por
   construção, não por código. `sort`/`dir` viajam escondidos para a ordenação sobreviver.
4. **Vazio nunca é tabela vazia**: "Nenhuma compra ainda" (não há) × "Ajuste a busca" (há, o filtro
   escondeu). Situações diferentes, frases diferentes.

**Desvio consciente no CSV:** a spec pede a coluna `País` e a `Company` **não tem campo de país** — o
endereço é texto livre de propósito (cada país tem uma estrutura). A coluna virou
`Cliente — endereço`, que entrega o país e mais; a busca da tela já casa contra ele. São 14 colunas do
mesmo jeito. Se o dono quiser `País` de verdade, é campo novo em `tenancy.Company`.

**16 testes novos** em `CompradorComprasTests`. **21 msgids novos**, traduzidos nos 3 catálogos, com
`context` explícito em `de`/`até` (palavra solta é ambígua em 4 idiomas). Cobertura conferida por
script: 54 msgids das duas telas, zero sem tradução.

### 🔁 C2 CORRIGIDO — a regra §4.1 já valia

`sem_preco` e `a_congelar` **não são "lotes em aberto"**. `vendas/services.py:1321` (`mark_shipped`):

> ⚠ Padrão F8: NUNCA levanta. Categoria sem preço no grid do comprador não pode impedir de registrar
> que a caixa saiu — **o fato físico aconteceu**. A ordem fica em **rascunho DESPACHADO**, aparece para
> o comprador assim mesmo.

Esses lotes **estão a caminho dele**; só não deu para congelar o ¥. E o filtro já é a regra da spec:
`Q(shipped_at__isnull=False) | Q(status=STATUS_CONFIRMED)`. Tirá-los sumiria com caixa despachada —
foi o que aconteceu em 18/08 ("todas as compras do comprador sumiram"), e o comentário logo acima do
filtro é a cicatriz.

**Decisão revista:** a lista não perde ninguém. O `BlockedQuote` continua na Etapa 6, como **segunda
vista** no lado dos preços. E o selo "Congelar" sem botão vira gap de verdade — a decisão de 18/08 é
que **quem congela é o comprador**, e não existe rota para ele fazer isso.

### ✅ Etapa 3 — o badge do nav (2026-08-26)

```
badge = (caixas a conferir) + (dívidas em aberto)
```

| Onde | O quê |
|---|---|
| `vendas/services.py` | `buys_badge(buyer)` — **duas contagens por empresa**, sem materializar nada |
| `pricing/views.py` | `partner_required` anexa `request.buys_badge`, como já fazia com o 🔔 |
| `pricing/templates/.../partner_base.html` | `<span class="pnav__b" data-buys-badge>` no item Compras |

**Consulta própria, não `orders_for_buyer`:** o badge aparece em toda tela do painel (preços,
catálogo, como funciona), e a lista completa re-resolve cotação viva de cada rascunho contra o grid.
Caro demais para pagar em toda página só para desenhar um número.

**`open` já significa saldo > 0** — o `register_payment` vira para `paid` no instante em que zera, e é
invariante do modelo. Contar saldo de novo aqui seria repetir a conta em outro lugar, com uma chance a
mais de divergir.

**`sem_preco` NÃO entra.** É pendência real e só o comprador resolve — mas se resolve na tela de
**preços**. Somá-la aqui o mandaria para Compras, onde não há o que fazer a respeito. Ela aparece do
lado certo do balcão pelo `BlockedQuote` (Etapa 6).

**Zero é string vazia, nunca `0`.** Quem esconde é o `.pnav__b:empty{display:none}` do pacote — a tela
só precisa não escrever o número. Zero desenhado é ruído que treina o olho a ignorar o badge
justamente quando ele passa a significar alguma coisa.

5 testes (3 script + 2 interface) · 1 msgid novo nos 3 catálogos.

### ✅ Etapa 4 — a aba Observações (2026-08-26)

Antes: **uma** nota por compra, escondida num campo do acerto (`Settlement.notes`) — sem autor
visível, sem data visível, escrita uma vez no diálogo de fechar resultado e nunca mais. Se ele
lembrasse de algo depois — a caixa chegou molhada, faltou fita, o rastreio estava errado — não havia
onde pôr.

| Onde | O quê |
|---|---|
| `vendas/models.py` | `OrderNote` — autor e data do servidor, `created_by` SET_NULL, ordem cronológica |
| `0015_ordernote` · `0016_ordernote_rls` · `0017_backfill_ordernote` | tabela + RLS/FORCE + as notas que já existem |
| `vendas/services.py` | `order_notes` · `add_order_note` · `remove_order_note`; `settle_and_invoice` passa a criar a nota |
| `vendas/pdf.py` | a seção vira LISTA, cada nota com data e a assinatura `Conferência` |
| `vendas/views_partner.py` · `urls_partner.py` | `observacao` e `observacao_remover`, com `?aba=` de volta |
| `partner_compra.html` · `ficha.css` | a aba, o campo, a lista, e a aba de Pagamentos obedecendo a §6.3 |

**A nota do fechamento entra na MESMA lista.** Dois lugares para procurar o que o comprador escreveu é
um a mais. O `Settlement.notes` continua gravado como registro **interno** do acerto — quem fechou o
quê, com qual observação, naquele instante — mas a tela e o PDF passam a ler da tabela nova.

**A autoria é cortada na ORIGEM.** O `result_document` monta cada nota com **só `at` e `text`**; o nome
nem chega ao PDF. §7.1 manda a autoria virar *"Conferência"* no papel, e mascarar no desenho deixaria
o nome no contexto esperando alguém desenhar de novo. Há teste cravando que o dict tem exatamente
`{at, text}`.

**Só o autor remove**, e a recusa é uma mensagem só: 404 por não existir e 403 por não ser dele, juntas,
contariam que a nota existe.

**`?aba=` com vocabulário fechado.** Depois de registrar, o comprador volta vendo o que escreveu —
cair no Resumo daria a impressão de que não pegou. Valor livre viraria `hidden` em todas as abas e a
ficha ficaria sem miolo; fora da lista, cai em `resumo`.

**A aba de Pagamentos passou a obedecer a §6.3:** antes do resultado ela fica **desabilitada e
visível**, com contador `—` e o title dizendo quando acende. Não some — senão ele procura o histórico
numa tela onde nunca esteve.

**A lista de chaves das abas saiu do JS cravado à mão** e passou a sair dos próprios botões. A lista
antiga já teria deixado a aba nova sem esconder as outras.

9 testes (5 script + 4 interface) · 8 msgids novos nos 3 catálogos. Cobertura conferida: 139 msgids
nas três telas do comprador, zero sem tradução.

⚠ **Ordem de deploy, e esta é diferente das outras:** o código NOVO precisa da tabela — o
`result_document` e a ficha consultam `vendas_ordernote`. O `setup.sh` roda `migrate` no build, antes
do release novo servir, então o fluxo normal já está correto. O inverso também é seguro: migrar antes
de subir o código não quebra nada, porque o código velho ignora tabela nova.

#### Dois portões do dono pegaram a Etapa 4 — e um deles tinha razão

**1. Glifo (`vendas/tests.py`, o portão do packing list).** Escolhi `驗貨` para a assinatura
`Conference` e o teste acusou *"sem glifo para 驗 na fonte embutida"*. A fonte tem o caractere — o que
não tinha era o PDF: **glifo só entra na fonte embutida se o rótulo for desenhado**, e `checked_by` só
aparece no documento de RESULTADO, não no packing list. O próprio teste já excluía esse grupo
(`result`, `notes`, `sent`…) por essa razão exata; faltava `checked_by` na lista.

⚠ Mas isso abria um buraco: nenhum teste conferia os rótulos do documento de resultado. Criei
`test_script_o_PDF_do_resultado_tem_glifo_para_os_rotulos_DELE`, que renderiza **com nota** (sem ela o
`checked_by` não é desenhado e o teste conferiria uma fonte onde ele nunca entrou).

**2. "Nada abaixo da tabela".** Este pegou de verdade, e vale registrar por quê. A regra do dono
(19/08) é: *"lote grande faz a tabela ter centenas de linhas, e botão no fim dela é botão que ninguém
alcança."* O teste media do fim da planilha até o primeiro diálogo e exigia zero controles ali — e a
aba Observações põe um formulário exatamente nesse trecho **do documento**.

Só que a planilha está `hidden` quando aquela aba está aberta: o campo nasce colado na barra de abas,
não no fim de centenas de linhas. O teste media ordem no **DOM**; o que o dono pediu é ordem na
**TELA**. E o protótipo (`parceiro-lote.js`) confirma o desenho — Observações é aba, com o campo no
topo do painel.

A fatia passou a ir até o começo da aba seguinte (a cauda da planilha, que é o que a regra protege), e
ganhou a **outra metade da regra**, que a fatia sozinha não alcançava: o formulário de outra aba tem de
estar no **topo** do painel dela — painel próprio não basta se o campo estiver no fim de uma lista
longa de notas.

### 🧪 Regra permanente — teste em SCRIPT e em INTERFACE (dono, 2026-08-26)

Tudo que se implementa sai com as duas camadas:

- **script** — chamar a função/serviço direto, sem HTTP. Prova o contrato de quem mais vai usá-la
  (o CSV, um comando, um relatório) e falha apontando a função.
- **interface** — exercitar a rota e olhar o que foi servido. Prova o que a pessoa vê.

**Por que as duas, com prova do mesmo dia:** a Etapa 2 saiu com 16 testes de interface e zero de
script. O que escapou foi um `{# … #}` **multi-linha** — que no Django **não é comentário, é texto** —
vazando renderizado na tela do comprador, entre a barra de filtro e a tabela, e dentro do modal de
pagamento. Nenhum teste pegou porque todos perguntavam o que a página **tem** e nenhum perguntava o
que ela **não pode ter**.

Portão permanente criado em `vendas/tests.py::DesignSystemNaTelaDoCompradorTests`:
`test_script_nenhum_template_do_repo_tem_comentario_multilinha` (varre o disco — pega template que
view nenhuma exercita) e `test_interface_a_pagina_servida_nao_mostra_marcacao_de_template`
(`{#`, `{%` e `{{` não podem aparecer no HTML servido de nenhuma tela do comprador).

### 🔴 Achado fora do escopo — `PartnerSelfAccessRLS` está vermelho por um bug REAL

O commit `a6b2008` (19/08) já registrava este teste como vermelho conhecido, sem causa. A causa é esta:

**`pricing/0010_buyer_self_policy`** existe por causa de um bug de PRODUÇÃO de 2026-07-09: o parceiro não
tem `Membership`, logo o middleware não emite `app.company_id`, logo a policy devolvia zero linhas de
`pricing_buyer`, logo `partner_required` não achava o buyer → **403**. O conserto foi a cláusula de
auto-acesso:

```sql
OR id IN (SELECT buyer_id FROM pricing_buyer_users
          WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::int)
```

**`pricing/0021_comprador_plataforma`** (03/08) trocou a `tenant_isolation` por quatro policies
(`tenant_read`/`ins`/`upd`/`del`) — e **a cláusula de auto-acesso não foi para a de LEITURA**:

```python
_READ_WIDE = f"(company_id = {_GUC} OR {_PLAT} OR company_id IS NULL)"   # ← sem o parceiro
_WRITE     = f"(company_id = {_GUC} OR {_PLAT} OR {_PARTNER})"           # ← só aqui sobrou
```

**Por que produção não cai hoje:** a mesma migração rodou `_flip_para_plataforma`, que pôs `company=NULL`
em todo Buyer — e `company_id IS NULL` deixa a linha legível por qualquer um. O portão do parceiro
funciona por acidente do DADO, não pela policy.

**O que quebra:** no instante em que existir um Buyer com `company_id` preenchido — que o model continua
suportando (`company` é nullable, não foi removido) — o parceiro dele leva **403**. É o bug de 2026-07-09
de volta, dormindo.

**Segundo efeito:** o teste também crava *"e nada mais"*. Com leitura ampla por `company_id IS NULL`, dois
compradores de plataforma se enxergam. O cabeçalho da 0021 documenta esse residual para **escrita**
(*"hoje há UM comprador; o app escopa por buyer nas views"*); para **leitura** ele existe e não está
documentado.

**Conserto:** migração nova que devolve a cláusula à `tenant_read` do `pricing_buyer`. Só AMPLIA
visibilidade para os usuários do próprio buyer — não esconde nada de ninguém, e é reversível.

### ⚠ O que só roda na máquina do dono

O sandbox não alcança o Postgres (o `venv/` do repo aponta para um Python que não existe do lado montado). Foi verificado aqui: `manage.py check` limpo, os três templates compilam, os `.mo` resolvem nos 3 idiomas, e a migração foi **gerada pelo Django**, não escrita à mão.

Falta rodar:

```
python manage.py makemigrations --check --dry-run
python manage.py test vendas pricing
```

Depois: **deploy ANTES do migrate em prod** — o campo é `default=''` sem backfill, então o código velho convive com a coluna nova, mas a regra da casa é a regra da casa.
