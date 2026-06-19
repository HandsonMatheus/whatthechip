# COMUNICADO — Convenção de Campos e BUG-8 Micron
**Data:** 2026-06-19 | **Sessão:** Correção de convenção de subtype + K4B DDR3 + Micron MT29TZZZ  
**Destino:** Agente responsável pela base Micron e pela gramática Samsung  
**Prioridade:** Alta — impacto direto na exibição do rótulo da caixa física na esteira

---

## 1. CONTEXTO — O QUE ACONTECEU

Esta sessão foi iniciada com uma captura de tela mostrando o chip **K4B8G0846D** classificado
na esteira. O campo "Caixa Física" exibia:

```
DDR3 PC DRAM 8Gb x8+8G   ← TRUNCADO NO DISPLAY DA ESTEIRA
```

O operador não consegue ler o rótulo. Investigando, identificamos que o `subtype` estava com
valor verbose ("DDR3 PC DRAM 8Gb x8") em vez de apenas a geração ("DDR3"). Isso revelou uma
violação sistemática da convenção de campos que afetava centenas de registros.

---

## 2. COMO O GATEWAY USA OS CAMPOS — ENTENDA O MECANISMO

O rótulo da caixa física é gerado por `estoque/views.py::_compute_gateway`. Para chips RAM:

```python
ct  = (result.get('chip_type') or '').lower()
gen = (result.get('subtype') or result.get('interface') or '').strip()

if 'lpddr' in ct or 'ddr' in ct or ct in ('ram', 'dram', 'sdram'):
    if 'lpddr' in ct or gen.upper().startswith('LPDDR'):
        size = _capacity_gb(result)    # GB total do pacote — para LPDDR
    else:
        size = _density_g(result)      # Gbit por die — para DDR/GDDR
    label = f"{gen}+{size}G"
```

**Ou seja:**
- `gen` vem de `result['subtype']` — que vem do campo `subtype` do KnownPart (se confirmado/manual) ou da gramática
- `size` para DDR/GDDR vem da gramática (campo `dram_density`, em Gbit, decodificado posicionalmente do PN)
- O rótulo é literalmente `"{subtype}+{dram_density_Gbit}G"`

### Consequência direta da violação

| subtype no banco | dram_density gramática | Rótulo gerado | Resultado |
|---|---|---|---|
| `"DDR3 PC DRAM 8Gb x8"` | `8` (Gbit) | `"DDR3 PC DRAM 8Gb x8+8G"` | ❌ Truncado, ilegível |
| `"DDR3"` | `8` (Gbit) | `"DDR3+8G"` | ✅ Legível, correto |
| `"LPDDR3 Mobile"` | — | `"LPDDR3 Mobile+4G"` | ❌ Verbose, truncado |
| `"LPDDR3"` | — | `"LPDDR3+4G"` | ✅ Correto |

A gramática (`dram_density`) estava correta. O problema era o `subtype` verboso.

---

## 3. A CONVENÇÃO CORRETA DOS CAMPOS (CANÔNICA)

Esta convenção é permanente e aplica-se a todos os chips RAM no banco e na gramática:

### `chip_type`
- RAM discreta (DDR1, DDR2, DDR3, DDR3L, GDDR3, GDDR5, DDR4...): **`"RAM"`**
- LPDDR (móvel): **a geração exata** — `"LPDDR3"`, `"LPDDR4"`, `"LPDDR4X"`, `"LPDDR5"`, etc.
- NÃO usar `"DDR3"`, `"DDR3L"`, `"DDR"` como chip_type — esses pertencem ao `subtype`

Por quê `"RAM"` para DDR/GDDR? O gateway verifica `'ddr' in ct` para entrar no branch RAM.
`"RAM"` também funciona (`ct in ('ram', ...)`), e é a categoria genérica correta.

### `subtype`
- **SOMENTE a geração** — sem densidade, sem bus width, sem "PC DRAM", sem "Mobile", sem "Multi-Channel"
- Exemplos corretos: `"DDR1"`, `"DDR2"`, `"DDR3"`, `"DDR3L"`, `"GDDR3"`, `"LPDDR3"`, `"LPDDR4"`, `"LPDDR4X"`
- Ambiguidade genuína: `"DDR3/DDR3L"` (chip que suporta ambas as voltagens), `"LPDDR4/4X"` — aceitáveis
- `subtype` é o que aparece como prefixo do rótulo da caixa física

### `interface`
- Bus width: `"x4"`, `"x8"`, `"x16"`, `"x32"` — somente isso
- Para LPDDR eMCP: deixar em branco (o engine zera automaticamente para eMCP)
- NÃO usar `"DDR3"`, `"DDR3L"`, `"LPDDR4"` no campo interface

### `capacity`
- Capacidade por die em MB/GB: `"512MB"`, `"1GB"`, `"2GB"`, etc.
- Para eMCP: capacidade total do pacote (ex: `"8GB"` para 8GB NAND + 1GB LPDDR3)
- Para DDR: 1 die = densidade Gbit ÷ bus_width × 8 bytes ÷ 8 (ex: 4Gbit x8 = 512MB por die)

### `dram_density`
- **NÃO É campo do KnownPart** — é calculado pelo engine a partir do PN via DecodeMap
- Aparece no resultado do `classify()` como `result['dram_density']`
- É o número Gbit que aparece após o "+" no rótulo: DDR3+**8**G

---

## 4. O QUE FOI CORRIGIDO — ARQUIVOS E ESCOPO

### 4.1 `fix_known_parts.py` (200+ linhas alteradas)

**K4B DDR3 — convenção completa**

Todos os KnownParts K4B (Samsung DDR3/DDR3L) estavam com:
```python
# ANTES (violação)
"chip_type": "DDR3",
"subtype":   "DDR3 PC DRAM 8Gb x8",
"interface": "DDR3",

# DEPOIS (correto)
"chip_type": "RAM",
"subtype":   "DDR3",
"interface": "x8",
```

Afetou todas as variantes: x8 (0846), x16 (1646), x4 (0446 — servidor/ECC).

**K4H DDR1 — chip_type e subtype verbose**

Chips Samsung DDR1 (K4H*) estavam:
```python
# ANTES
"chip_type": "DDR",
"subtype":   "DDR1 PC DRAM 512Mb x8",

# DEPOIS
"chip_type": "RAM",
"subtype":   "DDR1",
```

Afetados: K4H510438G (x4), K4H510838G (x8), K4H511638G (x16), K4H561638D (x16, 256Mb), K4H561638D-TCB3.

**K4T DDR2 — chip_type e subtype verbose**

Chips Samsung DDR2 (K4T*) estavam:
```python
# ANTES
"chip_type": "DDR",
"subtype":   "DDR2 PC DRAM 512Mb x16",

# DEPOIS
"chip_type": "RAM",
"subtype":   "DDR2",
```

Afetados: K4T51163QN (x16), -BI, -BHF8, -BFF8; K4T51083QN (x8), -BI; K4T1G084QJ (1Gb x8), K4T1G083QJ, -BI; K4T1G164QJ (1Gb x16), K4T1G163QJ, -BI, -BHF8, -BFF8.

**LPDDR verbose**

```python
# ANTES
"subtype": "LPDDR3 Mobile",
"subtype": "LPDDR4 Multi-Channel",
"subtype": "LPDDR4X Multi-Channel",
"subtype": "LPDDR4 standalone",     # MT53B Micron
"subtype": "NOR Flash + Mobile SDRAM (legado)",
"subtype": "Mobile SDR SDRAM (Toshiba)",

# DEPOIS
"subtype": "LPDDR3",
"subtype": "LPDDR4",
"subtype": "LPDDR4X",
"subtype": "LPDDR4",
"subtype": "NOR Flash + SDRAM",
"subtype": "SDR SDRAM",
```

**Base PNs x16 K4B corrigidos**

K4B4G1646B, K4B4G1646E, K4B8G1646Q estavam com `chip_type: "DDR"` em `create_defaults`
e sem `chip_type`/`subtype` em `fields`. Corrigido para `chip_type: "RAM"` + `subtype: "DDR3/DDR3L"`
em ambas as seções (para criar e para atualizar registros existentes).

---

### 4.2 `populate_samsung.py` (ChipFamily.subtype)

Os subtypes das ChipFamily alimentam a gramática e aparecem no resultado do `classify()`
quando o chip é decodificado pela gramática (sem KnownPart confirmado). Estavam verbose:

```python
# ANTES
subtype="LPDDR4 Multi-Channel"   # K3RG
subtype="LPDDR4X Mobile"         # K4U
subtype="LPDDR1 / Mobile DDR (legado)"  # K4M, K4X
subtype="LPDDR2 Multi-Channel PoP"      # família PoP
subtype="LPDDR3 Multi-Channel PoP"      # família PoP
subtype="NOR Flash + Mobile SDRAM (legado)"

# DEPOIS
subtype="LPDDR4"
subtype="LPDDR4X"
subtype="LPDDR1"
subtype="LPDDR2"
subtype="LPDDR3"
subtype="NOR Flash + SDRAM"
```

**Por que isso importa:** A gramática é a "válvula de escape" — cobre PNs não confirmados no banco.
Se o subtype da família está verbose, todo chip dessa família não confirmado vai gerar rótulo truncado.

---

### 4.3 `populate_rayson.py` (ChipFamily.subtype)

```python
# ANTES
subtype="LPDDR3 Mobile 1GB"     # capacity embutida no subtype!
subtype="LPDDR3 Mobile 2GB"
subtype="LPDDR4/4X Mobile 1GB"
subtype="LPDDR4/4X Mobile 2GB"
subtype="LPDDR4/4X Mobile 4GB"
subtype="LPDDR4/4X Mobile 8GB"

# DEPOIS
subtype="LPDDR3"
subtype="LPDDR3"
subtype="LPDDR4/4X"
subtype="LPDDR4/4X"
subtype="LPDDR4/4X"
subtype="LPDDR4/4X"
```

**Nota sobre "LPDDR4/4X":** Chips Rayson com esse prefixo são genuinamente ambíguos
(cobrem ambas as gerações dependendo do lote). A notação com "/" é aceitável para ambiguidade real,
igual ao "DDR3/DDR3L" da Samsung. O que não é aceitável é "Mobile" e capacidade embutida.

---

### 4.4 CSVs PSG (data/psg/)

67 linhas corrigidas em 4 arquivos (import via `import_samsung_psg.py`):

| Arquivo | Linhas | Correção |
|---|---|---|
| `psg_1h2017_mobile_dram.csv` | 16 | LPDDR4 Multi-Channel → LPDDR4, LPDDR3 Mobile → LPDDR3 |
| `psg_2h2014_mobile_dram.csv` | 14 | LPDDR3 Mobile → LPDDR3 |
| `samsung_global_lpddr3.csv` | 12 | LPDDR3 Mobile → LPDDR3 |
| `samsung_global_lpddr4_2017_2020.csv` | 25 | LPDDR4 Multi-Channel → LPDDR4 |

Esses CSVs são importados como KnownParts pelo `import_samsung_psg.py`.
A correção garante que novos imports não reinsiram subtypes verbose.

---

## 5. NOVOS PNs ADICIONADOS — Samsung DDR3 x8

### Por que K4B x8 e não x16?

Os chips x8 (bus width = 8 bits) são mais comuns em esteiras de reciclagem de smartphones
e tablets Android (SoC com memória discreta embarcada). Os x16 já estavam cobertos.
Fonte Tier 1 em todos os casos: Samsung Semiconductor Global + Octopart.

### K4B4G0846E — DDR3 4Gbit x8, E-die (512MB por die)

Sufixo "BC" = DDR3 (1.5V), "BY" = DDR3L (1.35V/1.5V dual).

| PN | Tipo | Confidence |
|---|---|---|
| K4B4G0846E | base | confirmed |
| K4B4G0846E-BCK0 | DDR3 | confirmed |
| K4B4G0846E-BCNB | DDR3 | confirmed |
| K4B4G0846E-BYK0 | DDR3L | confirmed |
| K4B4G0846E-BYMA | DDR3L | confirmed |

### K4B8G0846D — DDR3 8Gbit x8, D-die (1GB por die)

Sufixo "MC" = DDR3 (1.5V), "MY" = DDR3L (1.35V).

| PN | Tipo | Confidence |
|---|---|---|
| K4B8G0846D | base | confirmed |
| K4B8G0846D-MCMA | DDR3 | confirmed |
| K4B8G0846D-MCNB | DDR3 | confirmed |
| K4B8G0846D-MCK0 | DDR3 | confirmed |
| K4B8G0846D-MYK0 | DDR3L | confirmed |

**Este é o chip que mostrou o bug de truncamento.** Após a correção:
- `chip_type = "RAM"`, `subtype = "DDR3"`, `interface = "x8"`, `capacity = "1GB"`
- Rótulo da caixa: **`DDR3+8G`** ✅

### K4B1G0846I — DDR3 1Gbit x8, I-die (128MB por die)

Chip mais antigo/raro, ainda aparece em lotes de reciclagem de hardware legacy.

| PN | Tipo | Confidence |
|---|---|---|
| K4B1G0846I | base | confirmed |
| K4B1G0846I-BCK0 | DDR3 | confirmed |
| K4B1G0846I-BYK0 | DDR3L | confirmed |
| K4B1G0846I-BYMA | DDR3L | confirmed |
| K4B1G0846I-BYNB | DDR3L | confirmed |

### K4W4G1646D — GDDR3 4Gbit x16 D-die (512MB por die)

Fonte: Octopart (K4W4G1646D-BC1A = GDDR3 256Mx16). Adicionado base PN (manual) + sufixo (distributor).

| PN | Confidence |
|---|---|
| K4W4G1646D | manual |
| K4W4G1646D-BC1A | distributor |

---

## 6. PNs REMOVIDOS — K4EBE304EB e K4EBE304EC

Esses eram PNs base artificiais de 10 caracteres criados para LPDDR3 Samsung.
O problema: **LPDDR3 Samsung não tem separação por hífen**. O PN completo É o marking
(ex: `K4EBE304EBEGCF` — 14 chars, sem hífen separador).

Ao contrário do DDR3 (onde `K4B4G1646E` é o marking real antes do hífen),
no LPDDR3 a base de 10 chars não corresponde a nenhum chip físico real.
Esses PNs "base" causavam falsos positivos no fuzzy matching — buscas por
PNs parecidos retornavam esses registros sem sentido.

**Ação:** Removidos de `fix_known_parts.py`. PNs LPDDR3 completos (14 chars) permanecem.

---

## 7. BUG-8 — MT29TZZZ É LPDDR3, NÃO LPDDR2

### O que estava errado

A API FBGA da Micron retornava strings como:
```
"MLC EMMC/LPDDR2 72G VFBGA"   ← para chips MT29TZZZ 8D5
"MLC EMMC/LPDDR2 40G VFBGA"   ← para chips MT29TZZZ 8D4
```

Isso levou o sistema a classificar chips MT29TZZZ como LPDDR2. O `MIC_TZZZ_GEN` tinha a
chave `'8'→"LPDDR2"` porque a API dizia LPDDR2 para os chips com pn[8]='8'.

### Por que a API estava errada

A API Micron FBGA usa o campo `part-name` que é gerado por texto livre e mistura informações
de famílias relacionadas. Especificamente, ela confundia:

| Família | Tipo RAM | Encapsulamento | Bolas |
|---|---|---|---|
| `MT29PZZZ` | **LPDDR2** | VFBGA | 162-ball |
| `MT29TZZZ` | **LPDDR3** | VFBGA | 221-ball |

São pacotes fisicamente distintos, com pinagens incompatíveis. A API retornava
"LPDDR2" para MT29TZZZ porque o texto `part-name` de chips NAND relacionados
mencionava LPDDR2 — não o tipo RAM do próprio chip.

### Evidências Tier 1 que confirmam LPDDR3

1. **Datasheet oficial Micron** (PDF auditado via NXP community):
   `MT29TZZZ8D5JKEZB = "MLC e·MMC™ and Mobile LPDDR3 221-Ball MCP"`
   com seção "Mobile-LPDDR3-Specific Features" e data rate até 1866 Mb/s → LPDDR3.

2. **DigiKey**: `MT29TZZZ8D5BKFAH = "DRAM - LPDDR3 Memory IC ... 8Gbit (LPDDR3)"`

3. **Padrão de famílias Micron**: MT29PZZZ = LPDDR2 (162-ball); MT29TZZZ = LPDDR3 (221-ball).
   O prefixo define o tipo, não o campo `part-name` da API.

### O que foi corrigido

**`populate_micron_mcp.py`:**
- DecodeMap `MIC_TZZZ_GEN`: toda a família MT29TZZZ mapeada para LPDDR3 uniformemente
- Antes havia distinção por pn[10] (`8D5`→LPDDR2, `8D6`→LPDDR3) — incorreta
- Comentários atualizados com evidência e fonte hierárquica

**`chips/engine.py`:**
```python
# Adicionado dentro do bloco is_emcp:
if _decoded_gen and not _CAP_RE.search(_decoded_gen):
    r["subtype"] = _decoded_gen
```

Esse trecho sincroniza o campo `subtype` do resultado com o que o gen map decodificou.
Sem isso, `subtype` ficava com o default da família (ex: "LPDDR3") mesmo quando o gen map
produzia um tipo mais específico. O guard `_CAP_RE.search` evita que subtypes como
"LPDDR4X 6GB" (SK Hynix embute capacidade no gen map) contaminem o subtype.

**`fix_known_parts.py`:**
- `MT29TZZZ8D5BKFAH`: corrigido `emcp_ram → "LPDDR3 1GB"`, `subtype → "LPDDR3"`, `confidence → confirmed`
- `MT29TZZZ8D4BKFAH`: mesma correção prevista — mas o registro NÃO EXISTIA no banco (ver pendência)

---

## 8. O QUE O fix_known_parts APLICOU NO BANCO (resultado completo)

Execução de `python manage.py fix_known_parts` em 2026-06-19 aplicou **23 correções**:

| PN | Campos corrigidos |
|---|---|
| KLUDG4U1EA | doc_url: None → '' |
| K4B4G1646B | chip_type: 'DDR' → 'RAM' |
| K4B4G1646E | chip_type: 'DDR' → 'RAM'; subtype: '' → 'DDR3/DDR3L' |
| K4B8G1646Q | chip_type: 'DDR' → 'RAM'; subtype: '' → 'DDR3/DDR3L' |
| K4H510438G | chip_type: 'DDR' → 'RAM'; subtype: 'DDR1 PC DRAM 512Mb x4' → 'DDR1' |
| K4H510838G | chip_type: 'DDR' → 'RAM'; subtype: 'DDR1 PC DRAM 512Mb x8' → 'DDR1' |
| K4H511638G | chip_type: 'DDR' → 'RAM'; subtype: 'DDR1 PC DRAM 512Mb x16' → 'DDR1' |
| K4H561638D | chip_type: 'DDR' → 'RAM'; subtype: 'DDR1 PC DRAM 256Mb x16' → 'DDR1' |
| K4H561638D-TCB3 | chip_type: 'DDR' → 'RAM'; subtype: 'DDR1 PC DRAM 256Mb x16' → 'DDR1' |
| K4T51163QN | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 512Mb x16' → 'DDR2' |
| K4T51163QN-BI | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 512Mb x16' → 'DDR2' |
| K4T51163QN-BHF8 | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 512Mb x16' → 'DDR2' |
| K4T51163QN-BFF8 | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 512Mb x16' → 'DDR2' |
| K4T51083QN | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 512Mb x8' → 'DDR2' |
| K4T51083QN-BI | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 512Mb x8' → 'DDR2' |
| K4T1G084QJ | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x8' → 'DDR2' |
| K4T1G083QJ | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x8' → 'DDR2' |
| K4T1G083QJ-BI | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x8' → 'DDR2' |
| K4T1G164QJ | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x16' → 'DDR2' |
| K4T1G163QJ | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x16' → 'DDR2' |
| K4T1G163QJ-BI | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x16' → 'DDR2' |
| K4T1G164QJ-BHF8 | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x16' → 'DDR2' |
| K4T1G164QJ-BFF8 | chip_type: 'DDR' → 'RAM'; subtype: 'DDR2 PC DRAM 1Gb x16' → 'DDR2' |

Nota: 247 registros já estavam corretos (confirmação de que os commits anteriores aplicaram bem).

---

## 9. PENDÊNCIA — MT29TZZZ8D4BKFAH

A entrada em `fix_known_parts.py` para `MT29TZZZ8D4BKFAH` **não tem `"create": True`**,
então o comando só tenta atualizar — e como o registro não existe no banco, ele foi
reportado como "⚠ Não encontrado no banco".

O PN é válido (família MT29TZZZ, chave 8D4 = 4GB NAND + 1GB LPDDR3). Para resolver:

**Opção A (recomendada):** Adicionar `"create": True` e `"create_defaults"` à entrada:
```python
{
    "pn": "MT29TZZZ8D4BKFAH",
    "create": True,
    "create_defaults": {
        "brand_name": "Micron",
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",
        "status":     "enriched",
        "confidence": "confirmed",
    },
    "fields": {
        "emcp_ram":   "LPDDR3 1GB",
        "emcp_nand":  "4GB",
        "subtype":    "LPDDR3",
        "confidence": "confirmed",
        "status":     "enriched",
    },
    ...
}
```

**Opção B:** Deixar para o pipeline FBGA (`enrich_micron_fbga.py` + `fill_capacity_from_micron_api.py`)
criar o registro quando o chip aparecer na esteira. A gramática MT29TZZZ já está correta (LPDDR3),
então o classify() vai funcionar mesmo sem KnownPart.

---

## 10. REGRAS PERMANENTES — PARA ADICIONAR AO ARQUIVO DE CONHECIMENTO

### R1 — Convenção de campos para RAM discreta

```
chip_type = "RAM"
subtype   = geração (ex: "DDR3", "DDR1", "GDDR3")
interface = bus width (ex: "x8", "x16", "x4")
capacity  = por die em MB/GB (ex: "512MB", "1GB")
```

### R2 — Convenção de campos para LPDDR (móvel)

```
chip_type = geração (ex: "LPDDR3", "LPDDR4", "LPDDR4X")
subtype   = geração (mesmo que chip_type, só a geração)
interface = "" (vazio para LPDDR standalone; o engine preenche)
capacity  = capacidade total do pacote em GB
```

### R3 — Convenção de campos para eMCP

```
chip_type  = "eMCP"
subtype    = geração RAM (ex: "LPDDR3", "LPDDR4X")
emcp_ram   = "LPDDR3 1GB" (tipo + capacidade RAM)
emcp_nand  = "8GB" (capacidade NAND)
interface  = "" (engine zera)
```

### R4 — Subtype = SOMENTE a geração (regra universal)

Nunca incluir no `subtype`:
- Capacidade (Gbit ou GB)
- Bus width (x8, x16)
- Qualificadores ("Mobile", "Multi-Channel", "PoP", "standalone", "PC DRAM")
- Marca ("Samsung", "Toshiba")

### R5 — API FBGA Micron não é fonte para tipo de RAM

O campo `part-name` da API Micron FBGA não é confiável para determinar o tipo de RAM.
Use o **prefixo da família PN** para determinar o tipo:

| Prefixo | Tipo RAM |
|---|---|
| MT29PZZZ | LPDDR2 |
| MT29TZZZ | LPDDR3 |
| MT29FZZZ | LPDDR4X |

Para confirmar, use: datasheet oficial Micron → DigiKey → AllDatasheet.
**Nunca use `part-name` da API como fonte primária para tipo de RAM.**

### R6 — LPDDR3 Samsung: base PN não existe antes de hífen

PNs LPDDR3 Samsung são strings completas (14 chars, sem hífen).
Não criar "base PNs" artificiais de 10 chars — causam fuzzy falso-positivo.
Diferente do DDR3 (K4B*) onde o marking real é a parte antes do hífen.

### R7 — Sufixos K4B e voltagem

| Prefixo sufixo | Tipo | Voltagem |
|---|---|---|
| BC | DDR3 | 1.5V |
| BY | DDR3L | 1.35V / 1.5V dual (chips 1Gb-4Gb) |
| MC | DDR3 | 1.5V (chips 8Gb) |
| MY | DDR3L | 1.35V (chips 8Gb) |

Bus width pelo PN: `0846`=x8, `1646`=x16, `0446`=x4 (servidor ECC).

---

## 11. COMANDOS PARA APLICAR (usuário executa)

```bash
python manage.py populate_samsung --overwrite   # gramática Samsung (lru_cache)
python manage.py populate_rayson               # gramática Rayson
python manage.py populate_micron_mcp --overwrite  # BUG-8 Micron
python manage.py fix_known_parts               # KnownParts novos/corrigidos
# Reiniciar servidor após populate (lru_cache)
```

No Render (produção), após push para `main`:
```bash
python manage.py populate_samsung --overwrite
python manage.py populate_micron_mcp --overwrite
python manage.py fix_known_parts
# Reiniciar web service no dashboard Render
```

---

*Documento gerado em 2026-06-19 ao fim da sessão de correção de convenção de campos.*
*Fonte da verdade: código em `chips/engine.py`, `chips/models.py`, `MICRON.md`.*
