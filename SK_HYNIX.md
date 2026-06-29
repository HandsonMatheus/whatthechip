# SK_HYNIX.md — Bíblia Técnica e de Negócio
**WhatTheChip — documento vivo de referência**
Criado: 2026-06-19 | Atualizado: 2026-06-29
> Leia antes de tocar em qualquer arquivo relacionado à SK Hynix.
> Em conflito com qualquer outro doc, o **código é a fonte da verdade**
> (`chips/engine.py`, `populate_hynix.py`).
> Atualize este arquivo quando aprender algo duradouro.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro e limites de escopo

### 0.1 Arquivos que PODE editar (escopo SK Hynix)

```
chips/management/commands/populate_hynix.py     ← gramática mestre: ChipFamilies + DecodeMaps
chips/management/commands/fix_known_parts.py    ← somente entradas brand_name="SK Hynix"
add_confirmed_part.py                           ← PNs confirmados individualmente (seção SK Hynix)
```

### 0.2 Arquivos que NÃO PODE tocar sem revisão explícita do usuário

```
chips/engine.py                                    ← motor global — mudança afeta TODAS as marcas
estoque/views.py                                   ← gateway global — mudança afeta TODAS as marcas
chips/management/commands/populate_samsung.py
chips/management/commands/populate_micron_mcp.py
chips/management/commands/populate_kingston.py
chips/management/commands/populate_rayson.py
chips/management/commands/populate_toshiba.py
chips/management/commands/add_chip_families.py     ← compartilhado — editar só para famílias SK Hynix
chips/management/commands/fix_known_parts.py       ← seções de OUTRAS marcas (Samsung, Micron…)
```

> Se precisar de mudança em `engine.py` ou `estoque/views.py`, **proponha ao usuário**
> com justificativa e impacto — nunca edite silenciosamente.

### 0.3 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca execute `populate_*`,
   `fix_known_parts`, `migrate`, `add_confirmed_part` sem confirmação explícita do usuário.

2. **`--dry-run` antes de qualquer comando que escreve no banco.** Sempre.

3. **Reiniciar o servidor após `populate_hynix --overwrite`.** O `lru_cache` do engine
   não invalida automaticamente no processo do servidor web.

4. **`chip_type="RAM"` para todos os chips DDR/GDDR discretos** (HY5DU, HY5PS, H5PS,
   H5TQ, H5TC, H5AN, H5A, H5C, H5RS…). Nunca `"DDR3"`, `"DDR"`, `"GDDR3"` no `chip_type`.
   O gateway quebra se `chip_type` não for `"RAM"` para esses chips.

5. **`subtype` = SOMENTE a geração — sem mais nada. Isso vale para `ChipFamily.subtype`
   (em `populate_hynix.py`) E para `KnownPart.subtype` (em `fix_known_parts.py` /
   `add_confirmed_part.py`).** `"DDR3"` ✓ — `"DDR3 SDRAM"`, `"LPDDR4X standalone"`,
   `"GDDR3 Graphics"` ✗. Motivo: `_result_from_family` (engine linha ~402) copia
   `ChipFamily.subtype` diretamente ao resultado quando a gramática vence. Um subtype
   verboso vaza para o label da caixa física e trunca o display na esteira.
   `populate_hynix.py` ainda tem subtypes verbosos que precisam ser corrigidos (ver §8.11).

6. **`interface=""` (vazio) para LPDDR standalone e eMCP/uMCP.** Nunca colocar a
   geração de RAM no campo `interface`. `interface="LPDDR4"` é sempre ERRADO para
   esses tipos. Para DDR/GDDR discretos, `interface` = tipo de bus: `"DDR3"`, `"DDR4"`.

7. **`emcp_ram` = tipo ANTES da capacidade.** `"LPDDR3 1GB"` ✓ — nunca `"1GB LPDDR3"`.
   O campo `emcp_nand` é só GB: `"16GB"`, sem prefixo de tipo.

8. **Nunca inverta `val_primary`/`val_secondary` nos DecodeMaps.** Para mapas de
   capacidade: `val_primary` = valor legível (`"16GB"`, `"4GB"`). Para mapas de RAM
   (H9TQ_RAM_CAP, H9TP_RAM_CAP etc.): `val_primary` = string completa `"LPDDR3 2GB"`.
   Siga EXATAMENTE o padrão das linhas já existentes no mapa — nunca assuma sem verificar.

9. **Nunca escreva "por die" no `val_secondary`.** O engine já acrescenta " por die"
   automaticamente. Se vier no mapa, duplica: "por die por die".

10. **`decode_density_type` e `decode_cap_map` são mutuamente exclusivos.** Nunca
    configure os dois na mesma família — produz dados conflitantes no engine.

11. **Não confie em dados de distribuidor ou IA sem verificação.** Jotrin, WinSource,
    catálogos de Shenzhen e IAs confundem Gb/GB, invertem primary/secondary e alucinam
    capacidades. Sempre cruzar com `product.skhynix.com`, Alldatasheet ou Octopart.

12. **⚠️ Ouro = IDENTIDADE, não as specs derivadas. Atestar SEMPRE em tier-1.**
    Lição transferida da Micron (ver `MICRON.md §5` e `CLAUDE.md §7`): num registro
    `confidence="confirmed"`, o que está verificado é a **identidade** (o PN existe / o
    laser-marking ⇄ PN é real). `capacity`, `subtype`, `dram_density` e geração são
    **derivados** — de DecodeMap, de catálogo de distribuidor ou de inferência por prefixo
    — e **podem estar errados mesmo num registro confirmado**. Antes de popular ou confiar
    numa spec, atestar em fonte tier-1 (datasheet SK Hynix / `product.skhynix.com` / DigiKey).
    **A gramática não é deus; a fonte tier-1 é.** Dois modos clássicos de falha que isso evita:
    - **Geração por prefixo sem atestar** — assumir "prefixo X = LPDDR4" sem datasheet.
      Foi exatamente o erro `MT52L = LPDDR4` na Micron (era LPDDR3, tier-1 pegou). Aqui:
      H9DA é LPDDR1 e não LPDDR3 apesar do "H9D"; H5TQ=DDR3 1.5V vs H5TC=DDR3L 1.35V (§3.1).
    - **Sufixo de dies/pacote interpretado como multiplicador de capacidade** — na SK Hynix
      o decode é 100% por **DecodeMap** (tabela posicional curada), então o bug de dies da
      Micron (`×N`) é estruturalmente impossível; mesmo assim, confira a chave do mapa contra
      o datasheet ao adicionar uma nova capacidade, nunca extrapole por padrão numérico.

### 0.4 Hierarquia de fontes (imutável)

```
1. SK Hynix Product site: product.skhynix.com / Glochip LPDDR page
   → busca por PN → confirma specs (família, capacidade, geração de RAM)
2. Datasheet SK Hynix oficial: dl.skhynix.com
   → fonte definitiva para specs de timing, tensão, package, pinout
3. Alldatasheet / LCSC com rastreabilidade SK Hynix
   → frequentemente corretos; cruzar com site oficial para novos chips
4. Octopart com fonte rastreável (SK Hynix ou distribuidor autorizado)
   → checar se a "fonte" não é outro distribuidor sem datasheet
5. Distribuidor B2B rastreável (Preduo, OMO Electric, parceiros confirmados)
   → só como apoio; nunca rebaixa um "confirmed" com dado de distribuidor
6. iFixit Teardowns / GSMArena
   → chip_type confirmado por inspeção física real em dispositivo conhecido
7. IA externa (qualquer LLM)
   → ÚLTIMO RECURSO — nunca fonte primária; verificar SEMPRE antes de usar
```

Nunca usar como fonte primária: fóruns de reparo asiáticos (GSMForum), WinSource sem
rastreabilidade, catálogos genéricos de Shenzhen, eBay listings, output de IA sem verificação.

---

## 1. Visão Geral

SK Hynix é o **segundo maior fabricante global de DRAM** (depois da Samsung) e um dos
principais fornecedores de NAND Flash. Na bancada de reciclagem da eMiner, é a segunda marca
mais frequente depois da Samsung, com forte presença em LPDDR mobile e DDR PC.

| Categoria | Famílias mapeadas | Decode completo | Decode parcial | Gaps |
|---|---|---|---|---|
| DRAM DDR1 | 1 (HY5DU) | 1 | 0 | 0 |
| DRAM DDR2 | 2 (HY5PS, H5PS) | 2 | 0 | 0 |
| DRAM DDR3 1.5V | 1 (H5TQ) | 1 | 0 | 0 |
| DRAM DDR3L 1.35V | 1 (H5TC) | 1 | 0 | 0 |
| DRAM DDR4 Era 1 | 1 (H5AN) | 1 | 0 | 0 |
| DRAM DDR4 Era 2 | 1 (H5A) | 1 | 0 | 0 |
| DRAM DDR5 | 1 (H5C) | 1 | 0 | 1 (G6=64Gbit) |
| GDDR3 Gráfica | 1 (H5RS) | 0 | 0 | sem decode cap |
| LPDDR1 | 2 (H5MS, HY5MS) | 1 (H5MS) | 1 (HY5MS) | — |
| LPDDR2 standalone | 1 (H9TK) | 1 | 0 | 0 |
| LPDDR3 standalone | 2 (H9CC, H9CK) | 2 | 0 | 0 |
| LPDDR4/4X standalone | 3 (H9HC, H9HK, H9HCN) | 3 | 0 | 0 |
| LPDDR4X Era 2 | 1 (H54G) | 1 | 0 | 0 |
| LPDDR5/5X standalone | 2 (H9JK, H58G) | 2 | 0 | 1 (24GB) |
| eMMC standalone | 3 (H26M, H26T, H28M) | 2 | 1 (H28M) | — |
| UFS legado | 2 (H28U, H28S) | 2 | 0 | 0 |
| UFS atual (4D NAND) | 2 (HN8T, HN8G) | 2 | 0 | 0 |
| eMCP LPDDR1 | 1 (H9DA) | 1 | 0 | 0 |
| eMCP LPDDR3 | 1 (H9TQ) | 1 | 0 | 0 |
| eMCP LPDDR2 | 2 (H9TP, H9DP) | 2 | 0 | 0 |
| eMCP LPDDR4X | 1 (H9HP) | 1 | 0 | 0 |
| uMCP LPDDR4X | 1 (H9HQ) | 1 | 0 | 0 |
| uMCP LPDDR5 | 2 (H9HR, H9RT) | 2 | 0 | 0 |
| **TOTAL** | **34** | **31** | **2** | **~3** |

**Arquivos que definem as famílias:**
- `chips/management/commands/populate_hynix.py` — gabarito mestre (ChipFamilies + DecodeMaps)
- `chips/management/commands/fix_known_parts.py` — correções pontuais (seção SK Hynix)
- `add_confirmed_part.py` — PNs confirmados individualmente (seção SK Hynix)

---

## 2. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

### 2.1 Tabela canônica por tipo de chip

| Tipo de chip | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1 | `"RAM"` | `"DDR1"` | `"x8"` / `"x16"` / `"x4"` | `dram_density` (Gb por die) |
| DDR2 | `"RAM"` | `"DDR2"` | `"x8"` / `"x16"` | `dram_density` |
| DDR3 | `"RAM"` | `"DDR3"` | `"x8"` / `"x16"` / `"x4"` | `dram_density` |
| DDR3L | `"RAM"` | `"DDR3L"` | `"x8"` / `"x16"` | `dram_density` |
| DDR4 | `"RAM"` | `"DDR4"` | `"x8"` / `"x16"` / `"x4"` | `dram_density` |
| DDR5 | `"RAM"` | `"DDR5"` | `"x8"` / `"x16"` | `dram_density` |
| GDDR3 | `"RAM"` | `"GDDR3"` | `"x16"` | `dram_density` |
| LPDDR1 | `"LPDDR1"` | `"LPDDR1"` | `""` (vazio) | `capacity` (bytes, pacote) |
| LPDDR2 | `"LPDDR2"` | `"LPDDR2"` | `""` | `capacity` |
| LPDDR3 | `"LPDDR3"` | `"LPDDR3"` | `""` | `capacity` |
| LPDDR4 | `"LPDDR4"` | `"LPDDR4"` | `""` | `capacity` |
| LPDDR4X | `"LPDDR4X"` | `"LPDDR4X"` | `""` | `capacity` |
| LPDDR5 | `"LPDDR5"` | `"LPDDR5"` | `""` | `capacity` |
| LPDDR5X | `"LPDDR5X"` | `"LPDDR5X"` | `""` | `capacity` |
| eMMC | `"eMMC"` | `""` | `"eMMC"` (ou versão) | `capacity` (GB) |
| UFS | `"UFS"` | `""` | `"UFS 2.1"` / `"UFS 3.1"` | `capacity` (GB) |
| eMCP | `"eMCP"` | geração RAM (`"LPDDR3"`) | `""` | `emcp_nand` + `emcp_ram` |
| uMCP | `"uMCP"` | geração RAM (`"LPDDR5"`) | `""` | `emcp_nand` + `emcp_ram` |

### 2.2 Regras absolutas do `subtype`

- `subtype` = **SOMENTE a geração ou variante** (1–3 palavras)
- **NUNCA** colocar no `subtype`: densidade (`"4Gb"`), bus width (`"x8"`), tensão (`"1.35V"`),
  qualificadores como `"standalone"`, `"SDRAM"`, `"Mobile"`, `"PC"`, `"Graphics"`.
- **Atenção ao populate_hynix.py:** os campos de `ChipFamily.subtype` usam valores como
  `"DDR3 SDRAM"`, `"LPDDR3 standalone"` — isso é para a gramática/família.
  Os `KnownPart.subtype` (em fix_known_parts e add_confirmed_part) **devem** usar só a geração.

> **Label protegido por `canonical_gen` (2026-06-19) — FONTE ÚNICA da convenção.**
> O label da caixa é montado em `estoque/views.py::_compute_destination`, que passa o
> `subtype` por `chips/conventions.py::canonical_gen()`. Ela reduz qualquer subtype ao
> token canônico por **whitelist** (`"LPDDR4 Mobile"`→`"LPDDR4"`, `"DDR3 SDRAM"`→`"DDR3"`,
> `"SLC NAND paralela industrial"`→`"SLC NAND"`). **Consequência:** subtype verboso **não
> trunca mais a etiqueta** — para todas as marcas, banco e gramática, retroativamente.
>
> **Mas continue escrevendo `subtype` limpo (só a geração) ao popular PNs:** a normalização
> é aplicada só no label; o card de busca ainda mostra o subtype cru; e a função é fail-open
> (token não reconhecido passa intacto). A regra "subtype = só a geração" segue valendo no
> write-time.
>
> **SK Hynix:** os `ChipFamily.subtype` verbosos ainda em `populate_hynix.py`
> (`"DDR3 SDRAM"`, `"LPDDR3 standalone"` — §8.11), que chegam ao label pela **gramática**
> (`_result_from_family` copia `fam.subtype` literalmente), agora são normalizados no
> consumo — **não truncam mais a etiqueta**. Limpar §8.11 deixou de ser crítico para o
> label; segue valendo como higiene para o card de busca.

### 2.3 Campo `interface` — regras SK Hynix

- **DDR/GDDR:** **bus width** do chip — `"x8"`, `"x16"`, `"x4"`. Lido do PN pelo operador
  (H5TQ4G**6**3 → pn[6]=6 → x16; H5TQ4G**8**3 → pn[6]=8 → x8; H5TQ4G**4**3 → pn[6]=4 → x4).
  **Nunca** colocar a geração aqui — `"DDR3"` no campo `interface` é dado duplicado/errado
  (subtype já carrega a geração). O gateway ignora `interface` para montar o label DDR — mas
  ter dado errado aqui confunde auditoria futura.
- **LPDDR standalone, eMCP, uMCP:** `""` (string vazia). **Nunca** colocar geração aqui.
  (Corrigido em 11 famílias `populate_hynix.py` em 2026-06-19.)
- **eMMC:** `"eMMC"` genérico ou versão se conhecida.
- **UFS:** `"UFS 2.1"`, `"UFS 3.1"` etc.

### 2.4 Gateway de estoque — como o label é montado

```
RAM (DDR/GDDR):
  subtype="DDR3" + dram_density=2Gb → label "DDR3+2G"

LPDDR standalone:
  chip_type="LPDDR4X" + capacity="4GB" → label "LPDDR4X+4G"

eMCP/uMCP:
  emcp_nand="64GB" + emcp_ram (GB) → label "EMCP64+4" / "UMCP64+4"

eMMC: capacity="64GB" → label "EMMC64GB"
UFS:  capacity="128GB" → label "UFS128GB"
```

### 2.5 Campos `emcp_nand` e `emcp_ram`

- `emcp_nand` = capacidade NAND em GB: `"8GB"`, `"64GB"`
- `emcp_ram` = **tipo ANTES da capacidade**: `"LPDDR3 2GB"`, `"LPDDR5 8GB"` — **nunca** `"2GB LPDDR3"`
- Esses campos são preenchidos pelo engine via DecodeMaps; em KnownPart manual, seguir o mesmo padrão.

### 2.6 Tabela completa de campos — O que vai / O que NÃO vai

| Campo | O que vai | O que NÃO vai |
|-------|-----------|---------------|
| `chip_type` | `"RAM"` (DDR/GDDR) · `"eMMC"`, `"UFS"`, `"eMCP"`, `"uMCP"` · `"LPDDR4X"` etc. (LPDDR standalone) | specs, densidades, tensão, `"DDR3"`, `"DDR"`, `"NAND"` |
| `subtype` | **só a geração**: `"DDR3"`, `"DDR3L"`, `"LPDDR4X"`, `"DDR5"`, `"GDDR3"` | densidade (`"8Gb"`), barramento (`"x16"`), tensão (`"1.35V"`), qualificadores (`"Mobile"`, `"standalone"`, `"SDRAM"`, `"Graphics"`, `"PC DRAM"`) |
| `interface` | bus tipo para DDR/GDDR: `"DDR3"`, `"DDR4"` · versão para eMMC/UFS: `"eMMC"`, `"UFS 3.1"` | a geração de RAM (`"LPDDR4"`) — nunca repetir aqui · `""` vazio para LPDDR/eMCP/uMCP |
| `capacity` | capacidade total do **pacote** em bytes: `"512MB"`, `"4GB"`, `"128GB"` | gigabits · capacity de eMCP/uMCP (usar `emcp_nand`/`emcp_ram`) |
| `dram_density` | densidade do **die** para DDR/GDDR: `"4Gb"`, `"8Gb"` | bytes · capacidade de pacote · LPDDR |
| `emcp_nand` | (só eMCP/uMCP) NAND em GB: `"8GB"`, `"128GB"` | tipo de interface · RAM |
| `emcp_ram` | (só eMCP/uMCP) **tipo + capacidade**: `"LPDDR3 768MB"`, `"LPDDR5 8GB"` — tipo VEM ANTES | só o número (`"768MB"`) · ordem invertida (`"768MB LPDDR3"`) |
| `tip` | tudo que não couber: tensão, bus width, organização, avisos, notas de compatibilidade | — |

---

## 3. Anatomia do PN por Família

### 3.1 DDR PC/Desktop/Servidor (H5AN, H5A, H5C, H5TQ, H5TC, H5PS, HY5PS, HY5DU)

#### DDR1 — HY5DU (Hynix, 2.5V)
```
H  Y  5  D  U  [cap_hi][cap_lo] [org] ...
0  1  2  3  4      5        6     7+
```
`pn[5:7]` → HYX_DDR1_CAP: `64`=8MB · `28`=16MB · `56`=32MB · `12`=64MB

#### DDR2 era transição — HY5PS (Hynix, 1.8V)
```
H  Y  5  P  S  [cap_hi][cap_lo] ...
0  1  2  3  4      5        6
```
`pn[5:7]` → HYX_DDR2_HY5PS_CAP: `56`=32MB · `12`=64MB · `1G`=128MB

#### DDR2 nova nomenclatura — H5PS (SK Hynix, 1.8V)
```
H  5  P  S  [cap_hi][cap_lo] ...
0  1  2  3      4        5
```
`pn[4:6]` → HYX_DDR2_H5PS_CAP: `25`=32MB · `51`=64MB · `1G`=128MB · `2G`=256MB

#### DDR3 1.5V — H5TQ
```
H  5  T  Q  [cap_hi][cap_lo] [org] [gen] ...
0  1  2  3      4        5     6     7
```
`pn[4:6]` → HYX_DDR3_CAP: `51`=64MB · `1G`=128MB · `2G`=256MB · `4G`=512MB · `8G`=1GB

`pn[6]` = organização (bus width): `4`=x4 · `6`=x16 · `8`=x8
`pn[7]` = geração de revisão (A, B, C, D, E, M, T…)
Sufixo velocidade: `G7`=DDR3-1066 · `H9`=DDR3-1333 · `PB`=DDR3-1600 · `RD`=DDR3-1866 · `TE`=DDR3-2133

#### DDR3L 1.35V — H5TC
Decode idêntico ao H5TQ. Sufixo termina em `A` (DDR3L) em vez de `C` (DDR3):
`-PBA`=DDR3L-1600 · `-H9A`=DDR3L-1333 · sufixo `MR` = DDP (dois dies empilhados).

#### DDR4 Era 1 pré-2020 — H5AN (1.2V)
```
H  5  A  N  [cap_hi][cap_lo] [org] ...
0  1  2  3      4        5     6
```
`pn[4:6]` → HYX_DDR4_CAP: `4G`=512MB · `8G`=1GB · `AG`=2GB
`pn[6]` = organização: `4`=x4 · `6`=x16 · `8`=x8
Sufixos velocidade: `UH`=DDR4-2400 · `VK`=DDR4-2666 · `WM`=DDR4-2933 · `XN`=DDR4-3200

#### DDR4 Era 2 pós-2020 — H5A (1.2V)
```
H  5  A  [cap_hi][cap_lo] ...
0  1  2      3        4
```
`pn[3:5]` → HYX_DDR4_H5A_CAP: `G3`=1GB · `G4`=2GB · `G5`=4GB · `G6`=8GB
⚠ Prefixo H5A começa com H5AN → priority H5AN=50, H5A=55 (H5AN tem precedência).

#### DDR5 — H5C
```
H  5  C  [cap_hi][cap_lo] ...
0  1  2      3        4
```
`pn[3:5]` → HYX_DDR5_CAP: `G4`=2GB · `GD`=3GB (24Gbit, assimétrico) · `G5`=4GB

### 3.2 GDDR3 — H5RS
Sem decode de capacidade. Prefixo registrado só para routing — aciona alerta no operador.

### 3.3 LPDDR1 — H5MS / HY5MS (Mobile DDR, 1.8V)

**H5MS:**
```
H  5  M  S  [cap_hi][cap_lo] ...
0  1  2  3      4        5
```
`pn[4:6]` → HYX_LPDDR1_H5MS_CAP: `25`=32MB · `51`=64MB · `1G`=128MB · `2G`=256MB

**HY5MS:**
```
H  Y  5  M  S  [cap_hi][cap_lo] ...
0  1  2  3  4      5        6
```
`pn[5:7]` → HYX_LPDDR1_HY5MS_CAP: `7B`=64MB (único PN confirmado)

### 3.4 LPDDR2 standalone — H9TK (Mobile DRAM puro)
```
H  9  T  K  [N/M][N/M][N/M]  [cap] ...
0  1  2  3     4    5    6      7
```
`pn[7]` → HYX_LPDDR2_CAP: `1`=128MB · `2`=256MB · `4`=512MB · `8`=1GB · `A/B`=2GB

⚠ Preenchimento `pn[4:7]` pode ser `NNN` **ou** `MMM` — ambos válidos.

### 3.5 LPDDR3 standalone — H9CC (x32) / H9CK (x64)
```
H  9  C  [C|K]  [N/M][N/M][N/M]  [cap] ...
0  1  2    3      4    5    6       7
```
`pn[7]` → HYX_LPDDR3_CAP: `4`=512MB · `8`=1GB · `B`=2GB · `D`=3GB · `C`=4GB · `E`=6GB · `F`=8GB

⚠ H9CC = x32 barramento · H9CK = x64 (dual-channel).

### 3.6 LPDDR4/4X standalone Era 1 — H9HC (x32) / H9HK (x64) / H9HCN
```
H  9  H  [C|K|C]  [N/M][N/M][N/M]  [cap] ...
0  1  2     3        4    5    6       7
```
`pn[7]` → HYX_LPDDR4_H9HC_CAP: `4`=512MB · `8`=1GB · `B`=2GB · `D`=3GB · `C`=4GB · `E`=6GB · `F`=8GB

H9HCN = sub-prefixo (5 chars, priority=40) onde `pn[4]='N'` = RAM pura (zero NAND).
⚠ O `'C'` em `H9HCN` (pn[3]) atesta barramento LPDDR4X (VDDQ 0.6V) — **não é capacidade**.

### 3.7 LPDDR4X standalone Era 2 — H54G
```
H  5  4  G  [cap] [org] ...
0  1  2  3    4     5
```
`pn[4]` → HYX_LPDDR4X_H54G_CAP — dois sistemas coexistem:
- Numérico: `2`=512MB · `3`=1GB · `4`=2GB · `5`=4GB · `6`=8GB
- Alfabético: `A`=2GB · `C`=3GB · `E`=4GB · `G`=6GB · `J`=8GB
`pn[5]` = organização de banco (6 ou 8) — **não é capacidade**

### 3.8 LPDDR5/5X standalone Era 1 — H9JK
```
H  9  J  K  [N][N][N]  [cap] ...
0  1  2  3   4  5  6     7
```
`pn[7]` → HYX_LPDDR5_H9JK_CAP: `F`=8GB · `H`=12GB

### 3.9 LPDDR5/5X standalone Era 2 — H58G
```
H  5  8  G  [cap] [org] ...
0  1  2  3    4     5
```
`pn[4]` → HYX_LPDDR5_H58G_CAP:
- Numérico: `5`=4GB · `6`=8GB · `7`=16GB
- Alfabético: `D`=3GB · `E`=6GB · `G`=12GB · `U`=18GB
`pn[5]` = organização (6, 7, 8) — **não é capacidade**

### 3.10 eMMC — H26M / H26T / H28M
```
H  2  6  [M|T]  [cap] [org] ...
0  1  2    3      4     5
```
`pn[4]` → HYX_EMMC_CAP: `3`=4GB · `4`=8GB · `5`=16GB · `6`=32GB · `7`=64GB · `8`=128GB
`pn[5]` = organização interna (1=SDP, 2=DDP, 4=QDP, 7=ODP) — **não é capacidade**

⚠ `H26M64...` = 32GB (não 64GB). O `'6'` é o código de capacidade; o `'4'` é organização.

### 3.11 UFS legado — H28U / H28S
```
H  2  8  [U|S]  [cap] ...
0  1  2    3      4
```
H28U `pn[4]` → HYX_H28U_CAP: `6`=32GB · `7`=64GB · `8`=128GB
H28S `pn[4]` → HYX_H28S_CAP: `8`=128GB · `9`=256GB

### 3.12 UFS atual 4D NAND — HN8T / HN8G
```
H  N  8  [T|G]  [cap_hi][cap_lo] ...
0  1  2    3        4        5
```
`pn[4:6]` → HYX_HN8_CAP: `96`=64GB · `03/05/06`=128GB · `15/16`=256GB · `25`=512GB · `35`=1TB

### 3.13 eMCP — H9TQ (LPDDR3) / H9TP (LPDDR2) / H9DP (LPDDR2)
```
H  9  T  [Q|P|/]  [nand_hi][nand_lo]  [ram_hi][ram_lo] ...
0  1  2     3          4         5         6        7
```
H9TQ `pn[4:6]` → HYX_EMCP_NAND_CAP · `pn[6:8]` → HYX_H9TQ_RAM_CAP
H9TP `pn[4:6]` → HYX_EMCP_NAND_CAP · `pn[6:8]` → HYX_H9TP_RAM_CAP
H9DP `pn[4:6]` → HYX_H9D_NAND_CAP  · `pn[7]` (1 char) → HYX_H9D_RAM_CAP

⚠ H9DP: `pn[6]='A'` é código de controlador fixo — invisível para o decode de RAM.

### 3.13b eMCP — H9DA (LPDDR1 legado, ~2012-2015) — DECODE DIFERENTE
```
H  9  D  A  [nand]  G   H  [ram_hi][ram_lo]  [pkg]  [gen]  [tmp]
0  1  2  3    4     5   6      7        8       9      10     11
```
H9DA `pn[4]` (1 char) → HYX_H9DA_NAND_CAP · `pn[7:9]` (2 chars) → HYX_H9DA_RAM_CAP

⚠ `pn[5:7]='GH'` é **filler fixo** — NÃO faz parte do decode de capacidade.
⚠ H9DA usa esquema **completamente diferente** de H9TQ/H9TP/H9DP: NAND em 1 char (pn[4]), RAM em pn[7:9].
⚠ Sufixo `-4EM` = eMMC 4.x (protocolo legado). `pn[10]` = die gen (A=2ª · B=3ª · C=4ª).
⚠ **RAM é LPDDR1** (NÃO LPDDR3): H9DA = 137-ball/153-ball eMMC+LPDDR1 (Preduo tier-1 ✓).
  H9TP = LPDDR2 (162-ball); H9TQ = LPDDR3 (221-ball). Prefixo define geração.
⚠ Notação Preduo "X+Y": Y em **Gb** (Gigabits): "4+4" = 4GB NAND + 4Gb (512MB) LPDDR1.
⚠ `4J` (H9DA4GH4JJAM) confirmado via Preduo H9DA4VH4JJMMCR-4EM "4+4" → `4J`=4Gb=512MB LPDDR1.

### 3.14 eMCP LPDDR4X — H9HP / uMCP LPDDR4X — H9HQ
```
H  9  H  [P|Q]  [nand_hi][nand_lo]  [ram_hi][ram_lo] ...
0  1  2    3         4         5         6        7
```
H9HP `pn[4:6]` → HYX_H9HP_NAND_CAP · `pn[6:8]` → HYX_LPDDR4X_RAM_CAP
H9HQ `pn[4:6]` → HYX_H9HQ_NAND_CAP · `pn[6:8]` → HYX_LPDDR4X_RAM_CAP

### 3.15 uMCP LPDDR5 — H9HR / H9RT
H9HR `pn[4:6]` → HYX_H9HR_NAND_CAP · `pn[6:8]` → HYX_H9HR_RAM_CAP
H9RT `pn[4:6]` → HYX_H9RT_NAND_CAP · `pn[6:8]` → HYX_H9RT_RAM_CAP (decode diferente)

---

## 4. DecodeMaps — Inventário Completo

### 4.1 HYX_DDR1_CAP — pn[5:7], 2 chars (HY5DU)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `64` | 8MB | 64Mb | HY5DU64322AQ-5 ✓ | ✅ |
| `28` | 16MB | 128Mb | HY5DU281622ET-J ✓ | ✅ |
| `56` | 32MB | 256Mb | HY5DU561622ETP-4 ✓ | ✅ |
| `12` | 64MB | 512Mb | HY5DU121622DTP-J ✓ | ✅ |

Bloqueado: 1Gb (128MB) — nenhum PN rastreável nesta nomenclatura. **Status: ✅ COMPLETO p/ linha HY5DU.**

### 4.2 HYX_DDR2_HY5PS_CAP — pn[5:7], 2 chars (HY5PS)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `56` | 32MB | 256Mb | HY5PS561621BFP-2L ✓ | ✅ |
| `12` | 64MB | 512Mb | HY5PS121621C-FP-Y5 ✓ | ✅ |
| `1G` | 128MB | 1Gb | HY5PS1G1631CFP-S6 ✓ | ✅ |

Bloqueado: 2Gb — transição para H5PS ocorreu antes. **Status: ✅ COMPLETO p/ linha HY5PS.**

### 4.3 HYX_DDR2_H5PS_CAP — pn[4:6], 2 chars (H5PS)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `25` | 32MB | 256Mb | H5PS2562GFR ✓ | ✅ |
| `51` | 64MB | 512Mb | H5PS5142FFP-E3L ✓ | ✅ |
| `1G` | 128MB | 1Gb | H5PS1G83EFR-S6C ✓ | ✅ |
| `2G` | 256MB | 2Gb | H5PS2G83AFR ✓ | ✅ |

Bloqueado: `4G`=512MB — SK Hynix não escalou em standalone H5PS. **Status: ✅ COMPLETO.**

### 4.4 HYX_DDR3_CAP — pn[4:6], 2 chars (H5TQ e H5TC compartilham)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `51` | 64MB | 512Mb | H5TQ5163DFR-PBC ✓ | ✅ |
| `1G` | 128MB | 1Gb | H5TQ1G83EFR-H9C ✓ | ✅ |
| `2G` | 256MB | 2Gb | H5TQ2G83AFR-H9C ✓ | ✅ |
| `4G` | 512MB | 4Gb | H5TQ4G63AFR-PBC ✓ | ✅ |
| `8G` | 1GB | 8Gb | H5TC8G63AMR-PBA ✓ | ✅ |

Teto físico DDR3: 8Gb (1GB) por chip. **Status: ✅ COMPLETO.**

### 4.5 HYX_DDR4_CAP — pn[4:6], 2 chars (H5AN, Era 1)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `4G` | 512MB | 4Gb | H5AN4G6NBJR-UHC ✓ | ✅ |
| `8G` | 1GB | 8Gb | H5AN8G8NAFR-UHC ✓ | ✅ |
| `AG` | 2GB | 16Gb | H5ANAG6NAMR-TFC ✓ | ✅ |

Bloqueado: `BG`=4GB/32Gb — pertence à Era 2 (H5A, chave `G5`). Teto Era 1: 16Gb. **Status: ✅ COMPLETO.**

### 4.6 HYX_DDR4_H5A_CAP — pn[3:5], 2 chars (H5A, Era 2)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `G3` | 1GB | 8Gb | H5AG3... ✓ | ✅ |
| `G4` | 2GB | 16Gb | ✓ (datasheets pós-2020) | ✅ |
| `G5` | 4GB | 32Gb | ✓ (monolítico real) | ✅ |
| `G6` | 8GB | 64Gb | ✓ (3DS TSV servidores) | ✅ |

**Status: ✅ COMPLETO.**

### 4.7 HYX_DDR5_CAP — pn[3:5], 2 chars (H5C)

| Chave | capacity (bytes) | dram_density (die) | Fonte | Status |
|-------|------------------|--------------------|-------|--------|
| `G4` | 2GB | 16Gb | H5CG48MEBD-X014N ✓ | ✅ |
| `GD` | 3GB | 24Gb (assimétrico) | H5CGD8MGBDX021N ✓ | ✅ |
| `G5` | 4GB | 32Gb | H5CG58MHBDX051N ✓ | ✅ |

Bloqueado: `G6`=8GB/64Gb — previsto no JEDEC, sem PN físico confirmado. **Status: ⚠️ PARCIAL (G6 pendente).**

### 4.8 HYX_LPDDR1_H5MS_CAP — pn[4:6], 2 chars (H5MS)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `25` | 32MB | H5MS2562JFR-J3M ✓ |
| `51` | 64MB | H5MS5122FFR-E3M ✓ |
| `1G` | 128MB | H5MS1G22AFR-J3M ✓ |
| `2G` | 256MB | H5MS2G62MFR-E3M ✓ |

### 4.9 HYX_LPDDR1_HY5MS_CAP — pn[5:7], 2 chars (HY5MS)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `7B` | 64MB | HY5MS7B2BLFP-H — Octopart ✓ |

Esquema completamente diferente do H5MS — **jamais compartilhar mapas**.

### 4.10 HYX_LPDDR2_CAP — pn[7], 1 char (H9TK)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `1` | 128MB | H9TKNNN1GDAPLR ✓ |
| `2` | 256MB | H9TKNNN2GDAPLR ✓ |
| `4` | 512MB | H9TKNNN4KDMPRR ✓ · H9TKMMM4GDARUR ✓ |
| `8` | 1GB | H9TKNNN8JDAPLR ✓ · H9TKMMM8KDHPQR ✓ |
| `A` | 2GB | H9TKNNNAADMP ✓ (OMO, HKin) |
| `B` | 2GB | H9TKNNNBPDAR-NGM ✓ (teto confirmado) |

Bloqueado: `C`=4GB — SK Hynix migrou para LPDDR3 antes. **Status: ✅ COMPLETO.**

### 4.11 HYX_LPDDR3_CAP — pn[7], 1 char (H9CC e H9CK compartilham)

| Chave | val_primary | Densidade | Fonte |
|-------|-------------|-----------|-------|
| `4` | 512MB | 4Gbit | H9CCNNN4GTMLAR ✓ |
| `8` | 1GB | 8Gbit | H9CCNNN8GTMLAR ✓ |
| `B` | 2GB | 16Gbit | H9CCNNNBJTMLAR ✓ |
| `D` | 3GB | 24Gbit | H9CKNNNDATMTDR ✓ (assimétrico — viabilizou 3GB nos smartphones) |
| `C` | 4GB | 32Gbit | H9CKNNNCPTMTLR ✓ |
| `E` | 6GB | 48Gbit | H9CKNNNECTMUPR-NUH Preduo WP01025 256ball ✓ (jun/2026) |
| `F` | 8GB | 64Gbit | H9CCNNNFAGMLLR-NUD Preduo WP01836 253ball ✓ (jun/2026) |

⚠ O comentário anterior "BLOQUEADO — limite físico/térmico em 32Gb" estava errado. Preduo tier-1 confirma pacotes multi-die 48Gbit (E=6GB) e 64Gbit (F=8GB) circulando no mercado de reciclagem. Padrão idêntico ao HYX_LPDDR4_H9HC_CAP, onde E=6GB e F=8GB já eram confirmados desde a escrita inicial. O esquema de capacidade é consistente ao longo das gerações H9CC/H9CK → H9HC/H9HK. **Status: ✅ COMPLETO.**

### 4.12 HYX_LPDDR4_H9HC_CAP — pn[7], 1 char (H9HC, H9HK, H9HCN compartilham)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `4` | 512MB | H9HCNNN4KMMLHR-NMO ✓ |
| `8` | 1GB | H9HCNNN8KUMLHR-NME ✓ |
| `B` | 2GB | H9HCNNNBPUMLHR-NMO ✓ |
| `D` | 3GB | H9HKNNNDGUMUBR-NLHR ✓ (24Gbit assimétrico) |
| `C` | 4GB | H9HCNNNCPMMLHR-NME ✓ · H9HKNNNCTUMUBR-MUH ✓ |
| `E` | 6GB | H9HCNNNECMML ✓ (⚠ ver §8.5 — possível divergência de família) |
| `F` | 8GB | H9HCNNNFBMMLPR-NME ✓ |

### 4.13 HYX_LPDDR4X_H54G_CAP — pn[4], 1 char (H54G)

| Chave | val_primary | Sistema | Fonte |
|-------|-------------|---------|-------|
| `2` | 512MB | numérico | H54G26AYRPX066 ✓ |
| `3` | 1GB | numérico | H54G36AYRPX246 ✓ |
| `4` | 2GB | numérico | H54G46BYYQX085 ✓ |
| `5` | 4GB | numérico | H54G56CYRB-X247 ✓ (TechInsights HP Spectre) |
| `6` | 8GB | numérico | H54G66AYZVX106 ✓ |
| `A` | 2GB | alfabético | die-revision do `4` |
| `C` | 3GB | alfabético | fracionado 24Gbit |
| `E` | 4GB | alfabético | H54GE6CYRB-X252 ✓ (Helio G80/G85) |
| `G` | 6GB | alfabético | fracionado 48Gbit |
| `J` | 8GB | alfabético | die-revision do `6` |

### 4.14 HYX_LPDDR5_H9JK_CAP — pn[7], 1 char (H9JK)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `F` | 8GB | H9JKNNNFB3AECR-N6H ✓ (496-ball) |
| `H` | 12GB | H9JKNNNHA3MVJR-N6H ✓ (96Gbit assimétrico) |

### 4.15 HYX_LPDDR5_H58G_CAP — pn[4], 1 char (H58G)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `D` | 3GB | H58GD6AK8VX091N ✓ (24Gbit assimétrico) |
| `5` | 4GB | H58G56BK8PX068 ✓ |
| `E` | 6GB | H58GE6AK8QX168N ✓ |
| `6` | 8GB | H58G66BK8QX067N ✓ |
| `G` | 12GB | H58GG8AK8QX103N ✓ |
| `7` | 16GB | H58G76BK8HX095N ✓ |
| `U` | 18GB | H58GU6MK6HX042 ✓ (B2B) |

Bloqueado: 24GB (192Gbit) — chave desconhecida; aguardar PN físico.

### 4.16 HYX_EMMC_CAP — pn[4], 1 char (H26M, H26T, H28M por analogia)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `3` | 4GB | H26M31001HPR — Octopart ✓ |
| `4` | 8GB | H26M41208HPR — SK Hynix oficial ✓ |
| `5` | 16GB | H26M52208FPR — SK Hynix oficial ✓ |
| `6` | 32GB | H26M64208EMR — SK Hynix oficial ✓ |
| `7` | 64GB | H26M74002HMR — SK Hynix oficial ✓ |
| `8` | 128GB | H26M88002AMR — Preduo ✓ · H26T87001CMR ✓ |

Bloqueado: `9`=256GB e `A`=512GB — zero resultados verificados. **Status: ✅ COMPLETO (teto 128GB).**

### 4.17 HYX_H28U_CAP — pn[4], 1 char (H28U)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `6` | 32GB | H28U62301AMR — B2B ✓ |
| `7` | 64GB | H28U74301AMR — B2B ✓ |
| `8` | 128GB | H28U88301AMR — B2B ✓ |

### 4.18 HYX_H28S_CAP — pn[4], 1 char (H28S)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `8` | 128GB | H28S8Q302CMR — B2B ✓ |
| `9` | 256GB | H28S9O302BMR — B2B ✓ |

### 4.19 HYX_HN8_CAP — pn[4:6], 2 chars (HN8T, HN8G)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `96` | 64GB | HN8G962EHKX037 — UFS 2.2 ✓ |
| `03` | 128GB | HN8T039JHQX099N — Automotivo ✓ |
| `05` | 128GB | HN8T05DEHKX073 — UFS 3.1 ✓ |
| `06` | 128GB | HN8T062EHKX039 — UFS 2.2 ✓ |
| `15` | 256GB | HN8T15DEHKX075 — UFS 3.1 ✓ |
| `16` | 256GB | HN8T162EHKX041 — UFS 2.2 ✓ |
| `25` | 512GB | HN8T25DEHKX077 — UFS 3.1 ✓ |
| `35` | 1TB | HN8T35DZHKX079 — UFS 3.1 ✓ |

### 4.20 HYX_EMCP_NAND_CAP — pn[4:6], 2 chars (H9TQ, H9TP compartilham)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `16` | 16GB | H9TQ17ABJTMCUR — Preduo ✓ |
| `17` | 16GB | H9TQ17ABJTMCUR — Preduo ✓ |
| `26` | 32GB | H9TQ26ADFTMCUR-KUM — ssfkg.com ✓ |
| `27` | 32GB | H9TQ27ACLTMCUR-KUM — Preduo ✓ |
| `32` | 4GB | H9TP32A4GDCCPR-KGM — absunshine ✓ |
| `52` | 64GB | H9TQ52ACLTMCUR-KUM — Preduo ✓ |
| `64` | 8GB | H9TQ64ABJTMCUR — Preduo ✓ |
| `65` | 8GB | H9TQ65A8GTMCUR-KTM — distribuidores ✓ |

⚠ **COLISÃO CRÍTICA**: H9HP usa `16`=128GB; H9TQ usa `16`=16GB. **Mapas separados obrigatórios.**

### 4.21 HYX_H9TQ_RAM_CAP — pn[6:8], 2 chars (H9TQ — LPDDR3)
`val_primary` = string completa com tipo + GB (o engine usa diretamente como `emcp_ram`).

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `A6` | LPDDR3 768MB | H9TQ32A6BTMC — specs iFixit/GSMArena ✓ |
| `A8` | LPDDR3 1GB | H9TQ65A8GTMCUR-KTM — ssfkg ✓ |
| `AA` | LPDDR3 2GB | H9TQ64AAETAC — B2B asiático ✓ |
| `AB` | LPDDR3 2GB | H9TQ17ABJTMCUR — Preduo ✓ |
| `AC` | LPDDR3 4GB | H9TQ52ACLTMCUR-KUM — Preduo (32Gb=4GB) ✓ |
| `AD` | LPDDR3 3GB | H9TQ27ADFTMCUR-KUM — NetSource (24Gbit=3GB) ✓ |

⚠ **AC=4GB e AD=3GB**: a ordem não é alfabética por tamanho.

### 4.22 HYX_H9TP_RAM_CAP — pn[6:8], 2 chars (H9TP — LPDDR2)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `A4` | LPDDR2 512MB | H9TP32A4GDCCPR-KGM — absunshine ✓ |
| `A8` | LPDDR2 1GB | H9TP64A8JDACPR-KGM — Elnec ✓ |
| `AB` | LPDDR2 2GB | ⚠ sem PN H9TP confirmado — por analogia |

### 4.23 HYX_H9D_NAND_CAP — pn[4:6], 2 chars (H9DP)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `32` | 4GB | H9DP32A4JJAC ✓ · H9DP32A4JJMC ✓ |
| `64` | 8GB | H9DP64A8JJMC ✓ |
| `AG` | 16GB | H9DPAGA3JJMC ✓ |

### 4.24 HYX_H9D_RAM_CAP — pn[7], 1 char (H9DP)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `2` | LPDDR2 256MB | H9DP32A2JJAC ✓ |
| `4` | LPDDR2 512MB | H9DP32A4JJAC ✓ |
| `8` | LPDDR2 1GB | H9DP64A8JJMC ✓ |
| `3` | LPDDR2 1GB | H9DPAGA3JJMC ✓ (organização diferente, mesma capacidade) |

### 4.25 HYX_LPDDR4X_RAM_CAP — pn[6:8], 2 chars (H9HP e H9HQ compartilham)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `AC` | LPDDR4X 4GB | H9HP53ACPMMDAR-KMM ✓ · H9HP27ACPMMDAR-KMM (Preduo) ✓ |
| `AD` | LPDDR4X 3GB | H9HP27ADAMADAR-KMM — B2B ✓ (24Gb=3GB) |
| `AE` | LPDDR4X 6GB | H9HP52AECMMDAR-KMM — Preduo (48Gb) ✓ |
| `AF` | LPDDR4X 8GB | H9HQ15AFAMBDAR-KEM — B2B ✓ |

### 4.26 HYX_H9HP_NAND_CAP — pn[4:6], 2 chars (H9HP — eMCP)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `16` | 128GB | H9HP16ACPMMDAR-KMM — Preduo ✓ (⚠ ≠ H9TQ onde `16`=16GB) |
| `27` | 32GB | H9HP27ACPMMDAR-KMM — Preduo ✓ |
| `52` | 64GB | H9HP52ACPMADAR-KMM — Preduo ✓ |
| `53` | 64GB | H9HP53ACPMMDAR-KMM — B2B ✓ |

Bloqueado: `26`=? — eBay cita 32GB mas sem fonte B2B rastreável.

### 4.27 HYX_H9HQ_NAND_CAP — pn[4:6], 2 chars (H9HQ — uMCP)

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `15` | 128GB | H9HQ15ACPMADAR-KEM — B2B ✓ |
| `16` | 128GB | H9HQ16ACPMMDAR-KMM — Preduo ✓ |
| `21` | 256GB | H9HQ21AECMADAR-KEM — B2B ✓ |
| `53` | 64GB | H9HQ53ACPMMDAR-KMM — Preduo ✓ |
| `54` | 64GB | H9HQ54AECMMDAR-KEM — B2B ✓ |

### 4.28 HYX_H9HR_NAND_CAP / HYX_H9HR_RAM_CAP (H9HR — uMCP LPDDR5)

NAND `pn[4:6]`: `15`=128GB · `21`=256GB
RAM `pn[6:8]`: `JF`=LPDDR5 8GB
(Código `JF` — diferente do padrão `A_` do H9HP/H9HQ — mapas incompatíveis)

### 4.29 HYX_H9RT_NAND_CAP / HYX_H9RT_RAM_CAP (H9RT — uMCP LPDDR5)

NAND `pn[4:6]`: `0G`=128GB · `1G`=256GB · `2G`=512GB
RAM `pn[6:8]`: `6A/6M`=LPDDR5 8GB · `GA`=LPDDR5 12GB · `7M`=LPDDR5 16GB
(Esquema de codificação NAND "dígito+G" — completamente diferente de todas as outras famílias)

### 4.30 HYX_H9DA_NAND_CAP — pn[4], 1 char (H9DA — eMCP LPDDR1 legado)

⚠ Decode em **1 char** — único caso eMCP com NAND de 1 char (todos os outros usam 2).

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `1` | 1GB | H9DA1GH25HAMMR-4EM · H9DA1GH51JAMMR-4EM — ariat-tech ✓ |
| `2` | 2GB | H9DA2GH1GHAM-4EM — ariat-tech ✓ |
| `4` | 4GB | H9DA4GH2GJAM-4EM · H9DA4VH4JJMMCR-4EM — ariat-tech / Preduo ✓ |

### 4.31 HYX_H9DA_RAM_CAP — pn[7:9], 2 chars (H9DA — eMCP LPDDR1)

`val_primary` = string completa com tipo + capacidade.
⚠ **RAM = LPDDR1** (confirmado Preduo tier-1). Notação Preduo "X+Y": Y em **Gb** (Gigabits).
Chaves decimais `"25"`/`"51"` = 256Mbit/512Mbit (= 256MB/512MB); alfanuméricos `"2G"`/`"4J"` = Gigabits (2Gb=256MB, 4Gb=512MB).
⚠ `"2G"` ≠ 2GB — é 2Gb = **256MB** LPDDR1.

| Chave | val_primary | Fonte |
|-------|-------------|-------|
| `25` | LPDDR1 256MB | H9DA1GH25HAMMR-4EM — ariat-tech ✓ |
| `51` | LPDDR1 512MB | H9DA1GH51HAMMR-4EM · H9DA1GH51JAMMR-4EM — ariat-tech ✓ |
| `1G` | LPDDR1 1GB | H9DA2GH1GHAM-4EM — ariat-tech ✓ |
| `2G` | LPDDR1 256MB | H9DA4GH2GJAM-4EM — chip físico eMiner; 2Gb=256MB ✓ |
| `4J` | LPDDR1 512MB | H9DA4VH4JJMMCR-4EM — Preduo "4+4" (4Gb=512MB) ✓ |

---

## 5. Famílias — Inventário Completo

### 5.1 DRAM PC / Desktop / Servidor

| Prefixo | `chip_type` | `subtype` | Decode | Prioridade | Status |
|---------|-------------|-----------|--------|------------|--------|
| HY5DU | `"RAM"` | `"DDR1"` | HYX_DDR1_CAP pn[5:7] | 60 | ✅ Completo |
| HY5PS | `"RAM"` | `"DDR2"` | HYX_DDR2_HY5PS_CAP pn[5:7] | 60 | ✅ Completo |
| H5PS | `"RAM"` | `"DDR2"` | HYX_DDR2_H5PS_CAP pn[4:6] | 55 | ✅ Completo |
| H5TQ | `"RAM"` | `"DDR3"` | HYX_DDR3_CAP pn[4:6] | 55 | ✅ Completo |
| H5TC | `"RAM"` | `"DDR3L"` | HYX_DDR3_CAP pn[4:6] | 55 | ✅ Completo |
| H5AN | `"RAM"` | `"DDR4"` | HYX_DDR4_CAP pn[4:6] | 50 | ✅ Completo (teto AG=2GB) |
| H5A | `"RAM"` | `"DDR4"` | HYX_DDR4_H5A_CAP pn[3:5] | 55 | ✅ Completo |
| H5C | `"RAM"` | `"DDR5"` | HYX_DDR5_CAP pn[3:5] | 50 | ⚠️ Parcial (G6 pendente) |
| H5RS | `"RAM"` | `"GDDR3"` | nenhum | 50 | ℹ️ Routing (sem decode cap) |

> **H5AN vs H5A:** H5AN (priority=50) tem precedência sobre H5A (priority=55) porque o prefixo
> mais longo H5AN é testado primeiro. Correto — todo `H5AN...` começa com `H5A`.

### 5.2 LPDDR Mobile Standalone

| Prefixo | `chip_type` | `subtype` | Decode | Prioridade | Status |
|---------|-------------|-----------|--------|------------|--------|
| HY5MS | `"LPDDR1"` | `"LPDDR1"` | HYX_LPDDR1_HY5MS_CAP pn[5:7] | 60 | ⚠️ Parcial (1 PN) |
| H5MS | `"LPDDR1"` | `"LPDDR1"` | HYX_LPDDR1_H5MS_CAP pn[4:6] | 60 | ✅ Completo |
| H9TK | `"LPDDR2"` | `"LPDDR2"` | HYX_LPDDR2_CAP pn[7] | 50 | ✅ Completo |
| H9CC | `"LPDDR3"` | `"LPDDR3"` | HYX_LPDDR3_CAP pn[7] | 50 | ✅ Completo |
| H9CK | `"LPDDR3"` | `"LPDDR3"` | HYX_LPDDR3_CAP pn[7] | 50 | ✅ Completo |
| H9HC | `"LPDDR4"` | `"LPDDR4"` | HYX_LPDDR4_H9HC_CAP pn[7] | 55 | ✅ Completo |
| H9HK | `"LPDDR4X"` | `"LPDDR4X"` | HYX_LPDDR4_H9HC_CAP pn[7] | 55 | ✅ Completo |
| H9HCN | `"LPDDR4X"` | `"LPDDR4X"` | HYX_LPDDR4_H9HC_CAP pn[7] | 40 | ✅ Completo |
| H54G | `"LPDDR4X"` | `"LPDDR4X"` | HYX_LPDDR4X_H54G_CAP pn[4] | 50 | ✅ Completo |
| H9JK | `"LPDDR5"` | `"LPDDR5"` | HYX_LPDDR5_H9JK_CAP pn[7] | 50 | ⚠️ Parcial (2 densidades) |
| H58G | `"LPDDR5"` | `"LPDDR5"` | HYX_LPDDR5_H58G_CAP pn[4] | 50 | ⚠️ Parcial (24GB pendente) |

> **Interface de TODAS as famílias LPDDR:** `""` (string vazia). Corrigido em 2026-06-19.

### 5.3 eMMC Standalone

| Prefixo | `chip_type` | Interface | Decode | Status |
|---------|-------------|-----------|--------|--------|
| H26M | `"eMMC"` | `"eMMC 5.x"` | HYX_EMMC_CAP pn[4] | ✅ Completo (4GB–128GB) |
| H26T | `"eMMC"` | `"eMMC 5.1"` | HYX_EMMC_CAP pn[4] | ✅ Completo |
| H28M | `"eMMC"` | `"eMMC"` | HYX_EMMC_CAP por analogia | ⚠️ Sem documentação pública |

> **H28M:** família sem documentação oficial (zero resultados em Octopart, Preduo, SK Hynix).
> decode_cap_pos=None — capacidade não exibida para não induzir erro. Hipótese: misprint H26M→H28M.

### 5.4 UFS Standalone

| Prefixo | `chip_type` | Interface | Decode | Status |
|---------|-------------|-----------|--------|--------|
| H28U | `"UFS"` | `"UFS 2.0/2.1"` | HYX_H28U_CAP pn[4] | ✅ Completo (32–128GB) |
| H28S | `"UFS"` | `"UFS 2.1"` | HYX_H28S_CAP pn[4] | ✅ Completo (128–256GB) |
| HN8T | `"UFS"` | `"UFS 2.1/2.2/3.1"` | HYX_HN8_CAP pn[4:6] | ✅ Completo (64GB–1TB) |
| HN8G | `"UFS"` | `"UFS 2.2"` | HYX_HN8_CAP pn[4:6] | ✅ Completo (64GB) |

> ⚠️ **RISCO OPERACIONAL CRÍTICO:** UFS e eMMC compartilham BGA-153 (11.5×13mm).
> São eletricamente incompatíveis. Colocar UFS no socket eMMC destrói o chip.
> Triagem **obrigatória** pelo PN antes de qualquer contato físico.

### 5.5 eMCP / uMCP

| Prefixo | `chip_type` | RAM | Interface | Status |
|---------|-------------|-----|-----------|--------|
| H9DP | `"eMCP"` | LPDDR2 (legado) | eMMC + LPDDR2 | ✅ Completo |
| H9TP | `"eMCP"` | LPDDR2 (legado) | eMMC 4.x + LPDDR2 | ✅ Completo |
| H9DA | `"eMCP"` | LPDDR1 (legado ~2012-2015) | eMMC 4.x + LPDDR1 | ✅ Completo (4 PNs confirmados, Preduo tier-1) |
| H9TQ | `"eMCP"` | LPDDR3 | eMMC 5.x + LPDDR3 | ✅ Completo |
| H9HP | `"eMCP"` | LPDDR4X | eMMC 5.1 + LPDDR4X | ✅ Completo |
| H9HQ | `"uMCP"` | LPDDR4X | UFS 2.1 + LPDDR4X | ✅ Completo |
| H9HR | `"uMCP"` | LPDDR5 | UFS + LPDDR5 | ✅ Completo |
| H9RT | `"uMCP"` | LPDDR5 | UFS + LPDDR5 | ✅ Completo |

---

## 6. fix_known_parts — Template e Regras

### 6.1 Template correto — chip DDR (KnownPart com `dram_density`)

```python
# DDR3 por exemplo — H5TQ4G63EFR-RDC (4Gbit x16 = 512MB por die)
{
    "pn": "H5TQ4G63EFR-RDC",     # PN EXATO com sufixo se confirmado
    "create": True,
    "create_defaults": {
        "brand_name": "SK Hynix",
        "chip_type":  "RAM",          # sempre "RAM" para DDR/GDDR
        "subtype":    "DDR3",         # SÓ a geração — sem "SDRAM", sem qualificadores
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":     "RAM",
        "subtype":       "DDR3",
        "interface":     "x16",       # bus WIDTH do chip — "x4", "x8", "x16"
                                      # lido de pn[6]: 4=x4, 6=x16, 8=x8
                                      # NUNCA colocar a geração ("DDR3") aqui
        "capacity":      "512MB",     # por die, em bytes — 4Gbit ÷ 8
        "dram_density":  "4Gb",       # densidade do die em Gb
        "confidence":    "confirmed",
    },
    "reason": "LCSC C2803259 ✓ (datasheet SK Hynix H5TQ4G63EFR Rev1.2, Set/2016).",
},
```

### 6.2 Template — LPDDR standalone

```python
# LPDDR4X por exemplo — H9HCNNNCPMML (4GB, RAM pura)
{
    "pn": "H9HCNNNCPMML",
    "create": True,
    "create_defaults": {
        "brand_name": "SK Hynix",
        "chip_type":  "LPDDR4X",     # tipo LPDDR vai no chip_type (não "RAM")
        "subtype":    "LPDDR4X",     # mesmo que chip_type
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "LPDDR4X",
        "subtype":    "LPDDR4X",
        "interface":  "",             # SEMPRE VAZIO para LPDDR
        "capacity":   "4GB",         # capacidade do pacote
        "confidence": "confirmed",
    },
    "reason": "H9HCNNNCPMMLHR-NME: duas refs independentes mapa H9HC (C=4GB) ✓.",
},
```

### 6.3 Template — eMCP (H9TQ como exemplo)

```python
# eMCP H9TQ — H9TQ32A6BTMC (4GB NAND + 768MB LPDDR3)
{
    "pn": "H9TQ32A6BTMC",
    "create": True,
    "create_defaults": {
        "brand_name": "SK Hynix",
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",      # geração da RAM
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",
        "interface":  "",             # SEMPRE VAZIO para eMCP
        "emcp_nand":  "4GB",         # NAND em GB
        "emcp_ram":   "LPDDR3 768MB",  # tipo ANTES da capacidade
        "confidence": "confirmed",
    },
    "reason": "...",
},
```

### 6.4 Template — UPDATE-ONLY (corrigir registro já existente)

Quando o PN já existe no banco mas com dados errados — use sem `"create": True`:

```python
# Chip já existia com interface="LPDDR3" (errado) e subtype="LPDDR3 standalone" (errado)
{
    "pn": "H9CCNNNCLTML",
    # SEM "create": True — só atualiza se o registro existir, não cria
    "fields": {
        "chip_type":  "LPDDR3",
        "subtype":    "LPDDR3",     # forma curta — sem "standalone"
        "interface":  "",           # VAZIO — era "LPDDR3"
        "capacity":   "4GB",
        "confidence": "confirmed",
    },
    "reason": "Correção convenção 2026-06-19: subtype era 'LPDDR3 standalone', interface era 'LPDDR3'.",
},
```

> **Quando usar UPDATE-ONLY:** registro existe no banco via scraping ou entrada
> manual anterior com dados incorretos. Adicionar `"create": True` causaria duplicata.
> **Quando usar create:** PN nunca foi inserido no banco antes.

### 6.5 Regras de `capacity` e `dram_density`

- **DDR/GDDR:** `capacity` = bytes por die (em MB ou GB). `dram_density` = Gb por die.
  Ex.: 4Gbit → `capacity="512MB"`, `dram_density="4Gb"`.
- **LPDDR standalone:** `capacity` = GB do pacote. `dram_density` vazio.
- **eMCP/uMCP:** NÃO preencher `capacity` — usar `emcp_nand` e `emcp_ram`.
- **NUNCA** usar Gbit no campo `capacity`.

### 6.6 Regra dos dois PNs

Sempre que possível, adicionar:
1. **PN base** (sem sufixo de velocidade/grade) — ex.: `H5TQ4G63EFR`
2. **PN com sufixo** confirmado — ex.: `H5TQ4G63EFR-RDC`

O operador pode ver qualquer dos dois no laser marking.

---

## 7. assess_profitability — Limiares e Destinos Comerciais

Os limiares exatos vivem em `ProfitabilityConfig` (singleton no admin — editável via
`/admin/chips/profitabilityconfig/`). Os parâmetros relevantes para SK Hynix:

| Parâmetro ProfitabilityConfig | Default | Significado para SK Hynix |
|-------------------------------|---------|---------------------------|
| `ddr_min_gen` | 3 | DDR1/DDR2 (gen < 3) → **NÃO RENTÁVEL** sempre. HY5DU, HY5PS, H5PS caem aqui. |
| `ddr3_min_gbit` | 2.0 | DDR3 < 2 Gb (256MB/die) → **NÃO RENTÁVEL**. H5TQ com `51`=64MB, `1G`=128MB caem aqui. |
| `ddr4plus_min_gbit` | **1.0** | ✓ Já configurado em **1.0 Gb** no admin (verificado 2026-06-29). DDR4+ ≥1Gb (128MB/die) → rentável. NÃO reverter para 8.0 (classificaria DDR4 4Gb como NÃO RENTÁVEL erroneamente). |
| `lpddr_min_gen` | 3 | LPDDR1/2 (gen < 3) → **NÃO RENTÁVEL**. H9TK, H9TP, H9DP caem aqui. |
| `lpddr3_min_gb` | 2.0 | LPDDR3 < 2GB → **NÃO RENTÁVEL**. H9CC/H9CK com `4`=512MB, `8`=1GB caem aqui. |
| `emmc_min_gb` | 16.0 | eMMC < 16GB → **NÃO RENTÁVEL**. H26M/H26T com `3`=4GB, `4`=8GB caem aqui. |

**Como o engine lê a capacidade para profitability:**
1. Tenta `dram_density` field → extrai Gb diretamente (DDR/GDDR)
2. Fallback: `capacity` field → `_extract_gib()` converte para GB → compara com limiar
3. eMCP/uMCP: lê `emcp_nand` e `emcp_ram` separadamente

> **Por isso `capacity` deve estar em MB ou GB**, nunca em Gbit.
> `capacity="4Gbit"` → `_extract_gib()` falha → engine retorna `INDETERMINADO` —
> **bloqueador de produção** (chip fica sem destino definido no gateway).

Os valores abaixo refletem a lógica do engine em `chips/engine.py`:

| Família | Tipo | Rentabilidade | Destino |
|---------|------|---------------|---------|
| H9RT uMCP LPDDR5 512GB+ | uMCP | **RENTÁVEL** | Bancada uMCP topo — altíssimo valor |
| H9HR uMCP LPDDR5 | uMCP | **RENTÁVEL** | Bancada uMCP LPDDR5 |
| H9HQ uMCP LPDDR4X 64GB+ | uMCP | **RENTÁVEL** | Bancada uMCP/UFS premium |
| H9HP eMCP LPDDR4X 64GB+ | eMCP | **RENTÁVEL** | Bancada eMCP premium |
| H58G LPDDR5/5X 4GB+ | LPDDR5 | **RENTÁVEL** | Alta demanda refurb premium |
| H9JK LPDDR5 8GB+ | LPDDR5 | **RENTÁVEL** | Alta demanda |
| H54G LPDDR4X 2GB+ | LPDDR4X | **RENTÁVEL** | Alta demanda smartphones |
| H9HCN/H9HC LPDDR4X 2GB+ | LPDDR4X | **RENTÁVEL** | Alta demanda |
| H9CK/H9CC LPDDR3 4GB | LPDDR3 | **RENTÁVEL** | Moderada — tablets premium |
| H9CK/H9CC LPDDR3 2GB | LPDDR3 | **RENTÁVEL** (checar) | Demanda moderada |
| H9CK/H9CC LPDDR3 ≤1GB | LPDDR3 | **INDETERMINADO** | Verificar mercado |
| H9TQ eMCP LPDDR3 32GB+ | eMCP | **RENTÁVEL** | Bancada eMCP LPDDR3 |
| H5AN/H5A DDR4 | RAM | **RENTÁVEL** | Triagem DDR4 — boa liquidez |
| H5C DDR5 | RAM | **RENTÁVEL** | Triagem DDR5 — premium |
| H5TQ/H5TC DDR3 ≥2Gb | RAM | **RENTÁVEL** (checar limiar) | DDR3 ainda tem mercado |
| H5TQ DDR3 1Gb (128MB) | RAM | **NÃO RENTÁVEL** | Resíduo |
| H9TK LPDDR2 standalone | LPDDR2 | **NÃO RENTÁVEL** / limiar | Geração quase morta |
| H9TP/H9DP eMCP LPDDR2 | eMCP | **NÃO RENTÁVEL** | Resíduo — descarte |
| H5PS/HY5PS DDR2 | RAM | **NÃO RENTÁVEL** | Geração morta |
| HY5DU DDR1 | RAM | **NÃO RENTÁVEL** | Moagem/refino |
| HY5MS/H5MS LPDDR1 | LPDDR1 | **NÃO RENTÁVEL** | Refino de metais |
| HN8T/H28U/H28S UFS | UFS | **RENTÁVEL** | Alta demanda |
| H26M/H26T eMMC ≥16GB | eMMC | **RENTÁVEL** | Boa liquidez |
| H26M eMMC ≤8GB | eMMC | **NÃO RENTÁVEL** / limiar | Checar demanda |

**Regra `is_dead_by_generation`**: chips DDR1, DDR2, LPDDR1 e eMCP LPDDR2 vão para
descarte mesmo sem confirmação no banco — o engine detecta geração morta independente de capacidade.

---

## 8. Armadilhas e Decisões Arquiteturais

### 8.1 Colisão `"16"` — H9TQ vs H9HP (ARMADILHA PRINCIPAL)

`"16"` em HYX_EMCP_NAND_CAP (H9TQ) = **16GB**.
`"16"` em HYX_H9HP_NAND_CAP (H9HP) = **128GB**.

São famílias diferentes com mapas separados. O engine não se confunde porque identifica
o prefixo antes de buscar o mapa. Mas **humano editando** o mapa errado gera valores
catastróficos no estoque. **Nunca compartilhar esses dois mapas.**

### 8.2 H5TQ8G43 não existe

SK Hynix **nunca** produziu DDR3 1.5V com 8Gbit x4 (`H5TQ8G43...`). Não existe PN físico
rastreável. Se aparecer na bancada → chip suspeito (possível remarked de H5TC8G43AMR DDP).

### 8.3 H5TC8G43AMR = DDP, 1GB total (não 2GB)

Sufixo `MR` = multi-die package. Dois dies de 4Gbit empilhados = 1GB total por chip.
`dram_density = "4Gb"` (por die), `capacity = "512MB"` (por die).
O módulo com dois chips DDP = 2GB total — mas cada chip é 1GB.

### 8.4 H9CC/H9CC — chip físico mostra 12 chars sem sufixo

No laser marking: `H9CCNNNCLTML` (12 chars). PN completo do distribuidor: `H9CCNNNCLTMLAR-NTD`.
Adicionar ambos ao banco. O operador frequentemente digita o código curto.

### 8.5 H9HCNNNECMML (6GB) — divergência de família

`H9HCNNNECMML` (`E`=6GB) está no banco com `confidence="manual"` e **flag de divergência**.
6GB (48Gbit) existe no catálogo PN Guide SK Hynix, mas pesquisa Glochip (site oficial, 2021)
indica que a família H9HCNNN **200-ball** não inclui `E`. O 6GB 200-ball pertenceria à
família **H9HKNNN** (376/556-ball, pacote físico maior).
**Pendente confirmação física do chip na bancada.**

### 8.6 H28M — prefixo sem documentação

H28M não existe em nenhum catálogo oficial, Octopart, Preduo. O prefixo H28x é documentado
apenas para UFS (H28U, H28S). A família existe no banco por analogia estrutural — decode
desativado (`decode_cap_pos=None`) para não exibir valores especulativos.

### 8.7 H9DP decode de RAM usa 1 char (diferente do H9TQ/H9TP)

H9TQ/H9TP: `pn[6:8]` (2 chars) → mapas A_, e.g. `AB`=2GB.
H9DP: `pn[7]` (1 char) → mapa com `2`, `4`, `8`, `3`. O `pn[6]='A'` é código fixo de
controlador — invisível para o engine (não mapeado).

### 8.8 H54G — dois sistemas de codificação no mesmo prefixo

Números (2, 3, 4, 5, 6) e letras (A, C, E, G, J) coexistem. Não é erro — SK Hynix
introduziu a escala alfabética para die-revisions e capacidades fracionadas (3GB, 6GB).
`pn[5]` = organização de banco (6 ou 8) — **nunca** interpretar como capacidade.

### 8.9 H9RT — esquema "dígito+G" para NAND

H9RT usa `0G/1G/2G` para NAND (não dois dígitos numéricos como outras famílias).
`pn[4]` sozinho não é a chave — a chave é sempre `pn[4:6]` junto.
Já documentado no mapa HYX_H9RT_NAND_CAP.

### 8.10 Interface de LPDDR — erro histórico corrigido

Antes de 2026-06-19, 11 famílias em `populate_hynix.py` usavam a geração como `interface`
(ex.: `interface="LPDDR3"`). **Corrigido.** Se encontrar `interface="LPDDR*"` em qualquer
arquivo de qualquer marca → é um bug, corrija.

### 8.11 subtype no label — RESOLVIDO (canonical_gen + write-time já limpo)

> **Status (2026-06-29): RESOLVIDO em dois níveis.** Versões anteriores deste doc
> descreviam um "BUG REAL, CORREÇÃO PENDENTE" de `ChipFamily.subtype` verboso vazando
> para o label. Isso **não procede mais** — verificado no código.

**Por que o label está protegido (defesa no ponto de consumo):**
O gateway (`estoque/views.py`, linhas ~237/254/282) passa **todo** subtype por
`chips/conventions.py::canonical_gen()` antes de montar o label. Essa função é a
**FONTE ÚNICA** da convenção (mesma filosofia de `assess_profitability` / regra de ouro #11)
e reduz qualquer subtype ao token canônico de geração por **whitelist**:
`"LPDDR3 standalone"` → `"LPDDR3"`, `"DDR3 SDRAM"` → `"DDR3"`, `"LPDDR4X Multi-Channel"`
→ `"LPDDR4X"`. Cobre **as duas vias** (banco confirmado e gramática) e é **retroativa** —
sem reescrever o banco. É **fail-open**: token desconhecido passa intacto (nunca apaga o label).

**Por que o write-time também já está limpo:**
Auditoria de `populate_hynix.py` (2026-06-29, `grep "subtype="`) confirma que **todas as
34 famílias já usam o subtype canônico** — `H5TQ`=`"DDR3"`, `H5TC`=`"DDR3L"`, `H9CC`/`H9CK`
=`"LPDDR3"`, `H9TQ`=`"LPDDR3"`, `H9HP`=`"LPDDR4X"`, etc. As strings verbosas ("DDR3 standalone",
"LPDDR3 standalone") sobrevivem **apenas no campo `tip`** (texto descritivo do card de busca —
não alimenta o label). Nada a corrigir no código.

**Regra permanente (continua valendo):** escreva `subtype` = **só a geração/célula** (1–3
palavras) no write-time — em `populate_hynix.py` (`ChipFamily.subtype`), `fix_known_parts.py`
e `add_confirmed_part.py` (`KnownPart.subtype`). `canonical_gen` é cinto-e-suspensório, não
licença para subtype sujo: o subtype **cru** ainda aparece no card de busca.

**Verificação (se mexer em subtype):**
```bash
python manage.py shell -c "
from chips.engine import classify
print(classify('H9CCNNNCLTML').get('subtype'))   # 'LPDDR3' — limpo já na origem
from chips.conventions import canonical_gen
print(canonical_gen('LPDDR3 standalone'))        # 'LPDDR3' — defesa no label
"
```

### 8.12 UFS e eMMC têm BGA-153 idêntico

H28U, HN8T, HN8G (UFS) e H26M, H26T (eMMC) são fisicamente indistinguíveis pelo encapsulamento.
São eletricamente incompatíveis. **Triagem obrigatória pelo PN antes do contato com o socket.**

### 8.13 pn[5] em H9TQ = organização, não capacidade adicional

Em H9TQ/H9TP, `pn[5]` (2º char da chave NAND) **não é independente**. A chave é sempre
`pn[4:6]` em conjunto. `64`=8GB e `65`=8GB são distintos (dies diferentes), mesma capacidade.
Nunca tratar `pn[4]` isolado como código NAND nestas famílias.

---

## 9. Gaps e Roadmap

### Sprint A — Impacto imediato, risco baixo

**H5C DDR5 — chave G6:**
`G6`=8GB (64Gbit) previsto no JEDEC DDR5 e decodificador interno SK Hynix.
Nenhum PN físico `H5CG6...` rastreado em distribuidores B2B globais.
Adicionar quando aparecer na bancada com PN confirmado por Octopart/datasheet.

**H9JK LPDDR5 — mais chaves:**
Apenas `F`=8GB e `H`=12GB confirmados. Família de transição — aguardar PNs adicionais.

### Sprint B — Impacto alto, requer pesquisa Tier 1

**H9HCNNNECMML (6GB) — confirmação física:**
Operador precisa verificar o chip físico na bancada: contar os balls (200 = H9HCNNN;
376/556 = H9HKNNN). Se for H9HKNNN, criar família H9HKNN no banco com os campos corretos.

**H58G LPDDR5 — 24GB (192Gbit):**
Chave desconhecida. Chip existe em devices (OnePlus Ace 2 Pro, Red Magic 8S Pro+).
Nenhum PN H58G avulso com 24GB rastreado. Aguardar lote na bancada.

**H5RS GDDR3 — decode capacidade:**
Família registrada só para routing. Se chips H5RS chegarem em volume, criar
HYX_GDDR3_H5RS_CAP (necessita pesquisa Octopart de `pn[4:6]` dos PNs comuns).

### Sprint C — Qualidade de dados

**H28M — investigação:**
Fotografar o chip com `H28M31001BMR` e comparar com `H26M31001HPR` lado a lado.
Se confirmado como misprint, documentar. Se produto real, buscar datasheet via SK Hynix support.

**H9TP AB — confirmar:**
`HYX_H9TP_RAM_CAP chave AB=LPDDR2 2GB` foi adicionado por analogia sem PN H9TP físico.
Pendente verificação real antes de classificar como confirmed.

### Completude por categoria

```
CATEGORIA                 COMPLETUDE    PRÓXIMO PASSO
──────────────────────────────────────────────────────────
uMCP (H9HR, H9RT)         ████████░░ 95%   ampliar H9HR densidades
eMCP LPDDR4X (H9HP/H9HQ) ████████░░ 95%   chave 26=? H9HP pendente
LPDDR5 (H58G, H9JK)      ██████░░░░ 70%   24GB e G6 pendentes
LPDDR4X (H54G, H9HC)     ██████████100%   completo
LPDDR3 (H9CC, H9CK)      ██████████100%   completo
LPDDR2 (H9TK)            ██████████100%   completo
eMCP LPDDR3 (H9TQ)       ████████░░ 95%   A4=512MB H9TQ confirmar
DDR5 (H5C)               ████████░░ 90%   G6=8GB pendente
DDR4 (H5AN, H5A)         ██████████100%   completo
DDR3/3L (H5TQ, H5TC)     ██████████100%   completo
DDR2 (H5PS, HY5PS)       ██████████100%   completo
DDR1 (HY5DU)             ██████████100%   completo
eMMC (H26M, H26T)        ██████████100%   completo (128GB teto)
eMMC H28M                 ████░░░░░░ 40%   sem documentação
UFS (HN8T, H28U, H28S)   ██████████100%   completo
GDDR3 (H5RS)             ████░░░░░░ 40%   sem decode cap
LPDDR1 (H5MS, HY5MS)     ██████░░░░ 65%   HY5MS com 1 PN
```

---

## 10. Histórico de Correções

| Data | PN / Família | Ação | Fonte | Motivo |
|------|-------------|------|-------|--------|
| 2026-06-19 | 11 famílias LPDDR/eMCP/uMCP | `interface="LPDDR*"` → `""` | Auditoria convenção | Gateway lê chip_type não interface para LPDDR |
| 2026-06-19 | H9HCNNNECMML | confidence `confirmed` → `manual` + flag divergência | Pesquisa Glochip SK Hynix 2021 | 6GB pode não existir em 200-ball |
| 2026-06-19 | 22 chips LPDDR mobile | Adicionados em add_confirmed_part.py | iFixit, Glochip, distribuidores | H9CC/H9HCNNN/H9TK confirmados |
| 2026-06-19 | 27 chips DDR3/DDR3L/DDR4 x4 | Adicionados em add_confirmed_part.py | Alldatasheet, LCSC, Octopart | x4 (servidor RDIMM) não tinha cobertura |
| 2026-06-19 | Subtypes LPDDR | `"LPDDR3 standalone"` → `"LPDDR3"` (e similares) | Auditoria convenção | Qualificador "standalone" vazava para label |
| 2026-06-19 | H9TQ64AAETAC | Criado em fix_known_parts (PN âncora da chave AA) | eMiner 2026-05-13 | Chip físico na esteira |
| 2026-06-19 | SKHYNIX.md → SK_HYNIX.md | Bíblia reescrita seguindo template PROMPT_NOVO_MD_MARCA | — | Arquivo anterior não seguia estrutura canônica |
| 2026-06-25 | HYX_LPDDR3_CAP | Adicionadas chaves `E`=6GB (48Gbit) e `F`=8GB (64Gbit) | Preduo WP01025 e WP01836 tier-1 | Comentário "BLOQUEADO" anterior estava errado — multi-die confirmado |
| 2026-06-25 | 15 chips H9CK/H9CC LPDDR3 | Adicionados em fix_known_parts.py | Preduo, iFixit, absunshine, ssfkg | H9CKNNNBJTMP chip físico na esteira eMiner; restantes distributor |
| 2026-06-29 | §8.11 (doc) | "BUG REAL pendente" → **RESOLVIDO**: subtypes já canônicos no código + `canonical_gen` protege o label | Auditoria `grep subtype=` + `estoque/views.py` | Doc descrevia bug inexistente; risco de retrabalho/desconfiança |
| 2026-06-29 | §0.3 (doc) | Regra de ouro #12: ouro=identidade, atestar specs em tier-1 | Lição Micron (MT52L, dies) | Endurecer disciplina para chat que vai popular PNs |
| 2026-06-29 | §7 (doc) | `ddr4plus_min_gbit` marcado como já em 1.0 no admin | Admin Django (screenshot eMiner) | Aviso "verificar" obsoleto — já configurado |

### Chips confirmados individualmente (histórico)

| PN | Tipo | Capacidade | Fonte | Confiança |
|----|------|-----------|-------|-----------|
| H9CCNNNCLTML | LPDDR3 | 4GB | bancada eMiner ✓ | confirmed |
| H9HCNNNCPMML | LPDDR4X | 4GB | H9HCNNNCPMMLHR-NME × 2 refs | confirmed |
| H9TKNNN8JDAP | LPDDR2 | 1GB | iFixit LG Optimus L90 ✓ | confirmed |
| H9TQ32A6BTMC | eMCP | 4GB NAND + 768MB LPDDR3 | GSMArena Galaxy J1 Ace ✓ | confirmed |
| H9TQ17ABJTCC | eMCP | 16GB NAND + 2GB LPDDR3 | Preduo + H9TQ17ABJTMCUR ✓ | confirmed |
| H9DP32A4JJBC | eMCP | 4GB NAND + 512MB LPDDR2 | H9DP32A4JJAC/JJMC ✓ | confirmed |
| H26M74002HMR | eMMC | 64GB | Octopart ✓ | confirmed |
| H26M31001HPR | eMMC | 4GB | Octopart ✓ | confirmed |
| H26M64103EMR | eMMC | 32GB | Octopart ✓ (⚠ H26M64=32GB) | confirmed |
| H26M78103CCR | eMMC | 64GB | Preduo "64GB ODP" ✓ | confirmed |
| H26T87001CMR | eMMC | 128GB | Octopart ✓ | confirmed |
| H28U88301AMR | UFS | 128GB | B2B stock ✓ | confirmed |
| H28U64222MMR | UFS | 32GB | H28U62301AMR B2B (chave 6=32GB) ✓ | confirmed |
| H9HP16AECMMD | uMCP | 128GB + 6GB LPDDR4X | H9HP16AECMMDAR-KMM Preduo ✓ | confirmed |
| H54GE6CYRB | LPDDR4X | 4GB | broker B2B SEA (Helio G80/G85) ✓ | confirmed |
| HN8T05BZGR | UFS | 128GB | UFS 3.1, fabricante ✓ | confirmed |
| H5TQ4G63EFR-RDC | DDR3 | 512MB | LCSC C2803259 ✓ | confirmed |
| H5TQ4G83EFR-RDC | DDR3 | 512MB | Octopart ✓ | confirmed |
| H5TC4G83CFR-PBA | DDR3L | 512MB | datasheet SK Hynix Rev0.2 ✓ | confirmed |
| H5TC4G63CFR-PBA | DDR3L | 512MB | Octopart ✓ | confirmed |
| H5TQ8G63AMR-H9C | DDR3 | 1GB | Octopart AMR ✓ | confirmed |
| H5TC8G83AMR-PBA | DDR3L | 1GB (DDP) | Octopart ✓ | confirmed |
| H5TQ2G43AFR | DDR3 x4 | 256MB | Alldatasheet ✓ | confirmed |
| H5TC8G43AMR | DDR3L x4 | 1GB (DDP) | LCSC / Octopart ✓ | confirmed |
| H9CKNNNBJTMP | LPDDR3 x64 | 2GB | chip físico bancada eMiner; ssfkg H9CKNNNBJTMPLR 16Gb 168ball ✓ | manual |
| H9CKNNNBJTMPLR | LPDDR3 x64 | 2GB | ssfkg.com 16Gb 168ball LPDDR3 SK Hynix ✓ | distributor |
| H9CKNNNBKTMRPR | LPDDR3 x64 | 2GB | Preduo H9CKNNNBKTMRPR-NUH 16Gbit 256ball ✓ | distributor |
| H9CKNNN8KTMRWR | LPDDR3 x64 | 1GB | iFixit Apple iPhone 6 (2014) step 15 ✓ | distributor |
| H9CKNNNBPTMRLR | LPDDR3 x64 | 2GB | iFixit Google Nexus 5 (LG, 2013) ✓ | distributor |
| H9CKNNNDBTMTAR | LPDDR3 x64 | 3GB | iFixit Motorola Nexus 6 (Google, 2014) ✓ | distributor |
| H9CKNNNDATMUPR | LPDDR3 x64 | 3GB | Preduo WP01020 H9CKNNNDATMUPR-NUH 24Gbit 256ball ✓ | distributor |
| H9CKNNNDATMRPR | LPDDR3 x64 | 3GB | Preduo H9CKNNNDATMRPR-NUH 24Gbit 256ball ✓ | distributor |
| H9CKNNNCPTMRPR | LPDDR3 x64 | 4GB | Preduo H9CKNNNCPTMRPR-NUH/-NUM 32Gbit 256ball ✓ | distributor |
| H9CKNNNECTMUPR | LPDDR3 x64 | 6GB | Preduo WP01025 H9CKNNNECTMUPR-NUH 48Gbit 256ball ✓ | distributor |
| H9CCNNN8JTMLAR | LPDDR3 x32 | 1GB | absunshine 8Gb DDP 256MX32 FBGA-178 ✓ | distributor |
| H9CCNNNBKTMLBR | LPDDR3 x32 | 2GB | Preduo H9CCNNNBKTMLBR-NTD/-NUD 16Gbit 253ball ✓ | distributor |
| H9CCNNNBPTBLBR | LPDDR3 x32 | 2GB | Preduo H9CCNNNBPTBLBR-NTD 16Gbit 253ball ✓ | distributor |
| H9CCNNNCPTMLBR | LPDDR3 x32 | 4GB | Preduo H9CCNNNCPTMLBR-NTD 32Gbit 253ball ✓ | distributor |
| H9CCNNNFAGMLLR | LPDDR3 x32 | 8GB | Preduo WP01836 H9CCNNNFAGMLLR-NUD 64Gbit 253ball ✓ | distributor |

---

## 11. Pipeline de Trabalho

### Para atualizar a gramática (famílias + DecodeMaps)

```bash
# 1. Editar populate_hynix.py (ChipFamily ou DecodeMap)
# 2. Propor ao usuário — que roda:
python manage.py populate_hynix --dry-run       # revisar antes
python manage.py populate_hynix --overwrite     # usuário executa

# 3. REINICIAR O SERVIDOR — obrigatório; lru_cache não invalida automaticamente

# 4. Verificar resultado no shell:
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('H9TQ64AAETAC'), indent=2, ensure_ascii=False))
"
```

### Para corrigir registros individuais (sem alterar gramática)

```bash
# 1. Editar fix_known_parts.py (somente seção SK Hynix — brand_name="SK Hynix")
# 2. Propor ao usuário — que roda:
python manage.py fix_known_parts    # usuário executa
# NÃO requer reinício do servidor (não altera gramática/lru_cache)
```

### Para adicionar PNs confirmados individualmente

```bash
# 1. Editar add_confirmed_part.py (seção SK Hynix)
# 2. Propor ao usuário — que roda:
python add_confirmed_part.py        # usuário executa (idempotente)
# NÃO requer reinício do servidor
```

### Ordem típica de uma sessão de atualização SK Hynix

```bash
python manage.py populate_hynix --overwrite    # usuário
python manage.py fix_known_parts               # usuário
python add_confirmed_part.py                   # usuário
# → REINICIAR SERVIDOR ← (obrigatório após populate --overwrite)
# verificar chips representativos no shell (ver §12)
# git add + git commit + git push origin main
```

---

## 12. Como verificar se um chip SK Hynix está correto

### Verificação via shell Django

```bash
# eMCP — esperado: chip_type='eMCP', emcp_nand='4GB', emcp_ram='LPDDR3 768MB'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('H9TQ32A6BTMC'), indent=2, ensure_ascii=False))
"

# LPDDR4X standalone — esperado: chip_type='LPDDR4X', capacity='4GB', interface=''
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('H9HCNNNCPMML'), indent=2, ensure_ascii=False))
"

# DDR3 — esperado: chip_type='RAM', subtype='DDR3', dram_density='4Gb', capacity='512MB'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('H5TQ4G63EFR'), indent=2, ensure_ascii=False))
"

# eMMC — esperado: chip_type='eMMC', capacity='64GB'
python manage.py shell -c "
from chips.engine import classify; import json
print(json.dumps(classify('H26M74002HMR'), indent=2, ensure_ascii=False))
"

# URL alternativa: /chips/decode/?pn=<PN>
# No estoque: botão "Debug" → JSON completo + fonte de cada campo
```

### Checklist de chip correto

- [ ] `known=true` (foi encontrado no banco ou pela gramática)
- [ ] `confidence="confirmed"` ou `"manual"` (não `"estimated"` ou `"distributor"`)
- [ ] `chip_type` correto para o tipo (ver tabela §2.1)
- [ ] `subtype` é apenas a geração — sem qualificadores, máximo 3 palavras
- [ ] `interface=""` para LPDDR/eMCP/uMCP; tipo do bus (`"DDR3"`, `"DDR4"`) para DDR/GDDR
- [ ] Campo de capacidade preenchido:
  - DDR/GDDR: `dram_density` (Gb) + `capacity` (MB/GB)
  - LPDDR standalone: `capacity` (GB)
  - eMCP/uMCP: `emcp_nand` (GB) + `emcp_ram` (tipo + GB)
  - eMMC/UFS: `capacity` (GB)
- [ ] `profitable != "INDETERMINADO"` — INDETERMINADO = campo de capacidade ausente ou inválido
      → **bloqueador de produção** (chip fica sem destino no gateway)
- [ ] Label do estoque correto: `DDR3+4G`, `LPDDR4X+4G`, `EMCP64+4`, `EMMC64GB`, `UFS128GB`

---

## 13. Fontes de Pesquisa

| Fonte | Melhor para | Nível |
|-------|-------------|-------|
| SK Hynix Product site (`product.skhynix.com`) | Famílias oficiais, pn guide | Tier 1 |
| Glochip LPDDR page | Catálogo LPDDR mobile oficial | Tier 1 |
| Alldatasheet | Datasheets completos | Tier 1 |
| LCSC | Estoque + specs verificados | Tier 1-2 |
| Octopart | Multi-distribuidor + capacidades | Tier 2 |
| Preduo | Catálogo refurb com specs | Tier 2-3 |
| OMO Electric | Broker China — PNs LPDDR/eMCP | Tier 3 |
| iFixit Teardowns | Leitura de chip real (chip_type confirmado) | Tier 1 |
| Elnec / Datasheets360 | PNs legados / EOL | Tier 2 |

**Fontes a evitar para capacidade:** HardDiskDirect escreve "(8GB)" para 8Gbit.
Distribuidores chineses genéricos (Jotrin, WinSource) frequentemente invertem Gb/GB.
Sempre verificar a matemática: `Xbit ÷ 8 = YB`.

---

## 14. Arquivos-Chave SK Hynix

```
chips/management/commands/
  populate_hynix.py          ← GRAMÁTICA: ChipFamilies + todos os DecodeMaps
                                Editar para novas famílias ou chaves confirmadas
  fix_known_parts.py         ← PNs individuais SK Hynix com brand_name="SK Hynix"
                                Seção termina antes de SanDisk (~linha 2470)

add_confirmed_part.py        ← PNs confirmados individualmente (seção SK Hynix)
                                Idempotente — pode rodar múltiplas vezes

Referências cruzadas:
  CLAUDE.md §2               ← regras de ouro (não violar)
  CLAUDE.md §4               ← arquitetura do engine
  docs/CONVENCAO_CAMPOS_ESTOQUE.md ← convenção canônica de campos (projeto inteiro)
  docs/CONTRATO_RENTABILIDADE_GATEWAY.md ← regras de rentabilidade completas
  SAMSUNG.md                 ← modelo de referência de outra marca
  MICRON.md                  ← modelo de referência de outra marca
```

---

> **Regra de trabalho:** Claude edita arquivos. O usuário roda os comandos.
> Nunca execute `populate_hynix`, `fix_known_parts`, `migrate` sem confirmação do usuário.
> Sempre `--dry-run` antes de qualquer comando destrutivo.
> Reiniciar o servidor após `populate_hynix --overwrite` (regra de ouro #3 do CLAUDE.md).
