# RENTABILIDADE.md — Sistema de Rentabilidade WhatTheChip

> Bíblia técnica completa do sistema de avaliação de rentabilidade.
> Leia este documento inteiro antes de tocar em qualquer código relacionado
> a `assess_profitability`, `is_dead_by_generation`, `ProfitabilityConfig`
> ou no gateway do estoque. Ele substitui `CONTRATO_RENTABILIDADE_GATEWAY.md`
> como referência canônica — aquele é um briefing histórico; este é o estado atual.

---

## 1. O que é e para que serve

O sistema de rentabilidade avalia cada chip classificado pelo engine e devolve
um de três vereditos comerciais:

| Veredito | Significado |
|---|---|
| `RENTÁVEL` | Chip tem mercado B2B de reciclagem; vale recondicionar |
| `NÃO RENTÁVEL` | Sucata — moagem, resíduo eletrônico, ou apenas registro |
| `INDETERMINADO` | Dados insuficientes para decidir; requer confirmação humana |

O veredito é usado em dois lugares:

1. **Buscador** (`/chips/search/`, `/chips/decode/`) — exibe badge de rentabilidade
   no card do chip para o operador de bancada.
2. **Gateway do estoque** (`estoque/views.py::add_chip`) — roteia o chip para
   APROVADO / REPROVADO / FILA / DESCONHECIDO quando dado entrada no inventário.

---

## 2. Arquitetura — onde está o código

```
chips/engine.py
  ├── assess_profitability(result)   ← FONTE ÚNICA da rentabilidade
  ├── is_dead_by_generation(result)  ← derivada; usada pelo gateway
  ├── _strip_capacity(result)        ← helper interno de is_dead_by_generation
  └── _extract_gib / _extract_gbit   ← parsers de capacidade (GB/Gb)

chips/models.py
  └── ProfitabilityConfig            ← singleton; todos os thresholds

estoque/views.py
  ├── add_chip()                     ← gateway principal (entry point)
  └── _compute_gateway()             ← lógica de roteamento (APROVADO/REPROVADO/etc.)

estoque/templates/estoque/partials/confirm_card.html
  └── banner de rentabilidade (APROVADO / REPROVADO / etc.)

chips/templates/chips/partials/decode_card.html
  └── badge de rentabilidade (buscador público)
```

**Regra de ouro inviolável:** `assess_profitability` é a **única** fonte da
rentabilidade. Nunca reimplemente a lógica em outro lugar. O gateway, o badge
e qualquer futuro consumidor derivam dela.

---

## 3. `assess_profitability(result: dict) -> str`

### 3.1 Input

Recebe o dict `result` retornado por `classify(pn)` (ou qualquer dict com as
mesmas chaves). Campos relevantes:

| Campo | Tipo | Usado por |
|---|---|---|
| `chip_type` | str | todos os blocos |
| `subtype` | str | GDDR, DDR, LPDDR |
| `is_emcp` | bool | bloco eMCP/uMCP |
| `emcp_ram` | str | bloco eMCP/uMCP |
| `emcp_nand` | str | bloco eMCP/uMCP |
| `capacity` | str | eMMC, UFS, LPDDR |
| `dram_density` | str | DDR, LPDDR (fallback) |

### 3.2 Setup

```python
cfg = ProfitabilityConfig.get_config()   # singleton do banco

chip_type = (result.get("chip_type") or "").strip()
subtype   = (result.get("subtype")   or "").strip()
combined  = f"{chip_type} {subtype}".upper()
```

`combined` é a string de busca universal — todos os blocos usam `in combined`
para não depender de um campo só.

### 3.3 Fluxo de decisão (ordem exata)

```
1. Bloco de tipos → NÃO RENTÁVEL sem condição
2. Bloco eMCP/uMCP
3. Bloco eMMC standalone
4. Bloco UFS standalone
5. Bloco LPDDR standalone
6. Bloco GDDR (antes do DDR — intercepta substring)
7. Bloco DDR standalone
8. Fallthrough → INDETERMINADO
```

A ordem importa. Nunca mude sem entender as interações (especialmente GDDR
antes de DDR).

### 3.4 Bloco 1 — Tipos sempre NÃO RENTÁVEL

```python
if chip_type.lower() in ("nand flash", "nor flash", "mcp", "epop"):
    return "NÃO RENTÁVEL"
```

Tipos adicionados aqui são sucata **por classe**, independente de capacidade,
geração ou qualquer outro dado. A consequência é que `is_dead_by_generation`
retorna `True` automaticamente para eles.

| Tipo | Motivo |
|---|---|
| `nand flash` | NAND raw sem controlador (MT29F, K9*) — resíduo industrial |
| `nor flash` | Memória de código read-only — sem mercado B2B |
| `mcp` | MCP legado (NAND raw + mDDR1 pré-eMCP) — sem liquidez |
| `epop` | Package-on-Package (~2012-2015) — memória empilhada em SoC, sem mercado B2B de reciclagem |

⚠ Adicionar novos tipos aqui só após confirmar que `chip_type` é consistente
em **todos** os populate_* e fix_known_parts da marca. Um typo de `chip_type`
pode fazer chips válidos virarem sucata.

### 3.5 Bloco 2 — eMCP / uMCP

Ativado por `result.get("is_emcp") == True` **ou** `chip_type.lower() in ("emcp", "umcp")`.
A dupla checagem garante que resultados com `chip_type` literal também entram.

Fluxo interno:

```
1. ram_str / nand_str vazios? → INDETERMINADO
2. lpddr_gen = _lpddr_generation(ram_str)
3. lpddr_gen < emcp_min_lpddr_gen (default=3)? → NÃO RENTÁVEL   ← FIX 2026-05-27
4. ram_gb  = _extract_gib(ram_str)
5. nand_gb = _extract_gib(nand_str)
6. ram_gb ou nand_gb é None? → INDETERMINADO
7. lpddr_gen é None? → INDETERMINADO
8. lpddr_gen < min? → NÃO RENTÁVEL (redundante pós-fix, mantido por segurança)
9. ram_gb  < emcp_min_ram_gb?  → NÃO RENTÁVEL
10. nand_gb < emcp_min_nand_gb? → NÃO RENTÁVEL
11. → RENTÁVEL
```

**Atenção ao passo 3:** a verificação de geração vem ANTES de `_extract_gib`.
Isso é o FIX 2026-05-27. Antes, `emcp_ram="LPDDR2"` (sem GB) → `_extract_gib`
retornava None → INDETERMINADO antes de checar geração. Chips KMN5X/KML7X/KMK
eram afetados.

### 3.6 Bloco 3 — eMMC standalone

```python
if chip_type == "eMMC":
    cap_gb = _extract_gib(result.get("capacity") or "")
    if cap_gb is None: return "INDETERMINADO"
    return "RENTÁVEL" if cap_gb >= cfg.emmc_min_cap_gb - 0.01 else "NÃO RENTÁVEL"
```

Threshold: `emmc_min_cap_gb` (default = 4.0 GB).

Note o `- 0.01` em todas as comparações de threshold — tolerância de ponto
flutuante para evitar falsos negativos por arredondamento.

### 3.7 Bloco 4 — UFS standalone

Idêntico ao eMMC, usa `ufs_min_cap_gb` (default = 4.0 GB).

### 3.8 Bloco 5 — LPDDR standalone

```
1. "LPDDR" in combined? → entra
2. lpddr_gen = _lpddr_generation(combined)
3. lpddr_gen é None? → INDETERMINADO
4. lpddr_gen < lpddr_min_gen (default=3)? → NÃO RENTÁVEL   ← FIX 2026-06-19
5. cap_gb = _extract_gib(capacity ou dram_density)
6. cap_gb é None? → INDETERMINADO
7. lpddr_gen >= 4? usa lpddr4plus_min_cap_gb (default=1.0)
   lpddr_gen == 3? usa lpddr3_min_cap_gb (default=2.0)
8. cap_gb < threshold? → NÃO RENTÁVEL
9. → RENTÁVEL
```

**Atenção ao passo 4:** geração verificada ANTES da capacidade (FIX 2026-06-19).
Sem esse fix, LPDDR2 com `dram_density="8Gb = 1GB por die [~]"` retornava
INDETERMINADO porque `_strip_capacity` remove `"8Gb"` (re.I, b minúsculo) e
`"1GB"` → dram_density fica `" =  por die [~]"` → `_extract_gib` = None →
INDETERMINADO antes de checar geração.

Chips afetados antes do fix: K3PE, K4P, K4E8E (todos LPDDR2).

### 3.9 Bloco 6 — GDDR (GPU memory)

```python
if "GDDR" in combined:
    m = re.search(r'GDDR(\d+)', combined)
    gddr_gen = int(m.group(1)) if m else None
    if gddr_gen is None or gddr_gen < cfg.gddr_min_gen:
        return "NÃO RENTÁVEL"
    return "INDETERMINADO"
```

**Por que antes do DDR:** `"DDR" in combined` é True para "GDDR2" (substring).
O bloco DDR usa `_ddr_generation` com `(?<![A-Z])DDR` — o lookbehind falha em
"GDDR2" (G precede DDR) → ddr_gen=None → INDETERMINADO. O bloco GDDR intercepta
antes que isso aconteça.

**Convenção de campos:** dois padrões coexistem no banco:
- Gramática (ChipFamily K4N): `chip_type="GDDR2"`, `subtype="GDDR2 (legacy)"`
- KnownPart confirmado (fix_known_parts K4J/K4W/K4G/K4Z/H5RS): `chip_type="RAM"`, `subtype="GDDR3"` etc.

Ambos funcionam porque `"GDDR" in combined` captura as duas situações:
- `"GDDR2 GDDR2 (LEGACY)"` → True
- `"RAM GDDR3"` → True

GDDR3+ com `gddr_gen >= gddr_min_gen` retorna INDETERMINADO (sem threshold de
densidade definido por enquanto). Se o negócio decidir que GDDR3 também é
sucata, basta mudar `gddr_min_gen` para 4 no admin.

### 3.10 Bloco 7 — DDR standalone

```
1. "DDR" in combined? → entra
2. ddr_gen = _ddr_generation(combined)
   — usa (?<![A-Z])DDR(\d+)? → lookbehind bloqueia GDDR (já tratado no bloco 6)
3. ddr_gen é None? → INDETERMINADO
4. ddr_gen < ddr_min_gen (default=3)? → NÃO RENTÁVEL
5. Fonte primária: dram_density → _extract_gbit (Gigabits)
   Fallback: capacity → _extract_gib (Gigabytes, converte × 8)
6. ddr_gen >= 4? usa ddr4plus_min_gbit (default=1.0 Gb)
   ddr_gen == 3? usa ddr3_min_gbit (default=2.0 Gb)
7. gbit < threshold? → NÃO RENTÁVEL
8. → RENTÁVEL
```

Nota: thresholds em **Gigabits** (não GB). 2 Gb = 256 MB; 8 Gb = 1 GB. Cuidado
ao interpretar — um DDR3 de 256 MB (2 Gb) está no limite do padrão.

### 3.11 Fallthrough

```python
return "INDETERMINADO"
```

Qualquer tipo não coberto pelos blocos acima (SDRAM puro, SRAM, SoC, tipos
desconhecidos) cai aqui. Isso é intencional — melhor INDETERMINADO (vai para
revisão humana) do que um falso positivo ou negativo.

---

## 4. `ProfitabilityConfig` — configuração

### 4.1 Localização

`chips/models.py` — classe `ProfitabilityConfig`. Singleton (sempre pk=1).
Editável pelo admin Django em `/admin/chips/profitabilityconfig/`.

Alterações têm **efeito imediato** sem restart (o singleton é relido do banco
a cada chamada via `get_config()`).

### 4.2 Todos os campos e defaults

| Campo | Default | Unidade | Significado |
|---|---|---|---|
| `emcp_min_lpddr_gen` | 3 | — | Geração LPDDR mínima para eMCP/uMCP |
| `emcp_min_ram_gb` | 1.0 | GB | RAM mínima do eMCP/uMCP |
| `emcp_min_nand_gb` | 8.0 | GB | NAND mínima do eMCP/uMCP |
| `emmc_min_cap_gb` | 4.0 | GB | Capacidade mínima eMMC standalone |
| `ufs_min_cap_gb` | 4.0 | GB | Capacidade mínima UFS standalone |
| `lpddr_min_gen` | 3 | — | Geração LPDDR mínima standalone |
| `lpddr3_min_cap_gb` | 2.0 | GB | Capacidade mínima LPDDR3 standalone |
| `lpddr4plus_min_cap_gb` | 1.0 | GB | Capacidade mínima LPDDR4+ standalone |
| `ddr_min_gen` | 3 | — | Geração DDR mínima standalone |
| `ddr3_min_gbit` | 2.0 | Gb/die | Densidade mínima DDR3 |
| `ddr4plus_min_gbit` | 1.0 | Gb/die | Densidade mínima DDR4+ |
| `gddr_min_gen` | 3 | — | Geração GDDR mínima standalone |

### 4.3 O singleton e migrations

O singleton é criado automaticamente por `get_config()` se não existir.
Ao adicionar um campo novo ao modelo, obrigatoriamente:

```bash
python manage.py makemigrations chips
python manage.py migrate
# Commitar o arquivo de migration junto com o models.py
```

Se a migration não for commitada, o Render não tem como aplicar a coluna — o
engine quebra ao acessar o campo inexistente. (Já aconteceu com `gddr_min_gen`
em 2026-06-20.)

---

## 5. `is_dead_by_generation(result: dict) -> bool`

### 5.1 Definição

```python
def is_dead_by_generation(result: dict) -> bool:
    return assess_profitability(_strip_capacity(result)) == "NÃO RENTÁVEL"
```

Retorna `True` se o chip é NÃO RENTÁVEL **independente de qualquer número de
capacidade**. Literalmente: "removendo todos os números de GB/MB do result,
o chip ainda é sucata?"

### 5.2 Por que é derivada

`is_dead_by_generation` **não mantém lista própria de regras**. Ela deriva de
`assess_profitability`. Consequência: qualquer nova regra em `assess_profitability`
é refletida automaticamente em `is_dead_by_generation` sem nenhuma mudança
adicional. É filosofia de fonte única.

### 5.3 `_strip_capacity` — o que remove

```python
_CAP_NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:GB|MB)\b", re.I)
```

Remove de `capacity`, `dram_density`, `emcp_ram`, `emcp_nand`:
- `"16GB"` → `""`
- `"LPDDR3 1GB"` → `"LPDDR3"`
- `"8Gb = 1GB por die"` → `" =  por die"` ← **re.I remove "8Gb" (b minúsculo)**

**Armadilha do re.I:** o regex usa `re.I`, então `GB` casa `Gb`, `gb`, `gB`.
Isso é intencional para remover todas as formas de gigabytes/megabytes, mas
significa que `"8Gb"` (Gigabit — unidade de DRAM) também é removido. Esse
foi o bug que causava is_dead_by_generation=False para LPDDR2 com decode
DRAM_MOBILE (corrigido via FIX 2026-06-19 no bloco LPDDR).

### 5.4 Casos onde `is_dead_by_generation` retorna True

- Qualquer tipo no bloco 1 (nand flash, nor flash, mcp, epop)
- eMCP/uMCP com LPDDR2 (lpddr_gen < emcp_min_lpddr_gen): `emcp_ram="LPDDR2"` → sem número → não muda → still `< 3` → True
- LPDDR standalone com gen < lpddr_min_gen: `dram_density` esvaziado → gen check ainda dispara
- GDDR com gen < gddr_min_gen: `gddr_gen < 3` → True
- DDR com gen < ddr_min_gen: `ddr_gen < 3` → True

### 5.5 Casos onde `is_dead_by_generation` retorna False mas profitable="NÃO RENTÁVEL"

- eMMC 2GB: strip remove "2GB" → capacity="" → INDETERMINADO → False
- UFS 2GB: idem
- LPDDR3 512MB: strip remove "512MB" → capacity="" → INDETERMINADO → False
- eMCP LPDDR3 / RAM 512MB: strip remove os GBs → INDETERMINADO → False

Nesses casos a rejeição é **por capacidade** — o gateway exige confirmação
antes de descartar (ver seção 7).

---

## 6. Gateway do estoque — `estoque/views.py`

### 6.1 Entry point: `add_chip()`

Chamado quando um operador dá entrada de um chip no inventário. Fluxo:

```
classify(pn)
    ↓
assess_profitability(result)  → profitable
    ↓
is_dead_by_generation(result) → dead
    ↓
┌─────────────────────────────────────────────────────┐
│ dead == True?                                       │
│   → RejectedEntry (auto-descarte, auditoria)       │
│   → Fim. Não passa pela fila.                      │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ PN confirmado no banco (confidence confirmed/manual)│
│   NÃO → PendingEntry (FILA para aprovação humana)  │
│   SIM → continua                                   │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ profitable == "NÃO RENTÁVEL"?                       │
│   → RejectedEntry (REPROVADO confirmado)            │
│ profitable == "RENTÁVEL"?                           │
│   → InventoryEntry (APROVADO)                      │
│ profitable == "INDETERMINADO"?                      │
│   → InventoryEntry com flag INDETERMINADO           │
└─────────────────────────────────────────────────────┘
```

### 6.2 Os dois sabores de NÃO RENTÁVEL

Esta é a distinção mais importante do sistema:

| Sabor | Como decide | Precisa de confirmação? | Ação do gateway |
|---|---|---|---|
| **Por tipo/geração** | Regra dispara sem número de GB | **Não** | `RejectedEntry` automático via `is_dead_by_generation` |
| **Por capacidade** | Regra precisa do número de GB | **Sim** | `PendingEntry` (FILA) se não confirmado; `RejectedEntry` se confirmado |

A distinção existe porque a geração/tipo é extraída posicionalmente da gramática
com alta confiança ("LPDDR2" no decode é quase sempre correto), enquanto a
capacidade pode estar errada (decode incorreto, PN com typo, família não
mapeada). Jogar fora um chip valioso por capacidade incorreta é um erro de
negócio grave.

### 6.3 PendingEntry (FILA)

Quando um PN não confirmado entra no sistema e não é morto por geração,
vai para `PendingEntry`. O gestor acessa em `/admin/estoque/pendingentry/`
e escolhe Aprovar ou Reprovar.

A FILA protege contra:
- Typos de PN (JK5WA1E0K8 ≠ JK5WA1E0K)
- PNs de chips com capacidade não mapeada na gramática
- PNs completamente desconhecidos

`bless_base` é o comando para promover em massa os PNs do lote base a
`confirmed`, liberando a fila (ver CLAUDE.md §5).

### 6.4 RejectedEntry

Auditoria de todos os chips rejeitados. Gerada tanto pelo auto-descarte
(`is_dead_by_generation=True`) quanto pela rejeição manual via FILA e pela
rejeição direta de chips confirmados NÃO RENTÁVEL.

---

## 7. Frontend — badges e banners

### 7.1 Buscador (`decode_card.html`)

Badge discreto no card de resultado da busca pública. Exibe:
- RENTÁVEL (verde)
- NÃO RENTÁVEL (vermelho)
- INDETERMINADO (cinza)

### 7.2 Estoque (`confirm_card.html`)

Banner proeminente no card de confirmação do gateway. Estados:

| Estado do gateway | Label exibido | Cor |
|---|---|---|
| APROVADO | APROVADO | verde `#24a148` |
| REPROVADO (confirmed) | REPROVADO | vermelho `#da1e28` |
| REPROVADO (por geração) | REPROVADO POR GERAÇÃO | vermelho escuro |
| FILA | AGUARDANDO REVISÃO | amarelo |
| INDETERMINADO | INDETERMINADO | cinza |

### 7.3 Cores das caixas físicas (destination_cat)

O `_compute_destination` em `estoque/views.py` retorna um `destination_cat`
que o template usa para colorir o painel do tipo:

| Tipo | Cat | Cor |
|---|---|---|
| eMCP | emcp | vermelho `#da1e28` |
| uMCP | umcp | rosa `#ff7eb6` |
| UFS | ufs | amarelo `#f1c21b` |
| eMMC | emmc | verde `#42be65` |
| NAND Flash | nand | roxo `#8a3ffc` |
| GDDR | gddr | laranja `#ff6900` |
| DDR | ddr | marrom `#795548` |
| LPDDR | lpddr | azul `#4589ff` |

---

## 8. Histórico de bugs corrigidos

### Bug #1 — eMCP LPDDR2 INDETERMINADO (2026-05-27)

**Sintoma:** chips eMCP com geração LPDDR2 retornavam INDETERMINADO em vez de
NÃO RENTÁVEL quando `emcp_ram` não continha número de GB (ex.: `"LPDDR2"` puro).

**Causa:** bloco eMCP checava `ram_gb is None → INDETERMINADO` antes de
verificar a geração.

**Fix:** geração verificada antes de `_extract_gib`. Se `lpddr_gen < min → NÃO RENTÁVEL`
sem precisar do GB.

**Chips afetados:** KMN5X000ZM, KML7X000HM, KMK*, KMV*.

---

### Bug #2 — LPDDR standalone LPDDR2 INDETERMINADO (2026-06-19)

**Sintoma:** K3PE0E000E (LPDDR2, 2GB) ia para a FILA do estoque em vez do
auto-descarte. `profitable="NÃO RENTÁVEL"` mas `is_dead_by_generation=False`.

**Causa raiz:** `dram_density="8Gb = 1GB por die [~]"`. `_strip_capacity` com
`re.I` remove `"8Gb"` (b minúsculo = Gigabit, mas o regex case-insensitive
o confunde com GB) e `"1GB"`. Resultado: `dram_density=" =  por die [~]"`.
`_extract_gib` retorna None. Bloco LPDDR checava `cap_gb is None → INDETERMINADO`
antes de checar geração → `is_dead_by_generation=False`.

**Fix:** geração verificada antes de `_extract_gib` no bloco LPDDR standalone
(espelho do fix #1).

**Chips afetados:** K3PE (LPDDR2), K4P (LPDDR2), K4E8E (LPDDR2).

---

### Bug #3 — K3PE exibindo "RAM" em vez de "LPDDR2" (2026-06-19)

**Sintoma:** após `populate_samsung --overwrite` e restart, K3PE ainda mostrava
tipo "RAM".

**Causa:** `_families()` em `populate_samsung.py` tinha DOIS entries com
prefixo `"K3PE"` — um com priority=35 (correto) e outro com priority=100.
O loop de populate usa `filter(prefix=prefix).first()` para upsert — a segunda
iteração sobrescrevia o priority de 35 para 100. A família K3 genérica (priority=90)
então vencia sobre K3PE (priority=100) no engine.

**Fix:** merged em uma única entrada com priority=35 e decode_cap incluído.

---

### Bug #4 — GDDR2 INDETERMINADO (2026-06-20)

**Sintoma:** K4N51163Q7 (GDDR2) retornava INDETERMINADO.

**Causa:** `"DDR" in combined` é True para "GDDR2" (substring). `_ddr_generation`
usa `(?<![A-Z])DDR(\d+)?` — lookbehind bloqueia o match em "GDDR2" (G precede DDR)
→ `ddr_gen=None → INDETERMINADO`.

**Fix:** bloco GDDR adicionado antes do bloco DDR. Extrai geração via `GDDR(\d+)`.
`gddr_min_gen` (default=3) adicionado ao `ProfitabilityConfig`.

**Chips afetados:** qualquer GDDR sem bloco próprio (K4N Samsung, H5RS Hynix).

---

### Bug #5 — ePoP INDETERMINADO (2026-06-20)

**Sintoma:** KAT00F00NB (ePoP Samsung) retornava INDETERMINADO.

**Causa:** `is_emcp=True` → bloco eMCP. `emcp_ram="tipo 'T' — consultar datasheet
⚠ cap. não mapeada"` (string não-vazia, sem GB) → `_extract_gib` = None →
`ram_gb is None → INDETERMINADO`.

**Causa raiz:** a gramática KAT não tem decode map para capacidade → gera
placeholder strings. O engine não distingue placeholder de dado real.

**Fix:** `"epop"` adicionado ao bloco 1 (tipos sempre NÃO RENTÁVEL). Intercepta
antes de chegar ao bloco eMCP.

**Decisão de negócio:** ePoP é sempre NÃO RENTÁVEL para todas as marcas (memória
empilhada em SoC, sem mercado B2B de reciclagem).

---

### Padrão recorrente documentado (2026-06-20)

Os bugs #1, #2, #4 e #5 têm a mesma raiz: chips que são NÃO RENTÁVEL por tipo
ou geração retornam INDETERMINADO quando `assess_profitability` chega a um bloco
que exige dados de capacidade e não os encontra.

**Regra de prevenção:** ao adicionar um novo chip_type ao sistema:
1. "Este tipo é NÃO RENTÁVEL independente de capacidade?" → sim → bloco 1 (tipo-based)
2. "É NÃO RENTÁVEL por geração?" → verificar geração ANTES de `_extract_gib` no bloco
3. "É NÃO RENTÁVEL só por capacidade?" → caminho normal (exige confirmação)

---

## 9. Limitações e casos pendentes

### 9.1 GDDR3+ sem threshold de densidade

Chips com `gddr_gen >= gddr_min_gen` (padrão: GDDR3, GDDR5, GDDR6) retornam
INDETERMINADO. Não há threshold de densidade definido para GPU memory ainda.
Se o negócio decidir que GDDR3 também é sucata → `gddr_min_gen = 4` no admin.
Se quiser classificar GDDR5/6 por densidade → novo sub-bloco dentro do bloco GDDR.

### 9.2 Capacidade grammar não confiável para auto-descarte

Chips NÃO RENTÁVEL por capacidade (eMMC 2GB, LPDDR3 512MB) com PN não confirmado
vão para a FILA em vez do auto-descarte. Isso é intencional (ver seção 6.2).
Implicação: a FILA cresce com chips claramente ruins que precisam de aprovação
manual. Possível melhoria: se `grammar_complete=True` E profitable=NÃO RENTÁVEL
por capacidade → auto-rejeição (mudança de política, não de bug).

### 9.3 ProfitabilityConfig singleton — uma config para todas as marcas

Todos os thresholds são globais. Não há configuração por marca. Se Samsung e
Hynix tiverem thresholds diferentes para o mesmo tipo → não é suportado hoje.

### 9.4 SDRAM e RDRAM não cobertos

RAM de PC antiga (SDRAM, RDRAM) cai no fallthrough INDETERMINADO. Se aparecerem
no fluxo → seriam NÃO RENTÁVEL, mas o sistema atual não os captura. Se virarem
relevantes, adicionar ao bloco 1 (tipo-based) ou criar bloco específico.

### 9.5 `grammar_complete=False` não sinaliza para assess_profitability

Quando a gramática gera placeholders ("tipo 'T' — consultar datasheet"), o campo
`grammar_complete=False` existe no result mas `assess_profitability` não o lê.
O engine não tem caminho para "grammar incompleta + tipo problático = NÃO RENTÁVEL".
A solução atual é usar o bloco de tipos (ePoP, MCP) ou aceitar INDETERMINADO.

---

## 10. Regras invioláveis

1. **`assess_profitability` é a única fonte da rentabilidade.** Nunca reimplemente
   a lógica em outro lugar — nem no gateway, nem em views, nem em templates.

2. **`is_dead_by_generation` não tem lista própria.** Ela deriva de
   `assess_profitability`. Adicionar uma lista paralela quebraria a sincronia.

3. **Geração verificada ANTES de `_extract_gib` em todos os blocos.** Nunca
   inverta. Se inverter, chips de geração morta com capacidade desconhecida
   voltarão a retornar INDETERMINADO em vez de NÃO RENTÁVEL.

4. **GDDR antes de DDR.** "DDR" está contido em "GDDR" — trocar a ordem faz
   GDDR cair no bloco DDR com lookbehind bloqueando o match.

5. **Migrations commitadas junto com models.py.** O arquivo gerado por
   `makemigrations` pertence ao repositório. Sem ele no Render, qualquer acesso
   a campo novo quebra o engine.

6. **`ProfitabilityConfig` changes não precisam de restart.** Mas mudanças
   em `engine.py` **precisam** — o módulo usa `lru_cache` para famílias.

7. **`- 0.01` em todos os comparadores de threshold.** Tolerância de ponto
   flutuante. Nunca use `>=` direto contra floats de threshold.

---

## 11. Checklist para novos chip_types

Ao adicionar suporte a um tipo de chip que ainda não existe no sistema:

- [ ] O tipo é NÃO RENTÁVEL por natureza, independente de capacidade?
  - Sim → adicionar ao bloco 1 em `assess_profitability`
  - Não → criar bloco específico

- [ ] Se tem geração: a verificação de geração vem ANTES de `_extract_gib`?

- [ ] O `chip_type` no novo populate é exatamente o string que o engine espera?

- [ ] Testei `is_dead_by_generation(classify("PN_TESTE"))` e retornou True para
  chips de geração morta?

- [ ] Se adicionei campo ao `ProfitabilityConfig`: fiz `makemigrations`, `migrate`
  e commitei o arquivo de migration?

- [ ] Documentei o novo tipo na docstring de `assess_profitability`?

---

## 12. Comandos úteis para testar

```python
# Shell Django
from chips.engine import classify, assess_profitability, is_dead_by_generation

# Teste básico
result = classify("KLM8G1WEMB")
print(result["profitable"])
print(is_dead_by_generation(result))

# Verificar bloco GDDR
result = classify("K4N51163QC")
print(result["chip_type"], result["subtype"])
print(result["profitable"])  # deve ser NÃO RENTÁVEL

# Verificar ePoP
result = classify("KAT00F00NB")
print(result["chip_type"])    # ePoP
print(result["profitable"])   # NÃO RENTÁVEL

# Verificar LPDDR2
result = classify("K3PE0E000E")
print(result["profitable"])   # NÃO RENTÁVEL
print(is_dead_by_generation(result))  # True

# Verificar threshold eMMC
result = classify("KLM2G1HE3F")
print(result["capacity"])     # 2GB
print(result["profitable"])   # NÃO RENTÁVEL
print(is_dead_by_generation(result))  # False (por capacidade, não geração)
```

---

## 13. Relação com outros documentos

- **`CLAUDE.md §7`** — Armadilhas: lista os bugs corrigidos com contexto de sessão
- **`docs/CONTRATO_RENTABILIDADE_GATEWAY.md`** — briefing histórico do contrato
  gateway × rentabilidade (2026-05); estado atual está aqui
- **`HANDOFF.md`** — decisões de arquitetura gerais
- **`chips/engine.py`** — código é a fonte da verdade; confirme aqui em caso
  de conflito com este documento
