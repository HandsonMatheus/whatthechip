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

**Decidido (dono, 2026-08-26):** (a) sim; (b) sim; (c) **editáveis com moderação** — ele propõe, a
plataforma aprova, e a taxa vigente continua valendo até lá. Ver **Etapa 7** no §9.

⚠ Duas correções ao levantamento acima, achadas ao implementar: o catálogo PDF **já tinha** a seção SSD
(uma linha, "por GB") — quem faltava lá era o **K9**. E o protótipo desenha o SSD com **seis classes**,
taxonomia que **não existe no repo**; ficou uma linha só, que é o que o dado suporta.

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
| **C3** ✅ | **Expor SSD e K9 ao comprador + criar o piso por peça do SSD**, **editáveis com moderação** (2026-08-26) | Migração nova em `pricing` — mas **aditiva**: campo nullable no `Buyer` + tabela nova (`RateChangeRequest`). Nada que a bancada lê foi alterado. SSD `form:linear` com capacidades derivadas e marca no piso; K9 uma linha, um campo |
| **C4** | **Model `OrderNote` novo + migrar as notas de acerto existentes** | O textarea do modal passa a criar a primeira nota. PDF imprime a lista com autoria **"Conferência"**. 1 linha de migração por `Settlement` com nota |
| **C5** | Comprovante: manter **5 MB + MIME sniffado** (contra os 10 MB da spec) | Ajustar só o texto da tela |
| **C6** | Manter `/partner/compras/<pk>/` (não trocar por código do lote) e as rotas em **inglês** | Não quebra link guardado; preserva o teste que crava `/partner/how/` |
| **C7** ✅ | Remover `/partner/lists/<pk>/` e `/partner/save/<pk>/` (órfãs) na v2 (2026-08-26) | Feito com teste cravando o 404 — e a cobertura que elas tinham desceu para a rota viva |

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

### 4.3 `BlockedQuote` — a fila de cotação travada ✅ (Etapa 6)

Derivado, não armazenado: agregação dos lotes em `sem_preco` por (tipo, linha), com `orders`, `units` e
`since` (data do lote travado mais antigo). Entregue em `vendas/services.py::blocked_quotes` — ver
**Etapa 6** no §9.

Spec §3.5 crava a distinção que importa: **lacuna** (`miss`, célula vazia que ninguém está vendendo, pode
esperar) × **travado** (lote já fechado que a plataforma não consegue precificar, **fila de trabalho**).

### 4.4 Catálogo parametrizado ✅ (Etapa 8)

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
| **0** ✅ | Responder C1–C7 | — |
| **1** ✅ | B1 (idempotência do pagamento) + B2/B3 (verdade do câmbio) | — |
| **2** ✅ | Lista de compras: busca, status com contagem, período por despacho, ordenação, paginação | C2 |
| **3** ✅ | CSV da lista + badge do nav | 2 |
| **4** ✅ | `LotNote` + aba Observações + PDF com autoria "Conferência" | C4 |
| **5** ✅ | CSV por aba + modal de pagamento completo + carteira + rastreio clicável | 4 |
| **6** ✅ | `BlockedQuote` no resumo de preços | C2 |
| **7** ✅ | SSD + K9 nas telas de preço, piso do SSD | C3 |
| **8** ✅ | Catálogo parametrizado | 7 |
| **9** ✅ | Aplicar o design v2 em todos os templates do comprador | 1–8 |
| **10** ✅ | Celular (≤600px) + 4 idiomas das strings novas | 9 |

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

**E o portão novo falhou — por um defeito da TÉCNICA, não do PDF.** Copiei do packing list a busca por
`<XXXX>` nos bytes crus. Só que o `ToUnicode` do PDF do resultado sai **comprimido** (FlateDecode), e a
busca crua não acha nada: `備註` e `驗貨` estão os **dois** na fonte — verificado chamando
`render_result_pdf` direto, fora do banco.

O helper `_pdf_codepoints` descomprime os streams e lê a tabela `bfchar` de cada fonte. **Os dois
portões passaram a usá-lo:** o do packing list dá a mesma garantia de hoje e para de ser refém de o
reportlab decidir comprimir aquele documento — no dia em que decidisse, acusaria falta de glifo que é
falta de zlib. Foi o que gastou meia hora aqui.

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

### ✅ Etapa 5a — CSV por aba + rastreio das seis transportadoras (2026-08-26)

**Uma rota por aba, não `?aba=`.** O nome do arquivo faz parte da entrega:
`LOT-EMI-041-08-26-chips.csv` diz sozinho o que é, meses depois, numa pasta de downloads. Código do
lote com `/` virando `-`, mesma convenção do PDF do resultado (§3.6).

**Aba desconhecida é 404, não fallback.** No `?aba=` da tela um valor inválido cai no resumo; aqui o
que sairia é um **arquivo**, e arquivo errado com nome certo é pior do que erro nenhum.

**O link segue a aba.** Um `<a>` só, com o href trocado pelo JS ao mudar de aba, servido já apontando
para a aba inicial (funciona sem JS). Exportar "a aba aberta" com o href da anterior entregaria o
arquivo errado com o nome certo — de novo, o pior dos dois.

**As três colunas de recusa só existem depois do recebimento** (§6.4): antes não há recusa para
relatar, e coluna vazia num export é pergunta sem resposta.

**`payment_kinds` — o "Registro" da parcela (§3.9), derivado e nunca gravado.** `integral` (zerou e foi
o primeiro) · `quitacao` (zerou e não foi) · `parcial`. Gravar um campo criaria uma segunda verdade que
envelhece no primeiro estorno. Tolerância `PAY_TOL = 0.004` (§2.5) — sem ela um resíduo de 3,6e-12 faz
um lote quitado dizer PARCIAL.

**CNY equivalente do pagamento é leitura derivada** pela taxa **travada** do lote, nunca pela de hoje.

**Rastreio:** as seis transportadoras da §3.13 (DHL, FedEx, UPS, SF Express, EMS, Correios). Fora da
lista o código fica em texto puro copiável — melhor sem link do que com link quebrado.

7 testes (5 script + 2 interface) · 9 msgids novos. Cobertura: 150 msgids nas três telas, zero sem
tradução.

⚠ **Dívida anotada:** a aba Categorias marca a caixa desta compra com um **booleano**. A §6.6 quer a
**quantidade** — *"dizer 'veio' é menos do que dizer quanto veio, e é a quantidade que se confere
contra a bancada"*. Mudar exige mexer no `category_glossary`, que não é exclusivo do comprador.

### ✅ Etapa 5b — carteira, saldo e o modal de pagamento (2026-08-26)

| Onde | O quê |
|---|---|
| `vendas/models.py` + `0018_wallet` | `Wallet` — a carteira que RECEBE, do WhatTheChip |
| `vendas/admin.py` | `WalletAdmin` — só a plataforma edita |
| `vendas/templatetags/wtc_ident.py` | filtro `meio` — corte no MEIO de identificador longo |
| `views_partner.py` | `carteira`, o par ¥=US$ do saldo, e o REGISTRO já traduzido em cada parcela |
| `partner_compra.html` + `ficha.css` | aba de Pagamentos com três blocos + o modal completo |

**A carteira é do WhatTheChip, nunca do vendedor.** Mandar o comprador pagar o vendedor direto pularia
a plataforma e quebraria as duas pernas do dinheiro de uma vez.

**Sem `company` e sem RLS, de propósito** — mesma razão do `FxRate`: não há dado por-empresa aqui. É UM
endereço, da plataforma, que todo comprador lê. Uma coluna de empresa criaria a pergunta "a carteira de
quem?", que não existe.

**Nasce vazia.** Inventar um endereço padrão seria pôr dinheiro de verdade a caminho de um lugar
imaginário. Sem carteira a tela **diz** que não há — endereço em branco é convite a colar o errado. E
`active` existe para **aposentar** em vez de sobrescrever: o histórico de para onde se mandou tem de
sobreviver à troca.

**Corte no MEIO, nunca no fim** (§6.2). `truncatechars` e o `text-overflow` do CSS entregam o começo —
e ninguém confere endereço de blockchain pelo começo, porque é o começo que os golpes imitam. O valor
inteiro vai no `title`, e **o botão copia o inteiro**, não o desenhado.

**No modal:** a ordem aparece primeiro porque é ela que vai no memo — sem o código, o dinheiro chega e
ninguém sabe de qual compra é. A conversão sai **exata, sem `≈`** (§2.8): com câmbio travado é
aritmética, não palpite. O atalho **Restante** traz o valor exato do saldo, não 100% arredondado — é o
clique que quita, e centavo perdido ali vira lote pago dizendo PARCIAL para sempre. A tolerância do JS
é a **mesma do servidor** (`0.004`), senão o próprio botão que quita seria o que trava.

**O rótulo do botão diz o que o clique FAZ**, não o que o formulário é: *Registrar quitação* × *…
parcial*, trocado ao vivo.

**A barra de progresso conta em US$** (§6.7): é em US$ que ele deve, e centavo de dólar é o que a
carteira move. O ¥ ao lado é leitura conciliável, derivada da taxa travada — nunca base de comparação.

8 testes (2 script + 6 interface) · 18 msgids novos nos 3 catálogos.

⚠ **Depois do deploy:** cadastrar a carteira em `/admin/vendas/wallet/`. Até lá a aba de Pagamentos
mostra "Carteira ainda não cadastrada" — que é o comportamento certo, não uma pendência de código.

### ✅ Etapa 6 — a fila de cotação travada (`BlockedQuote`, §3.5) (2026-08-26)

O `falta preço` do cliente visto **do lado de quem pode resolver**. A Etapa 3 decidiu não somá-lo ao
badge de Compras justamente porque lá não há o que fazer a respeito; aqui é onde ele aparece.

| Onde | O quê |
|---|---|
| `vendas/services.py` | `blocked_quotes(buyer)` — agrega os rascunhos sem preço por (tipo, linha) |
| `pricing/views.py` | `_travados(request)` (uma vez por request) · `_kind_nav` passa a devolver **duas** contagens · a faixa no Resumo · a marca por linha na grade |
| `partner_home.html` | a **faixa** no topo + a coluna dizendo `travando N pedidos` |
| `partner_kind.html` | o **aviso vermelho** no topo + a marca na linha exata |
| `partner_base.html` | o selo **vermelho** na barra de tipos, antes do âmbar |
| `parceiro.css` | `.blk*` (faixa) · `.blkw*` (aviso) · `.ptype__b--block` · o gabarito da barra com dois selos |

**Derivado, nunca armazenado.** Uma tabela `BlockedQuote` teria de ser mantida em sincronia com o grid a
cada preço aprovado — e cache que erra aqui manda o comprador cotar o que já cotou. É o bug de 2026-08-18
na outra ponta ("aprovei o preço e a lista continua dizendo que falta") esperando para acontecer de novo.
Há teste cravando que **cotar a linha esvazia a fila na leitura seguinte**, sem congelar nada.

**Duas contagens, duas marcas.** A barra de tipos tinha uma só, âmbar. Somar as duas apagaria a diferença
que decide o que ele abre primeiro:

| Marca | Conta | O que é |
|---|---|---|
| âmbar | **lacuna** | célula sem cotação numa caixa que ninguém está vendendo — pode esperar |
| vermelha | **travado** | lote **já fechado** que a plataforma não consegue precificar — fila de trabalho |

O vermelho vem **antes** do âmbar. E o gabarito da barra precisou mudar: `.ptype` era uma grade de duas
colunas e o segundo selo caía para a linha de baixo, sob o nome do tipo. `grid-auto-flow:column` resolve
sem tocar no caso de um selo só — coluna implícita só existe quando há item nela.

**`ordens` NÃO é a soma dos `orders` das linhas.** Um lote com duas categorias sem preço aparece nas duas
linhas; somar contaria o mesmo pedido duas vezes e a faixa mentiria o dobro. São conjuntos de `pk`.

**A geração DOBRA** (`fold_gen`), aqui como no motor: a chave gravada pode ser `LPDDR4X` e a linha que ele
edita é `LPDDR4`. Nomear a linha pela chave crua o mandaria procurar o que a tabela dele não tem.

**`since` é a data do LOTE**, não a da ordem. As duas coincidem em prod (o rascunho nasce NO fechamento),
mas quem manda no relógio é a caixa — e `created_at` fica só como fallback de dado anterior ao `closed_at`.

**⚠ A escolha desta etapa: conta TODO rascunho, despachado ou não.** `orders_for_buyer` esconde rascunho
antes do despacho — decisão do dono de 18/08, *"mostrar seria prometer caixa que ninguém postou"*. Aquilo é
a lista de **compras**: promessa de caixa. A fila não mostra compra nenhuma — a entrada é uma **linha do
grid**, e há teste cravando que ela não carrega lote, cliente nem vendedor. E o lote fechado hoje e ainda
não postado é o caso **mais** urgente: sem o preço dele a ordem não congela, não fatura e não recebe. Fila
que esconde metade dos itens não é fila.

*Se o dono preferir o contrário*, é uma linha: somar `.filter(Q(shipped_at__isnull=False))` ao queryset de
`blocked_quotes`. O efeito colateral é a fila passar a subestimar o trabalho, e a decisão fica documentada
no docstring da função.

**Três paradas, e por que não uma.** (1) A **faixa** no Resumo é a ordem em que ele deve abrir as tabelas
hoje — cada célula é um link para a grade que resolve, e ela **desaparece quando zera**: não é painel, é
fila. (2) A **coluna** do Resumo troca `N sem cotação` por `travando N pedidos`: as duas são verdade, só
uma explica a urgência, e a contagem exata está a um clique. (3) O **aviso no topo da grade** existe para
quem chegou pela barra e não pela faixa — sem ele o selo vermelho o larga numa tabela de trinta linhas sem
dizer qual delas trava.

**Na matriz por marca a marca vai no cabeçalho da linha**, e é o **número**, não a frase: a primeira coluna
é `sticky` e `nowrap`, e "travando 2 pedidos" a alargaria o bastante para empurrar colunas de marca para
fora da tela. A frase inteira está no `title` e, por extenso, no aviso do topo. Na tabela unificada, que
tem coluna Estado, a frase sai por extenso e **vence** o selo "Não cotado".

**A linha travada nem sempre existe no grid.** Quando a plataforma não consegue precificar porque a tabela
não **tem** a linha, não há o que marcar — e é por isso que o aviso do topo é separado da marca. Há teste
para esse caso.

**Sem grade, sem link**: a célula continua na fila, só não vira `<a>`. Esconder o que trava seria pior
que não ter para onde ir. *(Na Etapa 6 os dois casos eram SSD e K9; a Etapa 7 deu tela aos dois, e o
`if kind in _NAV_KINDS` passou a cobri-los — a salvaguarda fica de pé para o próximo tipo sem grade.)*

24 testes (14 script + 10 interface) · 6 msgids novos nos 3 catálogos.

⚠ **Asserção que não prova nada:** `assertIn('ptn-tag--block', html)` passa pelo **CSS embutido** do
`partner_base`, não pela tela. As asserções cravam a classe **como ela é servida** (`ptn-tag
ptn-tag--block`). Foi um `assertNotIn` que denunciou — o `assertIn` teria passado calado.

### ✅ Etapa 7 — SSD e K9 ganham tela (piso por peça, taxa moderada) (2026-08-26)

Os dois existiam no motor e no catálogo desde julho/agosto e o comprador **não tinha onde vê-los**: o
preço só se mexia pelo Django admin, e ele nem sabia qual era.

| Onde | O quê |
|---|---|
| `pricing/models.py` | `Buyer.ssd_floor_rmb` (o piso) + `RateChangeRequest` (a moderação das taxas) |
| `0027_ssd_floor_e_pedido_de_taxa` · `0028_ratechangerequest_rls` | tabela + RLS/FORCE no molde da 0021 |
| `pricing/engine.py` | `ssd_linear_rmb` · `ssd_piso_venceu` · `ssd_rmb` — a fórmula em UM lugar |
| `pricing/pdf.py` | `SSD_CAPS` + capacidades derivadas na seção SSD, e o **K9 que faltava** |
| `pricing/views.py` | `_RATE_KINDS`, `_contrato_ctx`, `_rate_post`, `_rate_mensagens`, o sino somando as duas tabelas |
| `pricing/admin.py` | `RateChangeRequestAdmin` — a fila irmã, com a mesma ordem de pendente-primeiro |
| `partner_kind.html` | o bloco de contrato: campo(s), o aviso de pedido em pé, as capacidades e o cálculo ao vivo |

**Por que TABELA NOVA e não afrouxar o `PriceChangeRequest`.** SSD e K9 não têm linha de grade — o preço
mora no `Buyer` porque não varia com marca, geração nem densidade. A FK `price` daquele modelo é
**obrigatória**. As três saídas eram: afrouxá-la (mexer na tabela que a bancada lê, com constraint e RLS
em cima), cunhar `Price` falso para SSD/K9 (duas fontes de verdade para o mesmo número — e o ¥/GB tem 3
casas, que `price_min` não guarda), ou tabela nova. A nova é a única que não põe em risco o que já roda.

**A moderação é a mesma, e o comprador não vê a diferença.** Uma frase só para os dois envios
(`_rate_mensagens`), e a decisão cai na **mesma** lista de notificações: ele pediu uma mudança de preço e
quer saber se passou — de que tabela ela saiu é problema nosso.

**O piso por peça** (§3.2): `preço(cap) = max(round(¥/GB × GB), piso)`. Nasce NULL, e NULL é *exatamente*
o comportamento de antes — nenhum preço muda até alguém pôr um número. O linear puro cobra ¥13 por um SSD
de 128GB e ¥102 por um de 1TB, mas manusear, testar e embalar custa o mesmo nos dois.

**Empate NÃO é piso** (`>` e não `>=`): piso igual ao linear não corrigiu nada, e marcar a célula ali
diria que o piso está mordendo quando não está. E a comparação é contra o **¥ inteiro** — senão um piso
de ¥13 "venceria" um linear de 12,8 e a linha sairia marcada sem mudar de número.

**A fórmula mora em UM lugar.** `engine.ssd_rmb` precifica o lote, a grade e o catálogo. O JS da tela
repete a conta porque precisa recalcular enquanto ele digita — e por isso repete o arredondamento
meio-pra-cima também: tela que promete um preço que a compra não pratica é pior que tela sem cálculo.

**No papel o piso é RÓTULO, não cor.** O catálogo é impresso e lido por quem não tem âmbar: `128 GB ·
piso`. Sem isso a célula viraria "a conta deles está errada".

**Capacidade derivada não tem campo.** Campo que não vira preço é promessa falsa. Há teste cravando que
a página inteira tem **dois** campos — a taxa e o piso.

**A legenda da planilha sai.** `x = não compro` e `não fabricado` são convenções de CÉLULA; numa taxa de
contrato não existem, e ensiná-las ali faria o comprador digitar um "x" que a tela recusa.

**O selo âmbar da barra conta a taxa em branco.** SSD e K9 não têm `Price` para contar, e zero ali seria
dizer "tabela completa" a quem não tem preço nenhum.

**Uma linha, não seis.** O protótipo desenha o SSD com seis classes (SATA TLC/QLC, M.2 SATA, M.2 NVMe
TLC/QLC, PCIe 4.0), cada uma com taxa e piso próprios. **Essa taxonomia não existe no repo** — nem no
modelo, nem no classificador — e criá-la não estava no C3. Ficou UMA linha, que é o que o dado suporta.

**⚠ O único ponto em que esta etapa cruza a fronteira do cliente** — e é de propósito. `_ssd_quote` é o
mesmo motor que valora o lote na bancada e desenha o card da busca. Com o piso preenchido, o SSD passa a
valer mais lá também. Está certo assim: o piso **é** o preço que o comprador paga, e a bancada existe
para mostrar esse preço. Enquanto o campo estiver NULL — que é como ele nasce — nada muda em lugar
nenhum. Fora isso, tudo o que a etapa acrescentou é aditivo: campo nullable, tabela nova, e três funções
novas no motor que ninguém mais chama.

30 testes (11 do piso + 19 da tela) · 24 msgids novos nos 3 catálogos.

⚠ **Teste existente alterado:** `PartnerKindNavTests::test_tipo_fora_da_navegacao_404` usava `ssd` como
exemplo de "tipo fora da navegação". A REGRA não mudou, só o exemplo (`nand`/`xyz`) — e o par novo
(`ssd`/`k9` → 200) foi cravado logo abaixo, para a mudança de decisão ficar **provada**, não subtraída.

⚠ **Asserção que não prova nada, de novo:** `assertIn('ptn-cell--unquoted', html)` passa pelo CSS
embutido do `partner_base`. Toda asserção de classe destas classes crava a forma **servida**
(`class="ptn-cell ptn-cell--unquoted"`). Foi um `assertNotIn` que denunciou — o `assertIn` teria passado
calado, pela segunda vez em dois dias.

⚠ **Depois do deploy:** conferir `ssd_rmb_per_gb`, `ssd_floor_rmb` e `k9_rmb_each` em
`/admin/pricing/buyer/`. O piso nasce vazio de propósito.

### ✅ Etapa 8 — o catálogo parametrizado, e a tela que o monta (2026-08-26)

Antes: um card na home com dois selects (`lang`, `currency`). Ele mandava a tabela **inteira**, sempre,
sem validade e sem recado.

| Onde | O quê |
|---|---|
| `pricing/pdf.py` | `CURRENCIES` · `GAPS` · `_rmb_txt`/`_usd_txt` · `catalog_data(kinds, gaps)` · `render_catalog_pdf(fx, valid_until, cover_note)` |
| `pricing/views.py` | `_catalogo_tipos` · `partner_catalog` (a tela) · `_data_iso` · o gerador lendo GET **e** POST |
| `pricing/urls.py` | `catalogo/` (a tela); `catalog.pdf` continua sendo quem gera |
| `partner_catalog.html` + `parceiro.css` | a tela de duas colunas, os filtros, o painel escuro e a conta do rodapé |
| `partner_base.html` | **Catálogo** virou item de nav |
| `partner_home.html` | o card perdeu o formulário e virou **porta** |

**Seleção por EXCLUSÃO, nos dois lados.** A tela nasce com tudo marcado; o gerador trata `types` ausente
como **todos**. Uma lista de inclusões faria um POST antigo produzir um PDF vazio — e o comprador não
entenderia por quê. Assim tipo novo entra no catálogo sozinho, sem ninguém lembrar de marcá-lo.

**Todo parâmetro novo tem default, e o default é o de julho.** Há teste comparando o texto extraído do PDF
de um link guardado com o de um link novo: catálogo é coisa que se guarda.

**⚠ DESVIO da spec: `gaps` é `hide|show`, não `hide|dash`.** A spec manda publicar a lacuna como `—`. Mas
neste documento `—` **já é** "não fabricado" (`_SYM_NOT_MADE`), e a legenda o explica desde julho. Dar o
mesmo glifo a duas coisas numa tabela que circula para terceiros é o tipo de ambiguidade que custa
dinheiro: *"não existe"* e *"ainda não decidi"* são respostas diferentes para o vendedor. O modo de
publicar usa o que a legenda já define — **em branco: ainda sem cotação**.

**`hide` não engole linha com marca cotada.** Na matriz, some só a linha em que **nenhuma** marca tem
preço — uma cotada ainda é preço que o cliente dele compra. E seção que fica sem linha nenhuma **não
entra**: um título sozinho no papel faria o vendedor ler "LPDDR" e concluir que o comprador não compra
LPDDR.

**Moeda: `both` é um TERCEIRO valor, não uma troca.** `rmb` e `usd` continuam idênticos, e o default
segue `usd`. Nenhum documento existente muda. A tela oferece os dois da spec (`¥ RMB` e `¥ RMB + US$`), e
**sob câmbio ausente a opção com dólar nem aparece** — select que oferece dólar e devolve PDF sem dólar é
pior que select com uma opção só. O gerador tem a rede de baixo para o link forjado.

**🔴 Bug achado ao PROVAR o PDF: o `≈` virava `»`.** U+2248 não existe em WinAnsi/Helvetica e o reportlab
o substitui **em silêncio** — o rodapé saía dizendo `1 ¥ » US$ 0.1478`. A convenção do til vive na TELA,
onde a fonte é web. No papel a estimativa se declara em **palavras**, uma vez, no subtítulo: repetir um
símbolo duzentas vezes numa tabela é pior que dizer a frase uma vez, e um símbolo errado é pior ainda.
**Portão permanente**: nenhum texto do PDF pode conter `»`.

**Ler o PDF exigiu ferramenta.** O reportlab escreve os streams em **ASCII85 + Flate** — procurar a frase
nos bytes crus devolve `False` para tudo, e por um instante pareceu que nada tinha sido desenhado. Daí o
`_pdf_texto` em `pricing/tests.py`, que decodifica a cadeia e extrai os literais `(texto) Tj`. É o que
permite testar o que a PESSOA lê, e não o que o código acha que escreveu.

**Carimbo de taxa em TODA página.** Documento que circula solto: carimbo só na capa é carimbo que se
perde — a página que o cliente imprime e leva para a bancada costuma ser a do meio. Sem taxa, o rodapé
**diz** "sem taxa do dia" em vez de sumir: rodapé que às vezes traz a taxa e às vezes não deixa o leitor
sem saber se o documento é velho ou se o número não existe. O estado vem NOMEADO (`fx_display.state`,
Etapa 1) — ler `is_market` sozinho faria "mid-market" carimbar um número de anteontem.

**O card virou porta.** Dois lugares para gerar a mesma coisa é um a mais. E o nav ganhou o quarto item:
a spec desenha três porque o protótipo não tem "Como funciona" — aqui essa página existe, o dono a
construiu e há teste cravando a rota.

**SSD e K9 só aparecem na tela quando há taxa.** Sem ela o gerador pula a seção, e oferecer o tipo seria
uma caixinha que se marca e não muda o PDF: o rodapé contaria 8 de 8 tipos e sairiam 7 seções. Que a
lacuna deles apareça é papel do Resumo e do selo âmbar da barra.

**`not_made` não conta como linha** na cobertura (§3.3): ausência de PRODUTO não é linha de preço, e
contá-la faria a cobertura mentir para baixo em todo tipo com célula não fabricada.

**Sem JS a tela continua correta**: tudo nasce marcado e o formulário posta a seleção inteira. O script só
acrescenta busca, filtro de cobertura, o mestre `all`/`indeterminate` e a conta do rodapé — e a conta é da
**seleção inteira**, não do que está visível: filtrar é um jeito de achar, não de excluir.

31 testes (16 do gerador + 15 da tela) · 49 msgids novos nos 3 catálogos.

⚠ **Teste existente alterado:** `PartnerDashboardTests::test_catalogo_pdf` cravava `catalog.pdf` no HTML da
home. A REGRA é a mesma — o comprador chega ao catálogo a partir do painel —, mas o caminho ganhou um
degrau. As duas pontas ficaram cravadas: a home linka `/partner/catalogo/`, e a tela tem o form que posta
no `.pdf`.

### ✅ Etapa 9 — o desenho v2 nas cinco telas de preço, e o fim do `ptn-*` (2026-08-26)

Metade do painel já estava de roupa nova (Compras) e metade de roupa velha com peças novas costuradas.
Acabou. As cinco telas de preço falam o vocabulário do pacote, e as ~60 linhas de CSS de mão que viviam
no `<style>` do `partner_base` **saíram inteiras**.

| Tela | O que passou a usar |
|---|---|
| Resumo | `.phd` · `.seals` · `.blk` (a fila) · `.pkpi` · `.pdoor` · `.tile` + `.dtab` |
| Grade do tipo | `.phd` · `.seals` · `.gnote--blk` · `.grid2` + `.dtab` · `.tag` · `input.cell` · `.pfoot` |
| Catálogo | `.tbar` (a mesma barra de filtro das Compras) · `.tile` + `.dtab` · `.btn` |
| Como funciona | `.phd` · `.tile` · `.step4` · `.dtab` · `.faq` |
| Notificações | `.phd` · `.tile` + `.dtab` · `.tag` |

**O `.blkw` que inventei na Etapa 6 morreu.** O pacote já tinha `.gnote--blk` para exatamente isso — com
uma lição embutida que a minha versão não tinha: o SVG leva `flex:none` e tamanho FIXO, senão num aviso de
duas linhas ele vira um triângulo vermelho do tamanho da viewport e empurra a tabela para fora da tela.

**A MATRIZ ganhou coluna de Status.** Era ela que faltava desde a Etapa 6: por não existir, a marca de
"travando" tinha virado um número solto no rótulo, com a frase escondida no `title`. Agora cabe por
extenso, como na unificada.

**`data-label` em TODO `<td>`.** Abaixo de 600px a `.dtab` esconde o cabeçalho e a linha vira cartão. Sem
o rótulo, dois campos de preço lado a lado não dizem qual é o mínimo e qual é o máximo.

**Duas classes próprias, e só duas:** `.pkpi` (os três números) e `.pdoor` (a porta do catálogo). Não
reusei `.pmet`/`.quick` do pacote — aquelas são a lista rótulo→valor do painel da ficha e a fileira de
botões pequenos. Nome parecido, papel diferente; vestir com a classe errada é como um sistema de design
apodrece.

**🔴 O "Como funciona" não foi só roupa: o texto MENTIA em quatro pontos**, cada um por uma decisão
posterior que ninguém voltou para refletir ali —

| Dizia | Desde quando é falso |
|---|---|
| "Escolha uma **marca** no menu à esquerda" | 2026-07-27: a barra é por TIPO; marca virou coluna |
| "escolha o **estado** da linha" | v3: o seletor morreu, hoje é UM campo |
| "a taxa no topo é a do seu **contrato**" | PLANO_FX: é mid-market do dia; contrato é bootstrap |
| "o contador da página **Início**" | a seção passou a se chamar Preços |

Página que ensina errado é pior que página que não ensina: ela é lida com confiança. A tabela "o que você
digita na célula" passou a mostrar os quatro estados com o selo que a grade realmente desenha, e o FAQ
ganhou a pergunta que a Etapa 6 criou (*"o que é travando N pedidos?"*).

**As mensagens do Django viraram `.note`** do pacote, com o mapa `success→ok · error→dan · warning→warn ·
resto→info` num lugar só — em vez de a folha ganhar quatro apelidos para o mesmo componente.

### ✅ C7 — as rotas órfãs saíram (2026-08-26)

`/partner/lists/<pk>/` e `/partner/save/<pk>/` funcionavam e **nenhum link apontava para elas** desde que a
navegação virou por tipo. Rota viva que ninguém alcança é superfície para manter, testar e traduzir de
graça — e um segundo caminho para gravar preço, com regra própria, é onde os dois divergem calado.

**A cobertura não se perdeu — desceu para a rota viva.** Os três testes que valiam (ciclo de moderação
completo, recusa do valor ilegível, isolamento entre compradores) foram reescritos contra
`/partner/tipo/<kind>/enviar/`, com as mesmas asserções. O que morreu junto foi só o que era da página
morta: os filtros por tipo/estado dela. E a regra que aquele teste também guardava — *o comprador nunca vê
auditoria* — virou teste próprio na grade viva.

46 msgids novos nos 3 catálogos (21 na 9a + 25 na 9b) · 8 testes existentes atualizados, todos de
vocabulário ou de rota, **nenhuma regra alterada**.

⚠ **Nota de sandbox, não do repo:** a criação do banco de teste em memória passou de ~3s para ~37s nesta
máquina no meio da etapa, e estourou a janela de 45s do shell. Contornei com um `settings` descartável
FORA do repo apontando o banco de TESTE para arquivo, o que permite `--keepdb`. **Depois de qualquer
migração nova é obrigatório apagar o arquivo** — senão os testes rodam contra um esquema velho, que é a
única maneira de esse atalho mentir.

### ✅ Etapa 10 — a grade no telefone, e os quatro idiomas de verdade (2026-08-26)

#### O celular (≤600px)

A `.dtab` já vira cartão sozinha. O que faltava era o cartão **saber o papel de cada célula** — sem isso
as cinco caem numa pilha indistinguível, com o campo perdido no meio. É o mesmo problema que a
conferência do lote resolveu com `.dtab--conf`; a grade de preço é o **segundo** lugar do produto onde se
digita dentro de uma tabela.

| O quê | Como |
|---|---|
| Papéis de célula | `.g-lin` · `.g-st` · `.g-p` · `.g-pmax` · `.g-brand` · `.g-upd` |
| Modificador | `.dtab--grade` nas quatro tabelas da tela do tipo |
| Ordem do cartão | que linha é · como ela está · **quanto vale** |
| Campo | fileira inteira, **48px** de altura — acima do mínimo de 44 |
| Sai do cartão | a data da última atualização: referência não se lê com o dedo ocupado |

**A exceção do rótulo, e por que ela é exceção.** A regra do sistema é *"nenhum rótulo impresso"* — no
cartão a hierarquia substitui a legenda, e a `.dtab` zera o `::before` do `data-label` justamente para
isso. A grade precisa quebrar essa regra num ponto: numa linha com **faixa** há dois campos de preço, e
sem rótulo nada distingue o mínimo do máximo. Onde há ambiguidade real, legenda não é ruído — é o dado. O
estado continua sem rótulo: a pastilha se lê sozinha.

**Especificidade, não ordem de arquivo.** A exceção usa `.dtab.dtab--grade …` (0-4-1) contra o
`.dtab tbody td[data-label]` (0-3-1) que a apaga. Empatar em 0-3-1 e depender da ordem dos `<link>` é
como esta correção some no dia em que alguém reordenar o `<head>` — e some **calada**.

Fora da grade: a faixa da fila vira pilha, os três números viram dois por fileira, a porta do catálogo
desce o chevron, e o painel de opções do catálogo perde o `sticky` (numa tela curta ele cobriria a
seleção).

#### Os quatro idiomas

**🔴 Eu nunca tinha rodado o portão.** O projeto tem um `check_translations` que é o análogo i18n do
`validate_convention` — completude, placeholders, tags HTML, glossário protegido, frescor do `.mo` e PT
cru em template. A rotina da casa manda rodá-lo **depois de toda atualização de catálogo**. Eu adicionei
~120 msgids em cinco etapas e só o executei agora. Ele acusou **23 problemas**.

**22 eram um defeito DELE, que o meu trabalho fez aparecer.** O parser não conhecia `msgid_plural` nem
`msgstr[N]`, e o estrago era silencioso nos dois sentidos: a linha de continuação do plural era somada ao
**msgid** (uma entrada com dois `%(n)s` que nunca existiu), e `msgstr[0]`/`msgstr[1]` eram **concatenados
no mesmo campo**. As primeiras entradas plurais do projeto nasceram no painel v2 — até então o buraco não
tinha o que morder. Agora o parser lê plural, e `check_entry` confere **cada forma** contra o msgid, além
de exigir que singular e plural do ORIGINAL concordem entre si (se o português já divergir, nenhuma
tradução tem como acertar).

**1 era meu, e era de verdade:** em chinês eu tinha traduzido **Samsung** para 三星, no rótulo do K9.
Fabricante é token canônico — não traduz em idioma nenhum.

**Nove tokens da spec §9 faltavam no glossário:** `SSD · K9 · PCB · TLC · QLC · NVMe · SATA · M.2` (e o
`RMB`, que eu adicionei e **tirei de volta** — a lista canônica é de termos de PRODUTO, não do nome da
moeda; em chinês RMB é 人民币, e exigir a sigla obrigaria o comprador a ler o nome da própria moeda dele
em estrangeiro. O símbolo `¥` é que atravessa os idiomas, e já está em todas as strings).

**E o portão de `choices` pegou o modelo novo:** `RateChangeRequest.kind` tinha rótulos crus. Entrou na
lista de declarados como *rótulo = dado* — `SSD`/`K9` são os próprios tokens canônicos, e envolvê-los em
`_lazy` convidaria alguém a traduzir "SSD" um dia. O `review_status` do mesmo modelo **está** em `_lazy`:
ali o rótulo é palavra, não dado.

Resultado: **`Catálogos publicáveis ✓`** nos três idiomas, 936 entradas cada.

12 testes (7 script + 5 interface), entre eles o portão que crava que **toda célula da grade diz o que
é** — porque no telefone o cabeçalho some, e célula sem `data-label` nem classe de papel vira um valor
órfão no cartão.

⚠ **Uma asserção que não provava nada, de novo — e desta vez o defeito era o inverso.**
`assertNotEqual(t.gettext(msgid), msgid)` chamaria de "sem tradução" toda palavra que é igual nas duas
línguas (em espanhol *Catálogo* é *Catálogo*). E o `gettext()` devolve o próprio msgid **nos dois casos**
— ausente e idêntico —, então ele não serve de prova. O teste passou a perguntar se o msgid está no
catálogo COMPILADO, e guarda separado uma string que tem de mudar de forma, senão ele passaria com um
catálogo que só copia o português.

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

### ✅ CORREÇÃO — a suíte RODA no sandbox (2026-08-26, Etapa 6)

Eu escrevi aqui que os testes só rodavam na máquina do dono. **Estava errado**, e a correção vale mais que
o conserto de um teste: o `core.settings_test` usa **SQLite em memória** justamente para não precisar de
servidor de banco. O que o sandbox não alcança é o **Postgres** — e o que depende dele (RLS, `pgtrigger`)
já se marca `skip` sozinho.

Foi montado um venv descartável **fora do diretório montado** (`~/venv-wtc`, porque o `venv/` do repo tem
symlinks para um Python que não existe deste lado) com Django 5.2.15, `pghistory`, `psycopg2-binary`,
`polib`, `fontTools` e `openpyxl`. Com ele:

```
python manage.py test vendas   →  232 testes, OK
python manage.py test pricing  →  122 testes, OK (3 skipped: Postgres-only)
```

**A janela é de ~45s por comando** (cada chamada do shell é um processo novo, e processo de fundo morre
com ele). `vendas` leva ~25s e passa; a suíte inteira não cabe numa chamada — roda-se **por app**.

**O que continua fora:** qualquer coisa que precise de Postgres de verdade — `PricingRLSTests`,
`PartnerSelfAccessRLSTests`, `RLSHandshakeTests` e as policies das migrações. Essas o dono roda.

**O que isso muda no processo:** teste agora se roda ANTES de comitar, não depois de mandar. A Etapa 6
achou três defeitos meus assim — um módulo guardado em `setUpTestData` (que o Django tenta `deepcopy` e
não consegue), e duas asserções que casavam com o **CSS embutido** em vez da tela.

### ⚠ O que só roda na máquina do dono

O sandbox não alcança o **Postgres**. Verificado aqui, a cada etapa: `manage.py check` limpo, os templates
compilam, os `.mo` resolvem nos 4 idiomas, `vendas` e `pricing` verdes em SQLite, e as migrações foram
**geradas pelo Django**, não escritas à mão.

Falta rodar, com Postgres:

```
python manage.py makemigrations --check --dry-run
python manage.py test           # a suíte inteira, com RLS e pgtrigger de verdade
```

Depois: **deploy ANTES do migrate em prod** — o campo é `default=''` sem backfill, então o código velho convive com a coluna nova, mas a regra da casa é a regra da casa.

---

## 10. Realinhamento ao Claude Design — 2026-08-27

O dono apontou que o front estava diferente do projeto dele no Claude Design.
Estava. **O motivo não foi falta de acesso:** os protótipos vivos já estavam
no repositório, em `design_v2/ui_kits/whatthechip/`, listados na linha 12
deste próprio documento. A Etapa 9 foi construída a partir da spec e do pacote
de CSS, sem nunca abrir as telas. Registro isso aqui porque o erro não foi de
execução, foi de leitura — e é o tipo de erro que se repete se não ficar
escrito.

### O que os três zips novos trouxeram

| Pacote | Veredito |
|---|---|
| `handoff` | Os 5 documentos são **byte a byte idênticos** aos que já estavam no repo. A spec nunca mudou. |
| `design system` | `components.css` ganha **um** componente: `.mvd`. `patterns/parceiro.css` e `ficha.css` atualizados. |
| `front` | Todos os JS e CSS **idênticos** aos do repo. Só os 9 HTML diferem, e a diferença é de empacotamento (caminhos relativos). |

### `.mvd` — dinheiro em pé de igualdade

A regra veio escrita no próprio CSS e vale para tudo que vier depois:

- **`.mval`** = dinheiro como **consequência** (¥ grande, US$ menor em cinza).
  Estoque, triagem, painel.
- **`.mvd`** = dinheiro como **argumento**, para o ciclo de venda. As duas
  moedas no mesmo corpo, mesmo peso, mesma cor, ligadas por um `=` **literal**
  — à taxa travada, os dois valores são o mesmo dinheiro.
- O **`≈` vem uma vez na frente do par**, nunca uma por moeda: "dois tis dizem
  duas incertezas onde existe uma".

Aplicado nos três heróis da ficha do lote. **Não** aplicado na lista de
compras: ali ¥ e US$ são colunas separadas e ordenáveis, como no protótipo.

### O que saiu (invenções minhas que o design não tem)

`.pkpi` (a tira de três números da home) · `.pdoor` (a porta do catálogo) ·
`.catopt` (o painel de opções, virou o `.cat` do design) · `.dtab--grade` e as
seis classes de papel `.g-*` · `.wtc-calc` (o pacote tem `.calc`).

### O que ficou, contra o alinhamento, com o dono avisado

1. **`Como funciona` e `Notificações`** não existem no pacote do comprador do
   design. São duas telas nossas, com backend e testes. Ficam.
2. **O PDF não oferece «publicar como —»**: nesse mesmo documento o `—` já
   significa *não fabricado*. Duas coisas no mesmo símbolo é pior que a
   divergência.

### ⚠ O achado: o `data-label` que o pacote joga fora

O `parceiro-grid.js` emite `data-label` em toda célula da grade, com um
comentário dizendo que abaixo de 600px a linha vira cartão. **Nenhuma folha do
pacote imprime esse atributo** — o que existe é o contrário,
`.dtab tbody td[data-label]::before{content:none}`, duas vezes (no `@media` e
no `@container`), e o único `attr()` renderizado é o do `data-suffix`.

A convenção do sistema ("no cartão a hierarquia substitui a legenda") está
certa quase sempre. Quebra num lugar só, e é onde dói: a linha de eMCP tem um
campo de **mínimo** e um de **máximo**; empilhados sem cabeçalho e sem rótulo,
são dois retângulos vazios idênticos, e o comprador digita dinheiro em um deles
sem saber qual.

**Decisão do dono (2026-08-27):** abrir uma exceção nossa, escrita pela
**condição** e não por um modificador —
`.dtab:has(input.cell) tbody td[data-label]::before`. A tabela que tem campo é
a tabela onde a ambiguidade existe. A marcação segue idêntica à do protótipo,
célula por célula; o que muda é só a folha. Especificidade (0,4,2) contra
(0,3,2) do pacote — vence por peso, não por ordem de arquivo.

**Não restaurado:** a altura de toque de 48px nos campos, que também era da
Etapa 10. Não estava na decisão, e vale perguntar antes.

### Correções ao que eu havia relatado errado

- Eu disse que faltava o **seletor de idioma** no shell do comprador. Falso:
  já estava lá, via `partials/lang_select.html`.
- Eu disse que o **idioma do PDF** era função nova a implementar. Falso: o
  parâmetro `lang` já existia e funcionava em `partner_catalog_pdf`.

### Nota de operação: sem `msgfmt` nesta máquina

O GNU gettext não está instalado no Mac do dono e o `compilemessages` do Django
shella para ele. Os `.mo` desta rodada foram compilados por um escritor de
`.mo` em Python puro (formato do manual do gettext), com os plurais conferidos
por `ngettext` depois. Se o gettext for instalado um dia, o caminho normal
volta a funcionar sem nada a desfazer.

### Testes

`pricing 199` · `vendas 235` · `chips.tests_i18n 31`. Doze testes existentes
foram realinhados, cada um com o comentário do que mudou e por que a **regra**
não mudou. Três portões de regressão novos: o mecanismo paralelo não volta (na
marcação nem na folha), e a exceção do rótulo tem de existir nos dois at-rules.

### A conferência do lote — feita em 2026-08-27

A tabela passou de `.sst` para `.dtab dtab--conf`, e não por gosto: **todo** o
tratamento de celular que veio no pacote está escrito como `.dtab--conf .c-*`,
dentro do bloco de 600px. Com a tabela em `.sst` aquelas trinta regras não
pegariam em nada.

**Duas colunas novas, e são o motivo da passada:** «Aprovados» e «¥ resultado»,
por **linha**. Antes o aceito só existia como uma segunda linha de rodapé — um
total. O comprador via quanto sobrou no fim, mas não via o que **cada** recusa
custou, que é a leitura de que ele precisa enquanto digita. As três colunas do
resultado são tingidas pelo grupo do pacote: `.hr` a recusa, `.hg` o aprovado,
`.hb` o dinheiro. A faixa de cada marca ganhou subtotal nas três, e
`services.result_rows` ganhou `pago_rmb` por grupo para isso.

**A barra viva (`.conflive`)** só existe no telefone. Nasce preenchida pelo
servidor — no protótipo ela só era escrita pelo `live()`, e `live()` só roda no
input, então quem abria a aba via uma faixa preta vazia até tocar o primeiro
campo.

#### ⚠ Buraco antigo, achado por um teste novo

O template decidia a existência das colunas de resultado só por
`pode_acertar`, que responde *"ele pode digitar recusa agora?"* e vira falso
assim que a fatura nasce. Consequência: **no instante em que o comprador
fechava a conferência, ele perdia a vista do que tinha recusado.** A informação
continuava no banco e sumia da tela dele.

Quem decide isso agora é `tem_resultado` — *"a conferência já aconteceu?"*. A
tela não muda de **forma** quando a etapa passa; muda só o que aceita toque. É
a mesma distinção que a tela do cliente (`vendas/views.py`) já fazia desde
2026-08-18; a do comprador tinha ficado para trás.

### O que fica para depois

**A folha do resultado** — `.pr--dif` e a família
`.pr__ad/__adk/__cust/__custd/__custn/__sign/__tot/__two`, com os estados
`EM CONFERÊNCIA` / `CONFERIDO`. Fora por decisão do dono (2026-08-27): o
comentário do próprio design a descreve como "o documento que o comprador gera
e o **cliente** recebe" — nasce no comprador e encosta no cliente, e a regra
desta empreitada é não tocar no cliente. O CSS dela **não** foi trazido; sai do
pacote pronto no dia em que ele liberar.

**A altura de toque de 48px** nos campos da grade de preço (a da conferência já
tem, veio no pacote). Era da Etapa 10, não entrou na decisão de realinhamento,
e vale perguntar antes.

**Fora de escopo por decisão do dono (2026-08-27):** a folha do resultado
(`.pr__ad/__cust/__custd/__custn/__sign/__two`, estados `EM CONFERÊNCIA` /
`CONFERIDO`). O comentário do próprio design a descreve como "o documento que o
comprador gera e o **cliente** recebe" — nasce no comprador e encosta no
cliente, e a regra desta empreitada é não tocar no cliente.
