# SANDISK.md — Bíblia Técnica e de Negócio
**WhatTheChip — documento vivo de referência**
Criado: 2026-06-26
> Leia antes de tocar em qualquer arquivo relacionado à SanDisk / Western Digital.
> Em conflito com qualquer outro doc, o **código é a fonte da verdade**
> (`chips/engine.py`, `populate_sandisk.py`).
> Atualize este arquivo quando aprender algo duradouro.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro e limites de escopo

### 0.1 Arquivos que PODE editar (escopo SanDisk)

```
chips/management/commands/populate_sandisk.py   ← gramática mestre: ChipFamilies (sem DecodeMaps)
chips/management/commands/fix_known_parts.py    ← somente entradas brand_name="SanDisk"
```

### 0.2 Arquivos que NÃO PODE tocar sem revisão explícita do usuário

```
chips/engine.py                                    ← motor global — mudança afeta TODAS as marcas
estoque/views.py                                   ← gateway global — mudança afeta TODAS as marcas
chips/management/commands/populate_samsung.py
chips/management/commands/populate_hynix.py
chips/management/commands/populate_micron_mcp.py
chips/management/commands/add_chip_families.py     ← compartilhado — SD7DP foi migrado para populate_sandisk
chips/management/commands/fix_known_parts.py       ← seções de OUTRAS marcas
```

> Se precisar de mudança em `engine.py` ou `estoque/views.py`, **proponha ao usuário**
> com justificativa e impacto — nunca edite silenciosamente.

### 0.3 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca execute `populate_*`,
   `fix_known_parts`, `migrate` sem confirmação explícita do usuário.

2. **`--dry-run` antes de qualquer comando que escreve no banco.** Sempre.

3. **Reiniciar o servidor após `populate_sandisk --overwrite`.** O `lru_cache` do engine
   não invalida automaticamente no processo do servidor web.

4. **`chip_type="eMMC"` para eMMC standalone. `chip_type="eMCP"` para eMCP. `chip_type="UFS"` para UFS.**
   Nunca usar `"NAND"`, `"Flash"`, `"iNAND"` no `chip_type`. O gateway quebra com tipos não reconhecidos.

5. **`subtype=""` (vazio) para eMMC e UFS standalone. `subtype=geração RAM` para eMCP.**
   Valores como `"eMMC standalone (iNAND 7 Series)"` ou `"UFS standalone (iNAND OEM)"` são verbose —
   estão nos `ChipFamily.subtype` atuais do `populate_sandisk.py` e precisam de correção (ver §8.1).
   Mitigado no label pelo `canonical_gen`, mas visível no card de busca.

6. **`interface=""` (vazio) para eMCP.** O `populate_sandisk.py` atual tem bugs neste campo
   para as famílias SDEM e SDAD — documentados em §8.1 e a serem corrigidos no próximo
   `populate_sandisk --overwrite`.

7. **`emcp_ram` = tipo ANTES da capacidade.** `"LPDDR3 2GB"` ✓ — nunca `"2GB LPDDR3"`.
   O campo `emcp_nand` é só GB: `"16GB"`, sem prefixo de tipo.

8. **SanDisk NÃO usa DecodeMaps.** A capacidade é declarada no sufixo do PN (após o traço:
   `-8G`, `-16G`, `-32G`). O decode posicional não funciona de forma confiável por causa do
   comprimento variável do die code intermediário. **fix_known_parts.py é a única fonte de
   capacidade para PNs SanDisk — não existe gramática de capacidade para esta marca.**

9. **Sufixo do PN é normalizado pelo engine.** `re.sub(r"[^A-Z0-9]", "", pn)` — o traço
   é removido: `SDIN9DW4-16G` → `SDIN9DW416G`. Todas as entradas em `fix_known_parts.py`
   devem usar o PN **normalizado** (sem traço, sem espaço).

10. **221-ball = LPDDR3.** No catálogo Preduo, a categoria 221-ball é exclusivamente
    eMMC + LPDDR3. A categoria 254-ball corresponde a LPDDR4. Nunca presumir LPDDR4 num
    eMCP SanDisk 221-ball sem fonte Tier 1 separada.

### 0.4 Hierarquia de fontes (imutável)

```
1. Western Digital / wdc.com / westerndigital.com
   → documentação oficial pós-aquisição (2016+). Fonte definitiva para todas as famílias iNAND.
2. Datasheet SanDisk oficial (histórico)
   → datasheets pré-WD ainda são válidos para famílias legadas (ex: iNAND Ultra eMMC 4.41)
   → ex: doc# 80-36-03666 "Ultra e.MMC 4.41 I/F Released Data Sheet V1.2 May 2012"
3. Octopart (PN confirmado com especificações)
   → verificar se a fonte citada não é apenas outro distribuidor sem datasheet
4. Distribuidor B2B rastreável (Win Source, Veswin, Puris, ssfkg)
   → só como apoio; nunca rebaixa um "confirmed" com dado de distribuidor
5. Preduo (preduo.com)
   → catálogo de reciclagem; confiável para identificar tipo (eMMC vs eMCP, ball count)
   → não confiável para specs elétricos precisos
6. IA externa (qualquer LLM)
   → ÚLTIMO RECURSO — nunca fonte primária; verificar SEMPRE antes de usar
```

**Nunca aceitar como fonte única:** yoycart/chinahao sem cruzamento, eBay listings,
catálogos genéricos de Shenzhen sem rastreabilidade, output de IA sem verificação.

---

## 1. Visão Geral

SanDisk (adquirida pela Western Digital em 2016) fabrica chips de armazenamento embarcado
para o mercado de consumo — principalmente eMMC, eMCP e UFS para smartphones e tablets.
Na bancada de reciclagem da eMiner, os chips SanDisk aparecem com frequência moderada,
predominantemente eMMC standalone de gerações 4.41 a 5.1.

**Ponto crítico:** SanDisk **não usa decode posicional de capacidade**. Toda a capacidade
fica no sufixo após o traço (declarativo de fábrica). O engine strip o traço ao normalizar,
então a capacidade só fica acessível se o PN estiver confirmado no `fix_known_parts.py`.
Chips SanDisk sem KnownPart no banco entram na gramática sem capacidade — retornam
`profitable="INDETERMINADO"` até serem registrados manualmente.

| Categoria | Famílias mapeadas | Decode completo | Sem decode cap | Status |
|---|---|---|---|---|
| eMMC standalone | 3 (SD7DP, SDIN, SDMAG) | 0 | 3 (todo via fix_known_parts) | ⚠️ Parcial |
| UFS standalone | 2 (SDINB, SDHQB) | 0 | 2 (todo via fix_known_parts) | ⚠️ Parcial |
| eMCP (eMMC + LPDDR) | 2 (SDEM, SDAD) | 0 | 2 (todo via fix_known_parts) | ⚠️ Parcial |
| **TOTAL** | **7** | **0** | **7** | ⚠️ Base inicial |

**Arquivos que definem as famílias:**
- `chips/management/commands/populate_sandisk.py` — gabarito de famílias (sem DecodeMaps)
- `chips/management/commands/fix_known_parts.py` — KnownParts confirmados (seção SanDisk)

**Frequência na bancada:**
- `SDIN` é o prefixo mais comum — iNAND legacy (eMMC 4.5/5.0/5.1) em smartphones mid-range
- `SDAD` é o eMCP mais frequente — 221-ball LPDDR3, aparece em Smart POS e mid-range
- `SD7DP` e `SDMAG` aparecem com frequência menor
- `SDINB`, `SDHQB` (UFS) — pouco volume na esteira até 2026-06

---

## 2. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

### 2.1 Tabela canônica por tipo de chip

| Tipo de chip | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| eMMC | `"eMMC"` | `""` (vazio) | `"eMMC 4.41"` / `"eMMC 5.0"` / `"eMMC 5.1"` | `capacity` (GB) |
| UFS | `"UFS"` | `""` (vazio) | `"UFS 2.1"` / `"UFS 3.0"` / `"UFS 3.1"` | `capacity` (GB) |
| eMCP | `"eMCP"` | geração RAM: `"LPDDR3"` | `""` (VAZIO — sempre) | `emcp_nand` + `emcp_ram` |

> **Atenção:** os `ChipFamily.subtype` em `populate_sandisk.py` estão verbose (ver §8.1).
> Isso é um bug conhecido — não é a convenção. Ao criar KnownParts em `fix_known_parts.py`,
> use sempre o subtype canônico: `""` para eMMC/UFS, `"LPDDR3"` (ou geração correta) para eMCP.

### 2.2 Regras absolutas do `subtype`

- `subtype` = **vazio** para eMMC e UFS standalone
- `subtype` = **geração da RAM** (somente) para eMCP — ex.: `"LPDDR3"`, `"LPDDR4"`
- **NUNCA** colocar no `subtype`: "eMMC standalone", "iNAND 7 Series", "OEM", "UFS standalone",
  "eMMC + LPDDR", velocidade, tensão ou outros qualificadores verbosos

> **Label protegido por `canonical_gen` (2026-06-19) — FONTE ÚNICA da convenção.**
> O label da caixa é montado em `estoque/views.py::_compute_destination`, que passa o
> `subtype` por `chips/conventions.py::canonical_gen()`. Ela reduz o subtype ao token
> canônico por whitelist. O subtype verboso nos ChipFamilies SanDisk não quebra o label,
> mas aparece no card de busca. Corrigir no próximo `populate_sandisk --overwrite`.

### 2.3 Campo `interface` — regras SanDisk

- **eMMC:** versão do protocolo — `"eMMC 4.41"`, `"eMMC 5.0"`, `"eMMC 5.1"`. Se não confirmado: `"eMMC"` genérico.
- **UFS:** versão — `"UFS 2.1"`, `"UFS 3.0"`, `"UFS 3.1"`. Se ambíguo: `"UFS 2.1 / 3.0"`.
- **eMCP:** `""` (string vazia). **SEMPRE.** O `populate_sandisk.py` atual tem bug neste campo
  para SDEM e SDAD (interface="eMMC + LPDDR") — a ser corrigido.

### 2.4 Gateway de estoque — como o label é montado

```
eMMC:
  chip_type="eMMC" + capacity="16GB" → label "EMMC16GB"

UFS:
  chip_type="UFS" + capacity="128GB" → label "UFS128GB"

eMCP:
  chip_type="eMCP" + emcp_nand="16GB" + emcp_ram="LPDDR3 2GB"
  → emcp_ram_gb = 2 → label "EMCP16+2"
```

### 2.5 Campos `emcp_nand` e `emcp_ram`

- `emcp_nand` = capacidade NAND em GB: `"16GB"`, `"32GB"` — sem prefixo de tipo, só o número + GB
- `emcp_ram` = **tipo ANTES da capacidade**: `"LPDDR3 2GB"`, `"LPDDR3 1GB"` — **nunca** `"2GB LPDDR3"`

### 2.6 Tabela completa de campos — O que vai / O que NÃO vai

| Campo | O que vai | O que NÃO vai |
|-------|-----------|---------------|
| `chip_type` | `"eMMC"`, `"UFS"`, `"eMCP"` | `"iNAND"`, `"NAND"`, `"Flash"`, `"eMMC + LPDDR"` |
| `subtype` | `""` (eMMC/UFS) · geração RAM `"LPDDR3"` (eMCP) | "eMMC standalone", "iNAND 7 Series", "OEM", specs verbosos |
| `interface` | versão protocolo para eMMC/UFS: `"eMMC 5.1"`, `"UFS 2.1"` | qualquer coisa para eMCP (`""` vazio sempre) · geração RAM (`"LPDDR3"`) no interface |
| `capacity` | capacidade total do pacote em GB: `"8GB"`, `"16GB"`, `"32GB"` | gigabits · capacity de eMCP (usar emcp_nand/emcp_ram) |
| `emcp_nand` | (só eMCP) NAND em GB: `"16GB"`, `"32GB"` | tipo de interface · RAM |
| `emcp_ram` | (só eMCP) **tipo + capacidade**: `"LPDDR3 2GB"`, `"LPDDR3 1GB"` — tipo VEM ANTES | só o número (`"2GB"`) · ordem invertida (`"2GB LPDDR3"`) |
| `tip` | tudo que não couber: ball count, notas de geração, aviso de versão OCR | — |

---

## 3. Anatomia do PN por Família

### 3.1 Convenção geral SanDisk — Sufixo Declarativo de Capacidade

**Diferença fundamental em relação a Samsung/SK Hynix:** a capacidade SanDisk não está
numa posição fixa do PN — está sempre no **sufixo após o traço** (declarativo de fábrica).

```
[Prefixo Família] [Die Code / Variante] - [Capacidade]
  └─ Identifica família      └─ Processo WD     └─ -4G=4GB · -8G=8GB
                                                    -16G=16GB · -32G=32GB
                                                    -64G=64GB · -128G=128GB
```

O engine normaliza: `SDIN9DW4-16G` → `SDIN9DW416G` (strip do traço e tudo não-alfanumérico).
Por isso `fix_known_parts.py` deve usar o PN **sem traço** (normalizado).

**Por que decode posicional falha:** o die code intermediário tem comprimento variável:
```
SD7DP 24C -4G   → normalizado: SD7DP24C4G  (10 chars, "4G" em pos 8, len 2)
SD7DP 24C -16G  → normalizado: SD7DP24C16G (11 chars, "16G" em pos 8, len 3)  ← comprimento diferente!
SD7DP 25F -128G → normalizado: SD7DP25F128G (12 chars, "128G" em pos 9, len 4) ← diferente ainda
```
Portanto `decode_cap_pos/decode_cap_map` não se aplica — todos os `ChipFamily` SanDisk
têm `decode_cap_pos=None`.

### 3.2 Família SD7DP — eMMC 5.1 iNAND 7 Series

Linha iNAND de sétima geração (pré-WD). eMMC 5.1 standalone — sem RAM.

```
S  D  7  D  P  [die_code]  -  [cap_suffix]
0  1  2  3  4      5+         variável
```

- `pn[0:5]` = prefixo família `"SD7DP"`
- `pn[5+]` = die code (identifica processo WD — não é capacidade): ex.: `24C`, `25F`, `3W`
- Sufixo após traço: `-4G`=4GB · `-8G`=8GB · `-16G`=16GB · `-32G`=32GB · `-64G`=64GB

**Exemplos confirmados:** `SD7DP24C-4G` (4GB, WD datasheet ✓)

> ⚠️ **SD7DP já existia em `add_chip_families.py`** antes da criação do `populate_sandisk.py`.
> Foi migrado para `populate_sandisk.py` (esta é a fonte canônica) — o `add_chip_families.py`
> contém comentário de migração. Não recriar em `add_chip_families.py`.

### 3.3 Família SDIN — iNAND eMMC Legacy

Família mais comum na esteira. Cobre múltiplas sub-séries de gerações eMMC 4.5, 5.0 e 5.1.

```
S  D  I  N  [sub_série_code]  -  [cap_suffix]
0  1  2  3      4+               variável
```

Sub-séries confirmadas em Octopart/Preduo:

| Sub-série | Interface | Capacidades confirmadas | Fonte |
|-----------|-----------|------------------------|-------|
| `SDIN7DU2` | eMMC 4.41 (iNAND Ultra) | 8GB (SDIN7DU2-8G) | Datasheet doc# 80-36-03666 ✓ |
| `SDIN9DW4` | eMMC 5.0 (iNAND 7 Series) | 16GB, 32GB | Preduo + Octopart ✓ |
| `SDIN8DE4` | eMMC 5.0 | — | Preduo (pure eMMC, zero RAM) |
| `SDINADF4` | eMMC 5.1 | — | catálogos WD |

> **SDIN é o fallback genérico (priority=80).** O prefixo mais longo `SDINB` (UFS, priority=40)
> bate primeiro quando o PN começa com `SDINB`. Correto — SDINB tem maior prioridade.

### 3.4 Família SDINB — UFS iNAND OEM

Sub-família SanDisk com interface UFS. Prefixo mais longo (5 chars vs 4 do SDIN) garante
precedência via priority=40.

```
S  D  I  N  B  [variante_code]  -  [cap_suffix]
0  1  2  3  4      5+              variável
```

- `SDINBDG4` — UFS 2.1 (ex.: `SDINBDG4-128G` = 128GB)
- `SDINBEG4` — UFS 2.1 variante
- `SDINBEG5` — UFS 3.0 variante

Capacidade no sufixo: `-64G`=64GB · `-128G`=128GB · `-256G`=256GB

### 3.5 Família SDAD — eMCP SanDisk (confirmado)

eMCP SanDisk com RAM LPDDR3 (221-ball). É a família eMCP mais documentada desta marca.

```
S  D  A  D  [sub]  [die_variant]  -  [nand_cap]
0  1  2  3    4         5+           variável
```

Sub-séries identificadas:
- `SDADB` — 221-ball, LPDDR3 (confirmado por Preduo + B2B ✓)
  - Ex.: `SDADB48K-16G` = 16GB eMMC + 2GB LPDDR3 (221-ball)
- `SDADF` — variante (ex.: `SDADF4AP-16G` = mesma capacidade, PN irmão)

**Regra crítica:** capacidade no sufixo (`-16G`) refere-se ao **NAND**. A RAM é determinada
pelo ball count (221-ball = LPDDR3) e pela sub-série, não por posição no PN.

**Convenção de mercado (reciclagem):**
- Preduo "16+16" = 16GB NAND + 16Gb LPDDR3 = 16GB NAND + 2GB RAM
- Mercado de reciclagem BR/PY usa "16+2" (ambos em GB)
- `emcp_nand="16GB"` · `emcp_ram="LPDDR3 2GB"`

### 3.6 Família SDEM — eMCP SanDisk (genérico, pendente)

eMCP SanDisk genérico — citado em catálogos WD. Sem PN físico confirmado na esteira
até 2026-06. Família registrada para reconhecimento de marca.

### 3.7 Família SDMAG — eMMC iNAND variante MAG

Variante iNAND com prefixo SDMAG. Citada em documentação WD como família eMMC 5.1.
Sem PN físico confirmado na esteira até 2026-06.

### 3.8 Família SDHQB — UFS Standalone

UFS standalone SanDisk com prefixo SDHQB. Citado em catálogos WD.
Sem PN físico confirmado na esteira até 2026-06.

---

## 4. DecodeMaps — Inventário

**SanDisk não possui DecodeMaps no WTC.**

Diferente de Samsung, SK Hynix e Micron — que usam posição fixa no PN para codificar
capacidade — a SanDisk usa sufixo declarativo de comprimento variável. O decode posicional
não é aplicável (ver §3.1).

**Consequência operacional:** todo chip SanDisk que aparecer na esteira sem KnownPart
no banco retornará `profitable="INDETERMINADO"` — o engine classifica a família
(tipo e interface) mas não tem como extrair a capacidade pela gramática.

**Solução:** criar entradas em `fix_known_parts.py` (`create=True`) para cada PN físico
confirmado na esteira. Não existe outra forma de popular a capacidade automaticamente.

> **Proposta futura (não implementar sem fonte Tier 1):** seria possível criar um decode
> via `suffix_rules` no ChipFamily se os sufixos forem uniformes. Porém, como o die code
> intermediário varia de comprimento, o mapeamento seria por sufixo literal, não por posição.
> Não há suporte nativo para isso no engine atual — manter via fix_known_parts.

---

## 5. Famílias — Inventário Completo

### 5.1 eMMC Standalone

| Prefixo | `chip_type` | `subtype` (canônico) | Interface | Prioridade | Status |
|---------|-------------|----------------------|-----------|------------|--------|
| SD7DP | `"eMMC"` | `""` | `"eMMC 5.1"` | 50 | ⚠️ Roteamento OK; cap via fix_known_parts |
| SDIN | `"eMMC"` | `""` | `"eMMC 4.5 / 5.0 / 5.1"` | 80 | ⚠️ Fallback genérico; cap via fix_known_parts |
| SDMAG | `"eMMC"` | `""` | `"eMMC 5.1"` | 50 | ❌ Sem PN físico — pendente |

> **`subtype` canônico acima difere do `ChipFamily.subtype` atual no `populate_sandisk.py`.**
> O populate atual usa strings verbose (ver §8.1). A tabela acima reflete o que DEVERIA ser.
> Os valores canônicos devem ser usados nos KnownParts em `fix_known_parts.py`.

> **Prioridade numérica SanDisk:** número menor = prioridade maior (testado primeiro).
> SDINB (priority=40) bate antes do SDIN (priority=80) para PNs que começam com "SDINB".

### 5.2 UFS Standalone

| Prefixo | `chip_type` | `subtype` (canônico) | Interface | Prioridade | Status |
|---------|-------------|----------------------|-----------|------------|--------|
| SDINB | `"UFS"` | `""` | `"UFS 2.1 / 3.0"` | 40 | ⚠️ Roteamento OK; cap via fix_known_parts |
| SDHQB | `"UFS"` | `""` | `"UFS 2.1 / 3.1"` | 50 | ❌ Sem PN físico — pendente |

> ⚠️ **RISCO OPERACIONAL:** UFS e eMMC podem compartilhar encapsulamento BGA 153-ball
> visualmente idêntico. São eletricamente incompatíveis. Triagem obrigatória pelo prefixo
> do PN antes de qualquer contato físico com o socket.

### 5.3 eMCP (eMMC + LPDDR)

| Prefixo | `chip_type` | `subtype` (canônico) | Interface | Ball count | RAM | Status |
|---------|-------------|----------------------|-----------|------------|-----|--------|
| SDAD | `"eMCP"` | `"LPDDR3"` | `""` | 221-ball | LPDDR3 | ⚠️ 1 PN confirmado (SDADB48K-16G) |
| SDEM | `"eMCP"` | `"LPDDR3"` ou `"LPDDR4"` | `""` | — | LPDDR3/4 | ❌ Sem PN físico — pendente |

> **SDAD 221-ball = LPDDR3 (confirmado):** no catálogo Preduo, a categoria 221-ball
> é exclusivamente eMMC + LPDDR3. A categoria 254-ball corresponde a LPDDR4.
> Para qualquer PN SDAD 221-ball, `emcp_ram` = `"LPDDR3 ..."` (não LPDDR4).

> **SDEM — ambiguidade de geração RAM:** o catálogo WD indica LPDDR3 ou LPDDR4.
> Sem PN físico confirmado, não é possível determinar a geração por família.
> Usar `subtype="LPDDR3"` como padrão conservador; corrigir quando PN físico confirmar.

### 5.4 Destinos comerciais por categoria

| Categoria | Capacidade | Destino comercial | Rentabilidade |
|-----------|-----------|-------------------|---------------|
| eMMC 5.1 | 64GB+ | Bancada eMMC — alta demanda | RENTÁVEL |
| eMMC 5.0 / 5.1 | 32GB | Bancada eMMC | RENTÁVEL |
| eMMC 5.0 / 5.1 | 16GB | Bancada eMMC | RENTÁVEL (checar demanda) |
| eMMC 4.41 / 4.5 | 8GB+ | Bancada eMMC | INDETERMINADO sem capacidade no banco |
| eMMC < 8GB | qualquer | Resíduo provável | Checar demanda B2B |
| eMCP ≥ 16GB+2GB | 221-ball | Bancada eMCP (Smart POS, mid-range) | RENTÁVEL |
| UFS qualquer | 64GB+ | Bancada UFS — preço premium | RENTÁVEL |

> Limiares precisos dependem do `ProfitabilityConfig` no admin. Ver `assess_profitability`
> em `chips/engine.py` e `RENTABILIDADE.md` para a bíblia completa.

---

## 6. fix_known_parts — Template e Regras

### 6.1 Template correto — eMMC standalone

```python
# eMMC SanDisk — SDIN9DW4-16G (eMMC 5.0, 16GB)
# PN normalizado (engine strip o traço): SDIN9DW4-16G → SDIN9DW416G
{
    "pn": "SDIN9DW416G",           # PN NORMALIZADO — sem traço, maiúsculo
    "create": True,
    "create_defaults": {
        "brand_name": "SanDisk",
        "chip_type":  "eMMC",
        "subtype":    "",           # VAZIO para eMMC standalone — sempre
        # confidence DEVE estar aqui — NUNCA status (campo removido jun/2026)
        "confidence": "distributor",
    },
    "fields": {
        "capacity":   "16GB",       # sufixo -16G = 16GB
        "interface":  "eMMC 5.0",   # versão confirmada
    },
    "reason": (
        "Preduo: SDIN9DW4-16G → categoria eMMC 5.0, 16GB, BGA, SanDisk ✓. "
        "Octopart: 7 distribuidores ativos. Família SDIN9DW4 todas sem RAM. "
        "WD oficial não consultado diretamente → confidence=distributor."
    ),
},
```

### 6.2 Template correto — eMCP

```python
# eMCP SanDisk — SDADB48K-16G (16GB eMMC + LPDDR3 2GB, 221-ball)
# PN normalizado: SDADB48K-16G → SDADB48K16G
{
    "pn": "SDADB48K16G",
    "create": True,
    "create_defaults": {
        "brand_name": "SanDisk",
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",     # geração da RAM — somente "LPDDR3", sem qualificadores
        "confidence": "distributor",
    },
    "fields": {
        "emcp_nand": "16GB",            # NAND em GB — só o número + GB, sem tipo
        "emcp_ram":  "LPDDR3 2GB",      # tipo VEM ANTES da capacidade
    },
    "reason": (
        "B2B wholesale (chinahao, eBay): SDADB48K-16G = 16+2 EMCP 221ball SanDisk ✓. "
        "Preduo 221-ball = exclusivamente eMMC+LPDDR3 (não LPDDR4). "
        "WD oficial não encontrado → confidence=distributor."
    ),
},
```

### 6.3 Template para chip com `confidence="confirmed"` (fonte Tier 1)

```python
# Use confidence="confirmed" somente quando westerndigital.com ou datasheet oficial
# confirmar diretamente o PN com specs.
{
    "pn": "SD7DP24C4G",            # PN normalizado (SD7DP24C-4G sem traço)
    "create": True,
    "create_defaults": {
        "brand_name": "SanDisk",
        "chip_type":  "eMMC",
        "subtype":    "",
        "confidence": "confirmed",  # só com datasheet WD ou westerndigital.com
    },
    "fields": {
        "capacity":  "4GB",
        "interface": "eMMC 5.1",
    },
    "reason": "Western Digital iNAND 7 Series datasheet (westerndigital.com) ✓.",
},
```

### 6.4 Regra de normalização — PN sem traço

SanDisk usa traço no PN de fábrica (ex.: `SDIN9DW4-16G`). O engine remove
todos os caracteres não-alfanuméricos com `re.sub(r"[^A-Z0-9]", "", pn)`.

**Regra:** sempre salvar o PN **sem traço** em `fix_known_parts.py`.

```
SDIN7DU2-8G   →  SDIN7DU28G    ← forma correta em fix_known_parts
SDIN9DW4-16G  →  SDIN9DW416G
SDIN9DW4-32G  →  SDIN9DW432G
SDADB48K-16G  →  SDADB48K16G
SD7DP24C-4G   →  SD7DP24C4G
```

### 6.5 Regras de `capacity` e campos de tamanho

- **eMMC/UFS:** `capacity` = GB total do pacote. Ex.: `"16GB"`, `"128GB"`.
  **Nunca** usar Gbit no campo `capacity` (ex.: `"128Gbit"` → errado).
- **eMCP:** NÃO preencher `capacity`. Usar `emcp_nand` (GB) e `emcp_ram` (tipo + GB).
- **Sufixo SanDisk → GB:** `-8G`=8GB · `-16G`=16GB · `-32G`=32GB · `-64G`=64GB · `-128G`=128GB.
  O "G" no sufixo é Gigabyte (declaração de fábrica), não Gigabit.

### 6.6 confidence — localização correta

O `confidence` **deve obrigatoriamente aparecer em `create_defaults`**.
Colocado apenas em `fields`, não tem efeito no momento da criação — e o engine só
trata um registro como autoritativo (banco vence a gramática) quando
`confidence` ∈ (`confirmed`, `manual`). Com `distributor`/`estimated`, o registro
cai no decode posicional. *(Não há mais campo `status`; ele foi removido em jun/2026.)*

```python
# CORRETO:
"create_defaults": {
    "brand_name": "SanDisk",
    "chip_type": "eMMC",
    "subtype": "",
    "confidence": "confirmed", ← AQUI (create_defaults) — confirmed/manual para vencer a gramática
},

# ERRADO:
"create_defaults": {
    "brand_name": "SanDisk",
    "chip_type": "eMMC",
    "subtype": "",
    # confidence ausente → não autoritativo → engine usa a gramática
},
```

---

## 7. assess_profitability — Limiares SanDisk

A rentabilidade SanDisk é avaliada pelas mesmas regras do `ProfitabilityConfig` que
se aplicam a eMMC, eMCP e UFS de outras marcas. Não há parâmetros SanDisk-específicos.

| Parâmetro ProfitabilityConfig | Relevância para SanDisk |
|-------------------------------|------------------------|
| `emmc_min_gb` | eMMC < limiar → NÃO RENTÁVEL (default: verificar no admin) |
| `emcp_min_nand_gb` | eMCP NAND < limiar → NÃO RENTÁVEL |
| `emcp_min_ram_gb` | eMCP RAM < limiar → NÃO RENTÁVEL |

**Comportamento crítico sem capacidade:**
> Chips SanDisk sem KnownPart no banco retornam `profitable="INDETERMINADO"` porque
> o engine não consegue extrair a capacidade da gramática. O operador fica sem triagem
> automática. Solução: confirmar o PN em `fix_known_parts.py`.

### Mapeamento eMMC → rentabilidade (orientativo)

| eMMC versão | Capacidade | Expectativa |
|-------------|-----------|-------------|
| eMMC 5.1 | ≥ 32GB | RENTÁVEL (alta demanda B2B) |
| eMMC 5.0 | 16GB–32GB | RENTÁVEL (checar demanda) |
| eMMC 4.41 / 4.5 | ≥ 8GB | Depende do `emmc_min_gb` — verificar |
| eMMC 4.41 | ≤ 4GB | Provavelmente NÃO RENTÁVEL |

### Mapeamento eMCP → rentabilidade (orientativo)

| eMCP | Capacidade | Expectativa |
|------|-----------|-------------|
| 221-ball LPDDR3 | 16GB + 2GB | RENTÁVEL (Smart POS, mid-range) |
| 221-ball LPDDR3 | 8GB + 1GB | Depende do limiar — verificar |

---

## 8. Armadilhas e Decisões Arquiteturais

### 8.1 Bugs conhecidos em `populate_sandisk.py` — subtypes e interface verbosos

**Status:** bugs documentados, a corrigir no próximo `populate_sandisk --overwrite`.

| Família | Campo bugado | Valor atual (errado) | Valor correto |
|---------|-------------|----------------------|---------------|
| SD7DP | `subtype` | `"eMMC standalone (iNAND 7 Series)"` | `""` (vazio) |
| SDIN | `subtype` | `"eMMC iNAND (legado)"` | `""` (vazio) |
| SDINB | `subtype` | `"UFS standalone (iNAND OEM)"` | `""` (vazio) |
| SDMAG | `subtype` | `"eMMC iNAND (variante MAG)"` | `""` (vazio) |
| SDEM | `subtype` | `"eMCP (eMMC + LPDDR3/LPDDR4)"` | `"LPDDR3"` (conservador) |
| SDAD | `subtype` | `"eMCP (eMMC + LPDDR)"` | `"LPDDR3"` (confirmado: 221-ball) |
| SDHQB | `subtype` | `"UFS standalone"` | `""` (vazio) |
| SDEM | `interface` | `"eMMC + LPDDR3/LPDDR4"` | `""` (vazio — eMCP sempre vazio) |
| SDAD | `interface` | `"eMMC + LPDDR"` | `""` (vazio — eMCP sempre vazio) |

**Impacto atual:** o label da caixa não quebra (mitigado por `canonical_gen`), mas o card
de busca mostra os subtypes verbosos. Chips eMCP com interface="eMMC + LPDDR" podem gerar
comportamento inesperado no engine — corrigir é prioritário.

**Fix:** editar `populate_sandisk.py` com os valores corretos e rodar `populate_sandisk --overwrite`.
Reiniciar o servidor após o comando.

### 8.2 Normalização do PN — traço removido pelo engine

O engine normaliza qualquer PN com `re.sub(r"[^A-Z0-9]", "", pn)`. Isso significa:
- `SDIN9DW4-16G` → `SDIN9DW416G` (traço removido)
- `SD7DP24C-4G` → `SD7DP24C4G`

**Consequência:** se um KnownPart for salvo com traço (`SDIN9DW4-16G`), ele jamais será
encontrado pelo engine (que busca pela versão normalizada). Sempre usar o PN sem traço.

### 8.3 Decode posicional impossível — sufixo de comprimento variável

A tentativa de criar `decode_cap_pos` para capacidade SanDisk sempre falha porque:
1. O die code intermediário tem comprimento variável (2–4 chars)
2. O sufixo de capacidade tem comprimento variável: `4G`=2 chars, `16G`=3 chars, `128G`=4 chars
3. Não há posição fixa para o início da capacidade

**Decisão de design (imutável):** `decode_cap_pos=None` em todas as famílias SanDisk.
A capacidade só chega ao banco via `fix_known_parts.py` (create=True).

### 8.4 WD x SanDisk — nomenclatura dual

SanDisk foi adquirida pela Western Digital em 2016. Depois da aquisição:
- O **PN físico gravado no chip** permanece com prefixo `SD` (SanDisk)
- A **documentação técnica** migrou para westerndigital.com / wdc.com
- O chip pode ter logo "WD" impresso mas o PN começa com "SD" — é o mesmo chip

**Consequência:** ao pesquisar documentação, buscar em westerndigital.com (fonte atual)
e nas referências antigas SanDisk (para famílias legadas como iNAND Ultra eMMC 4.41).
O campo `brand_name` no banco é `"SanDisk"` para todos esses chips.

### 8.5 "16+2" vs "16+16" — convenção de mercado de reciclagem

O mercado de reciclagem BR/PY usa notação mista:
- Preduo: `"16+16"` = 16GB NAND + 16Gbit LPDDR3 (**atenção: o segundo número é em Gbit**)
- Mercado BR/PY: `"16+2"` = 16GB NAND + 2GB LPDDR3 (ambos em GB)

Conversão: 16Gbit LPDDR3 ÷ 8 = 2GB. Portanto `"16+16"` (Preduo) = `"16+2"` (mercado BR/PY).
No banco WTC, sempre salvar em GB: `emcp_nand="16GB"`, `emcp_ram="LPDDR3 2GB"`.

### 8.6 221-ball vs 254-ball — regra de ouro para tipo de RAM em eMCP SanDisk

| Ball count | Tipo de RAM | Fonte |
|------------|-------------|-------|
| 221-ball | LPDDR3 (sempre) | Preduo categoria exclusiva ✓ |
| 254-ball | LPDDR4 | Preduo categoria exclusiva ✓ |

Esta regra elimina a ambiguidade para todos os eMCP SanDisk 221-ball — a RAM é LPDDR3,
não LPDDR4. Para PNs de ball count desconhecido, não assuma a geração RAM sem fonte Tier 1.

### 8.7 `SDINB` não é sub-família de eMMC — é UFS

O prefixo `SDINB` começa com `SDIN` mas é **UFS** (não eMMC). Motivo: o engine testa
prefixos mais longos primeiro, e `SDINB` (priority=40) vence sobre `SDIN` (priority=80).
Correto — todo PN `SDINB...` é roteado para UFS antes de cair no fallback eMMC.

**Perigo:** sem olhar o prefixo cuidadosamente, o operador pode confundir `SDINBDG4-128G`
(UFS) com um eMMC SDIN — são eletricamente incompatíveis no socket.

### 8.8 Chip `SDAD` — geração da RAM não está no PN

Ao contrário de Samsung (KMQ, KMR etc. onde `pn[2]` = geração RAM), o prefixo SDAD
não encoda a geração da RAM no PN. A geração é determinada pelo ball count físico:
- SDADB... 221-ball → LPDDR3
- SDADF... (possível 254-ball) → investigar quando PN físico confirmar

**Não assuma** que sub-séries diferentes de SDAD têm a mesma geração de RAM sem evidência.

---

## 9. Gaps e Roadmap

### Sprint A — Impacto imediato (adicionar PNs físicos confirmados)

**✅ SD7DP — CONCLUÍDO (2026-06-26):**
4 PNs da família SD7DP adicionados ao `fix_known_parts.py` com
`confidence=distributor`. Cobertos: SD7DP28C-4G (Octopart Tier 2), SD7DP28C-8G (Tier 3 múlt.),
SD7DP24C-4G e SD7DP24F-4G (Tier 3 múlt.). Aguardando confirmação independente:
`SD7DP26A-4G` e `SD7DP41E-16G` (apenas 1 fonte Grandado — insuficiente).

**✅ SDINADF4 (iNAND 7232) — CONCLUÍDO (2026-06-26):**
8 PNs da família iNAND 7232 adicionados ao `fix_known_parts.py`. Tier 1 confirmado no Mouser
e Avnet/Octopart. Datasheet oficial WD DOC-06397 Rev 1.13. Cobertos: 16G/32G/64G/128G e
variantes -H. Interface: eMMC 5.1 HS400. NAND: TLC. Temp: -25°C a 85°C.
Confidence=`confirmed` para 16G, 64G, 16GH, 64GH (Mouser Tier 1); `distributor` para 32G, 128G e H.

**✅ SD5DH — CONCLUÍDO e FECHADO (2026-06-26):**
Nova ChipFamily `SD5DH` adicionada ao `populate_sandisk.py`. 2 PNs em
`fix_known_parts.py` (SD5DH24C4G e SD5DH24A4G). Era 2012-2013, eMMC 4.3/4.4 (estimada).
Dispositivos: Samsung GT-S5301 (Galaxy Pocket Plus), S6810 (Galaxy Fame), S6802 (Galaxy S Advance).
Interface sem Tier 1 — não adicionar campo `interface` sem datasheet oficial.
**Pesquisa exaustiva (2026-06-26) confirmou:** apenas 2 variantes existem (24C-4G e 24A-4G),
ambas 4GB. Sem variantes 8GB em nenhuma fonte (Mouser/DigiKey/Octopart/Tier 3/CH). Família mapeada.
Contexto: SDIN5D1 (SanDisk iNAND, datasheet Dec 2011) usa eMMC 4.41 — era coincide com SD5DH.

**✅ SDIN8DE2 — CONCLUÍDO (2026-06-26):**
5 PNs adicionados ao `fix_known_parts.py` (4G, 4G-I, 8G, 8G-A, 16G).
Interface **eMMC 4.51 HS200** — confirmado Mouser Tier 1 (SDIN8DE2-8G-A e SDIN8DE2-4G-I).
Datasheet WD/SanDisk: "SanDisk Commercial Embedded Storage Solutions" (alldatasheet.com).
Package: TFBGA-153, 11.5×13mm. NRND — legacy presente na esteira.
Confidence: `confirmed` para -8G-A e -4G-I (Mouser direto); `distributor` para -8G, -4G, -16G.

**✅ SDIN5C2 — CONCLUÍDO (2026-06-26):**
5 PNs adicionados ao `fix_known_parts.py` (8G, 8G-L, 16G-L, 32G-L, 64G-L).
Interface **eMMC 4.41** — confirmado pelo datasheet oficial SanDisk doc# 80-36-03462
(v1.4, Dec 2011, "SanDisk iNAND e.MMC 4.41 I/F — Released Data Sheet").
Todos os SKUs explícitos na tabela de ordering. Package: TFBGA-169, 12×16mm, X2 MLC NAND.
Confidence: `confirmed` para todos (datasheet Tier 1).

**eMMC SDIN — cobertura ampliada:**
Sub-séries ainda não mapeadas: `SDIN5D*` (eMMC 4.41, 11.5×13mm), `SDIN7*` (eMMC 4.41/4.5).
Quando aparecerem na esteira, adicionar via `fix_known_parts.py` com capacity + interface.

**eMCP SDAD — ampliar cobertura:**
`SDADF4AP-16G` (PN irmão de SDADB48K-16G, mesmo 16+2) é candidato próximo a confirmar.
Outros SDAD 221-ball que aparecerem na esteira: confirmar ball count antes de assumir LPDDR3.

### Sprint B — Correção de bugs (alta prioridade)

**Corrigir `populate_sandisk.py` — subtypes e interface verbosos:**
Ver tabela em §8.1. Fazer as correções e rodar `populate_sandisk --overwrite`.
Reiniciar o servidor. Verificar que cards de busca mostram subtype limpo.

**Confirmar `SDINB` (UFS) com PN físico:**
`SDINBDG4-128G` tem boas chances de aparecer na esteira — confirmar por Octopart.

### Sprint C — Expansão de cobertura

**`SDEM` e `SDHQB`:** confirmar PNs físicos quando aparecerem na esteira.
Não mapear capacidade sem evidência.

**`SDMAG`:** confirmar com PN físico. Até lá, só roteamento de marca.

**Outros prefixos possíveis (não mapeados):**
Chips SanDisk podem ter outros prefixos não documentados (ex.: `SDQ`, `SDCIT` para
cartões SD reimplantados — não confundir com chips embarcados).

### O que NÃO adicionar sem evidência Tier 1

- Capacidades "estimadas" para sub-séries SDIN não confirmadas
- Geração RAM para famílias SDEM/SDAD sem ball count ou fonte B2B rastreável
- Versão de interface UFS para SDINB além do confirmado (2.1/3.0)
- Qualquer chave de decode posicional (não existe conceito válido para SanDisk)

---

## 10. Histórico de Correções

| Data | PN / Família | Ação | Fonte | Motivo |
|------|-------------|------|-------|--------|
| 2026-06 (sessão anterior) | SD7DP | Criada em `add_chip_families.py` (provisório) | WD datasheet | Primeira família SanDisk no sistema |
| 2026-06 (sessão anterior) | SD7DP | Migrado para `populate_sandisk.py` (definitivo) | — | `populate_sandisk.py` é o gabarito canônico |
| 2026-06 (sessão anterior) | SDIN, SDINB, SDMAG, SDEM, SDAD, SDHQB | Criadas em `populate_sandisk.py` | fab-sandisk.html + catálogos WD | Base de famílias SanDisk |
| 2026-06-26 | SDIN7DU28G | fix_known_parts: eMMC 4.41, 8GB, confidence=distributor | Datasheet SanDisk doc# 80-36-03666 ✓ | Primeiro eMMC 4.41 confirmado |
| 2026-06-26 | SDIN9DW416G | fix_known_parts: eMMC 5.0, 16GB, confidence=distributor | Preduo + Octopart (7 distribuidores) ✓ | eMMC 5.0 iNAND 7 Series |
| 2026-06-26 | SDIN9DW432G | fix_known_parts: eMMC 5.0, 32GB, confidence=distributor | Octopart link direto + Preduo ✓ | eMMC 5.0 iNAND 7 Series |
| 2026-06-26 | SDADB48K16G | fix_known_parts: eMCP 16GB+LPDDR3 2GB, confidence=distributor | B2B wholesale (chinahao/eBay) + Preduo 221-ball ✓ | Primeiro eMCP SanDisk confirmado |
| 2026-06-26 | SD7DP28C4G | fix_known_parts: eMMC 5.1, 4GB, confidence=distributor | Octopart Tier 2 (5 distrib.) + Martview (Huawei Y625/G730) | Família SD7DP confirmada no banco |
| 2026-06-26 | SD7DP28C8G | fix_known_parts: eMMC 5.1, 8GB, confidence=distributor | Jotrin + Censtry (Tier 3, múltiplas fontes) | Variante 8GB — não está no Octopart |
| 2026-06-26 | SD7DP24C4G | fix_known_parts: eMMC 5.1, 4GB, confidence=distributor | Win Source + Veswin + Huawei Y330-U01 | Die code 24C confirmado |
| 2026-06-26 | SD7DP24F4G | fix_known_parts: eMMC 5.1, 4GB, confidence=distributor | IC-Components + Jotrin + OMO + Grandado (4 fontes Tier 3) | Die code 24F confirmado |
| 2026-06-26 | SD5DH | Nova ChipFamily em populate_sandisk.py (prefixo SD5DH, eMMC 4.3/4.4 est.) | serviceemmc.com + Jotrin (Tier 3) | Família completa: só 2 variantes 4GB existem |
| 2026-06-26 | SD5DH24C4G | fix_known_parts: eMMC, 4GB, confidence=distributor | serviceemmc.com: Samsung GT-S5301 (Galaxy Pocket Plus) / S6810 (Galaxy Fame) | Die code 24C, 24nm |
| 2026-06-26 | SD5DH24A4G | fix_known_parts: eMMC, 4GB, confidence=distributor | serviceemmc.com: Samsung S6802 (Galaxy S Advance) | Die code 24A, revisão do mesmo die 24nm |
| 2026-06-26 | SDINADF416G | fix_known_parts: eMMC 5.1, 16GB, confidence=**confirmed** | Mouser Tier 1 + DOC-06397 (WD/SanDisk) | iNAND 7232 — primeiro confirmed da série |
| 2026-06-26 | SDINADF432G | fix_known_parts: eMMC 5.1, 32GB, confidence=distributor | Octopart Tier 2 + serviceemmc.com (Honor V9) | PN do operador que mostrou INDETERMINADO |
| 2026-06-26 | SDINADF464G | fix_known_parts: eMMC 5.1, 64GB, confidence=**confirmed** | Mouser + Avnet/Octopart Tier 1 (LG H961N/H960) | Maior disponibilidade de estoque |
| 2026-06-26 | SDINADF4128G | fix_known_parts: eMMC 5.1, 128GB, confidence=distributor | Octopart Tier 2 + DOC-06397 range | Máxima capacidade da família |
| 2026-06-26 | SDINADF416GH | fix_known_parts: eMMC 5.1, 16GB, confidence=**confirmed** | Mouser Tier 1 | Variante -H (temperatura estendida) |
| 2026-06-26 | SDINADF432GH | fix_known_parts: eMMC 5.1, 32GB, confidence=distributor | Octopart Tier 2 | Variante -H do 32G |
| 2026-06-26 | SDINADF464GH | fix_known_parts: eMMC 5.1, 64GB, confidence=**confirmed** | Mouser Tier 1 + datasheet PDF | Variante -H do 64G — mais documentado |
| 2026-06-26 | SDINADF4128GH | fix_known_parts: eMMC 5.1, 128GB, confidence=distributor | Octopart Tier 2 | Variante -H do 128G |
| 2026-06-26 | SDIN8DE28G | fix_known_parts: eMMC 4.51, 8GB, confidence=distributor | Mouser India + Avaq (PN base); Mouser confirma -8G-A | PN da esteira eMiner |
| 2026-06-26 | **SDIN8DE28GA** | fix_known_parts: eMMC 4.51, 8GB, confidence=**confirmed** | **Mouser Tier 1** (#467-SDIN8DE2-8G-A) | Automotive variant — Tier 1 direto |
| 2026-06-26 | **SDIN8DE24GI** | fix_known_parts: eMMC 4.51, 4GB, confidence=**confirmed** | **Mouser Tier 1** (#467-SDIN8DE2-4G-I) | Industrial variant — Tier 1 direto |
| 2026-06-26 | SDIN8DE24G | fix_known_parts: eMMC 4.51, 4GB, confidence=distributor | FindChips + Veswin (Tier 3) | Variante consumer 4GB |
| 2026-06-26 | SDIN8DE216G | fix_known_parts: eMMC 4.51, 16GB, confidence=distributor | Mouser (NRND/obsoleto) + FindChips | Máxima capacidade da família |
| 2026-06-26 | **SDIN5C28G** | fix_known_parts: eMMC 4.41, 8GB, confidence=**confirmed** | **Datasheet SanDisk doc# 80-36-03462** (v1.4, Dec 2011) | PN da esteira eMiner — Tier 1 |
| 2026-06-26 | **SDIN5C28GL** | fix_known_parts: eMMC 4.41, 8GB, confidence=**confirmed** | **Datasheet SanDisk doc# 80-36-03462** — SKU explícito | Variante -L (tray packaging) |
| 2026-06-26 | **SDIN5C216GL** | fix_known_parts: eMMC 4.41, 16GB, confidence=**confirmed** | **Datasheet SanDisk doc# 80-36-03462** — SKU explícito | 12×16mm, X2 MLC |
| 2026-06-26 | **SDIN5C232GL** | fix_known_parts: eMMC 4.41, 32GB, confidence=**confirmed** | **Datasheet SanDisk doc# 80-36-03462** — SKU explícito | 12×16×1.2mm |
| 2026-06-26 | **SDIN5C264GL** | fix_known_parts: eMMC 4.41, 64GB, confidence=**confirmed** | **Datasheet SanDisk doc# 80-36-03462** — SKU explícito | Maior capacidade SDIN5C2 |

### Chips individuais confirmados (banco)

| PN (normalizado) | Tipo | Capacidade | Fonte | Status |
|------------------|------|-----------|-------|--------|
| SDIN7DU28G | eMMC 4.41 | 8GB | Datasheet doc# 80-36-03666 + Octopart (11 distrib.) | ✅ distributor |
| SDIN9DW416G | eMMC 5.0 | 16GB | Preduo + Octopart (7 distrib.) | ✅ distributor |
| SDIN9DW432G | eMMC 5.0 | 32GB | Octopart + Preduo | ✅ distributor |
| SDADB48K16G | eMCP | 16GB+LPDDR3 2GB | chinahao/eBay B2B + Preduo 221-ball | ✅ distributor |
| SD7DP28C4G | eMMC 5.1* | 4GB | Octopart Tier 2 (5 distrib.) + Martview | ✅ distributor |
| SD7DP28C8G | eMMC 5.1* | 8GB | Jotrin + Censtry + Grandado (Tier 3) | ✅ distributor |
| SD7DP24C4G | eMMC 5.1* | 4GB | Win Source + Veswin + Huawei Y330-U01 | ✅ distributor |
| SD7DP24F4G | eMMC 5.1* | 4GB | IC-Components + Jotrin + OMO + Grandado | ✅ distributor |
| SDIN8DE28G | eMMC 4.51 | 8GB | Mouser India + Avaq (PN base) + Mouser Tier 1 para -A | ✅ distributor |
| **SDIN8DE28GA** | **eMMC 4.51** | **8GB** | **Mouser Tier 1** — "eMMC 8GB 4.51 HS200 Auto" | **✅ confirmed** |
| **SDIN8DE24GI** | **eMMC 4.51** | **4GB** | **Mouser Tier 1** — "eMMC 4GB 4.51 HS200" | **✅ confirmed** |
| SDIN8DE24G | eMMC 4.51 | 4GB | FindChips + Veswin (Tier 3) | ✅ distributor |
| SDIN8DE216G | eMMC 4.51 | 16GB | Mouser (NRND) + FindChips | ✅ distributor |
| **SDIN5C28G** | **eMMC 4.41** | **8GB** | **Datasheet SanDisk doc# 80-36-03462** (Tier 1) | **✅ confirmed** |
| **SDIN5C28GL** | **eMMC 4.41** | **8GB** | **Datasheet SanDisk doc# 80-36-03462** (SKU explícito) | **✅ confirmed** |
| **SDIN5C216GL** | **eMMC 4.41** | **16GB** | **Datasheet SanDisk doc# 80-36-03462** (SKU explícito) | **✅ confirmed** |
| **SDIN5C232GL** | **eMMC 4.41** | **32GB** | **Datasheet SanDisk doc# 80-36-03462** (SKU explícito) | **✅ confirmed** |
| **SDIN5C264GL** | **eMMC 4.41** | **64GB** | **Datasheet SanDisk doc# 80-36-03462** (SKU explícito) | **✅ confirmed** |
| **SDINADF416G** | **eMMC 5.1** | **16GB** | **Mouser Tier 1 + DOC-06397** | **✅ confirmed** |
| SDINADF432G | eMMC 5.1 | 32GB | Octopart Tier 2 + Honor V9 | ✅ distributor |
| **SDINADF464G** | **eMMC 5.1** | **64GB** | **Mouser + Avnet/Octopart Tier 1** | **✅ confirmed** |
| SDINADF4128G | eMMC 5.1 | 128GB | Octopart Tier 2 | ✅ distributor |
| **SDINADF416GH** | **eMMC 5.1** | **16GB** | **Mouser Tier 1** | **✅ confirmed** |
| SDINADF432GH | eMMC 5.1 | 32GB | Octopart Tier 2 | ✅ distributor |
| **SDINADF464GH** | **eMMC 5.1** | **64GB** | **Mouser Tier 1 (datasheet PDF)** | **✅ confirmed** |
| SDINADF4128GH | eMMC 5.1 | 128GB | Octopart Tier 2 | ✅ distributor |
| SD5DH24C4G | eMMC 4.3/4.4† | 4GB | serviceemmc.com (GT-S5301 Galaxy Pocket Plus / S6810 Galaxy Fame) | ✅ distributor |
| SD5DH24A4G | eMMC 4.3/4.4† | 4GB | serviceemmc.com (S6802 Galaxy S Advance) | ✅ distributor |

> \* Interface "eMMC 5.1" herdada de `populate_sandisk.py`. Incerteza: a contraparte OEM SDIN7DP2
> (Mouser Product Brief oficial, dez/2015) é eMMC **4.51**. Se fonte Tier 1 confirmar 4.51,
> corrigir `populate_sandisk.py` e os registros acima.
>
> † Interface SD5DH estimada pela era (2012-2013). Sem datasheet Tier 1 confirmado para SD5DH.
> Contexto: SDIN5D1 (SanDisk iNAND standard, datasheet Dec 2011) usa eMMC 4.41 — era coincide.
> Não adicionar campo `interface` no banco até confirmar com datasheet oficial específico do SD5DH.

### Aguardando confirmação — NÃO adicionar sem fonte Tier 2+ independente

| PN | Motivo de espera | Próxima ação |
|----|-----------------|--------------|
| SD7DP26A-4G | Única menção: bundle Grandado NZ | Buscar no Octopart / Win Source |
| SD7DP41E-16G | Única menção: bundle Grandado NZ | Buscar no Octopart / Win Source |

---

## 11. Pipeline de trabalho

### Para atualizar gramática (famílias)

```bash
# 1. Editar populate_sandisk.py (ChipFamily — sem DecodeMaps)
# 2. Propor ao usuário — que roda:
python manage.py populate_sandisk --dry-run      # revisar antes
python manage.py populate_sandisk --overwrite    # usuário executa

# 3. REINICIAR O SERVIDOR — obrigatório; lru_cache não invalida automaticamente

# 4. Verificar resultado:
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('SDIN9DW416G'), indent=2, ensure_ascii=False))
"
```

### Para adicionar PNs confirmados (fix_known_parts)

```bash
# 1. Editar fix_known_parts.py (somente seção SanDisk)
# 2. Propor ao usuário — que roda:
python manage.py fix_known_parts    # usuário executa
# NÃO requer reinício do servidor (não altera gramática/lru_cache)
```

### Ordem típica de sessão de atualização SanDisk

```bash
# Se editou populate_sandisk.py:
python manage.py populate_sandisk --overwrite   # usuário
# → REINICIAR SERVIDOR ←

# Se editou só fix_known_parts.py:
python manage.py fix_known_parts                # usuário
# → sem restart necessário ←

# Verificar chips representativos via shell ou /chips/decode/?pn=<PN>
# git add + git commit
```

---

## 12. Como verificar se um chip SanDisk está correto

### Verificação via shell

```bash
# eMMC — esperado: chip_type='eMMC', capacity='16GB', interface='eMMC 5.0'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('SDIN9DW416G'), indent=2, ensure_ascii=False))
"

# eMCP — esperado: chip_type='eMCP', emcp_nand='16GB', emcp_ram='LPDDR3 2GB'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('SDADB48K16G'), indent=2, ensure_ascii=False))
"

# Chip não confirmado — esperado: chip_type='eMMC', known=false, profitable='INDETERMINADO'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('SDINBDG4128G'), indent=2, ensure_ascii=False))
"
```

### Checklist de chip correto

- [ ] `known=true` (ou `known_exact=true`) para chips em fix_known_parts
- [ ] `confidence="enriched"` ou `"confirmed"` — `"raw"` = invisível para o engine
- [ ] `chip_type` correto: `"eMMC"`, `"UFS"`, `"eMCP"` (nunca "iNAND", "NAND", "Flash")
- [ ] `subtype=""` para eMMC/UFS · `subtype="LPDDR3"` (ou geração) para eMCP
- [ ] `interface` correta: versão protocolo para eMMC/UFS · `""` para eMCP
- [ ] Campo de capacidade preenchido: `capacity` para eMMC/UFS · `emcp_nand`+`emcp_ram` para eMCP
- [ ] `profitable != "INDETERMINADO"` — INDETERMINADO = campo capacidade ausente → bloqueador de produção
- [ ] Label do estoque correto: `EMMC16GB`, `UFS128GB`, `EMCP16+2`
- [ ] PN normalizado (sem traço): `SDIN9DW416G` ✓ · `SDIN9DW4-16G` ✗

---

## 13. Arquivos-chave SanDisk

```
chips/management/commands/
  populate_sandisk.py         ← GRAMÁTICA: 7 famílias SanDisk (sem DecodeMaps).
                                 Editar para corrigir subtypes/interface verbosos (§8.1)
                                 ou adicionar novas famílias.
  fix_known_parts.py          ← KnownParts individuais SanDisk.
                                 ÚNICA forma de popular capacidade nos chips SanDisk.
                                 PNs devem estar normalizados (sem traço).

docs/
  PROMPT_NOVO_MD_MARCA.md     ← template de prompt para criar novos .md de marca
  CONTRATO_RENTABILIDADE_GATEWAY.md ← regras de rentabilidade (afeta todas as marcas)
  CONVENCAO_MICRON_ESTOQUE.md ← convenção canônica cross-marca (referência)

Referências cruzadas:
  CLAUDE.md §2                ← regras de ouro do projeto inteiro (não violar)
  CLAUDE.md §4                ← arquitetura do engine (classify, lru_cache, precedência)
  CLAUDE.md §5                ← pipeline de comandos completo do projeto
  CLAUDE.md §6                ← convenção canônica de campos por tipo de chip
  RENTABILIDADE.md            ← bíblia completa de assess_profitability
  HANDOFF.md                  ← histórico de decisões arquiteturais
```

---

> **Regra de trabalho:** Claude edita arquivos. O usuário roda os comandos.
> Nunca execute `populate_*`, `fix_known_parts`, `migrate` sem o usuário confirmar.
> Sempre `--dry-run` antes de qualquer comando que escreve no banco de dados.
>
> **Ponto mais importante desta marca:** SanDisk não tem decode posicional.
> Cada PN físico que aparecer na esteira sem KnownPart no banco retorna INDETERMINADO.
> A missão contínua é confirmar PNs em `fix_known_parts.py` à medida que aparecem.
