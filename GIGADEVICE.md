# GIGADEVICE.md — Referência técnica GigaDevice (WhatTheChip)

> Leia sob demanda quando trabalhar com PNs GigaDevice (prefixos GD25, GD5F, GDQ).
> Para contexto geral do sistema, consulte `CLAUDE.md`.

---

## 1. Sobre a marca

**GigaDevice Semiconductor** (兆易创新, Zhaoyi Innovation) é um fabricante
chinês de semicondutores fundado em 2005. Código WTC: `GGD`.

Produtos relevantes para reciclagem:

| Linha | Prefixo | Tipo | Relevância |
|---|---|---|---|
| NOR Flash SPI 3V | GD25Q, GD25B, GD25D, GD25F, GD25R, GD25T | NOR Flash | Alta — BIOS, firmware |
| NOR Flash SPI 1.8V | GD25LQ, GD25LB, GD25LE, GD25LF | NOR Flash | Média — móvel/IoT |
| NAND Flash SPI | GD5F | NAND Flash | Média — equipamentos de rede |
| DDR4 SDRAM | GDQ | RAM | Nicho — visto em reciclagem |
| NOR Flash 2Gb+ (nova geração) | GD55 | NOR Flash | Baixa — raramente em reciclagem (2026) |

---

## 2. Série GD25 — NOR Flash SPI

### 2.1 Anatomia do PN

```
GD  25  [L]  [tipo]  [capacidade]  [revisão]  [-sufixo-pacote]
 ↑   ↑   ↑      ↑         ↑            ↑             ↑
GD=  Flash  L=1.8V  Q/B/D/F/...  código Mbit  letra gen.   pkg/temp
GigaDevice  (sem L = 3.3V)
```

**Letras de tipo (posição após "25" ou "25L"):**

| Letra | Interface | Notas |
|---|---|---|
| Q | Quad SPI padrão | Mais comum |
| B | Enhanced Quad SPI | 4I/O por padrão (mais novo) |
| D | Dual SPI | Legado |
| F | Com ECC integrado | Alta confiabilidade |
| R | Com RPMC | Segurança |
| T | DTR (Double Transfer Rate) | Alta velocidade |
| E | Versão compacta / WLCSP | Fator de forma menor |

### 2.2 Códigos de capacidade — ARMADILHA PRINCIPAL

> ⚠ **"40" NÃO é 40Mbit — é 4Mbit.** Os códigos são não lineares e têm
> comprimento variável. Decode posicional é inviável; use datasheets ou
> `KnownPart` confirmados individualmente.

| Código no PN | Densidade real | Capacidade em MB |
|---|---|---|
| `05` | 512Kbit | 0,0625 MB |
| `10` | 1Mbit | 0,125 MB |
| `20` | 2Mbit | 0,25 MB |
| `40` | 4Mbit | 0,5 MB |
| `80` | 8Mbit | 1 MB |
| `16` | 16Mbit | 2 MB |
| `32` | 32Mbit | 4 MB |
| `64` | 64Mbit | 8 MB |
| `128` | 128Mbit | 16 MB |
| `256` | 256Mbit | 32 MB |
| `512M` | 512Mbit | 64 MB |

**Exemplo completo:**
```
GD25Q128ESIG
GD   = GigaDevice
25   = NOR Flash família principal
Q    = Quad SPI
128  = 128Mbit = 16MB
E    = revisão E
SIG  = SOP8 208mil, temperatura industrial
```

### 2.3 Campos WTC para NOR Flash GD25

```python
chip_type = "NOR Flash"
subtype   = "SPI NOR"
interface = "SPI"
capacity  = "16MB"   # sempre em MB (Mbit ÷ 8)
# Sem decode_gen_pos — NOR Flash não tem "geração de RAM"
# Sem decode_cap_pos — código de capacidade não linear/variável
```

### 2.4 Rentabilidade esperada

| Capacidade | Expectativa | Razão |
|---|---|---|
| ≤ 64Mbit (≤ 8MB) | NÃO RENTÁVEL | Chips de firmware de baixíssimo valor |
| 128Mbit (16MB) | NÃO RENTÁVEL | Commodity barato |
| 256Mbit+ | A verificar com operador | Pode ter nicho específico |

---

## 3. Série GD5F — NAND Flash SPI

### 3.1 Anatomia do PN

```
GD5F  [densidade]  [série]  [variante]  [pacote]
 ↑         ↑          ↑
GD5F=   1/2/4/8    GQ4/GQ5/GM9...
NAND
SPI
```

**Decode de densidade (pn[4], 1 char):**

| Char | Gbit | Capacidade |
|---|---|---|
| `1` | 1 Gbit | 128 MB |
| `2` | 2 Gbit | 256 MB |
| `4` | 4 Gbit | 512 MB |
| `8` | 8 Gbit | 1 GB |

**Séries:** GQ4 (Gen1) · GQ5 (Gen2) · GM9 (Gen3 — ECC embutido no chip)

**Exemplos confirmados:**
- `GD5F1GQ4UBYIG` — 1Gbit (128MB) ✓
- `GD5F2GQ4UBYIG` — 2Gbit (256MB) ✓
- `GD5F4GQ4UBYIG` — 4Gbit (512MB) ✓
- `GD5F1GQ5UEYIG` — 1Gbit (128MB) série GQ5 ✓

### 3.2 Campos WTC para NAND Flash GD5F

```python
chip_type     = "NAND Flash"
subtype       = "SPI NAND"
interface     = "SPI"
# decode posicional via GD5F_NAND_CAP (pn[4]):
decode_cap_pos = 4
decode_cap_len = 1
decode_cap_map = "GD5F_NAND_CAP"
```

> ⚠ NÃO é ONFI/Toggle. Interface SPI-like (NOR-protocol sobre NAND).
> NÃO confundir com GD25 (NOR Flash) — tipos de chip completamente distintos.

---

## 4. Série GDQ — DDR4 SDRAM

### 4.1 Anatomia do PN

Fonte: **DS-00808-GDQ2BFAA-Rev1.4** (datasheet oficial GigaDevice).

```
G D Q [densidade] [pacote] [org] [tensão] [revisão] - [temp][speed]
0 1 2      3         4       5      6        7
```

| Posição | Char | Significado |
|---|---|---|
| pn[2] | Q | DDR4 (D=DRAM família; Q=DDR4) |
| pn[3] | 2 | 4Gbit (256Mb×16) — único confirmado até Jun/2026 |
| pn[4] | B | FBGA-96 — ⚠ facilmente confundido com '6' no laser |
| pn[5] | F | ×16 (organização de 16 bits) |
| pn[6] | A | 1.2V |
| pn[7] | A | 2ª revisão de produto |
| sufixo | C/W | Commercial (0-95°C) / Wide (-40-95°C) |
| sufixo | E/Q/J | DDR4-2400 / DDR4-2666 / DDR4-3200 |

**PNs confirmados (datasheet DS-00808-GDQ2BFAA-Rev1.4):**

| PN completo | Temp | Speed |
|---|---|---|
| GDQ2BFAA-CE | Commercial | DDR4-2400 |
| GDQ2BFAA-CQ | Commercial | DDR4-2666 |
| GDQ2BFAA-CJ | Commercial | DDR4-3200 |
| GDQ2BFAA-WQ | Wide | DDR4-2666 |
| GDQ2BFAA-WJ | Wide | DDR4-3200 |

### 4.2 Armadilha de leitura laser — B vs 6

> ⚠ **GDQ26FAA = provavelmente GDQ2BFAA mal lido.**
>
> `pn[4]='B'` (pacote FBGA-96) é facilmente confundido com `'6'` por
> operadores na leitura do laser gravado no chip. Se o operador reportar
> `GDQ26FAA`, solicitar confirmação visual com o datasheet físico antes
> de classificar como PN desconhecido.

### 4.3 Campos WTC para DDR4 GDQ

```python
chip_type  = "RAM"       # NÃO "DDR4" — convenção WTC para DRAM standalone
subtype    = "DDR4"
interface  = "x16"       # apenas no KnownPart; família usa interface=""
capacity   = "512MB"     # 4Gbit ÷ 8 = 512MB por die
```

### 4.4 Rentabilidade

4Gbit (512MB) DDR4 → **RENTÁVEL** via `assess_profitability`
(4Gbit > `ddr4plus_min_gbit=1.0Gbit`? Verificar thresholds em `ProfitabilityConfig`).

---

## 5. Família no banco WTC

### DecodeMap criado

| map_name | char_key | val_primary |
|---|---|---|
| GD5F_NAND_CAP | 1 | 128MB |
| GD5F_NAND_CAP | 2 | 256MB |
| GD5F_NAND_CAP | 4 | 512MB |
| GD5F_NAND_CAP | 8 | 1GB |

### ChipFamilies criadas

| Prefixo | chip_type | subtype | Decode cap |
|---|---|---|---|
| GDQ | RAM | DDR4 | None (via KnownPart) |
| GD25Q | NOR Flash | SPI NOR | None (código variável) |
| GD25B | NOR Flash | SPI NOR | None (código variável) |
| GD25LQ | NOR Flash | SPI NOR | None (código variável) |
| GD25LB | NOR Flash | SPI NOR | None (código variável) |
| GD5F | NAND Flash | SPI NAND | GD5F_NAND_CAP (pn[4]) |

### KnownPart confirmados (`fix_known_parts.py`)

GDQ2BFAA (base) + variantes: GDQ2BFAA-CE, -CQ, -CJ, -WQ, -WJ.
Todos: DDR4, ×16, 512MB, confidence=confirmed, status=enriched.

---

## 6. Como rodar

```bash
# Popular famílias e DecodeMap
python manage.py populate_gigadevice --dry-run   # verificar antes
python manage.py populate_gigadevice --overwrite  # aplicar

# Adicionar KnownPart confirmados
python manage.py fix_known_parts --dry-run
python manage.py fix_known_parts

# OBRIGATÓRIO após qualquer populate: reiniciar o servidor
# (engine usa lru_cache — CLAUDE.md Regra de Ouro #3)
```

---

## 7. Fontes Tier 1

- **Datasheet DDR4:** GigaDevice DS-00808-GDQ2BFAA-Rev1.4 (gigadevice.com)
- **NOR Flash:** https://www.gigadevice.com/product/flash/spi-nor-flash/serial-nor-flash
- **NAND Flash:** DigiKey (buscar GD5F) + datasheets oficiais GigaDevice
- **LCSC:** C2937367 (GDQ2BFAA-CE) — confirma PN e specs

> ⚠ Não usar dados de distribuidores B2C ou IA sem verificação por datasheet
> ou DigiKey/Mouser. Confundem Gb/GB, capacidade, e tipo de interface.

---

*Criado: 2026-06-20 | Fonte: codebase WTC + GigaDevice datasheets (Tier 1).*
