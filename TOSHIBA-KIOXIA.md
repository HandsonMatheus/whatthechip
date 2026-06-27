# TOSHIBA-KIOXIA.md — Bíblia Técnica e de Negócio
**WhatTheChip — documento vivo de referência**
Criado: 2026-06-26 | Atualizado: 2026-06-26 (sessão 4 — 39 PNs Kioxia Tier 1; ChipFamilies THGAM/THGJF/THGAF; fix TB engine+estoque)
> Leia antes de tocar em qualquer arquivo relacionado à Toshiba ou Kioxia.
> Em conflito com qualquer outro doc, o **código é a fonte da verdade**
> (`chips/engine.py`, `populate_toshiba.py`).
> Atualize este arquivo quando aprender algo duradouro.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro e limites de escopo

### 0.1 Arquivos que PODE editar (escopo Toshiba / Kioxia)

```
chips/management/commands/populate_toshiba.py   ← gramática mestre: ChipFamilies + DecodeMaps
chips/management/commands/fix_known_parts.py    ← somente entradas brand_name="Toshiba" ou "Kioxia"
```

### 0.2 Arquivos que NÃO PODE tocar sem revisão explícita do usuário

```
chips/engine.py                                    ← motor global — mudança afeta TODAS as marcas
estoque/views.py                                   ← gateway global — mudança afeta TODAS as marcas
chips/management/commands/populate_samsung.py
chips/management/commands/populate_hynix.py
chips/management/commands/populate_micron_mcp.py
chips/management/commands/populate_kingston.py
chips/management/commands/populate_rayson.py
chips/management/commands/add_chip_families.py     ← compartilhado — Toshiba está em OBSOLETE
chips/management/commands/fix_known_parts.py       ← seções de OUTRAS marcas (Samsung, Micron…)
```

> Se precisar de mudança em `engine.py` ou `estoque/views.py`, **proponha ao usuário**
> com justificativa e impacto — nunca edite silenciosamente.

### 0.3 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca execute `populate_*`,
   `fix_known_parts`, `migrate` sem confirmação explícita do usuário.

2. **`--dry-run` antes de qualquer comando que escreve no banco.** Sempre.

3. **Reiniciar o servidor após `populate_toshiba --overwrite`.** O `lru_cache` do engine
   não invalida automaticamente no processo do servidor web.

4. **`chip_type="eMMC"` para THGBM.** Nunca `"Flash"`, `"NAND"` ou `"TLC"` no `chip_type`.
   O gateway de estoque precisa de `chip_type="eMMC"` para montar o label correto.

5. **`subtype` = texto curto de família, sem qualificadores de capacidade ou tensão.**
   `"eMMC Toshiba/Kioxia MLC/TLC"` ✓ para ChipFamily. Para KnownPart em `fix_known_parts`,
   seguir a mesma lógica: sem blocos verbosos extras.

6. **`interface=""` (vazio) para eMCP TYC/TYD.** Para THGBM eMMC standalone, `interface`
   recebe a versão decodificada pelo engine via `decode_gen_map` (ex.: `"eMMC 5.1"`).

7. **`emcp_ram` = tipo ANTES da capacidade.** `"LPDDR2 512MB"` ✓ — nunca `"512MB LPDDR2"`.
   `emcp_nand` = tipo **e** capacidade: `"eMMC 4.5 4GB"`.

8. **`pn_length=15` é exato para THGBM.** Nunca adicionar decode maps para PNs
   com comprimento diferente sem confirmar a estrutura posicional.

9. **Não confie em dado de IA sem verificação.** IAs confundem sufixo de bin (`R`/`L`)
   com código de capacidade, e alucinam a geração eMMC. Sempre cruzar com Octopart
   ou kioxia.com antes de usar qualquer dado.

10. **BLOQUEIO KLUE:** Nunca adicionar família KLUE (UFS Kioxia) sem verificar
    spec em `business.kioxia.com` ou datasheet oficial. Instrução explícita do operador.

11. **Chaves THGBM_CAP novas:** nunca adicionar sem PN âncora + fonte Tier 2+.
    O padrão matemático (densidade×dies) não substitui uma confirmação real — há
    variações de processo e empacotamento que o cálculo não prevê.

### 0.4 Hierarquia de fontes (imutável)

```
1. kioxia.com / toshiba.semicon-storage.com (TIER 1)
   → datasheet oficial, busca por PN, especificações primárias
2. Mouser, DigiKey, TrustedParts/ECIA, Octopart com fonte fabricante (TIER 2)
   → listagem com descrição técnica (Gb, versão eMMC, package)
3. utmel, censtry, neven7.eu, iiic.cc, Puris, AIChipLink (TIER 3)
   → B2B / catalogadores: úteis como corroboração, nunca como fonte única
4. Alibaba, OLX, listagens sem datasheet (TIER 4)
   → NUNCA adicionar sem âncora de outro tier
```

**Nunca usar como fonte primária:** output de IA sem verificação, descrições de
marketplaces de terceiros, títulos de página sem rastreabilidade técnica.

---

## 1. Visão Geral

Toshiba / Kioxia é o **terceiro maior fabricante mundial de NAND Flash**. Na bancada de
reciclagem da eMiner, aparece quase exclusivamente como **eMMC standalone (THGBM)** em
smartphones Android de entrada e mid-range. É uma marca de **baixo volume relativo**
comparado à Samsung e SK Hynix, mas com chips de boa liquidez B2B nas densidades maiores.

> **Nota histórica:** Em 2019 a divisão de memória da Toshiba foi separada e renomeada
> **Kioxia**. O prefixo THGBM continuou sendo usado em ambas as eras:
> chips pré-2019 têm silkscreen "Toshiba"; pós-2019 têm "KIOXIA". A gramática e
> as specs são idênticas — o banco classifica THGBM/TYC/TYD/TY890A sob Brand **"Toshiba"**.
> Novos prefixos pós-2019 (THGAM, THGJF, THGAF) usam Brand **"Kioxia"** —
> os product briefs que documentam esses chips são exclusivamente Kioxia (2020-2025).

| Categoria | Famílias mapeadas | Decode completo | Decode parcial | Sem decode |
|---|---|---|---|---|
| eMMC standalone (THGBM) | 1 | 1 | 0 | 0 |
| eMMC BiCS Kioxia (THGAM) | 1 (magra, sem decode) | — | — | magra |
| eMCP TYC (eMMC 4.5 + LPDDR2) | 1 (magra, sem decode) | — | — | magra |
| eMCP TYD (LPDDR3/BGA-221) | 1 (magra, sem decode) | — | — | magra |
| UFS Kioxia 3.1/4.0/4.1 (THGJF) | 1 (magra, sem decode) | — | — | magra |
| UFS Kioxia 2.1 (THGAF) | 1 (magra, sem decode) | — | — | magra |
| UFS KLUE (Kioxia) | 0 (BLOQUEADO) | — | — | — |
| NAND standalone TH58 | 0 (baixa prioridade) | — | — | — |
| DRAM TY890A (SDR SDRAM) | 0 (só KnownParts) | — | — | — |
| **TOTAL** | **6** (1 decode completo + 5 magras) | **1** | **0** | **5** |

**Arquivos que definem as famílias:**
- `chips/management/commands/populate_toshiba.py` — gabarito mestre (ChipFamilies + DecodeMaps)
- `chips/management/commands/fix_known_parts.py` — KnownParts manuais (Toshiba section)

---

## 2. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

### 2.1 Tabela canônica por tipo de chip

| Tipo de chip | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| eMMC standalone (THGBM) | `"eMMC"` | `""` | versão decodificada (`"eMMC 5.0"` / `"eMMC 5.1"`) | `capacity` (GB) |
| eMMC BiCS Kioxia (THGAM) | `"eMMC"` | `"eMMC Kioxia"` | `"eMMC 5.1"` (fixo, KnownPart) | `capacity` (GB) |
| UFS Kioxia 3.1/4.0/4.1 (THGJF) | `"UFS"` | `"UFS Kioxia"` | versão explícita (`"UFS 3.1"` / `"UFS 4.0"` / `"UFS 4.1"`) | `capacity` (GB ou TB) |
| UFS Kioxia 2.1 (THGAF) | `"UFS"` | `"UFS Kioxia"` | `"UFS 2.1"` (fixo, KnownPart) | `capacity` (GB) |
| eMCP LPDDR2 (TYC) | `"eMCP"` | `"eMCP Toshiba (eMMC + LPDDR2)"` | `""` (vazio) | `emcp_nand` + `emcp_ram` |
| eMCP LPDDR3 (TYD) | `"eMCP"` | `"eMCP Toshiba (eMMC + LPDDR3)"` | `""` (vazio) | `emcp_nand` + `emcp_ram` |
| DRAM (TY890A) | `"DRAM"` | `"SDR SDRAM"` | `""` | `capacity` (não confirmada) |

### 2.2 Regras absolutas do `subtype`

- Para **ChipFamily** (gramática): `subtype` = descrição curta da família, ex.:
  `"eMMC Toshiba/Kioxia MLC/TLC"`.
- Para **KnownPart** em `fix_known_parts`: usar a mesma string do ChipFamily, ou
  `"eMCP Toshiba (eMMC + LPDDR2)"` para eMCPs.
- **NUNCA** colocar no `subtype`: versão eMMC (`"5.1"`), capacidade (`"32GB"`),
  bus width, tensão ou qualificadores verbosos.

> **Label protegido por `canonical_gen` (2026-06-19) — FONTE ÚNICA da convenção.**
> O label da caixa é montado em `estoque/views.py::_compute_destination`, que passa o
> `subtype` por `chips/conventions.py::canonical_gen()`. Para eMMC, o label usa
> `capacity` (ex.: `"EMMC32GB"`), não o subtype — então subtype verboso não quebra
> o label eMMC. Ainda assim, escreva `subtype` limpo no write-time.

### 2.3 Campo `interface` — regras Toshiba / Kioxia

- **THGBM eMMC standalone:** `interface` = versão eMMC decodificada pelo `decode_gen_map`
  (THGBM_GEN). O engine preenche `r["interface"]` com `val_primary` do mapa.
  Em KnownPart manual (`fix_known_parts`), escrever explicitamente: `"eMMC 5.0"` ou `"eMMC 5.1"`.
- **eMCP TYC/TYD:** `interface=""` (string vazia). **Nunca** colocar geração de RAM aqui.
- **DRAM TY890A:** `interface=""`.

### 2.4 Gateway de estoque — como o label é montado

```
Para chip_type "eMMC":
  capacity = "32GB"
  label = "EMMC32GB"

Para chip_type "eMCP":
  emcp_nand = "eMMC 4.5 4GB"  → "4GB"
  emcp_ram  = "LPDDR2 512MB"  → "512MB" → 0 GB (arredondado)
  label = "EMCP4+0" (ou similar — ver gateway)
```

### 2.5 Campos `emcp_nand` e `emcp_ram` — eMCP TYC/TYD

- `emcp_nand` = tipo + capacidade: `"eMMC 4.5 4GB"`, `"eMMC 5.1 32GB"`
- `emcp_ram` = tipo **antes** da capacidade: `"LPDDR2 512MB"` — **nunca** `"512MB LPDDR2"`
- Para eMCP sem ChipFamily gramatical (TYC), esses campos vêm apenas do `fix_known_parts`.

### 2.6 Tabela de campos — O que vai / O que NÃO vai

| Campo | O que vai | O que NÃO vai |
|-------|-----------|---------------|
| `chip_type` | `"eMMC"`, `"eMCP"`, `"DRAM"`, `"UFS"` | `"Flash"`, `"NAND"`, `"TLC"`, `"eMMC 5.1"` |
| `subtype` | descrição curta da família | versão eMMC, capacidade, bus width |
| `interface` | versão eMMC para THGBM: `"eMMC 5.0"`, `"eMMC 5.1"` | geração de RAM, `""` para eMCP |
| `capacity` | capacidade total em GB: `"16GB"`, `"32GB"` | gigabits, capacidade eMCP |
| `emcp_nand` | (só eMCP) tipo + GB: `"eMMC 4.5 4GB"` | só o número, só o tipo |
| `emcp_ram` | (só eMCP) **tipo + capacidade**: `"LPDDR2 512MB"` — tipo VEM ANTES | ordem invertida |
| `tip` | avisos operacionais, notas de compatibilidade | specs que cabem nos outros campos |

---

## 3. Anatomia do PN por Família

### 3.1 THGBM — eMMC MLC/TLC (família principal)

```
T  H  G  B  M  [5]  [6] [7]  [8]  [9]  [10] B  A  [13] [14]
0  1  2  3  4   5    6   7    8    9    10   11 12  13   14

pn[0:5]  = "THGBM"   prefixo fixo da família
pn[5]    = geração NAND / versão eMMC → THGBM_GEN (1 char)
           N/T/F/B = eMMC 5.0  |  H/J/U = eMMC 5.1
pn[6]    = geralmente 'G' (processo de gravação — sem decode pelo engine)
           ⚠ EXCEÇÃO: pn[6]='T' em THGBMFT0CBLBAIS (128GB Supreme, 2014)
           O engine NÃO lê pn[6] — decode funciona independente deste char.
pn[7:10] = chave composta de capacidade → THGBM_CAP (3 chars)
           pn[7] = densidade/die (veja §4.1)
           pn[8] = tipo de stack (C/D/A/J/K/B — sem impacto na capacidade total)
           pn[9] = número de dies empilhados (1/2/4/8/B)
pn[10]   = tier de qualidade / organização (L/K/E/J…) — sem decode
           K = tier BG era (19nm 2nd gen) · L = tier padrão FG/HG/UG/JG eras
pn[11:13]= "BA" constante (package BGA153)
pn[13]   = grau de aplicação:  I = consumer/commercial  |  U = industrial
pn[14]   = variante de bin / package / temperatura:
           L = 11.5×13mm comercial padrão
           R = 11.5×13mm bin alternativo (Supreme 32/64GB era FG/BG)
           T = 11×10mm compacto (8GB)  |  W = 11×10mm (16/32GB)
           G/X = 64GB Supreme (11.5×13 / 11×10mm)  |  S = 128GB Supreme
           6/7/8 = extended temp industrial (-40°C a +105°C)
```

**Comprimento canônico:** 15 chars. PNs curtos ou longos não pertencem a esta família.

**Exemplos confirmados (todos Tier 1 — kioxia.com / product brief):**

| PN | pn[5] | pn[7:10] | Cap | eMMC | Fonte Tier 1 |
|---|---|---|---|---|---|
| THGBMBG7D2KBAIL | B | 7D2 | 16GB | 5.0 | kioxia.com 2013 |
| THGBMBG8D4KBAIR | B | 8D4 | 32GB | 5.0 | kioxia.com 2013 |
| THGBMFG7C1LBAIL | F | 7C1 | 16GB | 5.0 | Mouser/Kioxia America |
| THGBMFG7C2LBAIL | F | 7C2 | 16GB | 5.0 | kioxia.com 2014 |
| THGBMFG8C2LBAIL | F | 8C2 | 32GB | 5.0 | kioxia.com 2014 |
| THGBMFG8C4LBAIR | F | 8C4 | 32GB | 5.0 | kioxia.com 2014 |
| THGBMFG9C4LBAIR | F | 9C4 | 64GB | 5.0 | kioxia.com 2014 |
| THGBMFT0CBLBAIS | F | 0CB | 128GB | 5.0 | kioxia.com 2014 |
| THGBMHG8C4LBAU7 | H | 8C4 | 32GB | 5.1 | kioxia.com 2017 |
| THGBMHG9C8LBAU8 | H | 9C8 | 64GB | 5.1 | kioxia.com 2017 |
| THGBMUG8C2LBAIL | U | 8C2 | 32GB | 5.1 | product brief 2023 |
| THGBMJG9C8LBAU8 | J | 9C8 | 64GB | 5.1 | product brief 2023 |

### 3.2 TYC — eMCP LPDDR2 (sem ChipFamily gramatical)

```
T  Y  C  [3]  [4]  H  [6]  [7:9]  [9:12]  [12:14] [14]  [15]
0  1  2   3    4   5   6   7..9   9..12   12..14   14    15  (PN: 15-16 chars)

pn[0:3] = "TYC" prefixo eMCP LPDDR2 Toshiba
pn[3]   = capacidade NAND: '0'=4GB  |  '0G'=8GB? (hipótese não confirmada)
pn[4]   = variante de geração do NAND
pn[5]   = 'H' = LPDDR2 (hipótese — 'H12' = 512MB LPDDR2 na âncora)
pn[6:8] = '12' constante observada (significado não confirmado)
pn[8:14]= código de lote de fab (ex.: '1638', '1626', '1597'…)
pn[14:16]= sufixo de variante (ex.: 'RA')
```

**Nota:** A estrutura posicional do TYC **não foi verificada formalmente**. O decode
acima é hipótese baseada em cluster de lote. Não criar ChipFamily TYC sem confirmar
o decode de ao menos 3 posições via fonte Tier 2.

**PNs confirmados (via fix_known_parts):**

| PN | eMMC | LPDDR2 | Package | Fonte | Confidence |
|---|---|---|---|---|---|
| TYC0FH121638RA | eMMC 4.5 4GB | 512MB | BGA-162 | Octopart Tier 2 | distributor |
| TYC0FH121626RA | eMMC 4.5 4GB | 512MB | BGA-162 | Âncora 1638RA + mehrinfo | distributor |
| TYC0FH12162BRA | eMMC 4.5 4GB | 512MB | BGA-162 | Inferência estrutural (lote '2B') | estimated |

**⚠️ DISCREPÂNCIA PENDENTE — Preduo vs. Octopart:**
Preduo (Tier 3) categorizou `TYC0FH121642RA` como **"LPDDR3, 221ball"**. Isso contradiz
o Octopart (Tier 2) que confirma explicitamente `TYC0FH121638RA = "4Gb LPDDR2 + 4GB EMCP
device"`. Octopart prevalece sobre Preduo (Tier 2 > Tier 3). Interpretação: Preduo confunde
prefixos TYC/TYD. As entradas TYC* **não foram alteradas**. Revalidar em Octopart ou DigiKey
para o próprio `TYC0FH121642RA` se o PN aparecer na esteira.

### 3.3 TYD — eMCP LPDDR3 (BGA-221, sem ChipFamily gramatical)

Família mais recente que TYC: eMMC 4.5 + LPDDR3, package BGA-221 (~2015-2020).
Registrada como ChipFamily magra (prefixo reconhecido; decode posicional bloqueado por falta
de fonte Tier 1-2 suficiente).

```
T  Y  D  [3:5]  [5]  [6:8]  [8:12]  [12:14]
0  1  2   3..5   5    6..8   8..12   12..14  (PN: 14 chars)

pn[0:3]  = "TYD" → família eMCP LPDDR3/BGA-221 (TYC = LPDDR2/BGA-162)
pn[3:5]  = capacidade NAND: '0F'=4GB · '0G'=8GB (Preduo Tier 3 ✓)
pn[5]    = 'H' → marcador de RAM (hipótese — consistente com TYC)
pn[6:8]  = código de capacidade RAM: '22'=1GB LPDDR3 (âncora Preduo ✓)
pn[8:12] = código de lote/batch (ex.: 1627, 1651 — não encoda specs)
pn[12:14]= sufixo de grade (ex.: RA)
```

**Nota:** A estrutura posicional do TYD **não foi verificada formalmente em Tier 1-2**.
Decode acima é hipótese baseada em âncora Preduo (Tier 3) + cluster findcomponents.net.
Não criar DecodeMap sem confirmar ao menos 3 posições via fonte Tier 2.

**PNs confirmados (via fix_known_parts):**

| PN | eMMC | LPDDR3 | Package | Fonte | Confidence |
|---|---|---|---|---|---|
| TYD0GH221651RA | eMMC 4.5 8GB | 1GB | BGA-221 | Preduo Tier 3 (âncora) | — (só referência) |
| TYD0FH221627RA | eMMC 4.5 4GB | 1GB | BGA-221 | Inferência estrutural + cluster Tier 3 | estimated |

**Tabela de decode parcial (sem confirmação Tier 1-2):**

| pn[3:5] | NAND | Fonte |
|---|---|---|
| `0F` | 4GB | Preduo Tier 3 (contraste com 0G=8GB) |
| `0G` | 8GB | Preduo Tier 3 (âncora TYD0GH221651RA) |

| pn[6:8] | RAM | Fonte |
|---|---|---|
| `22` | 1GB LPDDR3 | Preduo Tier 3 (âncora TYD0GH221651RA: 8+8 = 8GB+8Gb=1GB) |

### 3.4 TY890A — DRAM Mobile SDR SDRAM (sem ChipFamily gramatical)

```
T  Y  8  9  0  A  [6:9]  [9:11]  [11:14]
0  1  2  3  4  5   6..9   9..11  11..14

pn[0:6] = "TY890A" prefixo família SDRAM mobile Toshiba
pn[6:9] = densidade (ex.: "111" para ~64MB? — não confirmado)
pn[9:11]= capacidade/organização interna (ex.: "22", "29" — diferem entre PNs irmãos)
pn[11:] = código de package/revisão
```

**⚠️ ATENÇÃO:** TY890A é **DRAM (SDR SDRAM)**, NÃO eMCP. Chips com prefixo "TY" podem
ser confundidos com eMCP TYC/TYD. A confirmação vem de iFixit PS Vita Teardown (2012),
Step 11: TY890A111222KA = "Mobile SDR SDRAM" na placa do modem 3G Qualcomm MDM6200.

### 3.5 THGJF — UFS 3.1 / 4.0 / 4.1 Kioxia (magra, sem decode posicional)

**Família pós-2019 — Brand "Kioxia".** Prefixo exclusivo Kioxia; nunca existiu como Toshiba.

```
T  H  G  J  F  [5]  [6]  [7]  [8]  [9]  B  A  [12] [13] [14]
0  1  2  3  4   5    6    7    8    9   10  11   12   13   14

pn[0:5]  = "THGJF"   prefixo UFS Kioxia
pn[5]    = geração UFS (P=3.1, M=4.0, R=4.1, A=3.1 variante, G=3.1 variante, J=4.0 variante…)
pn[6]    = designador de processo (T = BiCS FLASH 3D)
pn[7:10] = chave composta de capacidade (ex.: "0E1"=128GB, "1E4"=256GB, "2E4"=512GB, "3E8"=1TB)
           **Não mapeada no banco — magra sem DecodeMap**
pn[10:12]= "BA" (package constante)
pn[12]   = grau: I=consumer, T=industrial
pn[13:15]= sufixo de temperatura/bin (IP, TV, TZ, TW, VG…)
```

**Comprimento canônico:** 15 chars. Sem decode posicional implementado — cobertura via KnownParts `confirmed`.

**PNs confirmados (Tier 1 — kioxia.com product briefs, via fix_known_parts):**

| PN | UFS | Cap | Fonte Tier 1 |
|---|---|---|---|
| THGJFPT0E18BAIP | 3.1 | 128GB | UFS Brief Rev.3.0 (2025) |
| THGJFPT1E28BAIP | 3.1 | 256GB | UFS Brief Rev.3.0 (2025) |
| THGJFPT2E48BAIP | 3.1 | 512GB | UFS Brief Rev.3.0 (2025) |
| THGJFAT0T44BAIL | 3.1 | 128GB | UFS Brief Rev.2.0 (2022) |
| THGJFAT1T84BAIR | 3.1 | 256GB | UFS Brief Rev.2.0 (2022) |
| THGJFGT1E45BAIP | 3.1 | 256GB | UFS Brief Rev.3.0 (2025) |
| THGJFAT2T84BAIR | 3.1 | 512GB | UFS Brief Rev.2.0 (2022) |
| THGJFGT2T85BAIU | 3.1 | 512GB | UFS Brief Rev.2.0 (2022) |
| THGJFHT3TB4BAIG | 3.1 | 1TB | UFS Brief Rev.2.0 (2022) |
| THGJFMT1E45BATV | 4.0 | 256GB | UFS Brief Rev.3.0 (2025) |
| THGJFMT2E46BATV | 4.0 | 512GB | UFS Brief Rev.3.0 (2025) |
| THGJFMT3E86BATZ | 4.0 | 1TB | UFS Brief Rev.3.0 (2025) |
| THGJFJT0E25BAIP | 4.0 | 128GB | UFS Brief Rev.3.0 (2025) |
| THGJFJT1E45BATP | 4.0 | 256GB | UFS Brief Rev.3.0 (2025) |
| THGJFJT2T85BAT0 | 4.0 | 512GB | UFS Brief Rev.3.0 (2025) |
| THGJFRT1E45BATV | 4.1 | 256GB | UFS Brief Rev.3.0 (2025) |
| THGJFRT2E48BATV | 4.1 | 512GB | UFS Brief Rev.3.0 (2025) |
| THGJFRT3E88BATW | 4.1 | 1TB | UFS Brief Rev.3.0 (2025) |

> **⚠️ Nota TB:** 5 dos 18 PNs THGJF têm `capacity="1TB"`. O engine e o gateway de estoque
> exigem suporte a TB — **corrigido em `chips/engine.py` e `estoque/views.py` (2026-06-26)**.
> Ver armadilha §8.9.

### 3.6 THGAF — UFS 2.1 Kioxia (magra, sem decode posicional)

**Família de transição (pré-2019 a pós-2019) — Brand "Kioxia".** A linha THGAF nasceu na era
Toshiba (~2017-2018) mas só tem documentação Tier 1 nos briefs Kioxia. O silkscreen físico
pode trazer "TOSHIBA" ou "KIOXIA" conforme a data de fabricação — o banco usa Brand "Kioxia"
por ser a única fonte verificável Tier 1.

```
T  H  G  A  F  [5]  [6]  [7]  [8]  [9]  B  A  [12] [13] [14]
0  1  2  3  4   5    6    7    8    9   10  11   12   13   14

pn[0:5]  = "THGAF"   prefixo UFS 2.1 Kioxia
pn[5]    = designador de densidade/geração (8=16GB, B=32GB, E=32GB variante,
           B=64GB variante, F=64GB, B=128GB, E=128GB, B=256GB, E=256GB)
           — estrutura não confirmada formalmente
pn[6]    = designador de processo (G/T = tipo de die)
pn[7:10] = chave composta de capacidade — Não mapeada
pn[10:12]= "BA" (package constante)
pn[12]   = grau: I=consumer, B=automotive (AEC-Q100 Grade 2)
pn[13:15]= sufixo (IL=consumer, B7/B8=automotive)
```

**Comprimento canônico:** 15 chars. Sem decode posicional — cobertura via KnownParts `confirmed`.

**PNs confirmados (Tier 1 — kioxia.com product briefs, via fix_known_parts):**

| PN | UFS | Cap | Grau | Fonte Tier 1 |
|---|---|---|---|---|
| THGAF8G8T23BAIL | 2.1 | 32GB | Consumer | UFS Brief Rev.2.0 (2022) |
| THGAF8G9T43BAIR | 2.1 | 64GB | Consumer | UFS Brief Rev.2.0 (2022) |
| THGAF9G7L1LBAB7 | 2.1 | 16GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBG8T13BAB7 | 2.1 | 32GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFEG8T13BAB7 | 2.1 | 32GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBG9T23BAB8 | 2.1 | 64GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFEG9T23BAB8 | 2.1 | 64GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBT0T43BAB8 | 2.1 | 128GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFET0T43BAB8 | 2.1 | 128GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBT1T83BAB5 | 2.1 | 256GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFET1T83BAB5 | 2.1 | 256GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |

> **Variantes B vs E:** diferem apenas na nota 4 do brief ("max pre-load 100% da user area").
> Mesma capacidade/tipo/pacote. PNs distintos — o operador pode ler qualquer uma na esteira.
>
> **512GB automotive excluído:** `THGAFBT2T83BABI5` — PDF extraction produziu 15 ou 16 chars
> (ambiguidade com nota de rodapé ⁵). Não incluído por R1 (zero alucinação). Confirmar
> visualmente no PDF antes de adicionar como 40º PN.

### 3.7 THGAM — eMMC 5.1 BiCS FLASH Kioxia (magra, sem decode posicional)

**Prefixo exclusivo Kioxia pós-2019 — Brand "Kioxia".** O prefixo THGAM nunca existiu
na era Toshiba — surgiu com o BiCS FLASH 3D móvel (~2019+). Não confundir com THGBM.

```
T  H  G  A  M  [5]  [6]  [7]  [8]  [9]  B  A  [12] [13] [14]
0  1  2  3  4   5    6    7    8    9   10  11   12   13   14

pn[0:5]  = "THGAM"   prefixo eMMC BiCS Kioxia
pn[5]    = geração BiCS (V = BiCS gen V melhorado; S = BiCS gen S; R = BiCS gen R, 2019)
pn[6]    = designador de processo (G = tipo, S = slim variant?)
pn[7:10] = chave composta de capacidade (ex.: "7T1"=16GB, "8T1"=32GB, "9T2"=64GB, "T0T4"=128GB)
           **Hipótese não verificada formalmente — decode posicional bloqueado**
pn[10:12]= "BA" (package BGA-153)
pn[12]   = grau: I=consumer
pn[13:15]= sufixo (IL, IR)
```

**Comprimento canônico:** 15 chars. Package: 153-ball BGA (idêntico ao THGBM). Sem decode
posicional — cobertura via KnownParts `confirmed`.

**PNs confirmados (Tier 1 — kioxia.com e-MMC Product Brief Rev.2.0 (2023), via fix_known_parts):**

| PN | Cap | Série | Fonte Tier 1 |
|---|---|---|---|
| THGAMVG7T13BAIL | 16GB | Gen V | e-MMC Brief Rev.2.0 (2023) |
| THGAMVG8T13BAIL | 32GB | Gen V | e-MMC Brief Rev.2.0 (2023) |
| THGAMVG9T23BAIL | 64GB | Gen V | e-MMC Brief Rev.2.0 (2023) |
| THGAMVT0T43BAIR | 128GB | Gen V | e-MMC Brief Rev.2.0 (2023) |
| THGAMSG9T24BAIL | 64GB | Gen S (slim) | e-MMC Brief Rev.2.0 (2023) |
| THGAMST0T24BAIL | 128GB | Gen S (slim) | e-MMC Brief Rev.2.0 (2023) |

> **Gen R (2019):** THGAMRG7/8/9T*BAIL (16/32/64GB) e THGAMRT0T43BAIR (128GB) foram
> identificados em press release Kioxia 2019. Não incluídos na fase atual (source = press,
> não product brief) — adicionar se aparecerem na esteira com confirmação Tier 2+.

---

## 4. DecodeMaps — Inventário Completo

### 4.1 THGBM_CAP — pn[7:10], 3 chars (família THGBM)

Chave composta: `pn[7]`=densidade/die + `pn[8]`=stack type + `pn[9]`=die count.

**Densidade por die (pn[7]):**

| Código | Densidade/die | Bytes/die | Era típica |
|--------|--------------|-----------|------------|
| `4` | 16 Gbit | 2 GB | eMMC 4.x (~2013-2015) |
| `5` | 32 Gbit | 4 GB | eMMC 5.0 BiCS1/2 (~2015-2017) |
| `6` | 64 Gbit | 8 GB | eMMC 5.0/5.1 BiCS2/3 |
| `7` | 128 Gbit | 16 GB | eMMC 5.1 alta densidade |
| `8` | 64 Gbit | 8 GB | eMMC 5.1 BiCS3/4 (Toshiba Memory/Kioxia) |
| `9` | 64 Gbit | 8 GB | eMMC 5.1 multi-die alta densidade |

**Chaves confirmadas (por fonte, melhor primeiro):**

| Chave | `val_primary` | PN âncora principal | Melhor fonte | Status |
|-------|--------------|---------------------|-------------|--------|
| `4D1` | `"2GB"` | THGBM4G4D1HBAIR | censtry.com Tier 3 | ✅ |
| `5D1` | `"4GB"` | THGBMNG5D1LBAIT | **Kioxia product brief 2023 Tier 1 ✓** | ✅ T1 |
| `5D2` | `"8GB"` | THGBMDG5D2HBAIL | AIChipLink Tier 3 | ✅ |
| `6C1` | `"8GB"` | THGBMHG6C1LBAU6 | **kioxia.com 2017 Tier 1 ✓** | ✅ T1 |
| `6D1` | `"8GB"` | THGBMBG6D1KBAIL | Puris A19nm eMMC 5.0 Tier 3 | ✅ |
| `7C1` | `"16GB"` | THGBMFG7C1LBAIL | **Mouser/Kioxia America Tier 1 ✓** + Octopart Tier 2 ✓ | ✅ T1 |
| `7C2` | `"16GB"` | THGBMFG7C2LBAIL | **kioxia.com 2014 Tier 1 ✓** | ✅ T1 |
| `7D2` | `"16GB"` | THGBMBG7D2KBAIL | **kioxia.com 2013 Tier 1 ✓** (19nm 2nd gen, SOLICITADO) | ✅ T1 |
| `8C2` | `"32GB"` | THGBMFG8C2LBAIL | **kioxia.com 2014 Tier 1 ✓** + product brief 2023 Tier 1 ✓ | ✅ T1 **NOVO** |
| `8C4` | `"32GB"` | THGBMFG8C4LBAIR | **kioxia.com 2014 Tier 1 ✓** + Octopart Tier 2 ✓ | ✅ T1 |
| `8D4` | `"32GB"` | THGBMBG8D4KBAIR | **kioxia.com 2013 Tier 1 ✓** ("four 64Gbit chips"=32GB) | ✅ T1 |
| `9C4` | `"64GB"` | THGBMFG9C4LBAIR | **kioxia.com 2014 Tier 1 ✓** (Premium 64GB 15nm) | ✅ T1 **NOVO** |
| `9C8` | `"64GB"` | THGBMHG9C8LBAU8 | **kioxia.com 2017 Tier 1 ✓** + Mouser Tier 2 ✓ | ✅ T1 |
| `0CB` | `"128GB"` | THGBMFT0CBLBAIS | **kioxia.com 2014 Tier 1 ✓** (Supreme 128GB 15nm) | ✅ T1 **NOVO** |

**Chaves BLOQUEADAS (sem âncora Tier 2):**

| Chave | Capacidade esperada | Por quê bloqueada |
|-------|---------------------|-------------------|
| `4D4` | ~8GB? | Usuário estimou ~4GB, matemática diz 4×2GB=8GB — sem fonte verificável |
| `6A2` | ~16GB? | JS-rendered, estimativa de IA incorreta |
| `6A4` | ~32GB? | Não encontrado em fonte verificável |
| `8D2` | ~16GB? | Padrão: 2×8GB=16GB, mas sem âncora confirmatória |

**NÃO adicionar chaves BLOQUEADAS** sem nova pesquisa com PN âncora + fonte Tier 2+.

### 4.2 THGBM_GEN — pn[5], 1 char (família THGBM)

Codifica a geração do processo NAND / versão eMMC.
`val_primary` é usado pelo engine como `r["interface"]`.

| Chave | `val_primary` | PN âncora | Melhor fonte | Status |
|-------|--------------|-----------|-------------|--------|
| `N` | `"eMMC 5.0"` | THGBMNG5D1LBAIT | **Kioxia product brief 2023 Tier 1 ✓** | ✅ T1 |
| `T` | `"eMMC 5.0"` | THGBMTG5D1LBAIL | **Kioxia product brief 2023 Tier 1 ✓** | ✅ T1 |
| `F` | `"eMMC 5.0"` | THGBMFG7C2LBAIL | **kioxia.com 2014 Tier 1 ✓** (15nm process launch) | ✅ T1 |
| `B` | `"eMMC 5.0"` | THGBMBG7D2KBAIL | **kioxia.com 2013 Tier 1 ✓** (19nm 2nd gen launch) | ✅ T1 |
| `H` | `"eMMC 5.1"` | THGBMHG6C1LBAU6 | **kioxia.com 2017 Tier 1 ✓** (industrial -40°C a +105°C) | ✅ T1 |
| `J` | `"eMMC 5.1"` | THGBMJG6C1LBAU7 | **Kioxia product brief 2023 Tier 1 ✓** (industrial) | ✅ T1 |
| `U` | `"eMMC 5.1"` | THGBMUG6C1LBAIL | **Kioxia product brief 2023 Tier 1 ✓** (consumer) | ✅ T1 **NOVO** |

**Chaves BLOQUEADAS (sem fonte explícita para versão eMMC):**

| Chave | Hipótese | Por quê bloqueada |
|-------|----------|-------------------|
| `D` | eMMC 5.0 | THGBMDG5D2HBAIL — AIChipLink menciona mas sem versão eMMC explícita |
| `4` | eMMC 4.41 | THGBM4G… — lógico pelo prefixo mas sem fonte primária para versão |
| `G` / `M` | desconhecida | identificados em PNs de campo, versão não verificada |

---

## 5. Famílias — Inventário Completo

### 5.1 eMMC Standalone

| Prefixo | `chip_type` | `subtype` | Decode cap | Decode gen | Priority | Status |
|---------|-------------|-----------|-----------|-----------|----------|--------|
| THGBM | `"eMMC"` | `"eMMC Toshiba/Kioxia MLC/TLC"` | THGBM_CAP pn[7:10] | THGBM_GEN pn[5] | 50 | ✅ Completo |

**Configuração atual (populate_toshiba.py):**

```python
dict(
    prefix="THGBM",
    chip_type="eMMC",
    subtype="eMMC Toshiba/Kioxia MLC/TLC",
    interface="eMMC",
    pn_length=15,
    decode_cap_pos=7,
    decode_cap_len=3,
    decode_cap_map="THGBM_CAP",
    decode_gen_pos=5,
    decode_gen_len=1,
    decode_gen_map="THGBM_GEN",
    is_emcp=False,
    active=True,
    priority=50,
)
```

> **Devices típicos:** smartphones Android mid-range e entry-level (~2013–2023).
> Samsung Galaxy J/A series (OEM Toshiba), Xiaomi Redmi, Realme, feature phones MediaTek,
> tablets de entrada.

### 5.2 Famílias OBSOLETAS (DEVEM ser removidas pelo `--overwrite`)

```
OBSOLETE_FAMILY_PREFIXES = ["THGBMFG", "THGBMHG"]
```

Essas duas famílias foram criadas em 2025 por `add_chip_families.py` com
`interface='eMMC 5.1'` hardcoded e **sem decode maps**. Como o engine ordena por
`prefix_len DESC`, `THGBMHG` (len=7) e `THGBMFG` (len=7) interceptavam antes de
`THGBM` (len=5), bloqueando a gramática completa → `capacity=None` →
`grammar_complete=False` → chip aparecia como "desconhecido".

**Fix:** `python manage.py populate_toshiba --overwrite` deleta ambas automaticamente.
**Sempre rodar** depois de qualquer restauração de banco ou re-setup.

### 5.3 Famílias BLOQUEADAS — pesquisa pendente

| Prefixo | Tipo esperado | Por quê bloqueada |
|---------|--------------|-------------------|
| KLUE | UFS Kioxia (pós-2019) | **Instrução explícita do operador:** verificar kioxia.com antes de qualquer adição |
| TH58 | NAND standalone Toshiba | Baixa prioridade operacional; estrutura posicional não confirmada |

> **Desbloqueadas em sessão 4 (2026-06-26):** THGAF (11 PNs Tier 1 confirmados — §3.6 e §5.6),
> TYC (registrada como magra em sessão anterior), TYD (registrada como magra em sessão 3).
> THGAM também desbloqueada — ver §5.4 (agora ATIVA com 6 PNs confirmados).

### 5.4 THGAM — eMMC 5.1 BiCS FLASH Kioxia ✅ ATIVA (magra, sessão 4 — 2026-06-26)

**Status: ATIVA — magra, sem decode posicional.** ChipFamily registrada em `populate_toshiba.py`
(sessão 4). 6 PNs `confidence=confirmed` em `fix_known_parts.py`. Anatomia completa em §3.7.

**Prefixo:** `THGAM` — exclusivo Kioxia pós-2019. Brand: "Kioxia". `pn_length=15`, `BGA-153`.
`chip_type="eMMC"`, `subtype="eMMC Kioxia"`, `interface="eMMC 5.1"`.

**6 PNs confirmados (Tier 1 — kioxia.com e-MMC Product Brief Rev.2.0, 2023):**

| PN | Capacidade | Série | Confidence |
|---|---|---|---|
| THGAMVG7T13BAIL | 16GB | Gen V | confirmed |
| THGAMVG8T13BAIL | 32GB | Gen V | confirmed |
| THGAMVG9T23BAIL | 64GB | Gen V | confirmed |
| THGAMVT0T43BAIR | 128GB | Gen V | confirmed |
| THGAMSG9T24BAIL | 64GB | Gen S (slim) | confirmed |
| THGAMST0T24BAIL | 128GB | Gen S (slim) | confirmed |

> **Gen R (2019 press release):** 4 PNs adicionais (THGAMRG7/8/9*/THGAMRT0*) identificados
> em press release kioxia.com 2019 — não incluídos por ser fonte press (não product brief).
> Adicionar se aparecerem na esteira com âncora Tier 2.

**Para decode posicional completo (futuro):**
1. Confirmar pn[5] (gen NAND: R/V/S) e pn[7:10] (cap key) via datasheet ou Tier 2 com spec posicional
2. Criar `THGAM_CAP` e `THGAM_GEN` DecodeMaps em `populate_toshiba.py`

### 5.5 THGJF — UFS 3.1 / 4.0 / 4.1 Kioxia ✅ ATIVA (magra, sessão 4 — 2026-06-26)

**Status: ATIVA — magra, sem decode posicional.** ChipFamily registrada em `populate_toshiba.py`
(sessão 4). 18 PNs `confidence=confirmed` em `fix_known_parts.py`. Anatomia completa em §3.5.

**Prefixo:** `THGJF` — exclusivo Kioxia pós-2019. Brand: "Kioxia". `pn_length=15`.
`chip_type="UFS"`, `subtype="UFS Kioxia"`. `interface` varia por PN (3.1/4.0/4.1).

**18 PNs confirmados (Tier 1 — kioxia.com UFS Product Briefs Rev.2.0 2022 + Rev.3.0 2025):**

| PN | UFS | Cap | Confidence |
|---|---|---|---|
| THGJFPT0E18BAIP | 3.1 | 128GB | confirmed |
| THGJFPT1E28BAIP | 3.1 | 256GB | confirmed |
| THGJFPT2E48BAIP | 3.1 | 512GB | confirmed |
| THGJFAT0T44BAIL | 3.1 | 128GB | confirmed |
| THGJFAT1T84BAIR | 3.1 | 256GB | confirmed |
| THGJFGT1E45BAIP | 3.1 | 256GB | confirmed |
| THGJFAT2T84BAIR | 3.1 | 512GB | confirmed |
| THGJFGT2T85BAIU | 3.1 | 512GB | confirmed |
| THGJFHT3TB4BAIG | 3.1 | **1TB** | confirmed |
| THGJFMT1E45BATV | 4.0 | 256GB | confirmed |
| THGJFMT2E46BATV | 4.0 | 512GB | confirmed |
| THGJFMT3E86BATZ | 4.0 | **1TB** | confirmed |
| THGJFJT0E25BAIP | 4.0 | 128GB | confirmed |
| THGJFJT1E45BATP | 4.0 | 256GB | confirmed |
| THGJFJT2T85BAT0 | 4.0 | 512GB | confirmed |
| THGJFRT1E45BATV | 4.1 | 256GB | confirmed |
| THGJFRT2E48BATV | 4.1 | 512GB | confirmed |
| THGJFRT3E88BATW | 4.1 | **1TB** | confirmed |

> **5 PNs têm `capacity="1TB"`** — exigiram fix TB no engine e no gateway de estoque (§8.9).

### 5.6 THGAF — UFS 2.1 Kioxia ✅ ATIVA (magra, sessão 4 — 2026-06-26)

**Status: ATIVA — magra, sem decode posicional.** ChipFamily registrada em `populate_toshiba.py`
(sessão 4). 11 PNs `confidence=confirmed` em `fix_known_parts.py`. Anatomia completa em §3.6.

**Prefixo:** `THGAF` — linha UFS 2.1 (pré-2019 a pós-2019). Brand: "Kioxia". `pn_length=15`.
`chip_type="UFS"`, `subtype="UFS Kioxia"`, `interface="UFS 2.1"` (fixo para toda a família).

**11 PNs confirmados (Tier 1 — kioxia.com briefs, via fix_known_parts):**

| PN | Cap | Grau | Fonte Tier 1 |
|---|---|---|---|
| THGAF8G8T23BAIL | 32GB | Consumer | UFS Brief Rev.2.0 (2022) |
| THGAF8G9T43BAIR | 64GB | Consumer | UFS Brief Rev.2.0 (2022) |
| THGAF9G7L1LBAB7 | 16GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBG8T13BAB7 | 32GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFEG8T13BAB7 | 32GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBG9T23BAB8 | 64GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFEG9T23BAB8 | 64GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBT0T43BAB8 | 128GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFET0T43BAB8 | 128GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFBT1T83BAB5 | 256GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |
| THGAFET1T83BAB5 | 256GB | Auto AEC-Q100 Gr.2 | Auto Brief Rev.2.0 (2020) |

> **512GB automotive THGAFBT2T83BABI5 excluído:** ambiguidade de extração PDF (15 ou 16 chars).
> Confirmar visualmente antes de adicionar como 40º PN.

---

## 6. fix_known_parts — Template e Regras

### 6.1 Template — eMMC THGBM (KnownPart com capacidade explícita)

Usar quando um PN específico precisa ser promovido a `confirmed` (ex.: âncora de uma
nova chave do mapa, ou chip que chegou na esteira sem ser reconhecido):

```python
# eMMC Toshiba/Kioxia — THGBMHG8C4LBAIR (32GB eMMC 5.1, BGA153)
{
    "pn": "THGBMHG8C4LBAIR",
    "create": True,
    "create_defaults": {
        "brand_name": "Toshiba",
        "chip_type":  "eMMC",
        "subtype":    "eMMC Toshiba/Kioxia MLC/TLC",
        "confidence": "confirmed",   # campo status removido em jun/2026
    },
    "fields": {
        "capacity":   "32GB",
        "interface":  "eMMC 5.1",   # versão eMMC explícita
        "confidence": "confirmed",
    },
    "reason": (
        "Octopart (Tier 2, PN exato): 'Flash Card 32G-byte 3.3V Embedded MMC 153-Pin VFBGA' → 32GB ✓. "
        "pn[5]='H' → THGBM_GEN = eMMC 5.1. pn[7:10]='8C4' → THGBM_CAP = 32GB."
    ),
},
```

### 6.2 Template — eMCP TYC (sem ChipFamily gramatical)

Usar para eMCP Toshiba sem gramática — `create=True` é obrigatório pois o engine
não tem família TYC para reconhecer o chip:

```python
# eMCP Toshiba — TYC0FH121638RA (4GB eMMC 4.5 + 512MB LPDDR2, BGA-162)
{
    "pn": "TYC0FH121638RA",
    "create": True,
    "create_defaults": {
        "brand_name": "Toshiba",
        "chip_type":  "eMCP",
        "subtype":    "eMCP Toshiba (eMMC + LPDDR2)",
        "confidence": "distributor",   # ou "confirmed" se Tier 2+ com PN exato
        # campo status removido em jun/2026 — não incluir
    },
    "fields": {
        "emcp_nand": "eMMC 4.5 4GB",
        "emcp_ram":  "LPDDR2 512MB",  # tipo ANTES da capacidade
    },
    "reason": (
        "Octopart: '4Gb LPDDR2 + 4GB EMCP device, MMC v4.5/v4.51' → 4GB eMMC + 512MB LPDDR2 (4Gb÷8). "
        "Família TYC sem ChipFamily gramatical — create=True garante classificação manual."
    ),
},
```

### 6.3 Regras de `capacity` para Toshiba

- **THGBM eMMC standalone:** `capacity` = GB do chip, em bytes. Ex.: `"32GB"`, `"16GB"`.
- **eMCP TYC/TYD:** NÃO preencher `capacity` — usar `emcp_nand` e `emcp_ram`.
- **NUNCA** usar Gbit no campo `capacity` (ex.: `"256Gbit"` → errado).
- **Conversão Gbit→GB:** `256 Gbit ÷ 8 = 32 GB`. Verificar **sempre** — Octopart e
  catálogos misturam Gb e GB com frequência.

### 6.4 Diferença TYC vs TYD vs TY890A

| Prefixo | Tipo | Package | RAM | Como identificar |
|---------|------|---------|-----|-----------------|
| TYC | eMCP | BGA-162 | LPDDR2 | pn[2]='C' + 4GB/8GB NAND máx. conhecido |
| TYD | eMCP | BGA-221 | LPDDR3 (hipótese) | pn[2]='D' — sem PNs confirmados ainda |
| TY890A | DRAM (SDR SDRAM) | BGA | N/A (não é eMCP) | pn[2:5]='890' — iFixit confirms |

**⚠️ Armadilha:** o prefixo "TY" é compartilhado por famílias completamente diferentes.
Não assuma que todo "TY..." é eMCP.

---

## 7. assess_profitability — Limiares Toshiba / Kioxia

### 7.1 THGBM eMMC standalone

O engine usa a regra universal de eMMC:

```python
if chip_type == "eMMC":
    cap_gb = _extract_gib(result.get("capacity") or "")
    if cap_gb is None:
        return "INDETERMINADO"
    return "RENTÁVEL" if cap_gb >= cfg.emmc_min_cap_gb - 0.01 else "NÃO RENTÁVEL"
```

`cfg.emmc_min_cap_gb` vive em `ProfitabilityConfig` (editável no admin). **Default: 4.0 GB.**
Chips com `capacity ≥ 4.0 GB` são RENTÁVEL; abaixo de 4.0 GB → NÃO RENTÁVEL.

**Sem distinção de versão (5.0 vs 5.1)** — decisão de negócio confirmada pelo usuário.
eMMC 5.1 vale ~15-25% a mais na revenda B2B, mas a rentabilidade binária não muda.

| Chave THGBM_CAP | Capacidade | Rentabilidade | Observação |
|-----------------|-----------|--------------|------------|
| `4D1` | 2GB | **NÃO RENTÁVEL** | 2 < 4GB — sem liquidez B2B |
| `5D1` | 4GB | **RENTÁVEL** | 4GB = limiar mínimo (default 4.0) |
| `5D2` | 8GB | **RENTÁVEL** | ✓ |
| `6C1` | 8GB | **RENTÁVEL** | ✓ |
| `6D1` | 8GB | **RENTÁVEL** | ✓ |
| `7C1` | 16GB | **RENTÁVEL** | Alta liquidez |
| `7C2` | 16GB | **RENTÁVEL** | Alta liquidez |
| `7D2` | 16GB | **RENTÁVEL** | Alta liquidez |
| `8C2` | 32GB | **RENTÁVEL** | Prioridade Diamante (**NOVO** 2026-06-26) |
| `8C4` | 32GB | **RENTÁVEL** | Prioridade Diamante |
| `8D4` | 32GB | **RENTÁVEL** | Prioridade Diamante |
| `9C4` | 64GB | **RENTÁVEL** | Prioridade Diamante (**NOVO** 2026-06-26) |
| `9C8` | 64GB | **RENTÁVEL** | Prioridade Diamante |
| `0CB` | 128GB | **RENTÁVEL** | Prioridade Diamante (**NOVO** 2026-06-26) |

### 7.2 eMCP TYC (eMMC 4.5 + LPDDR2)

O engine usa o bloco eMCP:

```python
if chip_type == "eMCP":
    nand_gb = _extract_gib(result.get("emcp_nand") or "")
    ram_gb  = _extract_gib(result.get("emcp_ram")  or "")
    ...
    return "RENTÁVEL" if nand_gb >= cfg.emcp_min_nand and ram_gb >= cfg.emcp_min_ram
           else "NÃO RENTÁVEL"
```

TYC0FH121638RA / TYC0FH121626RA: 4GB NAND + 512MB RAM → **NÃO RENTÁVEL** pelos thresholds
atuais (threshold eMMC 4.x + LPDDR2 legado — confirmar `ProfitabilityConfig` no admin).

### 7.3 UFS THGJF / THGAF

O engine usa a regra universal de UFS:

```python
if chip_type == "UFS":
    cap_gb = _extract_gib(result.get("capacity") or "")
    if cap_gb is None:
        return "INDETERMINADO"
    return "RENTÁVEL" if cap_gb >= cfg.ufs_min_cap else "NÃO RENTÁVEL"
```

Todos os 29 PNs UFS da Kioxia (THGJF + THGAF) têm `capacity` explícita no KnownPart →
`_extract_gib` nunca retorna None → sem risco de INDETERMINADO. Verificar `cfg.ufs_min_cap`
no admin (`ProfitabilityConfig`) para confirmar o limiar vigente.

> **⚠️ Nota TB:** `_extract_gib("1TB")` retornava None antes de 2026-06-26 — os 5 PNs
> 1TB (THGJF*) seriam INDETERMINADO. Corrigido — ver §8.9.

### 7.4 Destinos comerciais por tipo

| Tipo | Densidade | Destino |
|------|-----------|---------|
| THGBM 64–128GB (qualquer gen) | 9C4, 9C8, 0CB | Bancada reacondicional eMMC — **Prioridade Diamante** |
| THGBM 32GB (qualquer gen) | 8C2, 8C4, 8D4 | Bancada reacondicional eMMC — **Prioridade Diamante** |
| THGBM 16GB (qualquer gen) | 7C1, 7C2, 7D2 | Bancada reacondicional eMMC — Alta liquidez |
| THGBM 8GB (qualquer gen) | 5D2, 6C1, 6D1 | Bancada reacondicional eMMC |
| THGBM 4GB | 5D1 | Bancada eMMC (RENTÁVEL — ≥ 4GB default) |
| THGBM 2GB | 4D1 | Resíduo (moagem/refino — NÃO RENTÁVEL) |
| THGAM eMMC 5.1 BiCS 16–128GB | — | Bancada reacondicional eMMC (mesma regra THGBM) |
| THGJF UFS 3.1/4.0/4.1 128GB–1TB | — | Bancada UFS — verificar `ufs_min_cap` |
| THGAF UFS 2.1 16–256GB | — | Bancada UFS — verificar `ufs_min_cap` |
| TYC eMCP 4GB NAND + 512MB LPDDR2 | — | A verificar — provavelmente NÃO RENTÁVEL |
| TY890A SDR SDRAM | — | Resíduo (era SDRAM — sem mercado B2B de reciclagem) |

---

## 8. Armadilhas e Decisões Arquiteturais

### 8.1 Sub-prefixos THGBMFG / THGBMHG interceptavam antes de THGBM

**O problema:** `add_chip_families.py` criou em 2025 famílias `THGBMFG` (len=7) e
`THGBMHG` (len=7) com `interface='eMMC 5.1'` hardcoded mas **sem decode maps**. O engine
ordena por `prefix_len DESC` → os sub-prefixos interceptavam antes de `THGBM` (len=5).
Resultado: `capacity=None` → `grammar_complete=False` → "chip desconhecido" na UI.

**O fix:** `OBSOLETE_FAMILY_PREFIXES = ["THGBMFG", "THGBMHG"]` em `populate_toshiba.py`.
Rodar `python manage.py populate_toshiba --overwrite` deleta ambas. Sem o `--overwrite`,
o comando não age sobre famílias existentes.

**Sintoma diagnóstico:** se um THGBM* aparecer como "chip desconhecido", verificar:
1. `THGBMFG` ou `THGBMHG` ainda existem no banco (`ChipFamily.objects.filter(prefix__startswith='THGBMFG')`)
2. A chave (3 chars `pn[7:10]`) existe no `THGBM_CAP`
3. A letra de geração (`pn[5]`) existe no `THGBM_GEN`

### 8.2 Sufixo R/L/7/8 (pn[14]) NÃO interfere no decode

**Erro comum de IAs externas:** alegar que o sufixo `R` (vs `L`) causou falha de
classificação. O decoder THGBM lê **apenas** `pn[5]` (GEN) e `pn[7:10]` (CAP).
`pn[14]` = variante de bin/temperatura (comercial/industrial) — invisível para o engine.

### 8.3 Toshiba → Kioxia: mesma gramática, brand diferente

Chips pré-2019 têm silkscreen "Toshiba"; pós-2019 têm "KIOXIA" — **mas o PN começa
com THGBM nos dois casos**. O banco usa `brand_name="Toshiba"` para a família THGBM.
Chips Kioxia são classificados corretamente pela mesma gramática.

**Não criar uma família THGBM duplicada sob `brand_name="Kioxia"`** — causaria conflito
de mapa e duplicação de decode.

### 8.4 "G" em nomes Toshiba é Gbit, não GB

No nome de peça Toshiba (diferente de Samsung), a densidado do THGBM_CAP é expressa
em Gbit por die. A conversão é: `Gbit ÷ 8 = GB`. Exemplo: pn[7]='8' = 64 Gbit/die = 8 GB/die.
Com 4 dies (pn[9]='4'): 4 × 8 GB = **32 GB total**. Verificar sempre a matemática
antes de adicionar uma chave nova.

### 8.5 TYC0FH: posições 10-11 são código de lote, não versão

Em TYC0FH121638RA e TYC0FH121626RA, as posições 10-11 diferem (`38` vs `26`). São
**códigos de lote de fabricação** — mesmas specs, só data/lote diferente. O cluster
TYC0FH121597RA / 1626RA / 1638RA / 1642RA / 1645RA / 1660RA são todos irmãos com
mesmas specs (confirmado via YIC + Allelco — mesma descrição TAEC Product, BGA).

`TYC0FH12162BRA` (lote `2B`, hex) entra neste cluster com specs inferidas —
`confidence=estimated` (Tier 1/2/3 não indexam este PN; inferência estrutural pura).
Confirmar via Tier 2 em sessão futura quando o PN ficar indexado.

### 8.6 TY890A: confusão com eMCP pelo prefixo "TY"

IA externas e distribuidores tendem a classificar TY890A como "eMCP" ou "eMMC" por
associação com a família TYC. TY890A é **SDRAM standalone** — confirmado por iFixit
(PS Vita 2012, Step 11). **Não criar família TY890A como eMCP**.

### 8.7 eMMC 5.0 vs 5.1: valor B2B diferente, rentabilidade igual

A versão eMMC impacta o preço de revenda (~15-25% de diferença), mas a regra de
`assess_profitability` não a distingue: só verifica `cap_gb >= 7.99`. Decisão de negócio
confirmada pelo usuário em 2026-06-26. Se houver necessidade futura de separar 5.0 e 5.1
na lógica de rentabilidade, **propor ao usuário antes de tocar no engine**.

### 8.8 `8C4` e `8D4` são ambos 32GB com processos diferentes

`pn[8]='C'` e `pn[8]='D'` diferem no tipo de stack de dies, mas a capacidade total
é a mesma (8×4 = 32GB). O engine trata ambas como `"32GB"`. Para fins de triagem
na esteira, são intercambiáveis.

### 8.9 `capacity="1TB"` sem suporte no engine — CORRIGIDO 2026-06-26

**O problema:** 5 PNs THGJF têm `capacity="1TB"` (Kioxia UFS 3.1/4.0/4.1 de 1TB).
Antes da correção:
- `_CAP_RE = r"(\d+)\s*([GMK])B"` — 'T' (terabyte) não estava no character class
- `_extract_gib("1TB")` retornava `None` → `assess_profitability` retornava `INDETERMINADO`
- `_CAP_BYTES_RE` em `estoque/views.py` também não reconhecia TB → label UFS ficava `"UFS"` (vazio)

**Fix aplicado em `chips/engine.py`:**
- `_CAP_RE` → `r"(\d+)\s*([TGMK])B"` (T adicionado)
- `_extract_gib`: bloco `if unit == "T": return val * 1024` (1TB → 1024GB)
- `_CAP_NUM_RE` → inclui `TB` no pattern `(?:TB|GB|MB)`

**Fix aplicado em `estoque/views.py`:**
- `_CAP_BYTES_RE` → `r'(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b'` (TB adicionado)
- Builders UFS e eMMC: trocado `_extract_gb + "GB"` hardcoded por `_format_cap(...)` que preserva a unidade original
- Resultado: `capacity="1TB"` → label `"UFS1TB"` ✓ (antes: `"UFS"` ✗)

**Compatibilidade retroativa:** `_format_cap("128GB")` → `"128GB"` → `"UFS128GB"` (idêntico ao anterior).
20/20 testes de regressão aprovados após fix.

---

## 9. Gaps e Roadmap

### 9.1 Chaves THGBM_CAP — não mapeadas

**Desbloqueadas em 2026-06-26 (agora no populate_toshiba.py):** 8C2 ✅, 9C4 ✅, 0CB ✅

| Sprint | Chave | Cap esperada | Evidência atual | O que falta |
|--------|-------|--------------|-----------------|-------------|
| A | `4D4` | ~8GB | Padrão matemático: 4×2GB=8GB | PN âncora Tier 2+ |
| B | `6A2` | ~16GB | JS-rendered, não verificável | Fonte estática com PN |
| B | `6A4` | ~32GB | Padrão, sem fonte | PN âncora Tier 2+ |
| B | `8D2` | ~16GB | Padrão: 2×8GB=16GB | PN âncora Tier 2+ |

### 9.2 Chaves THGBM_GEN — não mapeadas

**Desbloqueada em 2026-06-26 (agora no populate_toshiba.py):** U=eMMC 5.1 ✅

| Sprint | Chave | Hipótese | O que falta |
|--------|-------|----------|-------------|
| B | `D` | eMMC 5.0 | Fonte com versão eMMC explícita para THGBMDG* |
| C | `4` | eMMC 4.41 | Fonte Tier 2+ para THGBM4G* com versão |
| C | `G`, `M` | desconhecida | PN âncora + fonte |

### 9.3 Famílias BLOQUEADAS

| Sprint | Família | O que falta para desbloquear |
|--------|---------|------------------------------|
| A | KLUE (UFS Kioxia) | Verificação obrigatória em `business.kioxia.com` — instrução explícita do operador |
| B | TH58 (NAND standalone) | Baixa prioridade — confirmar estrutura posicional |

> **Desbloqueadas em sessão 4:** THGAM (magra ativa, 6 PNs confirmed), THGJF (magra ativa, 18 PNs),
> THGAF (magra ativa, 11 PNs), TYC (magra ativa, sessões anteriores), TYD (magra ativa, sessão 3).
> Para decode posicional completo de THGAM/THGJF/THGAF, ver §9.4.

### 9.4 O que NÃO adicionar sem evidência Tier 2

- Qualquer chave nova de THGBM_CAP baseada só em "padrão matemático" (sem PN âncora)
- Qualquer spec da família KLUE sem verificação em kioxia.com
- Qualquer PN TYD sem fonte Tier 2 explícita
- DecodeMap posicional para THGAM/THGJF/THGAF sem confirmar a estrutura decode (§3.5–3.7)

---

## 10. Histórico de Correções

| Data | PN / Família | Ação | Fonte | Motivo |
|------|-------------|------|-------|--------|
| 2025 (prior) | THGBMFG, THGBMHG | Criação de sub-famílias | `add_chip_families.py` | Tentativa de decode por sub-prefixo (incorreta) |
| 2026-05-25 | THGBMFG, THGBMHG | Adicionados a `OBSOLETE_FAMILY_PREFIXES` | — | Sub-prefixos interceptavam antes de THGBM sem decode maps |
| 2026-05-25 | THGBM_GEN: F, B | Desbloqueadas (eMMC 5.0) | Puris + Preduo + made-in-china | Confirmação de versão eMMC 5.0 para gen F e B |
| 2026-05-25 | TYC0FH121638RA | Adicionado a fix_known_parts | Octopart Tier 2 | eMCP Toshiba sem família gramatical |
| 2026-05-25 | TYC0FH121626RA | Adicionado a fix_known_parts | Âncora TYC0FH121638RA + mehrinfo | Variante de lote |
| 2026-05-25 | TY890A111229KC | Adicionado a fix_known_parts | iFixit PS Vita Tier 2 | SDR SDRAM, não eMCP |
| 2026-06-26 | THGBM_CAP: 7C1 | Âncora promovida Tier 3→Tier 1+2 | Mouser/Kioxia America + Octopart | THGBMFG7C1LBAIL confirmado em listagem ativa |
| 2026-06-26 | THGBMFG7C1LBAIL | Adicionado a fix_known_parts, confidence=confirmed | Mouser/Kioxia America Tier 1 + Octopart Tier 2 | Chip na esteira; promoção confirmed |
| 2026-06-26 | THGBM_CAP: 8C4 | Âncora promovida Tier 3→Tier 2 | Octopart Tier 2 (PN exato) | THGBMHG8C4LBAIR: "32G-byte VFBGA" |
| 2026-06-26 | THGBMHG8C4LBAIR | Adicionado a fix_known_parts, confidence=confirmed | Octopart Tier 2 | Chip mostrava "desconhecido" (causa: THGBMHG sub-prefix no banco) |
| 2026-06-26 (sessão 2) | THGBM_CAP: 7D2, 8C4, 8D4 | Âncoras promovidas Tier 3→Tier 1 | kioxia.com 2013 press (Tier 1) | BG era confirmada pelo press release original de lançamento |
| 2026-06-26 (sessão 2) | THGBM_CAP: 6C1, 7C2, 9C8 | Âncoras promovidas Tier 3→Tier 1 | kioxia.com 2017 press (Tier 1) | HG industrial era confirmada |
| 2026-06-26 (sessão 2) | THGBM_CAP: 8C2 (**NOVO**) | Chave 32GB adicionada ao mapa | kioxia.com 2014 + product brief 2023 (Tier 1) | THGBMFG8C2LBAIL (Premium) + THGBMUG8C2LBAIL |
| 2026-06-26 (sessão 2) | THGBM_CAP: 9C4 (**NOVO**) | Chave 64GB adicionada ao mapa | kioxia.com 2014 press (Tier 1) | THGBMFG9C4LBAIR (Premium 64GB) |
| 2026-06-26 (sessão 2) | THGBM_CAP: 0CB (**NOVO**) | Chave 128GB adicionada ao mapa | kioxia.com 2014 press (Tier 1) | THGBMFT0CBLBAIS (Supreme 128GB); pn[6]='T' nesta chave |
| 2026-06-26 (sessão 2) | THGBM_GEN: N, T, F, B, H, J | Todas as chaves promovidas a Tier 1 | kioxia.com 2013/2014/2017 + product brief 2023 (Tier 1) | Cada chave agora tem âncora Tier 1 explícita |
| 2026-06-26 (sessão 2) | THGBM_GEN: U (**NOVO**) | Chave eMMC 5.1 consumer adicionada | Kioxia product brief 2023 (Tier 1) | THGBMUG* = consumer eMMC 5.1 |
| 2026-06-26 (sessão 2) | THGAM* família | Descoberta documentada (§5.4) | kioxia.com 2019/2023 press (Tier 1) | Nova família BiCS FLASH — BLOQUEADA aguardando decode posicional |
| 2026-06-26 (sessão 2) | 22 PNs THGBM | Adicionados a fix_known_parts, confidence=confirmed | kioxia.com 2013/2014/2017 + product brief 2023 (Tier 1) | BG, FG, HG industrial, UG consumer, JG industrial |
| 2026-06-26 (sessão 3) | TYC0FH12162BRA | Adicionado a fix_known_parts, confidence=estimated | Inferência estrutural (cluster TYC0FH12XXXXRA) | Chip na esteira; Tier 1/2/3 não indexam; lote '2B' |
| 2026-06-26 (sessão 4) | `chips/engine.py` + `estoque/views.py` | Fix TB capacity: `_CAP_RE` + `_extract_gib` + `_CAP_NUM_RE` + `_CAP_BYTES_RE` + labels UFS/eMMC | — | 5 UFS 1TB retornavam INDETERMINADO e label "UFS" vazio (§8.9) |
| 2026-06-26 (sessão 4) | ChipFamily THGAM | Adicionada a populate_toshiba.py (magra, brand=Kioxia) | kioxia.com e-MMC Brief 2023 (Tier 1) | Prefixo novo — não coberto por gramática THGBM |
| 2026-06-26 (sessão 4) | ChipFamily THGJF | Adicionada a populate_toshiba.py (magra, brand=Kioxia) | kioxia.com UFS Briefs 2022/2025 (Tier 1) | UFS 3.1/4.0/4.1 Kioxia — 18 PNs confirmados |
| 2026-06-26 (sessão 4) | ChipFamily THGAF | Adicionada a populate_toshiba.py (magra, brand=Kioxia) | kioxia.com UFS + Auto Briefs 2020/2022 (Tier 1) | UFS 2.1 consumer + automotive — 11 PNs confirmados |
| 2026-06-26 (sessão 4) | 18 PNs THGJF | Adicionados a fix_known_parts, confidence=confirmed | kioxia.com UFS Brief Rev.3.0 (2025) + Rev.2.0 (2022) | UFS 3.1/4.0/4.1 128GB–1TB |
| 2026-06-26 (sessão 4) | 11 PNs THGAF | Adicionados a fix_known_parts, confidence=confirmed | kioxia.com UFS Brief Rev.2.0 + Auto Brief Rev.2.0 | UFS 2.1 consumer (32/64GB) + automotive (16–256GB) |
| 2026-06-26 (sessão 4) | 6 PNs THGAM | Adicionados a fix_known_parts, confidence=confirmed | kioxia.com e-MMC Brief Rev.2.0 (2023) | eMMC 5.1 BiCS gen V (16–128GB) + gen S (64/128GB) |
| 2026-06-26 (sessão 4) | 4 PNs THGBMJG*BAB | Adicionados a fix_known_parts, confidence=confirmed | kioxia.com Auto Brief Rev.2.0 (2020) | eMMC 5.1 automotive AEC-Q100 Grade 2 (8–64GB) |

**Chips confirmados individualmente (fix_known_parts, seção Toshiba — completo):**

| PN | Tipo | Capacidade | Confidence | Melhor fonte |
|----|------|-----------|------------|-------------|
| THGBMBG7D2KBAIL | eMMC 5.0 | 16GB | confirmed | kioxia.com 2013 Tier 1 |
| THGBMBG8D4KBAIR | eMMC 5.0 | 32GB | confirmed | kioxia.com 2013 Tier 1 |
| THGBMFG6C1LBAIL | eMMC 5.0 | 8GB | confirmed | kioxia.com 2014 Tier 1 |
| THGBMFG7C1LBAIL | eMMC 5.0 | 16GB | confirmed | Mouser/Kioxia America Tier 1 + Octopart Tier 2 |
| THGBMFG7C2LBAIL | eMMC 5.0 | 16GB | confirmed | kioxia.com 2014 Tier 1 |
| THGBMFG8C2LBAIL | eMMC 5.0 | 32GB | confirmed | kioxia.com 2014 Tier 1 (âncora 8C2) |
| THGBMFG8C4LBAIR | eMMC 5.0 | 32GB | confirmed | kioxia.com 2014 Tier 1 |
| THGBMFG9C4LBAIR | eMMC 5.0 | 64GB | confirmed | kioxia.com 2014 Tier 1 (âncora 9C4) |
| THGBMFG9C8LBAIG | eMMC 5.0 | 64GB | confirmed | kioxia.com 2014 Tier 1 |
| THGBMFT0CBLBAIS | eMMC 5.0 | 128GB | confirmed | kioxia.com 2014 Tier 1 (âncora 0CB) |
| THGBMHG6C1LBAU6 | eMMC 5.1 industrial | 8GB | confirmed | kioxia.com 2017 Tier 1 |
| THGBMHG7C2LBAU7 | eMMC 5.1 industrial | 16GB | confirmed | kioxia.com 2017 Tier 1 |
| THGBMHG8C4LBAIR | eMMC 5.1 | 32GB | confirmed | Octopart Tier 2 |
| THGBMHG8C4LBAU7 | eMMC 5.1 industrial | 32GB | confirmed | kioxia.com 2017 Tier 1 |
| THGBMHG9C8LBAU8 | eMMC 5.1 industrial | 64GB | confirmed | kioxia.com 2017 Tier 1 |
| THGBMNG5D1LBAIT | eMMC 5.0 | 4GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMTG5D1LBAIL | eMMC 5.0 | 4GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMUG6C1LBAIL | eMMC 5.1 consumer | 8GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMUG7C1LBAIL | eMMC 5.1 consumer | 16GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMUG8C2LBAIL | eMMC 5.1 consumer | 32GB | confirmed | Kioxia product brief 2023 Tier 1 (âncora 8C2) |
| THGBMJG6C1LBAU7 | eMMC 5.1 industrial | 8GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMJG7C2LBAU8 | eMMC 5.1 industrial | 16GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMJG8C4LBAU8 | eMMC 5.1 industrial | 32GB | confirmed | Kioxia product brief 2023 Tier 1 |
| THGBMJG9C8LBAU8 | eMMC 5.1 industrial | 64GB | confirmed | Kioxia product brief 2023 Tier 1 + Mouser Tier 2 |
| TYC0FH121638RA | eMCP LPDDR2 | 4GB NAND + 512MB RAM | distributor | Octopart Tier 2 |
| TYC0FH121626RA | eMCP LPDDR2 | 4GB NAND + 512MB RAM | distributor | Âncora TYC0FH121638RA |
| TYC0FH12162BRA | eMCP LPDDR2 | 4GB NAND + 512MB RAM | estimated | Inferência estrutural (lote '2B') |
| TY890A111229KC | SDR SDRAM | desconhecida | distributor | iFixit PS Vita Tear. Tier 2 |
| THGJFPT0E18BAIP | UFS 3.1 | 128GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFPT1E28BAIP | UFS 3.1 | 256GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFPT2E48BAIP | UFS 3.1 | 512GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFAT0T44BAIL | UFS 3.1 | 128GB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGJFAT1T84BAIR | UFS 3.1 | 256GB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGJFGT1E45BAIP | UFS 3.1 | 256GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFAT2T84BAIR | UFS 3.1 | 512GB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGJFGT2T85BAIU | UFS 3.1 | 512GB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGJFHT3TB4BAIG | UFS 3.1 | 1TB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGJFMT1E45BATV | UFS 4.0 | 256GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFMT2E46BATV | UFS 4.0 | 512GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFMT3E86BATZ | UFS 4.0 | 1TB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFJT0E25BAIP | UFS 4.0 | 128GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFJT1E45BATP | UFS 4.0 | 256GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFJT2T85BAT0 | UFS 4.0 | 512GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFRT1E45BATV | UFS 4.1 | 256GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFRT2E48BATV | UFS 4.1 | 512GB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGJFRT3E88BATW | UFS 4.1 | 1TB | confirmed | UFS Brief Rev.3.0 (2025) Tier 1 |
| THGAF8G8T23BAIL | UFS 2.1 | 32GB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGAF8G9T43BAIR | UFS 2.1 | 64GB | confirmed | UFS Brief Rev.2.0 (2022) Tier 1 |
| THGAF9G7L1LBAB7 | UFS 2.1 | 16GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFBG8T13BAB7 | UFS 2.1 | 32GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFEG8T13BAB7 | UFS 2.1 | 32GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFBG9T23BAB8 | UFS 2.1 | 64GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFEG9T23BAB8 | UFS 2.1 | 64GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFBT0T43BAB8 | UFS 2.1 | 128GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFET0T43BAB8 | UFS 2.1 | 128GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFBT1T83BAB5 | UFS 2.1 | 256GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAFET1T83BAB5 | UFS 2.1 | 256GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGAMVG7T13BAIL | eMMC 5.1 BiCS | 16GB | confirmed | e-MMC Brief Rev.2.0 (2023) Tier 1 |
| THGAMVG8T13BAIL | eMMC 5.1 BiCS | 32GB | confirmed | e-MMC Brief Rev.2.0 (2023) Tier 1 |
| THGAMVG9T23BAIL | eMMC 5.1 BiCS | 64GB | confirmed | e-MMC Brief Rev.2.0 (2023) Tier 1 |
| THGAMVT0T43BAIR | eMMC 5.1 BiCS | 128GB | confirmed | e-MMC Brief Rev.2.0 (2023) Tier 1 |
| THGAMSG9T24BAIL | eMMC 5.1 BiCS | 64GB | confirmed | e-MMC Brief Rev.2.0 (2023) Tier 1 |
| THGAMST0T24BAIL | eMMC 5.1 BiCS | 128GB | confirmed | e-MMC Brief Rev.2.0 (2023) Tier 1 |
| THGBMJG6C1LBAB7 | eMMC 5.1 auto | 8GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGBMJG7C2LBAB8 | eMMC 5.1 auto | 16GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGBMJG8C4LBAB8 | eMMC 5.1 auto | 32GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
| THGBMJG9C8LBAB8 | eMMC 5.1 auto | 64GB | confirmed | Auto Brief Rev.2.0 (2020) Tier 1 |
