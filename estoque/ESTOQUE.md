# ESTOQUE.md — Documentação Completa do Sistema de Inventário WTC

> **Para o próximo agente:** leia este arquivo antes de tocar em qualquer arquivo
> dentro de `estoque/`. Ele cobre o "porquê", o "como" e o "onde" de cada decisão.
> O CLAUDE.md da raiz continua sendo o índice geral do projeto; este documento
> aprofunda exclusivamente o app `estoque`.

---

## 1. O que é o sistema de estoque e qual problema resolve

O app `estoque` é o **módulo de triagem de bancada** do WhatTheChip. Um operador
lê o código gravado a laser num chip recuperado, digita no campo de busca, e o
sistema decide em tempo real:

1. **O chip é identificável?** (specs reais ou só chip desconhecido)
2. **O chip é de uma fonte confiável?** (confirmado no banco ou só gramática)
3. **O chip é rentável?** (avaliação comercial baseada em tipo/geração/capacidade)

Com base nessas três perguntas, o sistema direciona o chip para um de quatro
**destinos**:

| Destino | Cor | O que acontece |
|---|---|---|
| `aprovado` | Azul | Entra no `InventoryEntry` do lote ativo |
| `fila` | Laranja | Vai para `PendingEntry` — gestor aprova/reprova no admin |
| `reprovado` | Vermelho | Vai para `RejectedEntry` (log de auditoria) — resíduo eletrônico |
| `desconhecido` | Cinza tracejado | Vai para `UnknownChip` — chip sem specs identificáveis |

O sistema está organizado em torno de **lotes** (`Lot`): cada compra/fornecedor
vira um lote numerado sequencialmente. O operador abre um lote, digita chips
unitariamente, e fecha quando terminar a triagem.

---

## 2. Arquitetura de arquivos

```
estoque/
├── models.py              ← 4 modelos: Lot, InventoryEntry, PendingEntry, RejectedEntry
├── views.py               ← toda a lógica: helpers, gateway, CRUD de lotes
├── urls.py                ← 9 rotas sob app_name='estoque'
├── admin.py               ← admin com ações de aprovação/reprovação
├── migrations/
│   ├── 0001_initial.py    ← InventoryEntry original com operator FK
│   ├── 0002_*.py          ← add brand field
│   ├── 0003_lot.py        ← criação de Lot; lot FK nullable em InventoryEntry
│   ├── 0004_lot_seed.py   ← data migration: cria Lotes existentes, vincula entries
│   ├── 0005_lot_required.py ← lot FK NOT NULL; remove operator; unique(lot,pn)
│   ├── 0006_*.py          ← classification_source max_length
│   ├── 0007_pendingentry.py ← criação de PendingEntry com todos os campos snapshot
│   ├── 0008_*.py          ← alter PendingEntry id
│   └── 0009_rejectedentry.py ← criação de RejectedEntry (BigAutoField, sem unique)
└── templates/estoque/
    ├── base_estoque.html            ← IBM Carbon UI shell
    ├── lotes.html                   ← grid de cards de lotes
    ├── estoque.html                 ← tela principal da bancada (~1550 linhas)
    └── partials/
        ├── confirm_card.html        ← card de triagem com stepper (HTMX target)
        ├── table_body.html          ← lista do estoque (HTMX target #table-body-wrap)
        ├── pending_feedback.html    ← feedback após envio para fila
        ├── rejected_feedback.html   ← feedback após descarte (por rentabilidade ou geração)
        └── unknown_feedback.html    ← feedback após registro de chip desconhecido
```

---

## 3. Modelos de dados (`estoque/models.py`)

### 3.1 `Lot`

Representa um lote físico de chips (uma compra, um fornecedor, uma remessa).

```python
number       = IntegerField(unique=True)       # auto-incrementado (next_number())
operator     = FK(User)                        # operador dono do lote
description  = CharField(max_length=255, blank=True)
status       = CharField(choices=['open','closed'], default='open')
created_at   = DateTimeField(auto_now_add=True)
closed_at    = DateTimeField(null=True, blank=True)
```

Métodos relevantes:
- `Lot.next_number()` — classmethod que incrementa o último número existente
- `lot.is_open` — property: `status == 'open'`
- `lot.chip_count` — property: número de PN distintos no lote
- `lot.total_qty` — property: soma de quantidades de todos os entries

### 3.2 `InventoryEntry`

O estoque aprovado. Cada linha = PN único por lote.

```python
lot                  = FK(Lot)
part_number          = CharField(max_length=120)
chip_type            = CharField(max_length=80, blank=True)
brand                = CharField(max_length=60, blank=True)
capacity             = CharField(max_length=30, blank=True)    # bytes: "512MB", "16GB"
emcp_ram             = CharField(max_length=40, blank=True)    # "LPDDR3 1GB"
emcp_nand            = CharField(max_length=40, blank=True)    # "16GB"
is_emcp              = BooleanField(default=False)
interface            = CharField(max_length=30, blank=True)    # "x16", "x32"
classification_source = CharField(max_length=60, blank=True)  # "banco de dados", "gramática"
quantity             = PositiveIntegerField(default=1)
added_at             = DateTimeField(auto_now_add=True)
last_updated         = DateTimeField(auto_now=True)

# Constraint: unique(lot, part_number)
```

Propriedade `display_capacity`: monta uma string legível para exibição na UI
(ex.: "EMCP 16GB + LPDDR3 1GB", ou só "16GB").

### 3.3 `PendingEntry`

Chips identificados mas **não confirmados** no banco (só gramática). Aguarda
decisão do gestor no admin.

```python
lot                  = FK(Lot)
operator             = FK(User)
part_number          = CharField(max_length=120)
# Campos snapshot (cópia do resultado do classify() no momento da submissão):
chip_type            = CharField(max_length=80, blank=True)
brand                = CharField(max_length=60, blank=True)
capacity             = CharField(max_length=30, blank=True)
emcp_ram             = CharField(max_length=40, blank=True)
emcp_nand            = CharField(max_length=40, blank=True)
is_emcp              = BooleanField(default=False)
interface            = CharField(max_length=30, blank=True)
classification_source = CharField(max_length=60, blank=True)
nearest_confirmed    = CharField(max_length=120, blank=True)   # PN próximo no lote
confidence           = CharField(max_length=30, blank=True)
quantity             = PositiveIntegerField(default=1)
created_at           = DateTimeField(auto_now_add=True)

# Constraint: unique(lot, part_number)
```

### 3.4 `RejectedEntry`

Log de auditoria para chips recusados (NÃO RENTÁVEL ou NÃO RENTÁVEL por geração).
**Não tem unique constraint** — o mesmo PN pode ser recusado múltiplas vezes.

```python
lot                  = FK(Lot)
operator             = FK(User)
part_number          = CharField(max_length=120)
# Mesmos campos snapshot de PendingEntry
chip_type / brand / capacity / emcp_ram / emcp_nand / is_emcp / interface / classification_source
rejection_reason     = CharField(default='NÃO RENTÁVEL')   # ou 'NÃO RENTÁVEL (geração)'
created_at           = DateTimeField(auto_now_add=True)
```

---

## 4. O Gateway de Triagem (`_compute_gateway`)

O coração do sistema. Localizado em `estoque/views.py`. Recebe o `result` do
`classify()` e o flag `has_cap`, devolve um dict com:

```python
{
    'destination':    'aprovado' | 'fila' | 'reprovado' | 'desconhecido',
    'profitable':     'RENTÁVEL' | 'NÃO RENTÁVEL' | 'INDETERMINADO' | None,
    'profitable_key': 'rentavel' | 'nao_rentavel' | 'indeterminado' | '',
    'reject_by_generation': bool,    # True se reprovado por geração (não por capacidade)
                                     # ⚠ a chave REAL é 'reject_by_generation' (não 'by_generation');
                                     # confirme em views._compute_gateway._out e no confirm_card.html
    'steps': [
        {'label': 'Identificação', 'status': 'pass'|'fail'|'skip', 'detail': str},
        {'label': 'Fonte',         'status': ..., 'detail': str},
        {'label': 'Rentabilidade', 'status': ..., 'detail': str},
    ],
    'typo': {
        'has':         bool,
        'suggestions': list[str],
    },
}
```

### 4.1 Fluxo do gateway (ordem importa)

```
ATALHO GERAÇÃO (antes de tudo)
  ↓ is_dead_by_generation(result) AND NOT _is_confirmed(result)?
  → reprovado (by_generation=True) — tecnologia morta, age SEM confirmação e SEM capacidade

ETAPA 1 — Identificação
  ↓ has_cap? (specs reais no resultado)
  → desconhecido se não

ETAPA 2 — Fonte
  ↓ _is_confirmed(result)? (banco de dados ou confidence confirmed/manual)
  → fila se não (gramática-only)

ETAPA 3 — Rentabilidade
  ↓ assess_profitability(result)
  → reprovado se 'NÃO RENTÁVEL'
  → aprovado se 'RENTÁVEL' ou 'INDETERMINADO' (regra conservadora)

PARALELO (não bloqueia)
  typo: _nearest_in_lot() → sugestões de erro de digitação
```

### 4.2 Regra de ouro do gateway

**O gateway não tem regras de rentabilidade próprias.** Ele consome
`assess_profitability` e `is_dead_by_generation` do `chips/engine.py`.
Qualquer nova regra de negócio de rentabilidade vai em `assess_profitability`
e automaticamente é refletida no gateway — inclusive no atalho de geração.

Ver contrato completo: `docs/CONTRATO_RENTABILIDADE_GATEWAY.md`.

### 4.3 Por que INDETERMINADO → aprovado?

O sistema de rentabilidade ainda está imaturo para vários tipos. Um chip
INDETERMINADO pode ser valioso. Regra conservadora: é melhor aprovar um chip
duvidoso e descobrir depois do que perder material valioso. Só `NÃO RENTÁVEL`
claro bloqueia.

### 4.4 Por que o atalho de geração age sem confirmação?

Dois sabores de rejeição:
- **Por geração/era:** a gramática curada já sabe que a tecnologia é sucata
  (LPDDR2, DDR2, MCP legado). Seguro descartar mesmo sem banco confirmado.
- **Por capacidade:** um chip com 2GB pode ser gramática errada. Só reprova
  quando está confirmado no banco (valor de capacidade confiável).

---

## 5. Funções auxiliares em `views.py`

### `_is_confirmed(result)`
```python
source = result.get('classification_source', '')
confidence = result.get('confidence', '')
return source == 'banco de dados' or confidence in ('confirmed', 'manual')
```
Determina se o chip tem respaldo de fonte humana/oficial.

### `_snapshot(result)`
```python
# Converte None → "" para todos os campos CharField do snapshot
# Usando `result.get(key) or ""` (não `result.get(key, '')`)
# O `get(key, '')` não captura `key` presente com valor `None`
```
Previne `NotNullViolation` ao inserir `PendingEntry`/`RejectedEntry` para chips
não-eMCP (onde `emcp_ram`/`emcp_nand` são `None` no result).

### `_normalise_pn(raw)`
Caixa alta + remove não-alfanuméricos (exceto hífens). Ex.: `" k4x2g32 "` → `"K4X2G32"`.

### `_real_spec(val)`
Rejeita strings placeholder geradas pela gramática quando não consegue decodificar:
`"não mapead"`, `"consultar datasheet"`. Retorna `False` para esses casos.

### `_has_capacity(result)`
`True` se algum campo de capacidade tem spec real (não placeholder) OU se o chip
é known_exact com chip_type preenchido (banco confirmado com qualquer dado).

### `_extract_gb(text)`
Regex decimal-safe: `r'(?<!\d)(\d+(?:\.\d+)?)\s*GB'`
- Lookbehind negativo `(?<!\d)` evita pegar o "5" de "1.5GB"
- Suporte a decimais: "1.5GB" → 1.5
- Remove sufixo `.0`: "4.0" → "4"
- **Bug anterior (corrigido):** regex simples `r'(\d+)\s*GB'` pegava "5" de "1.5GB" → EMCP16+5 errado

### `_format_cap(text)`
Preserva a unidade original (MB ou GB). Ex.: `"512MB"` → `"512MB"`, `"16GB"` → `"16GB"`.
Usado no branch NAND para não perder chips < 1GB (antes usava `_extract_gb` que só lia GB).

### `_density_g(result)`
Extrai densidade do die em Gb para DRAM componente (DDR/GDDR):
1. Tenta `dram_density` (ex.: `"4Gb"` → `"4"`)
2. Se não, deriva da `capacity` (ex.: `"512MB"` → `"4"`, pois 512MB = 4Gbit)

### `_capacity_g(result)`
Extrai capacidade do pacote em GB para LPDDR (multi-die):
Lê de `capacity` (ex.: `"4GB"` → `"4"`).

### `_compute_destination(result)`
Monta o **rótulo da caixa física** e a **categoria** do chip. Retorna `(label, category)`.

| Categoria | Verifica | Formato do rótulo | Fonte dos dados |
|---|---|---|---|
| `emcp` | `is_emcp` e `emcp_nand` | `"EMCP{nand}+{ram}"` | `emcp_nand`, `emcp_ram` via `_extract_gb` |
| `umcp` | `chip_type` contém `umcp` | `"UMCP{nand}+{ram}"` | idem |
| `ufs` | `chip_type` contém `ufs` | `"UFS{cap}GB"` | `_extract_gb(capacity)` |
| `emmc` | `chip_type` contém `emmc` | `"EMMC{cap}GB"` | `_extract_gb(capacity)` |
| `gddr` | `chip_type` ou `subtype` contém `gddr` | `"{gen}+{density}G"` | `canonical_gen(subtype)` + `_density_g` |
| `ddr` | `chip_type` contém `ddr`/`ram`/`sdram`/`rdram` (sem gddr) | `"{gen}+{density}G"` | `canonical_gen(subtype)` + `_density_g` |
| `lpddr` | `chip_type` contém `lpddr` | `"{gen}+{cap}GB"` | `canonical_gen(subtype)` + `_capacity_g` |
| `nand` | `chip_type` contém `nand` | `"{cell} {cap}"` | `canonical_gen(subtype)` + `_format_cap` |
| `unknown` | fallback | `"Desconhecido"` | — |

**Ordem importa:** `gddr` vem ANTES de `ddr` para evitar falso positivo por
substring (`"gddr3" in "gddr3"` é True, mas `"ddr" in "gddr3"` também é True).

**`canonical_gen()`** de `chips/conventions.py` normaliza o `subtype` para o
token limpo da geração: `"LPDDR4 Mobile"` → `"LPDDR4"`, `"DDR3 SDRAM"` → `"DDR3"`,
`"SLC NAND paralela industrial"` → `"SLC NAND"`. É whitelist-based, fail-open.

### `_nearest_in_lot(lot, pn)`
Fuzzy matching por distância de Levenshtein contra todos os PNs já no lote.
Retorna o PN mais próximo se distância ≤ 3. Usado para sugerir "você quis dizer X?"
⚠️ Custo O(n) contra todos os `InventoryEntry` do lote — monitorar em lotes grandes.

---

## 6. Views (`estoque/views.py`)

### `lot_list` — `GET /estoque/`
Lista todos os lotes do operador logado. Renderiza `estoque/lotes.html`.

### `lot_create` — `POST /estoque/novo/`
Cria um novo lote com número sequencial e redireciona para `lot_detail`.

### `lot_detail` — `GET /estoque/lote/<lot_pk>/`
View principal do lote. Suporta filtros `?q=` (busca por PN) e `?tipo=` (filtro
por chip_type). Se for request HTMX (`HX-Request` header), retorna só o partial
`table_body.html`. Senão, renderiza `estoque.html` completo.

### `preview_chip` — `GET /estoque/lote/<lot_pk>/preview/`
Chamado via HTMX quando o operador termina de digitar o PN (trigger `pn-ready`).
Fluxo:
1. Normaliza PN; retorna HTML vazio se < 4 caracteres
2. `classify(pn)` → `result`
3. `_has_capacity(result)` → `has_cap`
4. `_compute_destination(result)` → `(destination, dest_cat)`
5. `_compute_gateway(result, has_cap)` → `gateway`
6. Busca `current_qty` no lote
7. Monta `display_cap` (especial para eMCP/LPDDR)
8. Renderiza `partials/confirm_card.html`

### `add_chip` — `POST /estoque/lote/<lot_pk>/add/`
Fluxo de decisão (ordem exata):

```
1. Lote fechado? → erro 400 (HTML inline)
2. PN inválido (< 4)? → erro
3. Reclassifica no servidor (não confia no form)
4. is_dead_by_generation AND NOT confirmed?
   → RejectedEntry(reason='NÃO RENTÁVEL (geração)') + rejected_feedback.html
5. has_cap == False?
   → UnknownChip.get_or_create + unknown_feedback.html
6. NOT confirmed?
   → PendingEntry (acumula qty se já existe) + pending_feedback.html
7. assess_profitability == 'NÃO RENTÁVEL'?
   → RejectedEntry(reason='NÃO RENTÁVEL') + rejected_feedback.html
8. Aprovado:
   → InventoryEntry (cria ou incrementa qty + last_updated=timezone.now())
   → Retorna table_body.html com HX-Trigger: 'est:added'
```

**Nota importante:** `last_updated` tem `auto_now=True` mas é atualizado
explicitamente em `.update()` via `last_updated=timezone.now()` porque
`auto_now` não funciona em querysets `.update()`.

### `remove_entry` — `POST /estoque/lote/<lot_pk>/remove/<entry_pk>/`
Recebe `qty_remove` do form. Se qty > 1 e qty_remove < qty total, decrementa.
Se qty_remove >= qty total, deleta o entry. Retorna `table_body.html` atualizado.

### `export_xls` — `GET /estoque/lote/<lot_pk>/export/`
Gera `.xlsx` via openpyxl. Cabeçalho com fundo IBM Carbon Blue (`#0f62fe`),
texto branco, bold. Colunas: PN / Marca / Tipo / Capacidade / Interface / Qty /
Fonte / Último acesso.

### `lot_close` / `lot_reopen` — `POST`
Atualizam `status` e `closed_at` do lote.

---

## 7. URLs (`estoque/urls.py`)

```python
app_name = 'estoque'

urlpatterns = [
    path('',                     lot_list,   name='index'),
    path('novo/',                lot_create, name='lot_create'),
    path('lote/<int:lot_pk>/',   lot_detail, name='lot_detail'),
    path('lote/<int:lot_pk>/preview/', preview_chip, name='preview'),
    path('lote/<int:lot_pk>/add/',     add_chip,     name='add'),
    path('lote/<int:lot_pk>/remove/<int:entry_pk>/', remove_entry, name='remove'),
    path('lote/<int:lot_pk>/export/',  export_xls,   name='export'),
    path('lote/<int:lot_pk>/fechar/',  lot_close,    name='lot_close'),  # POST
    path('lote/<int:lot_pk>/reabrir/', lot_reopen,   name='lot_reopen'), # POST
]
```

Todas as views são `@login_required`. Rotas de escrita são `@require_POST`.

---

## 8. Admin (`estoque/admin.py`)

### `LotAdmin`
Exibe: number, operator, description, status, created_at, closed_at.

### `InventoryEntryAdmin`
`list_filter` por `lot__operator` (não mais por `operator` direto — foi removido
da migration 0005).

### `PendingEntryAdmin`
Ações bulk:
- **`aprovar`**: para cada PendingEntry selecionado, cria um `InventoryEntry` com
  os dados do snapshot + chama `_confirm_as_knownpart()` para criar/atualizar um
  `KnownPart` com `confidence="manual"` e `status="enriched"`.
- **`reprovar`**: deleta o PendingEntry sem criar nada (operador descarta o chip).

`_confirm_as_knownpart(pending)` — função interna no admin:
- Cria ou atualiza `KnownPart` com os campos do snapshot
- Seta `confidence="manual"`, `status="enriched"`
- Isso faz o PN passar no `_is_confirmed()` na próxima triagem

### `RejectedEntryAdmin`
`list_display` inclui `rejection_reason` para distinguir "NÃO RENTÁVEL" de
"NÃO RENTÁVEL (geração)".

---

## 9. Templates

### `base_estoque.html`
- IBM Carbon UI shell: header dark (`#161616`), IBM Plex Sans/Mono do Google Fonts
- HTMX 2.0.4 carregado via unpkg
- Classe `wtc-panel` no body, `max-width: 1340px` na área de trabalho
- CSS variables IBM Carbon: `--bg`, `--surface`, `--surface-2`, `--surface-3`,
  `--text-primary`, `--text-secondary`, `--text-helper`, `--border-subtle`,
  `--border-default`, `--interactive` (#0f62fe), etc.
- `border-radius: 2px` em todos os elementos

### `lotes.html`
- Grid de cards (`minmax(320px, 1fr)`) via CSS Grid
- Formulário de criação no topo (descripção + botão "Criar Lote")
- Card: número monospace 28px, badge status (verde/cinza), descrição, chip_count,
  total_qty, datas, footer com botão "Abrir →" + Fechar/Reabrir
- Lote fechado: `opacity: 0.78` + `border-style: dashed`
- Dark mode: `[data-theme="dark"]` overrides para cores

### `estoque.html` (~1550 linhas)
**Layout:** 2 colunas — console de triagem (esquerda) + tabela do estoque (direita).

**CSS classes relevantes:**

| Classe | Função |
|---|---|
| `.est-steps` | Container do stepper de 3 etapas |
| `.est-step--pass` | Etapa aprovada (círculo verde #198038 com ✓) |
| `.est-step--fail` | Etapa reprovada (círculo vermelho #da1e28 com ✗) |
| `.est-step--skip` | Etapa pulada (círculo branco com número, borda cinza) |
| `.est-confirm--aprovado/fila/reprovado/desconhecido` | Root do card de triagem |
| `.est-dest--fila` | Painel de destino laranja (#ff832b) |
| `.est-dest--reprovado` | Painel de destino vermelho escuro (#750e13) |
| `.est-typo` | Banner amarelo para sugestões de erro de digitação |
| `.est-danger-led` | LED vermelho pulsante (chips perigosos/sucata) |
| `@keyframes est-danger-entrance` | Animação 3-pulso de atenção ao aparecer o card |
| `@keyframes est-row-flash` | Pulso amarelo 4s na linha adicionada ao estoque |
| `.est-toast` | Toast de confirmação no canto inferior direito |
| `.est-modal-overlay` / `.est-modal` | Modal de confirmação antes de deletar (Carbon) |

**Acessibilidade para bancada** (operador em pé, luz ruim, tela pequena):
- Input de PN: `height: 72px`, `font-size: 26px`
- Botões de ação: `height: 60px`
- Botão de delete na tabela: touch target `48×48px`
- Linhas da tabela: maior espaçamento

**JavaScript inline:**
- Forçar maiúsculas no input de PN
- Trigger `pn-ready` no HTMX após pausa de digitação
- `syncConfirmPn()` — sincroniza o valor do PN nos hidden inputs do form após
  HTMX swap (evita enviar o PN errado se o usuário editou)
- `openDeleteModal()` / `closeDeleteModal()` / `confirmDelete()` — modal de
  confirmação antes de remover entry; usa `htmx.ajax()` para o POST
- `showToast()` / `hideToast()` — toast com 5s de auto-dismiss e botão desfazer
- Debug button: delegação de eventos em `.est-debug-btn`, copia o JSON do
  `data-debug` formatado para clipboard

### `partials/confirm_card.html`
O card de triagem. Substituído via HTMX a cada decodificação.

**Estrutura:**
```
<div class="est-confirm est-confirm--{{ gateway_dest }}"
     data-debug="{{ result_json }}">
  <!-- Stepper: 3 círculos com linha conectora (hr absoluta em 17px top) -->
  <!-- Banner de typo (se gateway.typo.has) -->
  <!-- Painel de destino (min-height 168px) -->
  <!-- Form com todos os campos hidden + input qty + botões de ação -->
```

**Stepper visual:**
- Linha conectora: `<hr>` com `position: absolute; top: 17px; left: calc(...); z-index: 0`
- Círculo passe: fundo verde, `z-index: 1`
- Detalhe abaixo: label (11px bold) + "sim"/"não"/"—" em cor correspondente

**Painel de destino — cores por categoria** (só para `aprovado`):
- `emcp` → `#da1e28` (vermelho quente — produto de alto valor)
- `umcp` → `#ff7eb6` (rosa)
- `ufs` → `#f1c21b` (amarelo)
- `emmc` → `#42be65` (verde)
- `nand` → `#8a3ffc` (roxo)
- `gddr` → `#ff6900` (laranja queimado)
- `ddr` → `#795548` (marrom)
- `lpddr` / default → `#4589ff` (azul médio)

**Botões de ação condicionais:**
- `aprovado` → botão azul "+ Adicionar ao estoque" (hx-post → add; hx-target #table-body-wrap)
- `fila` → botão laranja "⏳ Enviar para conferência"
- `reprovado` → botão vermelho "✗ Registrar descarte"
- `desconhecido` → botão laranja "Registrar como desconhecido" (sem input qty)
- Sempre: "Cancelar" (borda preta, fundo branco) + 📋 debug (margin-left:auto)

**Campo qty:** input numérico com botões ▲▼ custom (sem spinner nativo do browser).

**Nota sobre `data-debug`:** usa `{{ result_json }}` sem filtro (auto-escape Django
produz `&quot;` que `getAttribute()` decodifica corretamente). **Não use `|escapejs`**
— isso escapa as aspas como `\"`, quebrando o atributo HTML.

### `partials/table_body.html`
Lista do estoque ativo. Cada `.wtc-stock-row` tem:
- PN como botão (clique re-decodifica o PN: preenche input e dispara `pn-ready`)
- Tag `chip_type`
- Quantidade
- Botão delete (48×48px, abre modal)
- Sub-linha: brand + display_capacity

Linha recém-adicionada: fundo `#defbe6` (verde claro) via `just_added` no context.

### `partials/pending_feedback.html`
Exibido após chip ir para fila. Mostra status laranja/warning, explica que o chip
não é confirmado, sugere separar fisicamente, e se houver `near` (fuzzy match no
lote), alerta que pode ser erro de digitação.

### `partials/rejected_feedback.html`
Exibido após descarte. Duas variantes via `by_generation`:
- `by_generation=True`: "Reprovado por geração — tecnologia obsoleta"
- `by_generation=False`: "Reprovado por rentabilidade — NÃO RENTÁVEL"

### `partials/unknown_feedback.html`
Exibido após chip desconhecido ser registrado em `UnknownChip`. Mensagem de
agradecimento, instrui a separar para análise posterior.

---

## 10. Relacionamento com `chips/engine.py`

O estoque **importa e consome** três funções do engine:

```python
from chips.engine import classify, assess_profitability, is_dead_by_generation
```

| Função do engine | Onde é usada no estoque |
|---|---|
| `classify(pn)` | `preview_chip` e `add_chip` — resultado base de tudo |
| `assess_profitability(result)` | `_compute_gateway` etapa 3 + `add_chip` bloqueio duro |
| `is_dead_by_generation(result)` | `_compute_gateway` atalho de geração + `add_chip` atalho |

**O estoque também importa:**
```python
from chips.models import UnknownChip   # chips desconhecidos
from chips.conventions import canonical_gen  # normalização de subtype para labels
```

### Como `is_dead_by_generation` funciona

```python
def is_dead_by_generation(result: dict) -> bool:
    return assess_profitability(_strip_capacity(result)) == "NÃO RENTÁVEL"
```

`_strip_capacity` remove todos os números de capacidade (`"LPDDR3 1GB"` →
`"LPDDR3"`, `"16GB"` → `""`). Se `assess_profitability` ainda devolve
`"NÃO RENTÁVEL"` sem os números, a rejeição é **por geração** (não depende
da capacidade). Chips assim vão para descarte **mesmo sem confirmação no banco**.

---

## 11. Convenção de campos por tipo de chip

Ver `docs/CONVENCAO_CAMPOS_ESTOQUE.md` para referência completa. Resumo:

| `chip_type` | Rótulo da caixa | Campos relevantes |
|---|---|---|
| `eMCP` | `EMCP{nand}+{ram}` | `emcp_nand` (GB), `emcp_ram` ("LPDDR3 1GB") |
| `uMCP` | `UMCP{nand}+{ram}` | idem |
| `eMMC` | `EMMC{cap}GB` | `capacity` em GB |
| `UFS` | `UFS{cap}GB` | `capacity` em GB |
| `RAM` (DDR/GDDR) | `{gen}+{density}G` | `subtype` (só geração), `dram_density` (Gb) |
| LPDDR standalone | `{gen}+{cap}GB` | `subtype` (só geração), `capacity` (GB do pacote) |
| NAND | `{cell} {cap}` | `subtype` ("SLC NAND"), `capacity` em MB ou GB |

**Regras absolutas:**
- `subtype` = SOMENTE célula (NAND) ou geração (RAM). Nunca densidade, barramento, voltagem.
- `dram_density` = die em **Gb** para DDR/GDDR componente
- `capacity` = pacote em **bytes** (GB ou MB) para LPDDR e Flash gerenciado
- `emcp_ram` = `"LPDDR{n} {cap}GB"` — tipo ANTES da capacidade

---

## 12. Especificidades por marca

### Samsung
- Maior fornecedor. Maioria dos chips passando pela bancada são Samsung.
- eMCP/uMCP: `K3` (eMCP LPDDR3), `K3R` (uMCP), `KLMAG` (eMMC)
- DDR/GDDR: `chip_type="RAM"`, `subtype` só a geração
- Referência completa: `SAMSUNG.md` na raiz

### SK Hynix
- Convenções similares ao Samsung
- Atenção: `populate_hynix.py` ainda tem subtypes verbosos (ex.: `"LPDDR3 Mobile"`)
  → `canonical_gen` corrige na hora, mas o ideal é limpar no populate
- Referência: `SK_HYNIX.md`

### Micron
- LPDDR standalone: `chip_type = generation` (ex.: `"LPDDR3"`), não `"RAM"`
- `capacity` = total do pacote
- FBGA code: 5 chars (ex.: `D9VFC`) → lookup via `KnownPart.fbga_code`
- API FBGA `part-name` **não é confiável para tipo de RAM** (BUG-8)
- Unidade: em PNs MTFC, "G" = **Gbit** (não GB): `64G = 8GB`
- Referência: `MICRON.md`

### PieceMakers
- Família PMF (DDR3): decode map próprio `PMF_DDR3_CAP`
- `chip_type="RAM"`, `subtype="DDR3"` — convenção idêntica a outras marcas DDR
- Referência: `PIECEMAKERS.md`

---

## 13. Histórico de migrations

| Migration | O que faz |
|---|---|
| `0001_initial` | InventoryEntry com `operator` FK direto, sem Lot |
| `0002` | Adiciona campo `brand` ao InventoryEntry |
| `0003_lot` | Cria modelo `Lot`; adiciona `lot` FK nullable ao InventoryEntry |
| `0004_lot_seed` | Data migration: cria 1 Lot por operador, vincula entries existentes |
| `0005_lot_required` | `lot` FK NOT NULL; remove `operator` de InventoryEntry; unique(lot, pn) |
| `0006` | Aumenta `max_length` de `classification_source` |
| `0007_pendingentry` | Cria `PendingEntry` com todos os campos snapshot |
| `0008` | Altera tipo do id de PendingEntry |
| `0009_rejectedentry` | Cria `RejectedEntry` (BigAutoField, sem unique constraint) |

---

## 14. Bugs corrigidos (histórico desta sessão)

### `_extract_gb` — decimal falso positivo
- **Sintoma:** `"LPDDR3 1.5GB"` → `_extract_gb` devolvia `"5"` (pegava o "5" antes de "GB")
- **Causa:** regex `r'(\d+)\s*GB'` sem lookbehind
- **Fix:** `r'(?<!\d)(\d+(?:\.\d+)?)\s*GB'` — lookbehind negativo + suporte decimal
- **Resultado:** `"EMCP16+5"` virou `"EMCP16+1.5"` corretamente

### `auto_now=True` não atualiza em `.update()`
- **Sintoma:** `last_updated` não era atualizado ao incrementar quantidade
- **Fix:** `InventoryEntry.objects.filter(...).update(quantity=F("quantity")+qty, last_updated=timezone.now())`

### `SystemCheckError E108` no admin
- **Sintoma:** após remover `operator` do InventoryEntry, admin.py ainda referenciava
- **Fix:** atualizar `list_display` e `list_filter` para usar `lot` e `lot__operator`

### `|escapejs` quebrando `data-debug`
- **Sintoma:** `{{ result_json|escapejs }}` escapava `"` como `\"`, quebrando o atributo
- **Fix:** usar `{{ result_json }}` puro — Django auto-escape usa `&quot;` que browsers decodificam

### GDDR falso positivo no `_compute_destination`
- **Sintoma:** `"GDDR3"` caía no branch DDR porque `"ddr" in "gddr3"` é True
- **Fix:** adicionar branch `gddr` ANTES do branch `ddr`

### `NotNullViolation` em PendingEntry/RejectedEntry
- **Sintoma:** `result.get('emcp_ram', '')` retorna `None` quando a chave existe com valor None
- **Fix:** `_snapshot()` usando `result.get(key) or ""` para todos os campos CharFields

### Label "NAND" sem capacidade
- **Sintoma:** chips NAND < 1GB exibiam só "NAND" (branch NAND usava `_extract_gb` que ignora MB)
- **Fix:** `_compute_destination` usa `_format_cap()` no branch NAND

---

## 15. Armadilhas conhecidas e limitações atuais

### Fuzzy matching em lotes grandes
`_nearest_in_lot` faz scan O(n) contra todos os `InventoryEntry` do lote. Para
lotes com > 500 PNs distintos, começará a sentir. Se necessário: pré-computar o
índice de PNs do lote em memória (set), ou usar trigram index no Postgres.

### `canonical_gen` é fail-open
Se um `subtype` não está na whitelist, passa intacto. O rótulo pode ficar verboso
se novos subtypes são adicionados sem atualizar a whitelist em `chips/conventions.py`.
Monitorar subtypes novos e adicionar à whitelist.

### Chips NOR/K5 — RESOLVIDO (2026-06-21: doc estava desatualizada)
`assess_profitability` **já tem** a regra capacity-independent (ver `chips/engine.py`,
hoje ~linha 1429):

```python
if chip_type.lower() in ("nand flash", "nor flash", "mcp", "epop"):
    return "NÃO RENTÁVEL"
```

Logo `is_dead_by_generation` retorna `True` para esses tipos e o atalho de geração
do gateway os reprova mesmo sem confirmação. **Cuidado (fragilidade):** o match é
por **string exata** de `chip_type` (`"nor flash"`, não `"nor"`). Se algum
`populate_*` gravar um `chip_type` ligeiramente diferente (`"NOR"`, `"NAND"`,
`"Raw NAND"`, `"MCP legado"`), a regra **não dispara** e o chip volta a cair em
INDETERMINADO → aprovado. O próprio `tests.py::test_confirmado_indeterminado_aprovado`
prova isso: `chip_type="NOR"` (sem "Flash") → INDETERMINADO. Mantenha os
`populate_*` gravando exatamente os tipos da whitelist. Ver §19.

### FBGA desconhecido enfileira em UnknownChip
Quando o operador digita um FBGA code (5 chars, padrão `^[A-Z][A-Z0-9]{4}$`), o
engine retorna resultado limitado. Se `_has_capacity()` falhar, vai para desconhecido.
O gestor precisa resolver na fila de FBGA noturna.

### PendingEntry acumula qty sem atualizar snapshot
Se um mesmo PN vai para fila duas vezes, a qty se acumula mas o snapshot não é
atualizado (mantém o primeiro). Se os campos mudaram entre as duas triagens, o
admin pode ver dados desatualizados. Aceitável por ora — a aprovação re-classifica.

### Cache do engine não é invalidado automaticamente
Após `populate_* --overwrite`, o servidor de produção serve o cache antigo até
reiniciar. O comando `populate_*` só chama `clear_engine_cache()` no próprio
processo. **Sempre reiniciar o servidor após populate em produção.**

---

## 16. Regras de ouro específicas do estoque

1. **O gateway não tem regras próprias de rentabilidade.** Qualquer nova regra
   de negócio (ex.: "NOR Flash = NÃO RENTÁVEL") vai em `assess_profitability`
   em `chips/engine.py`. O gateway consome — não reimplementa.

2. **`_snapshot()` para todos os inserts de PendingEntry/RejectedEntry.**
   Usar `result.get(key) or ""` — nunca `result.get(key, '')` — porque a chave
   pode existir com valor `None` para chips não-eMCP.

3. **`add_chip` reclassifica no servidor.** Nunca confiar nos hidden fields do
   form para tomar decisões de negócio. O form passa specs para acelerar o insert,
   mas a lógica de gateway re-executa `classify()` server-side.

4. **GDDR antes de DDR em qualquer comparação de substring.**
   `'gddr' in chip_type` deve vir antes de `'ddr' in chip_type`.

5. **`last_updated=timezone.now()` explícito em `.update()`.**
   `auto_now=True` não funciona em querysets — só em `.save()`.

6. **Toda rota de escrita é `@require_POST` + `@login_required`.**
   Sem exceções.

7. **Não reimplementar destino de lote fora de `_compute_destination`.**
   Assim como `assess_profitability` é fonte única de rentabilidade, `_compute_destination`
   é fonte única do rótulo de caixa.

---

## 17. O que o próximo agente deve fazer (tarefas pendentes)

### Atualizar `CLAUDE.md` (obrigatório)
O CLAUDE.md da raiz deve ser atualizado para:
- Mencionar o app `estoque` na seção de Apps Django (§4)
- Adicionar as armadilhas específicas do estoque (§7)
- Mencionar `estoque/ESTOQUE.md` na seção de Documentação profunda (§9)

### ~~Fixar NOR/K5 em `assess_profitability`~~ — FEITO (2026-06-21)
Regra implementada em `chips/engine.py`: `chip_type.lower() in ("nand flash",
"nor flash", "mcp", "epop") → NÃO RENTÁVEL`. Pendência remanescente: garantir que
os `populate_*` gravem exatamente esses `chip_type` (o match é por string exata —
ver §15 e §19). Sem isso, variações como `"NOR"` escapam.

### ~~Consertar o teste vermelho `test_caixa_dram_geracao_mais_densidade`~~ — FEITO (2026-06-21)
Asserções defasadas em DUAS dimensões corrigidas: categoria DDR/DDR3L `'lpddr'`→`'ddr'`
e rótulo LPDDR `'+NG'`→`'+NGB'` (convenção CLAUDE.md §6). Suíte agora **17/17 verde**.

### ~~Recomputar `has_cap` no servidor em `add_chip`~~ — FEITO (2026-06-21)
`add_chip` agora usa `has_cap = _has_capacity(server_result)` (regra de ouro #3),
não mais o hidden do form. 16 testes de integração seguem verdes.

### Achado 6 — copiar `subtype`/`density_gbit` no aprovar (PENDENTE — precisa migração)
`_confirm_as_knownpart` não persiste `subtype`/`density_gbit` ao `KnownPart` porque
o snapshot do `PendingEntry` nem os guarda. Fix completo exige: adicionar os dois
campos a `PendingEntry` + `_snapshot` (views) + **migração** (o usuário roda, regra
de ouro #1) + copiá-los em `_confirm_as_knownpart`. `is_emcp` não existe em
`KnownPart` (só em `ChipFamily`) — não copiar. Prioridade baixa.

### Limpar subtypes verbosos do `populate_hynix`
SK Hynix tem subtypes como `"LPDDR3 Mobile"` que o `canonical_gen` já corrige
no runtime, mas o ideal é corrigir na fonte.

### Considerar índice trigram para fuzzy matching
Se o volume de lotes crescer, substituir o scan O(n) de `_nearest_in_lot` por
`pg_trgm` do PostgreSQL com índice GIN.

### Tela de PendingEntry para o operador
Hoje, a gestão de PendingEntry é só via Django Admin. Considerar uma view
dedicada em `/estoque/fila/` para o gestor aprovar/reprovar sem precisar do admin.

### Log de auditoria de aprovações
Quando o admin aprova um PendingEntry via `_confirm_as_knownpart`, não há log
de quem aprovou e quando. Considerar adicionar `approved_by` e `approved_at`
ao modelo ou um `AuditLog` genérico.

---

## 18. Fluxo completo de uma triagem (fim a fim)

```
Operador digita PN no input da bancada
    ↓ (HTMX hx-trigger="pn-ready" após pausa)
preview_chip (GET)
    ↓ classify(pn) → result
    ↓ _has_capacity(result) → has_cap
    ↓ _compute_destination(result) → (label, category)
    ↓ _compute_gateway(result, has_cap) → gateway dict
    ↓ Renderiza confirm_card.html
Operador vê o stepper (3 etapas) + destino + botão de ação
    ↓ (operador confirma qty e clica no botão)
add_chip (POST)
    ↓ Reclassifica server-side (classify novamente)
    ↓ Decisão de destino (ordem: geração → desconhecido → fila → reprovado → aprovado)
    ↓ Insere no modelo correto (InventoryEntry / PendingEntry / RejectedEntry / UnknownChip)
    ↓ Retorna partial (table_body ou feedback)
Tabela do estoque atualiza via HTMX (hx-target="#table-body-wrap")
```

---

## 19. Revisão geral 2026-06-21 — parecer e achados

> Revisão completa de `estoque/` (views, models, admin, reconcile_core, urls,
> tests, templates, migrations) cruzada com `chips/engine.py`
> (`assess_profitability`, `is_dead_by_generation`, `_strip_capacity`) e
> `chips/conventions.py::canonical_gen`. **Suíte rodada:**
> `python manage.py test estoque --settings=core.settings_test` → **16 passam, 1
> falha** (detalhe abaixo).

### Parecer resumido

A arquitetura está **sólida e coerente**. O princípio de fonte única —
`assess_profitability` para rentabilidade e `_compute_destination` para o rótulo
da caixa — está respeitado, o gateway não reimplementa regra de negócio, e a
ordem das etapas em `preview_chip` e `add_chip` é a mesma (geração → desconhecido
→ fila → reprovado → aprovado). A separação Pending/Rejected/Unknown e o bloqueio
"só confirmados" estão consistentes com o que a doc descreve. Os achados abaixo
são pontuais; nenhum compromete a estrutura.

### Achado 1 — suíte de testes do estoque estava VERMELHA — CORRIGIDO (2026-06-21)

`estoque/tests.py::GatewayDestinationTests::test_caixa_dram_geracao_mais_densidade`
falhava. O método tinha asserções defasadas em **duas dimensões** (a 2ª ficava
mascarada pela 1ª, porque `assertEqual` para na primeira falha):

1. **Categoria CSS** — esperava `'lpddr'` para `DDR3L`/`DDR3`, mas
   `_compute_destination` (correto) retorna `'ddr'`. A categoria `ddr` (marrom) só
   foi separada de `lpddr` (azul) no split GDDR/DDR/LPDDR de jun/2026.
2. **Unidade do rótulo LPDDR** — esperava `'LPDDR3+4G'`/`'LPDDR4+6G'`, mas o código
   produz `'LPDDR3+4GB'`/`'LPDDR4+6GB'`. A convenção LPDDR passou de "G" (Gbit) para
   "GB" (capacidade do pacote) em jun/2026 — ver CLAUDE.md §6 (canônico
   `LPDDR4+4GB`). DDR continua em "G" (densidade do die em Gbit).

O **código estava certo nas duas** (CLAUDE.md §10: código vence). Corrigidas as
asserções (e as tabelas §5/§11, que também diziam `+G` para LPDDR). **Suíte agora
17/17 verde** (`python manage.py test estoque --settings=core.settings_test`).

### Achado 2 — `add_chip` confiava no `has_cap` do form — CORRIGIDO (2026-06-21)

Regra de ouro #3 (§16) manda **reclassificar no servidor e nunca confiar nos
hidden fields do form** para decisões de negócio. `add_chip` lia
`has_cap = request.POST.get('has_cap') == 'true'` — e `has_cap` decide se o chip
vira `UnknownChip` (decisão de negócio). Trocado por:

```python
has_cap = _has_capacity(server_result)
```

`classify()` é determinístico (lru_cache), então o valor casa com o do preview; um
POST forjado não burla mais a etapa. Os 16 testes de integração seguem verdes
(`test_has_cap_false_vai_para_unknown` usa um PN que o engine real também
classifica sem specs, então o recompute dá o mesmo resultado).

### Achado 3 — NOR/K5/ePoP já corrigido; doc estava desatualizada (resolvido aqui)

§15 e §17 listavam "NOR/K5 ainda é INDETERMINADO → aprovado" como limitação/tarefa
pendente. **Já está implementado** em `assess_profitability` (≈linha 1429):
`chip_type.lower() in ("nand flash", "nor flash", "mcp", "epop") → NÃO RENTÁVEL`.
Atualizei §15/§17. **Fragilidade que fica:** o match é por **string exata** de
`chip_type`; `"NOR"` (sem "Flash") escapa — o próprio
`test_confirmado_indeterminado_aprovado` (chip_type=`"NOR"`) prova retornando
INDETERMINADO. Garanta que os `populate_*` gravem exatamente os tipos da
whitelist.

### Achado 4 — chave do gateway documentada errada (corrigido aqui)

§4 documentava a chave `'by_generation'`; a chave real do dict é
`'reject_by_generation'` (ver `_compute_gateway._out`, `confirm_card.html` linha
~90 e `tests.py`). Corrigido em §4.

### Achado 5 — §2 (árvore de arquivos) estava incompleta

A árvore de `estoque/` em §2 omite arquivos que fazem parte do app:

- `reconcile_core.py` — lógica pura (sem Django) da reconciliação do lote #039
  (`category_key`, `RECOUNT_039`, `compute_reconciliation`); testada por
  `test_reconcile_039.py` na raiz.
- `tests.py` — `GatewayDestinationTests` (função pura) + `AddChipHardBlockTests`
  (integração com `classify` mockado).
- `management/commands/` — 7 comandos de manutenção (todos descritos no CLAUDE.md
  §5): `audit_targets`, `bless_base`, `clean_lote`, `fix_pns`, `list_unconfirmed`,
  `reconcile_lote_039`, `refresh_lote`. Dry-run por padrão, reversíveis via JSON.

### Achado 6 — `_confirm_as_knownpart` não persiste `subtype`/`density_gbit`/`is_emcp` (prioridade baixa)

Ao aprovar um `PendingEntry` no admin, `_confirm_as_knownpart` cria o `KnownPart`
com `chip_type/capacity/emcp_ram/emcp_nand/interface`, mas **não** copia `subtype`,
`density_gbit` nem `is_emcp`. Para uma RAM DDR, o `KnownPart` confirmado fica sem
`density_gbit` e sem `subtype` → numa busca futura o rótulo da caixa pode perder a
densidade/geração (cai no fallback da gramática). Não quebra nada hoje (o
`InventoryEntry` aprovado guarda o snapshot completo), mas degrada a qualidade do
dado confirmado. Considerar copiar esses campos do snapshot.

### Itens já conhecidos confirmados (sem ação nova)

`canonical_gen` fail-open, `_nearest_in_lot` O(n) por lote, `PendingEntry`
acumulando qty sem atualizar snapshot, cache do engine pós-`populate --overwrite`,
e ausência de view de fila para o operador — todos continuam válidos como descrito
em §15/§17.
