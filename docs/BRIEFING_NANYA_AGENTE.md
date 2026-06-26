# BRIEFING: Classificação de Chips Nanya — WhatTheChip

> **Para o agente que vai receber este prompt:**
> Este é o seu documento de onboarding completo para a sessão. Leia tudo antes
> de tocar em qualquer arquivo. Ele sobrescreve a necessidade de explorar o repo
> do zero.

---

## 0. Primeiro passo obrigatório

**Leia o `CLAUDE.md`** na raiz do repositório antes de qualquer coisa. Ele contém
as regras de ouro do sistema. As mais críticas para esta sessão estão resumidas
no §5 deste documento.

O repositório está em `/Users/raphaelsilvabastos/Documents/WhatTheChip/chipdocs/`
(ou no caminho que o ambiente indicar como workspace folder).

---

## 1. Contexto e objetivo da sessão

**WhatTheChip (WTC)** é um classificador Django de chips de memória para o
mercado de reciclagem/refurbishing. Um operador digita o Part Number (PN) gravado
a laser no chip e o sistema devolve: tipo, capacidade, destino comercial e se é
RENTÁVEL.

**Objetivo desta sessão:** criar suporte completo para a marca **Nanya Technology
Corporation (南亞科技)** no engine de classificação — gramática posicional,
documentação e PNs confirmados.

---

## 2. Estado atual do sistema para Nanya

### O que existe (incompleto e com bugs de convenção)

Em `chips/management/commands/add_chip_families.py`, existem **3 famílias "magras"**:

| Prefixo | chip_type | subtype atual (⚠️ ERRADO) | interface atual (⚠️ ERRADO) |
|---------|-----------|--------------------------|------------------------------|
| `NT5CC` | `"RAM"` | `"DDR3 SDRAM"` | `"DDR3"` |
| `NT5AD` | `"RAM"` | `"DDR4 SDRAM"` | `"DDR4"` |
| `NT5PA` | `"RAM"` | `"DDR3L SDRAM"` | `"DDR3L"` |

**Problemas:**
1. `subtype` com qualificador `"SDRAM"` — deve ser apenas `"DDR3"`, `"DDR4"` etc.
2. `interface` com geração (`"DDR3"`) — deve ser bus width (`"x8"`, `"x16"`) ou vazio
3. Sem `decode_cap_pos/map` — gramática não decodifica capacidade (operador não sabe se é 2GB ou 4GB)
4. Não há `populate_nanya.py` — a gramática Nanya é inexistente; chips caem em
   `grammar_complete=false`

### O que não existe e precisa ser criado

- `chips/management/commands/populate_nanya.py` — ⬅️ **entregável principal**
- `NANYA.md` na raiz — documentação profunda (igual a SAMSUNG.md)
- Entradas em `fix_known_parts.py` para PNs individuais confirmados
- Possivelmente `DecodeMap` com nome `NANYA_CAP` para o decode posicional

---

## 3. Quem é a Nanya?

**Nanya Technology** é o 4.º maior fabricante mundial de DRAM (Taiwanesa, fundada
1995, subsidiária do grupo Formosa Plastics). Faz exclusivamente DRAM — **não faz
NAND, eMMC, UFS nem eMCP**. No mercado de reciclagem aparece principalmente em:

- Notebooks e desktops de 2008-2020 (DDR3/DDR3L predominantes)
- Servidores antigos (DDR2/DDR3 ECC)
- Tablets e alguns phones antigos (LPDDR2/LPDDR3 raros)
- DDR4 mais recente (pós-2016)

**Site oficial:** https://www.nanya.com/en/Product/Memory
Lá constam as famílias e fichas técnicas. Use como fonte Tier 1.

---

## 4. Anatomia do Part Number Nanya

### Formato geral

```
NT  5  C  C  [density]  M  [width]  [speed]  [package]  -  [suffix]
↑   ↑  ↑  ↑  ──────────    ──────   ───────   ────────      ───────
│   │  │  │  capacidade     bits     vel.      encap.        temp/rev
│   │  │  └── tipo DDR (B=DDR3 std · C=DDR3L · A=DDR4 · T=DDR2 · D=SDRAM)
│   │  └───── subfamília (C, P, A…)
│   └──────── geração de produto (5 = SDR/DDR era; 6 = LPDDR?)
└──────────── Nanya Technology
```

### Decode de capacidade — VERIFICAR via Octopart/datasheet antes de criar mapa

A Nanya usa notação JEDEC: `[N]M` = N mega-endereços; capacidade total = N×M × width bits.

| Código PN | Cálculo | Capacidade total | MB/die |
|-----------|---------|-----------------|--------|
| `64M`×16 | 64M addr × 16b | 1Gb | 128MB |
| `128M`×8 | 128M addr × 8b | 1Gb | 128MB |
| `128M`×16 | 128M addr × 16b | 2Gb | 256MB |
| `256M`×8 | 256M addr × 8b | 2Gb | 256MB |
| `256M`×16 | 256M addr × 16b | 4Gb | 512MB |
| `512M`×8 | 512M addr × 8b | 4Gb | 512MB |
| `512M`×16 | 512M addr × 16b | 8Gb | 1GB |
| `1G`×8 | 1G addr × 8b | 8Gb | 1GB |

> ⚠️ **Nunca confunda Mb (megabit) com MB (megabyte).** O campo `capacity` do modelo
> KnownPart sempre vai em MB ou GB (bytes), nunca em Gbit.

### Prefixos conhecidos (verificar cobertura atual e lacunas)

| Prefixo | Tipo | `subtype` correto | `interface` correto | Volume na esteira |
|---------|------|-------------------|---------------------|-------------------|
| `NT5DS` | SDRAM | `"SDRAM"` | `""` | Muito baixo (pré-2004) |
| `NT5TU` | DDR2 | `"DDR2"` | `""` | Baixo (pré-2010) |
| `NT5CB` | DDR3 1.5V | `"DDR3"` | `""` | Alto |
| `NT5CC` | DDR3L 1.35V | `"DDR3L"` | `""` | **Muito alto** — laptop |
| `NT5PA` | DDR3L | `"DDR3L"` | `""` | Médio |
| `NT5AD` | DDR4 | `"DDR4"` | `""` | Crescente |
| `NT5AN` | DDR4 | `"DDR4"` | `""` | Crescente |
| `NT6CL` | LPDDR2 | `"LPDDR2"` | `""` | Baixo |
| `NT6AN` | LPDDR4 | `"LPDDR4"` | `""` | Baixo |

> ⚠️ **`interface` para DDR discretos:** deve ser o bus width posicional (`"x8"`,
> `"x16"`), lido do PN (ex.: `"16"` → `"x16"`). Se o `ChipFamily` não tiver
> decode posicional de largura, deixe `interface=""` — **nunca coloque a geração**
> (`"DDR3"`, `"DDR4"`) no campo interface. Veja §5 abaixo.

### Sufixos de temperatura (após `-`)

| Sufixo | Temperatura | Contexto |
|--------|-------------|---------|
| `-DI` | Industrial (-40°C a 95°C) | Equipamentos embarcados |
| `-EK` | Extended (-40°C a 85°C) | Telecom |
| sem sufixo ou `-` + letras | Comercial (0°C a 85°C) | Consumer |

Temperatura vai no campo `tip` — nunca no `subtype`.

---

## 5. Regras do sistema WTC que se aplicam aqui

### 5.1 Regras de ouro (do CLAUDE.md — nunca quebre)

1. **Banco de produção:** Claude edita arquivos; o usuário roda os comandos.
2. **Só `confidence` ∈ (`confirmed`, `manual`) é autoritativo.** Um KnownPart só vence a gramática com `confidence="confirmed"` ou `"manual"`; com `distributor`/`estimated` o engine usa o decode posicional. *(Não há mais campo `status`; foi removido em jun/2026.)*
3. **Após `populate_nanya --overwrite`, reiniciar o servidor.** O engine usa `lru_cache`.
4. **`val_primary`/`val_secondary` no DecodeMap:**
   - Em mapas de capacidade DDR: `val_primary` = capacidade legível (ex.: `"512MB"`)
   - Nunca escreva `"por die"` em `val_secondary` — o engine acrescenta automaticamente
5. **`confidence="confirmed"` ou `"manual"` vence a gramática.** Dados de IA e
   distribuidor são frequentemente errados — nunca use como fonte única.

### 5.2 Convenções de campo (críticas para Nanya DDR)

| Campo | DDR3/DDR4 discrete | DDR3L | LPDDR |
|-------|--------------------|-------|-------|
| `chip_type` | `"RAM"` | `"RAM"` | `"LPDDR3"` etc. |
| `subtype` | `"DDR3"` / `"DDR4"` | `"DDR3L"` | `"LPDDR3"` etc. |
| `interface` | `"x8"` ou `"x16"` (bus width) | idem | `""` (vazio) |
| `capacity` | bytes/die: `"256MB"`, `"512MB"`, `"1GB"` | idem | GB do pacote |
| `density_gbit` | em Gb: `"2Gb"`, `"4Gb"`, `"8Gb"` | idem | — |

> **`subtype` = SOMENTE a geração.** Nunca: `"DDR3 SDRAM"`, `"DDR3L Low Voltage"`,
> `"DDR4 SDRAM"`. Certo: `"DDR3"`, `"DDR3L"`, `"DDR4"`.

> **`interface` = bus width, não geração.** Nunca: `"DDR3"`, `"DDR4"`. Certo:
> `"x8"`, `"x16"`. Se o ChipFamily não decodifica largura posicionalmente, deixe `""`.

### 5.3 Rentabilidade Nanya

O `assess_profitability` usa `ProfitabilityConfig`:
- DDR2 → sempre **NÃO RENTÁVEL** (geração < 3)
- DDR3 < 2Gb → **NÃO RENTÁVEL** (abaixo de `ddr3_min_gbit=2.0`)
- DDR3 ≥ 2Gb → **RENTÁVEL** (verificar demanda B2B)
- DDR4 → **RENTÁVEL** (após ajuste `ddr4plus_min_gbit=1.0` no admin — **confirmar se já foi feito**)
- LPDDR ≤ LPDDR2 → **NÃO RENTÁVEL** (`lpddr_min_gen`)

> O `assess_profitability` lê do banco (sem cache) — não precisa reiniciar após mudar o config.

### 5.4 Hierarquia de fontes (imutável)

```
Nanya.com (datasheet/spec) > Octopart com fonte Nanya > DigiKey/Mouser >
Distribuidor B2B rastreável > IA/estimativa
```

**Nunca aceitar como fonte única:** fóruns de reparo, WinSource, catálogos de
Shenzhen, análise de IA local, Flash64Box.

---

## 6. O que produzir nesta sessão

### Entregável 1 — `chips/management/commands/populate_nanya.py`

Modelo: veja `populate_samsung.py` e `populate_hynix.py` para a estrutura exata.
Deve criar:
- `Brand` (se não existir): `name="Nanya"`, `short_name="NAN"`
- `ChipFamily` para cada prefixo, com `decode_cap_pos`, `decode_cap_len`,
  `decode_cap_map` apontando para um DecodeMap Nanya
- `DecodeMap` com nome `"NANYA_CAP"` ou prefixo-específico, com as chaves
  confirmadas por Tier 1

**Antes de criar o mapa:** pesquise pelo menos 4-5 PNs reais no Octopart/Nanya para
confirmar as chaves. Não invente chaves de decode.

### Entregável 2 — `NANYA.md` na raiz

Seguindo a estrutura de `SAMSUNG.md`:
- §1 Prefixos (tabela)
- §2 Anatomia do PN
- §3 DecodeMaps
- §4 Famílias — inventário completo
- §5 fix_known_parts — template e regras
- §6 Gaps e roadmap
- §7 Histórico de correções

### Entregável 3 — `fix_known_parts.py` (entradas confirmadas)

Para PNs individuais confirmados via Tier 1 que o agente encontrar durante a
pesquisa. Template:

```python
# ── Nanya DDR3L 4Gb x16 ──────────────────────────────────────────────────
{
    "pn": "NT5CC256M16DP-DI",
    "create": True,
    "create_defaults": {
        "brand_name": "Nanya", "chip_type": "RAM",
        "subtype": "DDR3L", "confidence": "confirmed",
    },
    "fields": {
        "chip_type": "RAM", "subtype": "DDR3L",
        "interface": "x16",          # bus width, não geração
        "capacity": "512MB",         # 4Gb ÷ 8 = 512MB/die
        "confidence": "confirmed", 
    },
    "reason": "Nanya datasheet NT5CC256M16DP: 4Gb DDR3L x16. nanya.com ✓.",
},
```

---

## 7. Armadilhas específicas da Nanya

### 7.1 NT5CC vs NT5CB — confusão frequente

`NT5CC` = DDR3**L** (low-voltage, 1.35V) — o mais comum em notebooks pós-2012.
`NT5CB` = DDR3 padrão (1.5V) — menos comum, mais antigo.
O 3.º caractere define a tensão, não a família. **Não coloque ambos na mesma
ChipFamily.** Prefixos separados, famílias separadas.

### 7.2 Density coding ≠ Samsung

Nanya usa `[N]M[width]` (ex.: `256M16` = 4Gb), enquanto Samsung usa códigos
de 2 chars no decode map (ex.: `8G`=8Gb). A posição de decode no PN Nanya
é diferente — determine por inspeção de PNs reais, não por analogia com Samsung.

### 7.3 NT5PA — prefixo inconsistente

`NT5PA` aparece em alguns notebooks como DDR3L alternativo. Confirme se é
genuinamente distinto de `NT5CC` antes de criar uma família separada.
Se o decode map for igual, considere unificar com `NT5CC` via prioridade.

### 7.4 Interface ≠ geração (bug já existente no sistema)

As famílias em `add_chip_families.py` têm `interface="DDR3"`, `interface="DDR4"`.
**Isso está errado.** Ao criar `populate_nanya.py`, use:
- `interface=""` no ChipFamily (deixa o decode posicional preencher, ou fica vazio)
- `interface="x8"` / `"x16"` apenas se tiver decode posicional no PN

### 7.5 `decode_density_type` vs `decode_cap_map` — mutuamente exclusivos

Para DDR discrete (PC DRAM), use `decode_density_type="pc"` com o mapa `DRAM_PC`
**OU** crie um `NANYA_CAP` próprio com `decode_cap_map`. **Nunca os dois juntos
na mesma família.** (Regra de ouro CLAUDE.md — produz dados conflitantes.)

Se os códigos Nanya coincidem com os do `DRAM_PC` (chaves `1G`, `2G`, `4G`,
`8G`), **reutilize** `decode_density_type="pc"` em vez de criar mapa novo.
Se as chaves são diferentes (ex.: `128M`, `256M`, `512M`), crie `NANYA_CAP`.

### 7.6 `add_chip_families.py` não será removido

O `add_chip_families.py` cria famílias "magras" para várias marcas de uma vez.
Depois de criar `populate_nanya.py`, as famílias Nanya do `add_chip_families.py`
podem ser **desativadas** (`active=False`) no populate ou sobrescritas por
prioridade (família com mais dados e prioridade alta vence). **Nunca delete** uma
família já aplicada em produção — use `active=False`.

---

## 8. Workflow de aplicação

```bash
# 1. (Claude edita o arquivo)
# populate_nanya.py criado/editado

# 2. Usuário roda dry-run (local ou produção):
python manage.py populate_nanya --dry-run

# 3. Usuário aplica:
python manage.py populate_nanya --overwrite

# 4. REINICIAR O SERVIDOR (lru_cache)

# 5. Verificar engine:
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('NT5CC256M16FP-DI'), indent=2, ensure_ascii=False))
"

# 6. Testar PNs chave:
python manage.py shell -c "
from chips.engine import classify
pns = ['NT5CB128M16FP-DI','NT5CC256M16FP-DI','NT5CC512M16IP-EK','NT5AD512M8A3-CK']
for pn in pns:
    r = classify(pn)
    print(pn, '->', r.get('chip_type'), r.get('subtype'), r.get('dram_density',''), r.get('profitable'))
"
```

---

## 9. Checklist de saída da sessão

Antes de terminar, confirme:
- [ ] `populate_nanya.py` criado com Brand + ChipFamily + DecodeMap
- [ ] Pelo menos NT5CC e NT5AD têm decode de capacidade (`grammar_complete=true`)
- [ ] `subtype` sem qualificadores ("DDR3", não "DDR3 SDRAM")
- [ ] `interface` sem geração (vazio ou bus width)
- [ ] Testes de engine passando para pelo menos 4 PNs reais
- [ ] `NANYA.md` criado com anatomia, mapa de capacidade e gaps documentados
- [ ] Entradas `fix_known_parts` para PNs confirmados individualmente
- [ ] `CLAUDE.md` atualizado se algo novo for descoberto (nova regra, nova armadilha)
- [ ] Commit proposto com mensagem clara (usuário executa)

---

## 10. Referências rápidas

```
CLAUDE.md              → regras de ouro do sistema (leia PRIMEIRO)
SAMSUNG.md             → modelo de doc profunda (siga a mesma estrutura para NANYA.md)
chips/engine.py        → classify(), _result_from_family() — não mexa sem proposta formal
chips/management/commands/populate_samsung.py  → modelo de populate_* a seguir
chips/management/commands/add_chip_families.py → famílias Nanya atuais (linhas 352-387)
chips/management/commands/fix_known_parts.py   → onde adicionar PNs confirmados
```

**Nunca edite `engine.py` ou `estoque/views.py` sem propor ao usuário e aguardar
aprovação explícita.**

---

*Gerado em 2026-06-20 como briefing para sessão de classificação Nanya.*
