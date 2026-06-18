# Briefing Técnico — Gateway de 4 Etapas para o Estoque
> Gerado em 17/06/2026 após sessão de brainstorm.
> Este documento é o briefing completo para implementação em nova sessão.
> Leia CLAUDE.md antes de qualquer coisa.

---

## 1. Contexto e problema

O WhatTheChip classifica chips de memória (`chips/engine.py → classify(pn)`) e o
módulo `estoque/` gerencia o inventário por lotes. O operador de bancada lê o PN
gravado no chip, digita no sistema, e o confirm card mostra o resultado.

**O problema que motivou esta mudança:** operadores estão adicionando ao estoque
chips NÃO RENTÁVEIS e chips classificados apenas por gramática (sem confirmação
no banco). Isso causa prejuízo direto porque o estoque acaba com chips que não
têm liquidez de venda.

A solução não é apenas técnica — é de UX. O sistema precisa comunicar claramente
para onde vai cada chip e POR QUE, sem ambiguidade, para qualquer operador,
incluindo novatos.

---

## 2. O que já existe no codebase (NÃO reimplementar)

Antes de implementar qualquer coisa, mapeie o que já está funcionando:

### Backend (`estoque/views.py`)

```python
# Bloqueio "só confirmados" — já existe e já está ativo
CONFIRMED_SOURCES = {"banco de dados"}
CONFIRMED_CONF = {"confirmed", "manual"}

def _is_confirmed(result: dict) -> bool:
    return (
        result.get("classification_source") in CONFIRMED_SOURCES
        or result.get("confidence") in CONFIRMED_CONF
    )
```

Em `add_chip`, chips não confirmados já vão para `PendingEntry` em vez de
`InventoryEntry`. Esse bloqueio está funcionando. Não toque nele.

```python
# Checagem de specs completas — já existe
_PLACEHOLDER_MARKERS = ("não mapead", "nao mapead", "consultar datasheet")

def _real_spec(val) -> bool:
    """True só se o valor é uma spec REAL, não placeholder de gramática."""
    ...

def _has_capacity(result: dict) -> bool:
    """True se o chip tem specs utilizáveis."""
    ...
```

```python
# Extração de GB e destino físico — já existem
def _extract_gb(text: str) -> str: ...
def _compute_destination(result: dict) -> tuple: ...  # (label, category)
```

### Engine (`chips/engine.py`)

```python
# Avaliação de rentabilidade — já existe e é completa
def assess_profitability(result: dict) -> str:
    # Retorna: "RENTÁVEL" | "NÃO RENTÁVEL" | "INDETERMINADO"
    # Regras por tipo: eMCP/uMCP, eMMC, UFS, LPDDR, DDR, MCP legado
    ...
```

### Modelos (`estoque/models.py`)

- `Lot` — lote com operador, status (open/closed), numeração sequencial global
- `InventoryEntry` — chip confirmado no estoque do lote (constraint `unique(lot, pn)`)
- `PendingEntry` — chip não confirmado, aguarda gestor aprovar/reprovar no admin
  - Campos: `lot`, `part_number`, `quantity`, classificação snapshot, `confidence`,
    `nearest_confirmed`, `operator`, `created_at`
  - Constraint: `unique(lot, part_number)` — segunda tentativa incrementa qty
- `UnknownChip` (em `chips/models.py`) — chips que o engine não identificou

### Templates relevantes

```
estoque/templates/estoque/
  estoque.html                    → painel principal do lote
  lotes.html                      → lista de lotes
  partials/
    confirm_card.html             → card de resultado (TARGET PRINCIPAL)
    table_body.html               → tabela de estoque
    pending_feedback.html         → feedback de envio para fila
    unknown_feedback.html         → feedback de chip desconhecido
```

O `confirm_card.html` é o arquivo central desta mudança. Atualmente tem:
- Header compacto (status + PN)
- Bloco de DESTINO (caixa física com cor por tecnologia: EMCP16+1.5, UFS128GB, etc.)
- Meta-pills (estoque atual, confiança, rentabilidade)
- Aviso fuzzy (se `result.pn_not_in_db and result.fuzzy_suggestions`)
- Form com botões condicionais: "Adicionar ao estoque" vs "Enviar para conferência"

---

## 3. A nova lógica: Gateway de 4 Etapas

### Visão geral dos 3 destinos

Todo chip classificado termina em um de 3 destinos físicos:

| Destino | Significado | Ação do operador |
|---|---|---|
| ✅ APROVADO | Pode entrar no estoque | Adiciona ao lote |
| ⏳ FILA | Precisa de revisão do gestor | Envia para conferência |
| 🗑 REPROVADO | Vai para resíduo eletrônico | Descarta fisicamente |

Um 4º caso existe mas é separado do fluxo principal:
| ❓ DESCONHECIDO | Engine não identificou | Registra como desconhecido |

### As 4 etapas (fluxo sequencial)

```
ETAPA 1: FONTE
  Pergunta: o chip está CONFIRMADO no banco (confidence=confirmed/manual)?
  ✓ Sim → segue para etapa 2
  ✗ Não (só gramática, distribuidor, IA, estimated) → destino: FILA
        └→ mostrar sugestões fuzzy como mecanismo de recuperação
           (se o operador quis dizer outro PN, seleciona e reinicia o fluxo)

ETAPA 2: SPECS (só avaliada se etapa 1 passou)
  Pergunta: o chip tem especificações completas e reais (sem placeholders)?
  ✓ Sim → segue para etapa 3
  ✗ Não → destino: DESCONHECIDO

ETAPA 3: RENTABILIDADE (só avaliada se etapas 1 e 2 passaram)
  Pergunta: o chip é rentável segundo as regras de negócio?
  ✓ RENTÁVEL → destino: APROVADO
  ✓ INDETERMINADO → destino: APROVADO  ← REGRA CRÍTICA (ver §3.1)
  ✗ NÃO RENTÁVEL → destino: REPROVADO

ETAPA 4: DIGITAÇÃO (avaliação de segurança, não é gate hard)
  Pergunta: existem PNs confirmados muito parecidos que sugerem typo?
  Quando ativar: QUALQUER etapa pode mostrar sugestões fuzzy se existirem.
  - Nas etapas 1-3, funciona como ALERTA (soft warning), não como bloqueio.
  - O operador pode confirmar o PN atual ou selecionar uma sugestão.
  - Exibido como indicador na barra de etapas (⚠ vs ✓).
```

### 3.1 REGRA CRÍTICA: INDETERMINADO = APROVADO

O sistema de rentabilidade ainda está em maturação. As regras em
`assess_profitability()` não cobrem todos os tipos de chip (NOR flash, SoC,
SDRAM, etc.). Para esses casos, a função retorna `"INDETERMINADO"`.

**Decisão de negócio:** INDETERMINADO vai para APROVADO. É melhor deixar entrar
um chip que talvez não seja rentável do que descartar um chip valioso por falta
de regra. O prejuízo de uma regra incompleta é menor que o prejuízo de perder
material com valor.

O INDETERMINADO pode aparecer em dois momentos:
- Etapa 2: specs incompletas → `assess_profitability()` retorna INDETERMINADO por
  falta de dados → nesse caso, destino é DESCONHECIDO (etapa 2 falhou)
- Etapa 3: specs completas, mas tipo sem regra de rentabilidade → destino é APROVADO

Portanto a lógica exata da etapa 3 é:
```python
profitable = assess_profitability(result)
if profitable == "NÃO RENTÁVEL":
    gateway_dest = "reprovado"
else:
    # RENTÁVEL ou INDETERMINADO → aprovado
    gateway_dest = "aprovado"
```

### 3.2 Chips remarcados (remarked_flag)

**Decisão:** chips remarcados não são uma preocupação operacional neste contexto
(não chegam para o operador da eMiner). **Não implemente nada relacionado ao
`remarked_flag` neste refactor.** O campo existe no engine mas será ignorado aqui.

### 3.3 A fila de pendências (gramática) não é um problema

Com o bloqueio da etapa 1, chips classificados por gramática vão para
`PendingEntry`. Com o tempo, à medida que mais PNs são confirmados no banco, a
fila diminui naturalmente. **Não tente resolver a fila com lógica extra** — deixe
o processo de enriquecimento do banco lidar com isso.

---

## 4. O que precisa ser implementado

### 4.1 Nova função `_compute_gateway()` em `estoque/views.py`

Esta é a peça central. Deve ser adicionada entre os helpers existentes:

```python
def _compute_gateway(result: dict, has_cap: bool) -> dict:
    """
    Avalia as 4 etapas de aprovação e retorna o estado do gateway.
    
    Retorna um dict com:
      - destination: 'aprovado' | 'fila' | 'desconhecido' | 'reprovado'
      - steps: list de 4 dicts, cada um com:
          { 'id': str, 'label': str, 'status': 'pass'|'fail'|'warn'|'skip', 'detail': str }
      - fuzzy_suggestions: list (reutiliza result.fuzzy_suggestions)
    
    Regras:
      etapa 1 (fonte): _is_confirmed(result) → pass / fail
      etapa 2 (specs): has_cap → pass / fail  [só avaliada se etapa 1 pass]
      etapa 3 (rentabilidade): assess_profitability → pass/fail  [só se etapas 1+2 pass]
      etapa 4 (digitação): fuzzy_suggestions presentes → warn / pass  [sempre avaliada]
    
    INDETERMINADO → aprovado (regra de negócio: melhor aprovar do que perder)
    """
    steps = [
        {'id': 'fonte',         'label': 'Fonte',        'status': 'skip', 'detail': ''},
        {'id': 'specs',         'label': 'Specs',        'status': 'skip', 'detail': ''},
        {'id': 'rentabilidade', 'label': 'Rentabilidade','status': 'skip', 'detail': ''},
        {'id': 'digitacao',     'label': 'Digitação',    'status': 'skip', 'detail': ''},
    ]
    
    fuzzy = result.get('fuzzy_suggestions') or []
    
    # ── Etapa 1: Fonte ──────────────────────────────────────────
    confirmed = _is_confirmed(result)
    if confirmed:
        steps[0] = {'id': 'fonte', 'label': 'Fonte', 'status': 'pass',
                    'detail': result.get('classification_source', 'banco de dados')}
    else:
        steps[0] = {'id': 'fonte', 'label': 'Fonte', 'status': 'fail',
                    'detail': result.get('classification_source', 'gramática')}
        # Etapa 4 (digitação) ainda é avaliada mesmo com falha na etapa 1
        steps[3] = _step_digitacao(fuzzy)
        return {'destination': 'fila', 'steps': steps, 'fuzzy_suggestions': fuzzy,
                'profitable': '', 'profitable_key': 'indeterminado'}
    
    # ── Etapa 2: Specs ──────────────────────────────────────────
    if has_cap:
        steps[1] = {'id': 'specs', 'label': 'Specs', 'status': 'pass', 'detail': 'completas'}
    else:
        steps[1] = {'id': 'specs', 'label': 'Specs', 'status': 'fail', 'detail': 'incompletas'}
        steps[3] = _step_digitacao(fuzzy)
        return {'destination': 'desconhecido', 'steps': steps, 'fuzzy_suggestions': fuzzy,
                'profitable': '', 'profitable_key': 'indeterminado'}
    
    # ── Etapa 3: Rentabilidade ───────────────────────────────────
    profitable = assess_profitability(result)
    prof_key = {'RENTÁVEL': 'rentavel', 'NÃO RENTÁVEL': 'nao_rentavel',
                'INDETERMINADO': 'indeterminado'}.get(profitable, 'indeterminado')
    
    if profitable == 'NÃO RENTÁVEL':
        steps[2] = {'id': 'rentabilidade', 'label': 'Rentabilidade', 'status': 'fail',
                    'detail': 'Não rentável'}
        steps[3] = _step_digitacao(fuzzy)
        return {'destination': 'reprovado', 'steps': steps, 'fuzzy_suggestions': fuzzy,
                'profitable': profitable, 'profitable_key': prof_key}
    else:
        # RENTÁVEL ou INDETERMINADO → aprovado
        detail = 'Rentável' if profitable == 'RENTÁVEL' else 'Indeterminado (aprovado)'
        steps[2] = {'id': 'rentabilidade', 'label': 'Rentabilidade', 'status': 'pass',
                    'detail': detail}
    
    # ── Etapa 4: Digitação ───────────────────────────────────────
    steps[3] = _step_digitacao(fuzzy)
    
    return {'destination': 'aprovado', 'steps': steps, 'fuzzy_suggestions': fuzzy,
            'profitable': profitable, 'profitable_key': prof_key}


def _step_digitacao(fuzzy: list) -> dict:
    if fuzzy:
        return {'id': 'digitacao', 'label': 'Digitação', 'status': 'warn',
                'detail': f'{len(fuzzy)} sugestão(ões)'}
    return {'id': 'digitacao', 'label': 'Digitação', 'status': 'pass', 'detail': 'OK'}
```

### 4.2 Atualizar `preview_chip` em `estoque/views.py`

Substituir os cálculos individuais de `profitable`, `prof_key`, etc. pelo resultado
do gateway:

```python
@login_required
def preview_chip(request, lot_pk):
    lot = _get_lot(request, lot_pk)
    pn  = _normalise_pn(request.GET.get('pn', ''))

    if len(pn) < 4:
        return HttpResponse('')

    result  = classify(pn)
    has_cap = _has_capacity(result)

    # Capacidade para exibição
    if result.get('is_emcp'):
        parts = [p for p in [result.get('emcp_nand', ''), result.get('emcp_ram', '')] if p]
        display_cap = ' / '.join(parts)
    else:
        display_cap = result.get('capacity') or result.get('dram_density') or ''

    # Estoque atual no lote
    try:
        current_qty = InventoryEntry.objects.get(lot=lot, part_number=pn).quantity
    except InventoryEntry.DoesNotExist:
        current_qty = 0

    # Destino físico (caixa colorida) — só relevante se aprovado/specs completas
    destination, dest_cat = _compute_destination(result)

    # Gateway de 4 etapas — NOVA FUNÇÃO
    gateway = _compute_gateway(result, has_cap)

    ctx = {
        'lot':             lot,
        'pn':              pn,
        'result':          result,
        'has_cap':         has_cap,
        'display_cap':     display_cap,
        'result_json':     json.dumps({**result, 'pn': pn}),
        'current_qty':     current_qty,
        'destination':     destination,
        'destination_cat': dest_cat,
        # Gateway (substitui profitable/prof_key individuais)
        'gateway':         gateway,
        'gateway_dest':    gateway['destination'],  # 'aprovado'|'fila'|'desconhecido'|'reprovado'
        'gateway_steps':   gateway['steps'],
        'profitable':      gateway['profitable'],
        'profitable_key':  gateway['profitable_key'],
        # Mantém para retrocompat com template (fuzzy agora vem do gateway)
        'fuzzy_suggestions': gateway['fuzzy_suggestions'],
    }
    return render(request, 'estoque/partials/confirm_card.html', ctx)
```

**Importante:** o `add_chip` **NÃO muda** nesta implementação. O bloqueio de
rentabilidade é apenas UI (sem botão de adicionar para REPROVADO). O backend
continua bloqueando apenas gramática (via `_is_confirmed()`). Não adicione
verificação de rentabilidade no `add_chip` — é uma decisão consciente de negócio
(sistema de rentabilidade ainda imaturo).

### 4.3 Reescrever `confirm_card.html`

Este é o arquivo de maior mudança. A nova estrutura do card é:

```
┌──────────────────────────────────────────────────────┐
│ HEADER COMPACTO                                      │
│ [✓ Chip identificado]              [KMFN10012M]      │
├──────────────────────────────────────────────────────┤
│ BARRA DE ETAPAS (nova)                               │
│ [① FONTE ✓] [② SPECS ✓] [③ RENTÁVEL ✗] [④ ─ ]    │
├──────────────────────────────────────────────────────┤
│ BLOCO DE DESTINO (condicional por gateway_dest)      │
│  aprovado   → caixa colorida por tecnologia          │
│  fila       → bloco laranja "FILA DE CONFERÊNCIA"   │
│  desconhecido → bloco cinza "NÃO IDENTIFICADO"      │
│  reprovado  → bloco vermelho escuro "REPROVADO"      │
├──────────────────────────────────────────────────────┤
│ META-PILLS                                           │
│ [N em estoque] [● Confirmado] [✓ RENTÁVEL]          │
├──────────────────────────────────────────────────────┤
│ SUGESTÕES FUZZY (se houver, independente do destino) │
├──────────────────────────────────────────────────────┤
│ FORM + BOTÕES (condicionais por gateway_dest)        │
│  aprovado   → [Qtd.] [+ Adicionar ao estoque] [Cancelar] [📋]  │
│  fila       → [Qtd.] [⏳ Enviar para conferência] [Cancelar] [📋] │
│  desconhecido → [Registrar como desconhecido] [Cancelar]        │
│  reprovado  → [Cancelar] [📋]  (sem botão de adição)            │
└──────────────────────────────────────────────────────┘
```

#### CSS da barra de etapas (adicionar em `estoque.html`)

```css
/* ── Barra de 4 etapas (gateway) ─────────────────────────────── */
.est-steps {
  display: flex;
  gap: 4px;
  margin-bottom: var(--s4);
  padding: 10px var(--s4);
  background: var(--surface-2);
  border-bottom: 1px solid var(--border-subtle);
}
.est-step {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
  padding: 5px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-radius: 2px;
}
.est-step__num {
  font-size: 9px;
  opacity: .6;
  font-weight: 700;
}
.est-step--pass   { background: #defbe6; color: #0e6027; }
.est-step--fail   { background: #fff1f1; color: #da1e28; }
.est-step--warn   { background: #fff8e1; color: #8a5c00; }
.est-step--skip   { background: transparent; color: var(--text-disabled, #a8a8a8); }

/* ── Bloco de destino REPROVADO (adicionar às cores de dest) ─── */
.est-dest--reprovado {
  background: #2d0a0a;
  color: #ffb3b8;
}
/* ── Bloco de destino FILA ────────────────────────────────────── */
.est-dest--fila {
  background: #3a1f00;
  color: #ffd9a0;
}
```

#### Template HTML da barra de etapas

```html
{# ── Barra de 4 etapas ──────────────────────────────────────── #}
<div class="est-steps">
  {% for step in gateway_steps %}
  <div class="est-step est-step--{{ step.status }}" title="{{ step.detail }}">
    <span class="est-step__num">{{ forloop.counter }}</span>
    {% if step.status == 'pass' %}✓{% elif step.status == 'fail' %}✗{% elif step.status == 'warn' %}⚠{% else %}—{% endif %}
    {{ step.label }}
  </div>
  {% endfor %}
</div>
```

#### Bloco de destino condicional

```html
{# ── DESTINO — condicional por gateway_dest ─────────────────── #}
{% if gateway_dest == 'aprovado' %}
<div class="est-dest est-dest--{{ destination_cat }}">
  <div class="est-dest__label">{{ destination }}</div>
  <div class="est-dest__meta">
    {{ result.chip_type }}{% if result.brand %} · {{ result.brand }}{% endif %}
    {% if display_cap %} · {{ display_cap }}{% endif %}
  </div>
</div>

{% elif gateway_dest == 'fila' %}
<div class="est-dest est-dest--fila">
  <div class="est-dest__label">FILA</div>
  <div class="est-dest__meta">
    Não confirmado no banco · aguarda revisão do gestor
    {% if result.classification_source %} · {{ result.classification_source }}{% endif %}
  </div>
</div>

{% elif gateway_dest == 'desconhecido' %}
<div class="est-dest est-dest--unknown">
  <div class="est-dest__label" style="font-size:32px;">?</div>
  <div class="est-dest__meta">
    Chip não identificado — specs ausentes ou incompletas
  </div>
</div>

{% elif gateway_dest == 'reprovado' %}
<div class="est-dest est-dest--reprovado">
  <div class="est-dest__label">REPROVADO</div>
  <div class="est-dest__meta">
    NÃO RENTÁVEL — encaminhar para resíduos eletrônicos
    {% if result.chip_type %} · {{ result.chip_type }}{% endif %}
    {% if display_cap %} · {{ display_cap }}{% endif %}
  </div>
</div>
{% endif %}
```

#### Botões condicionais por destino

```html
<div class="est-confirm-actions">
  <div class="est-qty-wrap">
    <label class="est-label" for="confirm-qty">Qtd.</label>
    <input class="est-input est-input--qty" type="number" id="confirm-qty"
           name="qty" value="1" min="1" max="9999">
  </div>

  {% if gateway_dest == 'aprovado' %}
    <button class="est-btn est-btn--primary est-btn--lg" type="submit">+ Adicionar ao estoque</button>

  {% elif gateway_dest == 'fila' %}
    {# O backend (add_chip) já faz o roteamento para PendingEntry automaticamente #}
    <button class="est-btn est-btn--lg est-btn--warning" type="submit"
            title="Vai para fila de conferência do gestor — não entra no estoque">
      ⏳ Enviar para conferência
    </button>

  {% elif gateway_dest == 'desconhecido' %}
    {# Form alternativo sem has_cap=true — backend registra UnknownChip #}
    <button class="est-btn est-btn--secondary est-btn--lg" type="submit"
            onclick="...">
      Registrar como desconhecido
    </button>

  {% elif gateway_dest == 'reprovado' %}
    {# Sem botão de adicionar. Apenas cancelar e debug. #}
    <p style="font-size:12px;color:#da1e28;font-weight:700;flex:1;">
      ✗ Chip reprovado — não adicionar ao estoque
    </p>

  {% endif %}

  <button class="est-btn est-btn--cancel est-btn--lg" type="button"
          onclick="this.closest('.est-confirm').remove(); document.getElementById('pn-input').value=''; document.getElementById('pn-input').focus();">
    Cancelar
  </button>
  <button class="est-btn est-btn--debug est-debug-btn" type="button"
          title="Copia diagnóstico completo para o clipboard">📋</button>
</div>
```

---

## 5. Modelo de auditoria: `RejectedEntry`

Para auditar chips reprovados (entender quais chips estão sendo descartados,
calibrar as regras de rentabilidade), adicionar um novo modelo em `estoque/models.py`:

```python
class RejectedEntry(models.Model):
    """
    Registro de auditoria: chip que o operador tentou adicionar mas foi reprovado
    por NÃO RENTÁVEL na etapa 3 do gateway. Não entra no estoque nem na fila —
    vai para resíduo. Este modelo serve apenas para auditoria e calibração das
    regras de rentabilidade.
    """
    lot         = models.ForeignKey(
        Lot, on_delete=models.CASCADE, related_name='rejected', verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')
    quantity    = models.PositiveIntegerField(default=1, verbose_name='Quantidade')

    # Snapshot da classificação
    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    confidence  = models.CharField(max_length=20,  blank=True, default='', verbose_name='Confiança')

    # Razão da reprovação (sempre "NÃO RENTÁVEL" por enquanto, mas extensível)
    rejection_reason = models.CharField(max_length=100, default='NÃO RENTÁVEL', verbose_name='Razão')

    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rejected_entries', verbose_name='Operador',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Reprovado em')

    class Meta:
        verbose_name = 'Reprovado'
        verbose_name_plural = 'Reprovados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (reprovado · Lote #{self.lot.number:03d})'
```

### Quando gravar o `RejectedEntry`

No `add_chip`, se o chip tem `has_cap=true` e é confirmado (`_is_confirmed()`),
mas `assess_profitability()` retorna `"NÃO RENTÁVEL"` (ou seja, chegaria ao
gateway_dest='reprovado'), gravar o registro:

```python
# Em add_chip, após verificar _is_confirmed() e antes de gravar InventoryEntry:
profitable_check = assess_profitability(server_result)
if profitable_check == "NÃO RENTÁVEL":
    RejectedEntry.objects.create(
        lot=lot, part_number=pn, quantity=qty,
        chip_type=server_result.get('chip_type', ''),
        brand=server_result.get('brand', ''),
        capacity=server_result.get('capacity', ''),
        emcp_ram=server_result.get('emcp_ram', ''),
        emcp_nand=server_result.get('emcp_nand', ''),
        is_emcp=bool(server_result.get('is_emcp')),
        interface=server_result.get('interface', ''),
        classification_source=server_result.get('classification_source', ''),
        confidence=server_result.get('confidence', ''),
        rejection_reason='NÃO RENTÁVEL',
        operator=request.user,
    )
    # Retornar feedback de reprovado (não o table_body)
    return render(request, 'estoque/partials/rejected_feedback.html', {
        'pn': pn, 'qty': qty,
        'chip_type': server_result.get('chip_type', ''),
        'capacity': server_result.get('capacity', ''),
    })
```

**Nota importante:** Não adicione mais verificações ao `add_chip` além desta.
O `add_chip` deve ser um servidor defensivo mínimo. A maior parte da lógica de
exibição vive em `preview_chip` → template → `confirm_card.html`.

### Admin do `RejectedEntry`

```python
@admin.register(RejectedEntry)
class RejectedEntryAdmin(admin.ModelAdmin):
    list_display = ("part_number", "lot", "chip_type", "rejection_reason",
                    "quantity", "operator", "created_at")
    list_filter  = ("chip_type", "rejection_reason", "lot__operator")
    search_fields = ("part_number", "chip_type")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
```

---

## 6. Novo template: `rejected_feedback.html`

```html
{# estoque/templates/estoque/partials/rejected_feedback.html #}
<div class="est-confirm est-confirm--unknown" style="border-left-color:#da1e28;">
  <div class="est-confirm-head">
    <span class="est-confirm-status" style="color:#da1e28;">
      ✗ Reprovado — Resíduo eletrônico
    </span>
    <span class="est-confirm-pn">{{ pn }}</span>
  </div>
  <p style="font-size:13px;color:var(--text-secondary);margin:0 0 var(--s4);">
    Este chip ({{ chip_type }}{% if capacity %} · {{ capacity }}{% endif %})
    foi registrado como reprovado e deve ir para o descarte de resíduos eletrônicos.
    Nenhuma unidade foi adicionada ao estoque.
  </p>
</div>
```

---

## 7. Migração necessária

Depois de adicionar `RejectedEntry` ao model:

```bash
python manage.py makemigrations estoque
python manage.py migrate estoque
```

Não há dados a migrar — é um modelo novo sem FKs de modelos antigos.

---

## 8. Funcionalidade futura: interface de triagem de chips desconhecidos

**Não implementar nesta sessão — apenas registrar o plano.**

O modelo `UnknownChip` (em `chips/models.py`) registra chips que o engine não
identificou. Atualmente a gestão desses chips é feita pelo admin Django, o que
escala mal conforme o volume aumenta.

A ideia é criar uma interface dedicada em `/estoque/desconhecidos/` (ou em
`/chips/admin/desconhecidos/`, já que é um modelo de `chips/`) com:
- Lista paginada de `UnknownChip` ordenada por frequência de busca
- Busca por PN
- Ação em lote: "enviar para enriquecimento" / "marcar como não identificável"
- Link direto para o PN no site de busca do WhatTheChip

Isso é uma feature de gestão, não urgente para o problema atual.

---

## 9. Checklist de implementação

Na ordem sugerida:

1. [ ] Ler `CLAUDE.md` completo antes de qualquer coisa
2. [ ] Ler `estoque/views.py`, `estoque/models.py`, `chips/engine.py` (función `assess_profitability`)
3. [ ] Ler `estoque/templates/estoque/partials/confirm_card.html` (estado atual)
4. [ ] Ler `estoque/templates/estoque/estoque.html` (CSS existente, para não duplicar)
5. [ ] Adicionar `_compute_gateway()` e `_step_digitacao()` em `views.py`
6. [ ] Atualizar `preview_chip()` em `views.py` para usar o gateway
7. [ ] Adicionar CSS das etapas em `estoque.html` (`.est-steps`, `.est-step--*`, `.est-dest--reprovado`, `.est-dest--fila`)
8. [ ] Reescrever `confirm_card.html` com barra de etapas + destinos condicionais + botões condicionais
9. [ ] Adicionar modelo `RejectedEntry` em `estoque/models.py`
10. [ ] Registrar `RejectedEntry` em `estoque/admin.py`
11. [ ] Adicionar lógica de gravação de `RejectedEntry` em `add_chip` em `views.py`
12. [ ] Criar template `rejected_feedback.html`
13. [ ] `makemigrations estoque && migrate`
14. [ ] Testar manualmente com chips de cada destino:
    - Chip confirmado + rentável (ex: KMFN10012M) → APROVADO
    - Chip confirmado + não rentável (ex: chip LPDDR2) → REPROVADO
    - Chip confirmado + INDETERMINADO (ex: NOR flash, se houver) → APROVADO
    - Chip só por gramática (ex: PN não catalogado mas família conhecida) → FILA
    - PN desconhecido completamente (ex: lixo aleatório) → DESCONHECIDO
    - PN com typo (ex: próximo de confirmado mas errado) → FILA + sugestões fuzzy

---

## 10. Restrições e armadilhas a evitar

1. **Não toque no `add_chip` além do que está especificado.** O bloqueio de gramática
   já funciona. A nova lógica de `RejectedEntry` é a única adição.

2. **Não adicione verificação de rentabilidade como hard block no backend `add_chip`.**
   É uma decisão explícita de negócio para esta fase. O bloqueio é apenas UI.

3. **O `has_cap` no hidden input do form é reavaliado no servidor.** O `add_chip`
   já reclassifica o PN server-side (`server_result = classify(pn)`). Não confie
   nos hiddens para lógica de segurança.

4. **CSS: `border-radius: 0` em todo o design system (IBM Carbon White).** Não
   adicione `border-radius` nos novos componentes além do que já existe.

5. **Famílias e mapas usam `lru_cache`.** Não faça chamadas de `classify()` extras
   desnecessárias — já é feito uma vez em `preview_chip` e uma vez em `add_chip`.

6. **`auto_now=True` não atualiza via `.update()`** — já resolvido com
   `last_updated=timezone.now()` explícito. Não quebre isso.

7. **Sugestões fuzzy**: o campo `result.fuzzy_suggestions` vem do engine como lista
   de strings (PNs parecidos). Pode ser vazio. O gateway repassa esse campo
   intacto no contexto do template. Não modifique a lógica do engine para isso.

8. **Não crie arquivos de handoff na raiz.** Salve em `docs/archive/` com data.
   O `CLAUDE.md` é o índice canônico — adicione à seção §2 se descobrir uma
   nova regra de ouro.
